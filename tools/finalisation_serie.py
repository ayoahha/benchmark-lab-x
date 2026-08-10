# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Valider et verrouiller une série composée sans recopier ses acquisitions"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

RACINE = Path(__file__).parent.parent.resolve()

from empreintes import empreinte
from protocole_v2 import (
    PROTOCOLE_VERSION,
    ContratV2Invalide,
    cellule_du_lock,
    charger_json,
    chemin_relatif_sur,
    ecrire_json_immuable,
    empreinte_lock,
    resoudre_sous,
    sha256_fichier,
    sha256_octets,
    valider_chaine_collecte,
    valider_lock,
    valider_recu_couverture,
)


SCHEMA_COMPOSITION = "benchmark-lab-x/acquisition-composition/v1"
SCHEMA_FINALISATION = "benchmark-lab-x/series-finalization-lock/v1"
SCHEMA_RESULTATS = "benchmark-lab-x/results-data/v3"
SCHEMA_AUTORISATION_NOTATION = "benchmark-lab-x/offline-scoring-authorization/v1"

CHAMPS_COMPOSITION = {
    "schema_version", "series_id", "status", "created_at", "instrument_context",
    "panel", "runs", "slots", "counts", "sources", "costs",
    "routing_status_by_alias", "configuration_replacement",
}
CHAMPS_VERROU = {
    "schema_version", "protocol_version", "series_id", "created_at",
    "repository_source", "instrument_source", "composition_source",
    "coverage_receipt", "expected", "outputs", "scoring_authorization",
}
CHEMINS_SOURCE_FINALISATION = (
    "tools/empreintes.py",
    "tools/finalisation_serie.py",
    "tools/moteur_rendu.py",
    "tools/noter_campagne.py",
    "tools/protocole_v2.py",
    "tools/rapport_campagne.py",
)


@dataclass(frozen=True)
class AcquisitionComposee:
    slot_id: str
    alias: str
    run: int
    source_campaign_dir: Path
    source_lock: dict[str, Any]
    source_lock_hash: str
    cellule: dict[str, Any]
    attempt_receipt: dict[str, Any]
    collection_receipt: dict[str, Any]
    collection_receipt_hash: str
    response_path: Path
    raw_response_path: Path


@dataclass(frozen=True)
class CompositionValidee:
    path: Path
    sha256: str
    objet: dict[str, Any]
    acquisitions: tuple[AcquisitionComposee, ...]
    source_locks: tuple[tuple[Path, dict[str, Any], str], ...]
    instrument_commit: str
    measurement_environment: dict[str, Any]


@dataclass(frozen=True)
class FinalisationSerie:
    lock_path: Path
    lock: dict[str, Any]
    lock_hash: str
    composition: CompositionValidee
    coverage_receipt: dict[str, Any]
    score_dir: Path
    audits_dir: Path
    results_path: Path

    @property
    def acquisitions_by_id(self) -> dict[str, AcquisitionComposee]:
        return {acquisition.slot_id: acquisition for acquisition in self.composition.acquisitions}


def _exiger(condition: bool, message: str) -> None:
    if not condition:
        raise ContratV2Invalide(message)


def _git(racine: Path, args: list[str], libelle: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(racine), *args],
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise ContratV2Invalide(f"Git inaccessible pour {libelle}")
    return proc.stdout


def _git_head(racine: Path) -> str:
    return _git(racine, ["rev-parse", "--verify", "HEAD"], "HEAD").decode("ascii").strip()


def _git_commit(racine: Path, commit: str) -> str:
    confirme = _git(
        racine, ["rev-parse", "--verify", f"{commit}^{{commit}}"], "commit source"
    ).decode("ascii").strip()
    _exiger(confirme == commit, "le commit source ne désigne pas le commit exact")
    return confirme


def _git_blob(racine: Path, commit: str, relatif: str) -> bytes:
    chemin_relatif_sur(relatif, "actif Git")
    _exiger(":" not in relatif, f"chemin Git invalide: {relatif}")
    return _git(racine, ["show", f"{commit}:{relatif}"], relatif)


def _source_runtime(racine: Path, commit: str) -> list[dict[str, Any]]:
    fichiers = []
    for relatif in CHEMINS_SOURCE_FINALISATION:
        path = resoudre_sous(racine, relatif)
        _exiger(path.is_file() and not path.is_symlink(), f"source runtime absente: {relatif}")
        data = path.read_bytes()
        _exiger(data == _git_blob(racine, commit, relatif), f"source runtime différente du commit: {relatif}")
        fichiers.append({
            "path": relatif,
            "sha256": sha256_octets(data),
            "bytes": len(data),
        })
    return fichiers


def _preuve_fichier(
    racine: Path, preuve: dict[str, Any], libelle: str
) -> tuple[Path, bytes]:
    _exiger(
        isinstance(preuve, dict) and set(preuve) == {"path", "sha256"},
        f"preuve de fichier invalide: {libelle}",
    )
    relatif = chemin_relatif_sur(preuve.get("path"), f"{libelle}.path")
    path = resoudre_sous(racine, relatif)
    _exiger(path.is_file() and not path.is_symlink(), f"fichier absent ou lié: {libelle}")
    data = path.read_bytes()
    _exiger(sha256_octets(data) == preuve.get("sha256"), f"empreinte différente: {libelle}")
    return path, data


def _contrat_compatibilite(cellule: dict[str, Any]) -> str:
    manifeste = cellule["execution_manifest"]
    parametres = copy.deepcopy(manifeste["request_parameters"])
    parametres.pop("provider", None)
    contrat = {
        "model_identity": {
            "mode": manifeste["mode"],
            "model_requested": manifeste["model_requested"],
            "revision": copy.deepcopy(manifeste["revision"]),
        },
        "execution_contract": {
            "task_version": cellule["task_version"],
            "prompt_sha256": cellule["prompt_sha256"],
            "quantization": copy.deepcopy(manifeste["quantization"]),
            "reasoning_effort": manifeste["reasoning_effort"],
            "request_parameters_without_routing": parametres,
            "max_tokens": manifeste["max_tokens"],
            "data_policy_requested": manifeste["data_policy_requested"],
            "request_adapter_version": manifeste["request_adapter_version"],
            "tools": copy.deepcopy(manifeste["tools"]),
            "agent": copy.deepcopy(manifeste["agent"]),
            "local_environment": copy.deepcopy(manifeste["local_environment"]),
        },
    }
    return empreinte(contrat)


def _identite_modele(cellule: dict[str, Any]) -> dict[str, Any]:
    manifeste = cellule["execution_manifest"]
    return {
        "mode": manifeste["mode"],
        "model_requested": manifeste["model_requested"],
        "revision": copy.deepcopy(manifeste["revision"]),
    }


def _identite_route(cellule: dict[str, Any]) -> dict[str, Any]:
    manifeste = cellule["execution_manifest"]
    route = cellule["route"]
    return {
        "backend": manifeste["backend"],
        "provider_pinned": manifeste["provider_pinned"],
        "provider_expected": manifeste["provider_expected"],
        "endpoint_tag": manifeste.get("endpoint_tag"),
        "ownership": copy.deepcopy(route.get("ownership")),
        "metadata_evidence": copy.deepcopy(route.get("metadata_evidence")),
    }


def _instrument_commit(lock: dict[str, Any]) -> str:
    source = lock.get("instrument_source") or lock.get("repository_source")
    _exiger(isinstance(source, dict), "commit d'instrument absent du lock source")
    commit = source.get("commit")
    _exiger(isinstance(commit, str) and len(commit) in {40, 64}, "commit d'instrument invalide")
    return commit


def _verifier_actifs_git(
    racine: Path, commit: str, instrument_context: dict[str, Any]
) -> None:
    actifs: dict[str, tuple[str, int]] = {}
    task = instrument_context["task"]
    for entree in task.get("task_tree", []):
        relatif = f"{task['task_dir']}/{entree['path']}"
        actifs[relatif] = (entree["sha256"], entree["bytes"])
    for axe in instrument_context["axes"]:
        for entree in axe["verify_manifest"]["assets"]:
            precedente = actifs.get(entree["path"])
            attendu = (entree["sha256"], entree["bytes"])
            _exiger(precedente in {None, attendu}, f"actif verrouillé contradictoire: {entree['path']}")
            actifs[entree["path"]] = attendu
    for relatif, (sha256, taille) in sorted(actifs.items()):
        data = _git_blob(racine, commit, relatif)
        _exiger(len(data) == taille, f"taille Git différente: {relatif}")
        _exiger(sha256_octets(data) == sha256, f"empreinte Git différente: {relatif}")


def charger_composition(racine: Path, composition_path: Path) -> CompositionValidee:
    racine = racine.resolve()
    path = composition_path.resolve()
    _exiger(path.is_file() and not path.is_symlink(), "composition absente ou liée")
    _exiger(path.is_relative_to(racine), "composition hors dépôt")
    composition = charger_json(path)
    _exiger(set(composition) == CHAMPS_COMPOSITION, "champs de composition différents du contrat")
    _exiger(composition.get("schema_version") == SCHEMA_COMPOSITION, "acquisition-composition/v1 absent")
    _exiger(composition.get("status") == "complete", "composition encore incomplète")
    panel = composition.get("panel")
    runs = composition.get("runs")
    slots = composition.get("slots")
    _exiger(
        isinstance(panel, list) and panel and len(panel) == len(set(panel)),
        "panel composé absent ou dupliqué",
    )
    _exiger(isinstance(runs, int) and not isinstance(runs, bool) and runs > 0, "runs composés invalides")
    _exiger(isinstance(slots, list) and slots, "slots composés absents")
    attendus = {f"{alias}__r{run}" for alias in panel for run in range(1, runs + 1)}
    _exiger(len(slots) == len(attendus), "nombre de slots différent de la grille")

    instrument_context = composition.get("instrument_context")
    _exiger(
        isinstance(instrument_context, dict) and set(instrument_context) == {"task", "axes"},
        "contexte d'instrument composé invalide",
    )
    _exiger(isinstance(instrument_context["axes"], list) and instrument_context["axes"], "axes absents")

    contexts_locks: dict[str, tuple[Path, dict[str, Any], str]] = {}
    acquisitions: list[AcquisitionComposee] = []
    vus: set[str] = set()
    environnements: list[dict[str, Any]] = []
    commits_instrument: set[str] = set()
    cout_accepte = 0
    contrats_par_alias: dict[str, set[str]] = {alias: set() for alias in panel}

    for index, slot in enumerate(slots):
        champs_slot = {
                "slot_id", "alias", "run", "status", "compatibility_contract_sha256",
                "route_role", "acquisition",
        }
        _exiger(
            isinstance(slot, dict)
            and set(slot) in {frozenset(champs_slot), frozenset(champs_slot | {"scientific_configuration"})},
            f"slot composé invalide: {index}",
        )
        slot_id = slot.get("slot_id")
        alias = slot.get("alias")
        run = slot.get("run")
        _exiger(slot_id == f"{alias}__r{run}" and slot_id in attendus, f"slot non canonique: {slot_id}")
        _exiger(slot_id not in vus, f"slot dupliqué: {slot_id}")
        vus.add(slot_id)
        _exiger(slot.get("status") == "acquired", f"slot non acquis: {slot_id}")
        if "scientific_configuration" in slot:
            _exiger(
                alias == "hy3"
                and slot["scientific_configuration"]
                == composition["configuration_replacement"]["replacement_configuration"],
                f"configuration scientifique invalide: {slot_id}",
            )
        acquisition = slot.get("acquisition")
        _exiger(isinstance(acquisition, dict), f"acquisition absente: {slot_id}")
        campagne_rel = chemin_relatif_sur(
            acquisition.get("source_campaign_path"), f"{slot_id}.source_campaign_path"
        )
        campagne_dir = resoudre_sous(racine, campagne_rel)
        _exiger(campagne_dir.is_dir() and not campagne_dir.is_symlink(), f"campagne source absente: {slot_id}")
        lock_rel = chemin_relatif_sur(acquisition.get("source_lock_path"), f"{slot_id}.source_lock_path")
        lock_path = resoudre_sous(racine, lock_rel)
        _exiger(lock_path.parent == campagne_dir, f"lock hors campagne source: {slot_id}")
        lock_sha = acquisition.get("source_lock_sha256")
        _exiger(lock_path.is_file() and not lock_path.is_symlink(), f"lock source absent: {slot_id}")
        _exiger(sha256_fichier(lock_path) == lock_sha, f"lock source modifié: {slot_id}")
        if lock_rel not in contexts_locks:
            source_lock = valider_lock(charger_json(lock_path))
            source_lock_hash = empreinte_lock(source_lock)
            _exiger(
                source_lock.get("task") == instrument_context["task"]
                and source_lock.get("axes") == instrument_context["axes"],
                f"instrument source différent: {lock_rel}",
            )
            environnement = source_lock.get("environments", {}).get("measurement")
            _exiger(isinstance(environnement, dict), f"environnement source absent: {lock_rel}")
            contexts_locks[lock_rel] = (lock_path, source_lock, source_lock_hash)
            environnements.append(environnement)
            commits_instrument.add(_instrument_commit(source_lock))
        _, source_lock, source_lock_hash = contexts_locks[lock_rel]
        _exiger(
            acquisition.get("source_campaign_lock_hash") == source_lock_hash,
            f"empreinte contractuelle du lock différente: {slot_id}",
        )
        _exiger(
            acquisition.get("source_campaign_id") == source_lock.get("campaign_id"),
            f"identifiant de campagne source différent: {slot_id}",
        )
        _exiger(acquisition.get("source_collection_id") == slot_id, f"collecte source différente: {slot_id}")
        cellule = cellule_du_lock(source_lock, slot_id)
        _exiger(cellule["alias"] == alias and cellule["run"] == run, f"cellule source différente: {slot_id}")
        contrat = _contrat_compatibilite(cellule)
        _exiger(
            contrat == slot.get("compatibility_contract_sha256")
            == acquisition.get("compatibility_contract_sha256"),
            f"contrat de compatibilité différent: {slot_id}",
        )
        contrats_par_alias[alias].add(contrat)
        _exiger(acquisition.get("model_identity") == _identite_modele(cellule), f"identité modèle différente: {slot_id}")
        _exiger(acquisition.get("route_identity") == _identite_route(cellule), f"identité route différente: {slot_id}")

        attempt_path, _ = _preuve_fichier(racine, acquisition.get("attempt_receipt"), f"{slot_id}.attempt")
        receipt_path, _ = _preuve_fichier(racine, acquisition.get("collection_receipt"), f"{slot_id}.collection")
        raw_path, _ = _preuve_fichier(racine, acquisition.get("raw_response"), f"{slot_id}.raw")
        response_path, _ = _preuve_fichier(racine, acquisition.get("response"), f"{slot_id}.response")
        for preuve_path in (attempt_path, receipt_path, raw_path, response_path):
            _exiger(preuve_path.is_relative_to(campagne_dir), f"preuve hors campagne source: {slot_id}")
        attempt = charger_json(attempt_path)
        collection = charger_json(receipt_path)
        valider_chaine_collecte(attempt, collection, source_lock_hash, cellule)
        collection_hash = empreinte(collection)
        _exiger(collection.get("result") == "COLLECTED", f"collecte non scoreable: {slot_id}")
        _exiger(
            collection.get("candidate", {}).get("sha256") == sha256_fichier(response_path),
            f"réponse candidate modifiée: {slot_id}",
        )
        _exiger(
            collection.get("response_json_sha256") == sha256_fichier(raw_path),
            f"réponse brute modifiée: {slot_id}",
        )
        _exiger(collection.get("served") == acquisition.get("served"), f"identité servie différente: {slot_id}")
        cout = collection.get("cost_accounting", {}).get("cost_microdollars")
        _exiger(cout == acquisition.get("cost_microdollars"), f"coût composé différent: {slot_id}")
        _exiger(collection.get("attempt") == acquisition.get("attempt"), f"tentative composée différente: {slot_id}")
        cout_accepte += cout
        acquisitions.append(AcquisitionComposee(
            slot_id=slot_id,
            alias=alias,
            run=run,
            source_campaign_dir=campagne_dir,
            source_lock=source_lock,
            source_lock_hash=source_lock_hash,
            cellule=cellule,
            attempt_receipt=attempt,
            collection_receipt=collection,
            collection_receipt_hash=collection_hash,
            response_path=response_path,
            raw_response_path=raw_path,
        ))

    _exiger(vus == attendus, "grille composée incomplète")
    _exiger(all(len(valeurs) == 1 for valeurs in contrats_par_alias.values()), "contrat variable dans un alias")
    _exiger(len(commits_instrument) == 1, "plusieurs commits d'instrument dans la composition")
    _exiger(
        len({empreinte(environnement) for environnement in environnements}) == 1,
        "plusieurs environnements de mesure dans la composition",
    )
    counts = composition.get("counts")
    _exiger(
        isinstance(counts, dict)
        and counts.get("total") == len(attendus)
        and counts.get("acquired") == len(attendus)
        and counts.get("pending") == 0,
        "compteurs de composition invalides",
    )
    _exiger(
        composition.get("costs", {}).get("scientific_accepted_acquisitions_microdollars")
        == cout_accepte,
        "coût scientifique composé différent des reçus",
    )
    remplacement = composition.get("configuration_replacement")
    _exiger(isinstance(remplacement, dict), "remplacement de configuration absent")
    exclusion_path, _ = _preuve_fichier(
        racine, remplacement.get("historical_exclusions"), "exclusions historiques"
    )
    exclusions = charger_json(exclusion_path)
    hashes_actifs = {
        slot.collection_receipt_hash for slot in acquisitions
    }
    historiques = exclusions.get("historical_acquisitions")
    _exiger(isinstance(historiques, list), "acquisitions historiques exclues absentes")
    _exiger(
        all(
            entree.get("collection_receipt", {}).get("sha256") not in hashes_actifs
            for entree in historiques if isinstance(entree, dict)
        ),
        "acquisition historique réintroduite dans la composition",
    )

    instrument_commit = next(iter(commits_instrument))
    _git_commit(racine, instrument_commit)
    _verifier_actifs_git(racine, instrument_commit, instrument_context)
    acquisitions.sort(key=lambda item: (panel.index(item.alias), item.run))
    source_locks = tuple(sorted(contexts_locks.values(), key=lambda item: item[0].as_posix()))
    return CompositionValidee(
        path=path,
        sha256=sha256_fichier(path),
        objet=composition,
        acquisitions=tuple(acquisitions),
        source_locks=source_locks,
        instrument_commit=instrument_commit,
        measurement_environment=copy.deepcopy(environnements[0]),
    )


def _selectionner_lock_couverture(
    composition: CompositionValidee, receipt: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    demande = receipt.get("campaign_lock_hash")
    for _, lock, lock_hash in composition.source_locks:
        if lock_hash == demande:
            return lock, lock_hash
    _, lock, lock_hash = composition.source_locks[0]
    return lock, lock_hash


def valider_couverture(
    racine: Path, composition: CompositionValidee, receipt_path: Path
) -> dict[str, Any]:
    _exiger(receipt_path.is_file() and not receipt_path.is_symlink(), "reçu R-016 absent ou lié")
    receipt = charger_json(receipt_path)
    source_lock, source_lock_hash = _selectionner_lock_couverture(composition, receipt)
    qualifie, motifs = valider_recu_couverture(
        receipt, source_lock, source_lock_hash, racine
    )
    _exiger(qualifie and not motifs, f"reçu R-016 non qualifiant: {motifs}")
    return receipt


def integrer_couverture_exacte(source: Path, destination: Path) -> None:
    _exiger(source.is_file() and not source.is_symlink(), "source R-016 absente ou liée")
    data = source.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    _exiger(not destination.is_symlink(), "destination R-016 symbolique")
    if destination.exists():
        _exiger(destination.is_file() and destination.read_bytes() == data, "reçu R-016 canonique différent")
        return
    fd, nom = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    tmp = Path(nom)
    try:
        with os.fdopen(fd, "wb") as flux:
            flux.write(data)
            flux.flush()
            os.fsync(flux.fileno())
        os.chmod(tmp, 0o600)
        try:
            os.link(tmp, destination)
        except FileExistsError:
            _exiger(
                destination.is_file() and not destination.is_symlink()
                and destination.read_bytes() == data,
                "reçu R-016 canonique différent",
            )
    finally:
        tmp.unlink(missing_ok=True)


def construire_verrou_finalisation(
    racine: Path,
    composition: CompositionValidee,
    coverage_path: Path,
    source_commit: str,
    created_at: str,
) -> dict[str, Any]:
    racine = racine.resolve()
    _git_commit(racine, source_commit)
    _exiger(_git_head(racine) == source_commit, "HEAD différent du commit de finalisation")
    coverage = valider_couverture(racine, composition, coverage_path)
    out_dir = composition.path.parent
    relatif = lambda path: path.resolve().relative_to(racine).as_posix()
    lock = {
        "schema_version": SCHEMA_FINALISATION,
        "protocol_version": PROTOCOLE_VERSION,
        "series_id": composition.objet["series_id"],
        "created_at": created_at,
        "repository_source": {
            "commit": source_commit,
            "files": _source_runtime(racine, source_commit),
        },
        "instrument_source": {"commit": composition.instrument_commit},
        "composition_source": {
            "path": relatif(composition.path),
            "sha256": composition.sha256,
            "schema_version": SCHEMA_COMPOSITION,
        },
        "coverage_receipt": {
            "path": relatif(coverage_path),
            "sha256": sha256_fichier(coverage_path),
            "schema_version": coverage["schema_version"],
            "qualified": True,
        },
        "expected": {
            "acquisitions": len(composition.acquisitions),
            "axes": len(composition.objet["instrument_context"]["axes"]),
            "score_receipts": (
                len(composition.acquisitions)
                * len(composition.objet["instrument_context"]["axes"])
            ),
        },
        "outputs": {
            "score_receipts_dir": relatif(out_dir / "series-scores"),
            "audits_dir": relatif(out_dir / "series-audits"),
            "results_path": relatif(out_dir / "results-data.series-v1.json"),
        },
        "scoring_authorization": {
            "required": True,
            "schema_version": SCHEMA_AUTORISATION_NOTATION,
            "path": relatif(out_dir / "offline-scoring-authorization.json"),
        },
    }
    valider_verrou_finalisation(lock, racine, composition, coverage_path)
    return lock


def valider_verrou_finalisation(
    lock: dict[str, Any],
    racine: Path,
    composition: CompositionValidee | None = None,
    coverage_path: Path | None = None,
) -> dict[str, Any]:
    _exiger(isinstance(lock, dict) and set(lock) == CHAMPS_VERROU, "champs du verrou de finalisation invalides")
    _exiger(lock.get("schema_version") == SCHEMA_FINALISATION, "series-finalization-lock/v1 absent")
    _exiger(lock.get("protocol_version") == PROTOCOLE_VERSION, "protocole v2 absent")
    source = lock.get("repository_source")
    _exiger(
        isinstance(source, dict) and set(source) == {"commit", "files"},
        "source de finalisation absente",
    )
    commit = source.get("commit")
    _git_commit(racine, commit)
    _exiger(_git_head(racine) == commit, "HEAD différent du commit de finalisation")
    _exiger(source.get("files") == _source_runtime(racine, commit), "sources runtime différentes du verrou")
    composition_source = lock.get("composition_source")
    _exiger(
        isinstance(composition_source, dict)
        and set(composition_source) == {"path", "sha256", "schema_version"}
        and composition_source.get("schema_version") == SCHEMA_COMPOSITION,
        "source de composition invalide",
    )
    path_composition, _ = _preuve_fichier(
        racine,
        {
            "path": composition_source["path"],
            "sha256": composition_source["sha256"],
        },
        "composition",
    )
    composition = composition or charger_composition(racine, path_composition)
    _exiger(composition.sha256 == composition_source["sha256"], "composition différente du verrou")
    _exiger(lock.get("series_id") == composition.objet["series_id"], "identifiant de série différent")
    instrument = lock.get("instrument_source")
    _exiger(
        isinstance(instrument, dict) and instrument == {"commit": composition.instrument_commit},
        "commit d'instrument différent de la composition",
    )
    coverage_source = lock.get("coverage_receipt")
    _exiger(
        isinstance(coverage_source, dict)
        and set(coverage_source) == {"path", "sha256", "schema_version", "qualified"}
        and coverage_source.get("qualified") is True,
        "liaison R-016 invalide",
    )
    coverage_path = coverage_path or resoudre_sous(
        racine, chemin_relatif_sur(coverage_source.get("path"), "coverage_receipt.path")
    )
    _exiger(sha256_fichier(coverage_path) == coverage_source.get("sha256"), "reçu R-016 différent du verrou")
    coverage = valider_couverture(racine, composition, coverage_path)
    _exiger(coverage.get("schema_version") == coverage_source.get("schema_version"), "schéma R-016 différent")
    expected = lock.get("expected")
    attendu_axes = len(composition.objet["instrument_context"]["axes"])
    _exiger(
        expected == {
            "acquisitions": len(composition.acquisitions),
            "axes": attendu_axes,
            "score_receipts": len(composition.acquisitions) * attendu_axes,
        },
        "cardinalités de finalisation invalides",
    )
    outputs = lock.get("outputs")
    _exiger(
        isinstance(outputs, dict)
        and set(outputs) == {"score_receipts_dir", "audits_dir", "results_path"},
        "sorties de finalisation invalides",
    )
    parent = composition.path.parent
    attendues = {
        "score_receipts_dir": parent / "series-scores",
        "audits_dir": parent / "series-audits",
        "results_path": parent / "results-data.series-v1.json",
    }
    for nom, attendu in attendues.items():
        path = resoudre_sous(racine, chemin_relatif_sur(outputs.get(nom), f"outputs.{nom}"))
        _exiger(path == attendu, f"sortie de finalisation différente: {nom}")
        _exiger(not path.is_symlink(), f"sortie de finalisation symbolique: {nom}")
    autorisation = lock.get("scoring_authorization")
    _exiger(
        isinstance(autorisation, dict)
        and autorisation == {
            "required": True,
            "schema_version": SCHEMA_AUTORISATION_NOTATION,
            "path": composition.path.parent.joinpath(
                "offline-scoring-authorization.json"
            ).relative_to(racine).as_posix(),
        },
        "contrat d'autorisation Chromium invalide",
    )
    empreinte(lock)
    return lock


def charger_finalisation(lock_path: Path, racine: Path = RACINE) -> FinalisationSerie:
    racine = racine.resolve()
    lock_path = lock_path.resolve()
    _exiger(lock_path.is_file() and not lock_path.is_symlink(), "verrou de finalisation absent ou lié")
    lock = charger_json(lock_path)
    composition_source = lock.get("composition_source") or {}
    composition_path = resoudre_sous(
        racine, chemin_relatif_sur(composition_source.get("path"), "composition_source.path")
    )
    composition = charger_composition(racine, composition_path)
    valider_verrou_finalisation(lock, racine, composition)
    coverage_path = resoudre_sous(
        racine, chemin_relatif_sur(lock["coverage_receipt"]["path"], "coverage_receipt.path")
    )
    coverage = valider_couverture(racine, composition, coverage_path)
    outputs = lock["outputs"]
    return FinalisationSerie(
        lock_path=lock_path,
        lock=lock,
        lock_hash=empreinte(lock),
        composition=composition,
        coverage_receipt=coverage,
        score_dir=resoudre_sous(racine, outputs["score_receipts_dir"]),
        audits_dir=resoudre_sous(racine, outputs["audits_dir"]),
        results_path=resoudre_sous(racine, outputs["results_path"]),
    )


def chemin_score(
    finalisation: FinalisationSerie,
    acquisition: AcquisitionComposee,
    card: dict[str, Any],
) -> Path:
    return (
        finalisation.score_dir
        / acquisition.source_lock_hash
        / acquisition.collection_receipt_hash
        / card["id"]
        / f"{card['verify_hash']}.json"
    )


def valider_autorisation_notation(
    finalisation: FinalisationSerie, racine: Path = RACINE
) -> dict[str, Any]:
    relatif = finalisation.lock["scoring_authorization"]["path"]
    path = resoudre_sous(racine, relatif)
    _exiger(path.is_file() and not path.is_symlink(), "autorisation Chromium absente ou liée")
    autorisation = charger_json(path)
    _exiger(
        isinstance(autorisation, dict)
        and set(autorisation) == {
            "schema_version", "decision", "finalization_lock_hash",
            "expected_score_receipts", "approved_by", "approved_at",
        },
        "champs de l'autorisation Chromium invalides",
    )
    _exiger(
        autorisation.get("schema_version") == SCHEMA_AUTORISATION_NOTATION
        and autorisation.get("decision") == "GO_OFFLINE_SCORING"
        and autorisation.get("finalization_lock_hash") == finalisation.lock_hash
        and autorisation.get("expected_score_receipts")
        == finalisation.lock["expected"]["score_receipts"],
        "autorisation Chromium liée à une autre finalisation",
    )
    for champ in ("approved_by", "approved_at"):
        _exiger(
            isinstance(autorisation.get(champ), str) and autorisation[champ].strip(),
            f"{champ} absent de l'autorisation Chromium",
        )
    empreinte(autorisation)
    return autorisation


@contextmanager
def instrument_fige(finalisation: FinalisationSerie, racine: Path = RACINE) -> Iterator[Path]:
    commit = finalisation.composition.instrument_commit
    with tempfile.TemporaryDirectory(prefix="instrument-finalisation-") as tmp:
        tmp_path = Path(tmp)
        archive_path = tmp_path / "instrument.tar"
        extraction = tmp_path / "repo"
        extraction.mkdir()
        proc = subprocess.run(
            ["git", "-C", str(racine), "archive", "--format=tar", "-o", str(archive_path), commit],
            check=False,
            capture_output=True,
        )
        _exiger(proc.returncode == 0, "extraction Git de l'instrument impossible")
        with tarfile.open(archive_path, mode="r:") as archive:
            archive.extractall(extraction, filter="data")
        instrument_context = finalisation.composition.objet["instrument_context"]
        actifs: dict[str, tuple[str, int]] = {}
        for entree in instrument_context["task"]["task_tree"]:
            relatif = (
                f"{instrument_context['task']['task_dir']}/{entree['path']}"
            )
            actifs[relatif] = (entree["sha256"], entree["bytes"])
        for axe in instrument_context["axes"]:
            for entree in axe["verify_manifest"]["assets"]:
                actifs[entree["path"]] = (entree["sha256"], entree["bytes"])
        for relatif, (sha256, taille) in actifs.items():
            path = resoudre_sous(extraction, relatif)
            _exiger(
                path.is_file() and not path.is_symlink()
                and path.stat().st_size == taille and sha256_fichier(path) == sha256,
                f"actif extrait différent: {relatif}",
            )
        yield extraction


def _main_prepare(args: argparse.Namespace) -> dict[str, Any]:
    composition_path = args.composition.resolve()
    coverage_source = args.coverage_source.resolve()
    out_dir = args.out_dir.resolve()
    composition = charger_composition(RACINE, composition_path)
    valider_couverture(RACINE, composition, coverage_source)
    destination = out_dir / "witness-coverage-receipt.json"
    integrer_couverture_exacte(coverage_source, destination)
    lock = construire_verrou_finalisation(
        RACINE, composition, destination, args.source_commit, args.created_at
    )
    lock_path = out_dir / "series-finalization.lock.v1.json"
    ecrire_json_immuable(lock_path, lock)
    finalisation = charger_finalisation(lock_path, RACINE)
    return {
        "status": "PREPARED_LOCAL_ONLY",
        "series_id": lock["series_id"],
        "finalization_lock": lock_path.relative_to(RACINE).as_posix(),
        "finalization_lock_sha256": sha256_fichier(lock_path),
        "finalization_lock_hash": finalisation.lock_hash,
        "composition_sha256": composition.sha256,
        "r016_qualified": True,
        "acquisitions": lock["expected"]["acquisitions"],
        "score_receipts": lock["expected"]["score_receipts"],
        "chromium": "HOLD",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--composition", type=Path, required=True)
    parser.add_argument("--coverage-source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args()
    try:
        resultat = _main_prepare(args)
    except (ContratV2Invalide, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
