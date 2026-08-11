# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Produire cinq reçus de score immuables depuis une collecte v2

Le vérificateur reçoit uniquement une copie neutre de `response.md`. Ni alias,
ni chemin de campagne, ni métadonnée de collecte ne lui sont transmis

Usage:
    uv run tools/noter_campagne.py runs/<campagne>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from empreintes import empreinte  # noqa: E402
from finalisation_serie import (  # noqa: E402
    charger_finalisation,
    chemin_score,
    instrument_fige,
    valider_autorisation_notation,
)
from moteur_rendu import descripteur  # noqa: E402
from protocole_v2 import (  # noqa: E402
    CAUSE_CODES,
    PROTOCOLE_VERSION,
    SCHEMA_COLLECTION,
    SCHEMA_CONTEXT,
    SCHEMA_SCORE,
    ContratV2Invalide,
    cellule_du_lock,
    charger_json,
    ecrire_json_immuable,
    empreinte_lock,
    resoudre_sous,
    sha256_fichier,
    valider_chaine_collecte,
    valider_environnement_observe,
    valider_lock,
    valider_recu_collecte,
    valider_recu_score,
)


def _executer_borne(
    cmd: list[str], delai: int, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True, env=env)
    try:
        sortie, erreur = proc.communicate(timeout=delai)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.communicate()
        raise
    return subprocess.CompletedProcess(cmd, proc.returncode, sortie, erreur)


def _recu_collecte(campaign_dir: Path, collection_id: str) -> tuple[Path, dict[str, Any]]:
    racine = campaign_dir / "collections" / collection_id
    recus = sorted(racine.glob("attempt-*/collection-receipt.json"))
    if len(recus) != 1:
        raise ContratV2Invalide(
            f"{collection_id}: un reçu de collecte COLLECTED exact est requis, trouvé {len(recus)}"
        )
    receipt = charger_json(recus[0])
    if receipt.get("schema_version") != SCHEMA_COLLECTION:
        raise ContratV2Invalide(f"{collection_id}: schéma de reçu de collecte invalide")
    if receipt.get("result") != "COLLECTED":
        raise ContratV2Invalide(f"{collection_id}: reçu non scoreable")
    return recus[0], receipt


def _valider_collecte(
    receipt_path: Path,
    receipt: dict[str, Any],
    lock_hash: str,
    cellule: dict[str, Any],
) -> Path:
    valider_recu_collecte(receipt, lock_hash, cellule)
    attempt_path = receipt_path.parent / "attempt-receipt.json"
    if not attempt_path.is_file() or attempt_path.is_symlink():
        raise ContratV2Invalide("reçu de tentative COMPLETE absent")
    valider_chaine_collecte(
        charger_json(attempt_path), receipt, lock_hash, cellule
    )
    response = receipt_path.parent / "response.md"
    if not response.is_file() or response.is_symlink():
        raise ContratV2Invalide("response.md absent ou lié symboliquement")
    if sha256_fichier(response) != receipt["candidate"]["sha256"]:
        raise ContratV2Invalide("empreinte de response.md différente du reçu")
    response_json = receipt_path.parent / "raw.json"
    if not response_json.is_file() or response_json.is_symlink():
        raise ContratV2Invalide("raw.json absent ou lié symboliquement")
    if sha256_fichier(response_json) != receipt["response_json_sha256"]:
        raise ContratV2Invalide("empreinte de raw.json différente du reçu")
    served = receipt.get("served")
    if not isinstance(served, dict):
        raise ContratV2Invalide("identité servie absente du reçu")
    attendue = cellule["route"].get("expect_provider") or cellule["route"]["provider"]
    normaliser = lambda x: str(x or "").strip().lower().replace(" ", "-").replace("_", "-")
    execution = cellule["execution_manifest"]
    if normaliser(served.get("model")) != normaliser(execution["model_requested"]):
        raise ContratV2Invalide("modèle servi différent du lock")
    if normaliser(served.get("provider")) not in {
        normaliser(cellule["route"]["provider"]), normaliser(attendue)
    }:
        raise ContratV2Invalide("provider servi différent du lock")
    return response


def _sortie_unknown(card: dict[str, Any], cause: str, detail: str) -> dict[str, Any]:
    return {"etat": "UNKNOWN", "cause_code": cause, "predicates": {}, "measurements": {},
            "detail": detail, "card_id": card["id"],
            "verify_version": card["verify_version"]}


def _noter_une_carte(
    card: dict[str, Any],
    response: Path,
    instrument_root: Path = RACINE,
    offline: bool = False,
) -> dict[str, Any]:
    verifier = resoudre_sous(instrument_root, card["verifier_path"])
    if not verifier.is_file():
        raise ContratV2Invalide(f"vérificateur absent: {verifier}")
    manifeste = card.get("verify_manifest")
    if not isinstance(manifeste, dict) or empreinte(manifeste) != card["verify_hash"]:
        raise ContratV2Invalide(f"manifeste du vérificateur invalide: {card['id']}")
    for asset in manifeste.get("assets", []):
        path = resoudre_sous(instrument_root, asset["path"])
        if not path.is_file() or sha256_fichier(path) != asset["sha256"]:
            raise ContratV2Invalide(f"actif du vérificateur modifié: {asset['path']}")
    with tempfile.TemporaryDirectory(prefix="score-v2-") as tmp:
        neutre = Path(tmp) / "response.md"
        shutil.copyfile(response, neutre)
        environnement = None
        if offline:
            environnement = dict(os.environ)
            environnement["UV_OFFLINE"] = "1"
        try:
            out = _executer_borne(
                ["uv", "run", str(verifier), "--card", card["id"], str(neutre)],
                int(card["watchdog_s"]),
                env=environnement,
            )
        except subprocess.TimeoutExpired:
            return _sortie_unknown(card, "VERIFY_TIMEOUT", "garde-fou de 180 s dépassé")
    if out.returncode != 0:
        marqueurs_environnement = ("MoteurNonConforme", "BrowserType.launch", "TargetClosedError")
        cause = ("ENVIRONMENT_MISMATCH" if any(m in out.stderr for m in marqueurs_environnement)
                 else "VERIFY_PROCESS_ERROR")
        return _sortie_unknown(card, cause,
                               f"processus du vérificateur sorti avec le code {out.returncode}")
    try:
        result = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        return _sortie_unknown(card, "VERIFY_PROCESS_ERROR", f"JSON invalide: {exc}")
    if not isinstance(result, dict) or result.get("card_id") != card["id"]:
        return _sortie_unknown(card, "VERIFY_PROCESS_ERROR", "sortie liée à une autre carte")
    return result


def _valider_sortie(result: dict[str, Any], card: dict[str, Any]) -> None:
    etat = result.get("etat")
    if etat not in {"SCORED", "UNKNOWN"}:
        raise ContratV2Invalide(f"état de score invalide pour {card['id']}")
    cause = result.get("cause_code")
    if cause is not None and cause not in CAUSE_CODES:
        raise ContratV2Invalide(f"cause_code inconnu pour {card['id']}: {cause}")
    if etat == "SCORED":
        if result.get("verdict") not in {"PASS", "FAIL"}:
            raise ContratV2Invalide(f"verdict invalide pour {card['id']}")
        if card["kind"] == "levels":
            niveau = result.get("niveau")
            if not isinstance(niveau, int) or isinstance(niveau, bool) or not 0 <= niveau <= len(card["predicates"]):
                raise ContratV2Invalide(f"niveau invalide pour {card['id']}")
    if etat == "UNKNOWN" or result.get("verdict") == "FAIL":
        if cause not in CAUSE_CODES:
            raise ContratV2Invalide(f"cause_code requis pour {card['id']}")
    predicats = result.get("predicates")
    if not isinstance(predicats, dict):
        raise ContratV2Invalide(f"prédicats absents pour {card['id']}")
    if etat == "SCORED" and set(predicats) != set(card["predicates"]):
        raise ContratV2Invalide(f"ensemble des prédicats différent pour {card['id']}")


def noter_collection(
    campaign_dir: Path,
    lock: dict[str, Any],
    collection_id: str,
    *,
    score_dir: Path | None = None,
    instrument_root: Path = RACINE,
    offline: bool = False,
) -> list[Path]:
    lock_hash = empreinte_lock(lock)
    cellule = cellule_du_lock(lock, collection_id)
    receipt_path, collection = _recu_collecte(campaign_dir, collection_id)
    response = _valider_collecte(receipt_path, collection, lock_hash, cellule)
    collection_hash = empreinte(collection)
    environment = descripteur()
    valider_environnement_observe(lock, "measurement", environment)
    environment_hash = empreinte(environment)
    produits = []
    for card in lock["axes"]:
        result = _noter_une_carte(
            card, response, instrument_root=instrument_root, offline=offline
        )
        _valider_sortie(result, card)
        context = {
            "schema_version": SCHEMA_CONTEXT,
            "protocol_version": PROTOCOLE_VERSION,
            "task": {
                "id": lock["task"]["task_id"],
                "version": lock["task"]["task_version"],
            },
            "prompt_hash": lock["task"]["prompt_sha256"],
            "system_prompt_hash": None,
            "axis_id": card["id"],
            "verify_version": card["verify_version"],
            "verify_hash": card["verify_hash"],
            "measurement_environment_hash": environment_hash,
            "confidentiality_regime": lock["task"]["confidentiality_regime"],
        }
        score = {
            "schema_version": SCHEMA_SCORE,
            "protocol_version": PROTOCOLE_VERSION,
            "campaign_lock_hash": lock_hash,
            "collection_id": collection_id,
            "collection_receipt_hash": collection_hash,
            "response_sha256": collection["candidate"]["sha256"],
            "alias": cellule["alias"],
            "run": cellule["run"],
            "axis_id": card["id"],
            "verify_version": card["verify_version"],
            "verify_hash": card["verify_hash"],
            "measurement_context": context,
            "measurement_context_hash": empreinte(context),
            "measurement_environment": environment,
            "etat": result["etat"],
            "cause_code": result.get("cause_code"),
            "verdict": result.get("verdict"),
            "niveau": result.get("niveau"),
            "frontiere": result.get("frontiere"),
            "predicats": (result.get("predicates") or {}) if result["etat"] == "SCORED" else {},
            "mesures": (result.get("measurements") or {}) if result["etat"] == "SCORED" else {},
        }
        valider_recu_score(
            score, lock, lock_hash, card, cellule, collection, collection_hash
        )
        racine_scores = campaign_dir / "scores" if score_dir is None else score_dir / lock_hash
        path = (racine_scores / collection_hash / card["id"]
                / f"{card['verify_hash']}.json")
        ecrire_json_immuable(path, score)
        produits.append(path)
    return produits


def noter_serie(finalization_lock: Path) -> list[Path]:
    finalisation = charger_finalisation(finalization_lock, RACINE)
    valider_autorisation_notation(finalisation, RACINE)
    produits: list[Path] = []
    with instrument_fige(finalisation, RACINE) as instrument_root:
        for acquisition in finalisation.composition.acquisitions:
            recus = noter_collection(
                acquisition.source_campaign_dir,
                acquisition.source_lock,
                acquisition.slot_id,
                score_dir=finalisation.score_dir,
                instrument_root=instrument_root,
                offline=True,
            )
            for card, path in zip(acquisition.source_lock["axes"], recus):
                attendu = chemin_score(finalisation, acquisition, card)
                if path != attendu:
                    raise ContratV2Invalide(
                        f"sortie de score différente du verrou: "
                        f"{acquisition.slot_id}/{card['id']}"
                    )
            produits.extend(recus)
    attendu = finalisation.lock["expected"]["score_receipts"]
    if len(produits) != attendu:
        raise ContratV2Invalide(
            f"nombre de reçus de score différent: {len(produits)} au lieu de {attendu}"
        )
    return produits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign_dir", type=Path, nargs="?")
    ap.add_argument("--lock", type=Path)
    ap.add_argument("--collection-id")
    ap.add_argument("--finalization-lock", type=Path)
    args = ap.parse_args()
    try:
        if args.finalization_lock is not None:
            if args.campaign_dir is not None or args.lock is not None or args.collection_id is not None:
                raise ContratV2Invalide(
                    "la finalisation composée est incompatible avec les arguments de campagne"
                )
            produits = noter_serie(args.finalization_lock)
        else:
            if args.campaign_dir is None:
                raise ContratV2Invalide("dossier de campagne absent")
            lock_path = args.lock or args.campaign_dir / "campaign.lock.json"
            lock = valider_lock(charger_json(lock_path), RACINE)
            ids = (
                [args.collection_id]
                if args.collection_id
                else [c["collection_id"] for c in lock["collections"]]
            )
            produits = []
            for collection_id in ids:
                produits.extend(noter_collection(args.campaign_dir, lock, collection_id))
    except ContratV2Invalide as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "SCORES_WRITTEN", "receipts": [str(p) for p in produits]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
