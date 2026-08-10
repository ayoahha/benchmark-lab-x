"""Contrats purs de campagne pour benchmark-lab-x/protocol/v2

Ce module ne fait aucun appel réseau et ne lance aucun navigateur. Il porte les
portes vérifiables avant collecte : lock résolu, liste fermée de fichiers,
budget en microdollars, reprises bornées, agrégation et reçu R-016
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any

from empreintes import empreinte


PROTOCOLE_VERSION = "benchmark-lab-x/protocol/v2"
SCHEMA_LOCK_V3 = "benchmark-lab-x/campaign-lock/v3"
SCHEMA_EXECUTION_V3 = "benchmark-lab-x/execution-manifest/v3"
SCHEMA_LOCK = "benchmark-lab-x/campaign-lock/v4"
SCHEMA_LOCK_CONTINUATION_V5 = "benchmark-lab-x/campaign-lock/v5"
SCHEMA_LOCK_CONTINUATION = "benchmark-lab-x/campaign-lock/v6"
SCHEMA_EXECUTION = "benchmark-lab-x/execution-manifest/v4"
SCHEMA_ATTEMPT = "benchmark-lab-x/attempt-receipt/v3"
SCHEMA_COLLECTION = "benchmark-lab-x/collection-receipt/v3"
SCHEMA_SCORE = "benchmark-lab-x/score-receipt/v3"
SCHEMA_COLLECTION_STATE = "benchmark-lab-x/collection-state/v1"
SCHEMA_AUDIT = "benchmark-lab-x/axis-audit-receipt/v1"
SCHEMA_PANEL_EVENTS = "benchmark-lab-x/panel-events/v1"
SCHEMA_OPERATOR_HOLD = "benchmark-lab-x/operator-hold/v1"
SCHEMA_ABANDONMENT = "benchmark-lab-x/campaign-abandonment/v1"
SCHEMA_COVERAGE = "benchmark-lab-x/witness-coverage-receipt/v2"
SCHEMA_LEDGER = "benchmark-lab-x/budget-ledger/v2"
SCHEMA_CONTEXT = "benchmark-lab-x/measurement-context/v3"
SCHEMA_PAID_AUTH = "benchmark-lab-x/paid-authorization/v1"
SCHEMA_ENVIRONMENT = "benchmark-lab-x/environment/v1"
POLITIQUE_PORTEE_ECHEC = "benchmark-lab-x/failure-scope/v1"

SCHEMA_LOCK_HISTORIQUE = "benchmark-lab-x/campaign-lock/v2"
SCHEMA_EXECUTION_HISTORIQUE = "benchmark-lab-x/execution-manifest/v2"
PLAFOND_B0_HISTORIQUE = 55_000_000
ESTIMATION_B0_HISTORIQUE = 31_812_500

CHAMPS_ENVIRONNEMENT = {
    "schema_version", "os", "architecture", "locale", "timezone",
    "runtimes", "browser", "sandbox_image_digest",
}
CHEMINS_SOURCE_RUNTIME = (
    "docs/ARD.md",
    "docs/PRD.md",
    "docs/RULES.md",
    "models.toml",
    "tools/audit_instrument.py",
    "tools/choisir_provider.py",
    "tools/collect.py",
    "tools/empreintes.py",
    "tools/figer_routes_precollecte.py",
    "tools/integrer_temoins_r016.py",
    "tools/lancer_campagne.py",
    "tools/moteur_rendu.py",
    "tools/noter_campagne.py",
    "tools/oracle_pentagone.py",
    "tools/page_resultats.py",
    "tools/preparer_campagne.py",
    "tools/protocole_v2.py",
    "tools/qualifier_temoins.py",
    "tools/rapport_campagne.py",
    "tools/verifier_pentagone_v5.py",
)
CHEMINS_SOURCE_COLLECTE = (
    "tools/collect.py",
    "tools/empreintes.py",
    "tools/lancer_campagne.py",
    "tools/protocole_v2.py",
)

ETATS_TENTATIVE = {"COMPLETE", "FAILED_RETRYABLE", "FAILED_NON_RETRYABLE"}
ETATS_COLLECTE = {"COLLECTED", "INELIGIBLE", "INFRA_ERROR", "MISSING"}
ETATS_SCORE = {"SCORED", "UNKNOWN", "INELIGIBLE", "INFRA_ERROR", "MISSING"}
CAUSES_REPRISE = {
    "HTTP_429", "HTTP_503", "TRANSPORT_NO_HTTP_RESPONSE", "EMPTY_HTTP_BODY",
}
# EMPTY_HTTP_BODY reste admis ici pour valider les reçus historiques immuables
CAUSES_TENTATIVE_NON_RETRYABLE = {
    "LOCK_PARAMETER_MISMATCH", "LOCK_PAYLOAD_MISMATCH", "HTTP_REDIRECT",
    "HTTP_NON_RETRYABLE", "EMPTY_HTTP_BODY", "INVALID_JSON", "API_ERROR",
    "RESPONSE_SCHEMA_INVALID", "ROUTE_MISMATCH", "LOCK_MANIFEST_MISMATCH",
    "LOCK_PROMPT_MISMATCH", "KEY_LEAK_GUARD", "WRITE_FAILED",
    "UNEXPECTED_ERROR",
}
CAUSES_COLLECTE_TERMINALE = {
    "ATTEMPTS_EXHAUSTED", "ROUTE_INELIGIBLE",
    "ABANDONED_AFTER_IDENTITY_MISMATCH", "PROVIDER_ROUTE_UNAVAILABLE",
}
CAUSES_HOLD_OPERATEUR = CAUSES_TENTATIVE_NON_RETRYABLE | {
    "IN_FLIGHT_UNRECONCILED", "RETRY_RECONCILIATION_FAILED",
    "ATTEMPT_RECEIPT_MISSING", "ATTEMPT_RECEIPT_INVALID",
    "COST_ACCOUNTING_UNKNOWN",
}
CAUSE_CODES = {
    "OUTPUT_NO_PAGE", "API_MISSING_OR_INVALID", "NON_DETERMINISTIC", "ORDER_DEPENDENT",
    "INITIAL_STATE_INVALID", "VERIFY_TIMEOUT", "VERIFY_PROCESS_ERROR",
    "ENVIRONMENT_MISMATCH", "OUT_OF_BOUNDS", "PRECISION_THRESHOLD_FAILED",
    "UPSTREAM_CARD_UNOBSERVABLE", "FINISH_LENGTH_AMBIGUOUS", "COLLECTION_UNAVAILABLE",
    "SCORE_RECEIPT_MISSING",
}
CAUSES_UNKNOWN_SCORE = {
    "VERIFY_TIMEOUT", "VERIFY_PROCESS_ERROR", "ENVIRONMENT_MISMATCH",
    "UPSTREAM_CARD_UNOBSERVABLE", "FINISH_LENGTH_AMBIGUOUS",
}
CAUSES_ECHEC_PAR_CARTE = {
    "pentagone-api": {"OUTPUT_NO_PAGE", "API_MISSING_OR_INVALID"},
    "pentagone-determinisme": {"NON_DETERMINISTIC", "ORDER_DEPENDENT"},
    "pentagone-confinement-court": {"INITIAL_STATE_INVALID", "OUT_OF_BOUNDS"},
    "pentagone-precision-24s": {"PRECISION_THRESHOLD_FAILED"},
    "pentagone-horizons-longs": {"OUT_OF_BOUNDS", "PRECISION_THRESHOLD_FAILED"},
}
AXES_PENTAGONE = (
    "pentagone-api",
    "pentagone-determinisme",
    "pentagone-confinement-court",
    "pentagone-precision-24s",
    "pentagone-horizons-longs",
)
# Alias de lecture pour les vérificateurs v4/v5 historiques. Les nouveaux
# objets sérialisés emploient `axes`, jamais `score_cards`
CARDS_V4 = AXES_PENTAGONE

CHAMPS_MANIFESTE_EXECUTION = {
    "schema_version", "mode", "model_requested", "backend",
    "provider_pinned", "provider_expected", "endpoint_tag",
    "quantization", "revision",
    "reasoning_effort", "request_parameters", "max_tokens",
    "data_policy_requested", "request_adapter_version", "tools", "agent",
    "local_environment",
}
CHAMPS_MANIFESTE_EXECUTION_V3 = CHAMPS_MANIFESTE_EXECUTION - {"endpoint_tag"}
CHAMPS_CONTEXTE_MESURE = {
    "schema_version", "protocol_version", "task", "prompt_hash",
    "system_prompt_hash", "axis_id", "verify_version", "verify_hash",
    "measurement_environment_hash", "confidentiality_regime",
}
CHAMPS_RECU_TENTATIVE = {
    "schema_version", "protocol_version", "campaign_lock_hash",
    "collection_id", "attempt", "result", "cause_code",
    "execution_manifest_hash", "payload_hash", "http_response_received",
    "candidate_artifact_accepted", "cost_accounting", "retry_after",
}
CHAMPS_RECU_COLLECTE = {
    "schema_version", "protocol_version", "campaign_lock_hash",
    "collection_id", "attempt", "result", "payload_hash",
    "execution_manifest_hash", "served", "candidate", "response_json_sha256",
    "usage", "cost_accounting", "duration_ns", "cause_code",
}
CHAMPS_RECU_SCORE = {
    "schema_version", "protocol_version", "campaign_lock_hash",
    "collection_id", "collection_receipt_hash", "response_sha256", "alias",
    "run", "axis_id", "verify_version", "verify_hash", "measurement_context",
    "measurement_context_hash", "measurement_environment", "etat", "cause_code",
    "verdict", "niveau", "frontiere", "predicats", "mesures",
}
PANEL_B0 = (
    "reference-gpt-5-6", "reference-gpt-5-6-high", "reference-gpt-5-6-xhigh",
    "opus-5-high", "opus-5-xhigh", "fable-5-medium", "fable-5-high",
    "fable-5-xhigh", "grok-4-5", "grok-4-5-high", "qwen3-8-max",
    "mistral-medium-3-5", "deepseek-v4-flash", "deepseek-v4-pro", "mimo-v2-5",
    "minimax-m3", "hy3", "kimi-k3-max", "muse-spark-1-2-max",
)
TOLERANCES_24 = (
    "1e+2", "3e+1", "1e+1", "3e+0", "1e+0", "3e-1", "1e-1", "3e-2", "1e-2",
    "3e-3", "1e-3", "3e-4", "1e-4", "3e-5", "1e-5", "3e-6", "1e-6", "3e-7",
    "1e-7", "3e-8", "1e-8", "3e-9", "1e-9", "3e-10", "1e-10", "3e-11", "1e-11",
    "3e-12", "1e-12", "3e-13", "1e-13", "3e-14", "1e-14", "3e-15", "1e-15",
    "3e-16", "1e-16",
)
PREDICATS_V4 = {
    "pentagone-api": ("P0_PAGE", "P1_API_NUMERIC_TOTAL"),
    "pentagone-determinisme": ("D1_REPEATABLE", "D2_ORDER_INDEPENDENT"),
    "pentagone-confinement-court": (
        "I0_INITIAL_STATE", "C2_CONFINEMENT", "C10_CONFINEMENT", "C20_CONFINEMENT",
    ),
    "pentagone-precision-24s": tuple(f"P24_{tol}" for tol in TOLERANCES_24),
    "pentagone-horizons-longs": (
        "C35_CONFINEMENT", "E35_PRECISION", "C55_CONFINEMENT",
        "E55_PRECISION", "C75_CONFINEMENT", "E75_PRECISION",
    ),
}
PREDICATS_V5 = {
    **PREDICATS_V4,
    "pentagone-horizons-longs": (
        "C35_CONFINEMENT", "E35_PRECISION", "C55_CONFINEMENT",
        "E55_PRECISION", "C75_CONFINEMENT",
    ),
}


class ContratV2Invalide(ValueError):
    """Le manifeste ou le reçu ne satisfait pas le contrat v2"""


class PlafondDepasse(RuntimeError):
    """Une réservation dépasserait le plafond préenregistré"""


def predicats_pour_verificateur(verify_version: str) -> dict[str, tuple[str, ...]]:
    """Conserver les catalogues historiques tout en versionnant l'instrument actif"""
    if verify_version == "verify-v5":
        return PREDICATS_V4
    if verify_version == "verify-v6":
        return PREDICATS_V5
    raise ContratV2Invalide(f"catalogue de prédicats inconnu: {verify_version}")


def sha256_octets(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_fichier(path: Path) -> str:
    return sha256_octets(path.read_bytes())


def charger_json(path: Path) -> dict[str, Any]:
    try:
        objet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContratV2Invalide(f"JSON illisible {path}: {type(exc).__name__}") from exc
    if not isinstance(objet, dict):
        raise ContratV2Invalide(f"objet JSON attendu dans {path}")
    return objet


def resultat_acquis_v2(racine: Path, collection_id: str) -> str | None:
    """Refuser un appel direct après acquisition ou notation du run"""
    dossier = racine / "collections" / collection_id
    if dossier.is_dir():
        for tentative in sorted(dossier.glob("attempt-*")):
            if not tentative.is_dir():
                continue
            if (tentative / "COMPLETE").is_file():
                return f"résultat COMPLETE déjà acquis dans {tentative.name}"
            recu = tentative / "collection-receipt.json"
            if recu.is_file():
                try:
                    objet = charger_json(recu)
                except ContratV2Invalide:
                    return f"reçu de collecte antérieur invalide dans {tentative.name}"
                if objet.get("collection_id") == collection_id and objet.get("result") in {
                    "COMPLETE", "COLLECTED"
                }:
                    return f"reçu de collecte déjà acquis dans {tentative.name}"

    scores = racine / "scores"
    if scores.is_dir():
        for recu in scores.glob("*/*/*.json"):
            try:
                objet = charger_json(recu)
            except ContratV2Invalide:
                continue
            if objet.get("collection_id") == collection_id and objet.get("etat") == "SCORED":
                return "score SCORED déjà acquis"
    return None


def ecrire_json_immuable(path: Path, objet: dict[str, Any]) -> None:
    """Écrire une fois ou confirmer que les octets existants sont identiques"""
    texte = json.dumps(objet, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ContratV2Invalide(f"lien symbolique interdit pour le reçu {path}")
    fd, nom_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(nom_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as flux:
            flux.write(texte)
            flux.flush()
            os.fsync(flux.fileno())
        os.chmod(tmp, 0o600)
        try:
            os.link(tmp, path)
        except FileExistsError:
            if path.is_symlink() or path.read_text(encoding="utf-8") != texte:
                raise ContratV2Invalide(f"refus d’écraser le reçu immuable {path}")
    finally:
        tmp.unlink(missing_ok=True)


def _exiger(condition: bool, message: str) -> None:
    if not condition:
        raise ContratV2Invalide(message)


def _entier_positif(value: Any, chemin: str, zero: bool = False) -> int:
    minimum = 0 if zero else 1
    _exiger(isinstance(value, int) and not isinstance(value, bool) and value >= minimum,
            f"{chemin} doit être un entier >= {minimum}")
    return value


def _sha(value: Any, chemin: str) -> str:
    _exiger(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            f"{chemin} doit être un SHA-256 hexadécimal complet")
    return value


def _git_oid(value: Any, chemin: str) -> str:
    _exiger(
        isinstance(value, str)
        and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value) is not None,
        f"{chemin} doit être un identifiant Git complet",
    )
    return value


def descripteur_environnement_hote(
    runtimes_supplementaires: list[dict[str, str]],
    browser: dict[str, str] | None,
) -> dict[str, Any]:
    """Décrire l'hôte sans lancer de navigateur ni consulter le réseau"""
    import locale as locale_hote
    import platform
    import time as temps_hote

    try:
        langue, codage = locale_hote.getlocale()
        locale = f"{langue}.{codage}" if langue and codage else (langue or "opaque")
    except (ValueError, TypeError):
        locale = "opaque"
    runtimes = [
        {"name": "python", "version": platform.python_version()},
        *runtimes_supplementaires,
    ]
    return {
        "schema_version": SCHEMA_ENVIRONMENT,
        "os": {
            "name": platform.system(),
            "version": platform.release(),
            "kernel": platform.version(),
        },
        "architecture": platform.machine(),
        "locale": locale,
        "timezone": temps_hote.tzname[0] if temps_hote.tzname else "opaque",
        "runtimes": sorted(runtimes, key=lambda x: x["name"]),
        "browser": browser,
        "sandbox_image_digest": None,
    }


def descripteur_environnement_runner() -> dict[str, Any]:
    return descripteur_environnement_hote([], None)


def valider_descripteur_environnement(
    environnement: Any,
    chemin: str,
) -> dict[str, Any]:
    _exiger(isinstance(environnement, dict), f"{chemin} absent")
    _exiger(set(environnement) == CHAMPS_ENVIRONNEMENT,
            f"{chemin} doit contenir les huit champs contractuels exacts")
    _exiger(environnement.get("schema_version") == SCHEMA_ENVIRONMENT,
            f"schéma invalide dans {chemin}")
    os_info = environnement.get("os")
    _exiger(isinstance(os_info, dict) and set(os_info) == {"name", "version", "kernel"},
            f"os invalide dans {chemin}")
    _exiger(
        all(isinstance(os_info.get(cle), str) and os_info[cle] for cle in ("name", "version"))
        and (os_info.get("kernel") is None
             or isinstance(os_info.get("kernel"), str) and bool(os_info["kernel"])),
        f"identité os invalide dans {chemin}",
    )
    for cle in ("architecture", "locale", "timezone"):
        _exiger(isinstance(environnement.get(cle), str) and environnement[cle],
                f"{cle} invalide dans {chemin}")
    runtimes = environnement.get("runtimes")
    _exiger(isinstance(runtimes, list) and runtimes,
            f"runtimes absents dans {chemin}")
    noms = []
    for i, runtime in enumerate(runtimes):
        _exiger(isinstance(runtime, dict) and set(runtime) == {"name", "version"},
                f"runtime invalide dans {chemin}.runtimes[{i}]")
        _exiger(
            all(isinstance(runtime.get(cle), str) and runtime[cle]
                for cle in ("name", "version")),
            f"identité runtime invalide dans {chemin}.runtimes[{i}]",
        )
        noms.append(runtime["name"])
    _exiger(noms == sorted(noms) and len(noms) == len(set(noms)),
            f"runtimes non triés ou dupliqués dans {chemin}")
    browser = environnement.get("browser")
    _exiger(
        browser is None
        or isinstance(browser, dict)
        and set(browser) == {"name", "version"}
        and all(isinstance(browser.get(cle), str) and browser[cle]
                for cle in ("name", "version")),
        f"browser invalide dans {chemin}",
    )
    digest = environnement.get("sandbox_image_digest")
    _exiger(
        digest is None
        or isinstance(digest, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None,
        f"sandbox_image_digest invalide dans {chemin}",
    )
    return environnement


def _decimal_non_negatif(value: Any, chemin: str) -> Decimal:
    _exiger(isinstance(value, str) and value, f"{chemin} doit être une chaîne décimale")
    try:
        nombre = Decimal(value)
    except InvalidOperation as exc:
        raise ContratV2Invalide(f"{chemin} n'est pas décimal") from exc
    _exiger(nombre.is_finite() and nombre >= 0, f"{chemin} doit être fini et positif ou nul")
    return nombre


def _cout_max_depuis_route(route: dict[str, Any], max_tokens: int, chemin: str) -> int:
    borne_prompt = _entier_positif(
        route.get("prompt_token_upper_bound"), f"{chemin}.prompt_token_upper_bound"
    )
    entree = _decimal_non_negatif(
        route.get("input_usd_per_million_tokens"),
        f"{chemin}.input_usd_per_million_tokens",
    )
    sortie = _decimal_non_negatif(
        route.get("output_usd_per_million_tokens"),
        f"{chemin}.output_usd_per_million_tokens",
    )
    requete = _decimal_non_negatif(route.get("request_usd"), f"{chemin}.request_usd")
    total = entree * borne_prompt + sortie * max_tokens + requete * Decimal(1_000_000)
    return int(total.to_integral_value(rounding=ROUND_CEILING))


def chemin_relatif_sur(value: Any, chemin: str) -> str:
    _exiger(isinstance(value, str) and value, f"{chemin} doit être un chemin relatif")
    p = Path(value)
    _exiger(not p.is_absolute() and ".." not in p.parts and "." not in p.parts,
            f"{chemin} contient une traversée ou un chemin absolu")
    _exiger(str(p) == value, f"{chemin} n’est pas sous forme canonique")
    return value


def resoudre_sous(racine: Path, relatif: str) -> Path:
    """Résoudre un chemin fermé sous une racine sans accepter de lien"""
    chemin_relatif_sur(relatif, "chemin")
    racine_resolue = racine.resolve()
    courant = racine_resolue
    for part in Path(relatif).parts:
        courant = courant / part
        if courant.is_symlink():
            raise ContratV2Invalide(f"lien symbolique interdit dans {relatif}")
    resolu = courant.resolve()
    _exiger(resolu == racine_resolue or racine_resolue in resolu.parents,
            f"chemin hors racine: {relatif}")
    return resolu


def _extraire_consignes(task_file: Path) -> str:
    texte = task_file.read_bytes().decode("utf-8")
    m = re.search(
        r"^## Consignes visibles par le modèle.*?\n(.*?)(?=^## )",
        texte,
        re.DOTALL | re.MULTILINE,
    )
    _exiger(m is not None, f"consignes visibles absentes de {task_file}")
    lignes = [ligne for ligne in m.group(1).splitlines() if ligne.startswith(">")]
    def dequote(ligne: str) -> str:
        return ligne[2:] if ligne.startswith("> ") else ligne[1:]
    consignes = "\n".join(dequote(ligne) for ligne in lignes).strip()
    _exiger(bool(consignes), f"consignes visibles vides dans {task_file}")
    return consignes


def assembler_prompt_verrouille(
    racine_depot: Path,
    tache: dict[str, Any],
    verifier_arbre: bool = True,
    verifier_prompt: bool = True,
) -> tuple[str, dict[str, str]]:
    """Reconstruire uniquement le prompt décrit par le lock"""
    task_dir_rel = chemin_relatif_sur(tache.get("task_dir"), "task.task_dir")
    task_dir = resoudre_sous(racine_depot, task_dir_rel)
    _exiger(task_dir.is_dir(), f"dossier de tâche absent: {task_dir_rel}")
    task_file_name = chemin_relatif_sur(tache.get("task_file"), "task.task_file")
    _exiger(len(Path(task_file_name).parts) == 1, "task.task_file doit être un nom simple")
    task_file = resoudre_sous(task_dir, task_file_name)
    _exiger(task_file.is_file(), f"fichier de tâche absent: {task_file_name}")

    manifeste = tache.get("task_tree")
    _exiger(isinstance(manifeste, list) and manifeste, "task.task_tree doit être une liste fermée")
    declares: dict[str, dict[str, Any]] = {}
    for i, entree in enumerate(manifeste):
        _exiger(isinstance(entree, dict), f"task.task_tree[{i}] doit être un objet")
        nom = chemin_relatif_sur(entree.get("path"), f"task.task_tree[{i}].path")
        _exiger(nom not in declares, f"fichier dupliqué dans task_tree: {nom}")
        _sha(entree.get("sha256"), f"task.task_tree[{i}].sha256")
        _entier_positif(entree.get("bytes"), f"task.task_tree[{i}].bytes", zero=True)
        _exiger(entree.get("role") in {"instructions", "input", "judge", "historical", "control"},
                f"rôle inconnu pour {nom}")
        declares[nom] = entree

    if verifier_arbre:
        trouves: set[str] = set()
        for path in sorted(task_dir.rglob("*")):
            if path.is_symlink():
                raise ContratV2Invalide(f"lien symbolique interdit dans la tâche: {path}")
            if path.is_file():
                trouves.add(path.relative_to(task_dir).as_posix())
        _exiger(trouves == set(declares),
                f"arbre de tâche différent du lock, ajoutés={sorted(trouves - set(declares))}, "
                f"absents={sorted(set(declares) - trouves)}")

    for nom, entree in declares.items():
        path = resoudre_sous(task_dir, nom)
        _exiger(path.is_file(), f"fichier verrouillé absent: {nom}")
        data = path.read_bytes()
        _exiger(len(data) == entree["bytes"], f"taille modifiée: {nom}")
        _exiger(sha256_octets(data) == entree["sha256"], f"empreinte modifiée: {nom}")

    _exiger(task_file_name in declares and declares[task_file_name]["role"] == "instructions",
            "task_file doit être l’unique source d’instructions")
    entrees_visibles = [e for e in manifeste if e["role"] == "input"]
    _exiger(bool(entrees_visibles), "au moins un fichier d’entrée visible est requis")
    parties = [_extraire_consignes(task_file)]
    inputs: dict[str, str] = {}
    for entree in sorted(entrees_visibles, key=lambda x: x["path"]):
        nom = entree["path"]
        contenu = resoudre_sous(task_dir, nom).read_bytes().decode("utf-8")
        parties.append(f"\n--- FILE: {nom} ---\n{contenu}")
        inputs[nom] = contenu
    prompt = "\n".join(parties)
    if verifier_prompt:
        _exiger(sha256_octets(prompt.encode("utf-8")) == tache.get("prompt_sha256"),
                "prompt reconstruit différent de task.prompt_sha256")
    return prompt, inputs


def _git_lire(racine_depot: Path, arguments: list[str], motif: str) -> bytes:
    try:
        proc = subprocess.run(
            ["git", "-C", str(racine_depot), *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise ContratV2Invalide(f"Git indisponible pour {motif}") from exc
    _exiger(proc.returncode == 0, f"preuve Git absente pour {motif}")
    return proc.stdout


def _chemins_source_lock(lock: dict[str, Any]) -> list[str]:
    continuation = lock.get("schema_version") in {
        SCHEMA_LOCK_CONTINUATION_V5, SCHEMA_LOCK_CONTINUATION,
    }
    chemins = set(
        CHEMINS_SOURCE_COLLECTE if continuation else CHEMINS_SOURCE_RUNTIME
    )
    registry = lock.get("registry_source")
    if isinstance(registry, dict) and not continuation:
        chemins.add(chemin_relatif_sur(registry.get("path"), "registry_source.path"))
    task = lock.get("task")
    if isinstance(task, dict):
        task_dir = chemin_relatif_sur(task.get("task_dir"), "task.task_dir")
        for i, entree in enumerate(task.get("task_tree") or []):
            _exiger(isinstance(entree, dict), f"task.task_tree[{i}] invalide")
            relatif = chemin_relatif_sur(
                entree.get("path"), f"task.task_tree[{i}].path"
            )
            chemins.add((Path(task_dir) / relatif).as_posix())
    objets_mesure = ([] if continuation else (
        lock.get("axes")
        if lock.get("schema_version") in {
            SCHEMA_LOCK_V3, SCHEMA_LOCK,
            SCHEMA_LOCK_CONTINUATION_V5, SCHEMA_LOCK_CONTINUATION,
        }
        else lock.get("score_cards")
    )) or []
    for i, card in enumerate(objets_mesure):
        _exiger(isinstance(card, dict), f"axe[{i}] invalide")
        manifeste = card.get("verify_manifest")
        _exiger(isinstance(manifeste, dict), f"verify_manifest absent dans axe[{i}]")
        for j, asset in enumerate(manifeste.get("assets") or []):
            _exiger(isinstance(asset, dict),
                    f"actif invalide dans axes[{i}].verify_manifest.assets[{j}]")
            chemins.add(chemin_relatif_sur(
                asset.get("path"),
                f"axes[{i}].verify_manifest.assets[{j}].path",
            ))
    return sorted(chemins)


def _verifier_source_depot(lock: dict[str, Any], racine_depot: Path) -> None:
    source = lock["repository_source"]
    commit = source["commit"]
    confirme = _git_lire(
        racine_depot, ["rev-parse", "--verify", f"{commit}^{{commit}}"], "commit source"
    ).decode("ascii", errors="strict").strip()
    _exiger(confirme == commit, "le commit source ne désigne pas le commit exact")
    head = _git_lire(
        racine_depot, ["rev-parse", "--verify", "HEAD"], "HEAD"
    ).decode("ascii", errors="strict").strip()
    _exiger(head == commit, "HEAD différent du commit source verrouillé")
    for relatif in _chemins_source_lock(lock):
        _exiger(":" not in relatif, f"chemin source Git invalide: {relatif}")
        path = resoudre_sous(racine_depot, relatif)
        _exiger(path.is_file() and not path.is_symlink(),
                f"source requise absente ou liée: {relatif}")
        octets_commit = _git_lire(
            racine_depot, ["cat-file", "blob", f"{commit}:{relatif}"], relatif
        )
        _exiger(path.read_bytes() == octets_commit,
                f"source courante différente du commit: {relatif}")


def _valider_sources_continuation(
    lock: dict[str, Any], racine_depot: Path | None
) -> None:
    instrument = lock.get("instrument_source")
    champs_instrument = {
        "commit", "reference_lock_path", "reference_lock_sha256",
        "reference_campaign_lock_hash",
    }
    _exiger(isinstance(instrument, dict) and set(instrument) == champs_instrument,
            "source d'instrument de continuation invalide")
    commit_instrument = _git_oid(
        instrument.get("commit"), "instrument_source.commit"
    )
    reference_lock_path = chemin_relatif_sur(
        instrument.get("reference_lock_path"),
        "instrument_source.reference_lock_path",
    )
    _sha(instrument.get("reference_lock_sha256"),
         "instrument_source.reference_lock_sha256")
    _sha(instrument.get("reference_campaign_lock_hash"),
         "instrument_source.reference_campaign_lock_hash")

    serie = lock.get("series_source")
    champs_serie = {
        "series_id", "inventory_path", "inventory_sha256", "inventory_hash",
        "global_cap_microdollars", "source_ledger_engaged_microdollars",
        "continuation_cap_microdollars", "approved_estimate_microdollars",
        "approved_fallback_routes",
    }
    _exiger(isinstance(serie, dict) and set(serie) == champs_serie,
            "source de série de continuation invalide")
    _exiger(isinstance(serie.get("series_id"), str) and serie["series_id"],
            "series_source.series_id absent")
    inventory_path = chemin_relatif_sur(
        serie.get("inventory_path"), "series_source.inventory_path"
    )
    _sha(serie.get("inventory_sha256"), "series_source.inventory_sha256")
    _sha(serie.get("inventory_hash"), "series_source.inventory_hash")
    global_cap = _entier_positif(
        serie.get("global_cap_microdollars"),
        "series_source.global_cap_microdollars",
    )
    engage = _entier_positif(
        serie.get("source_ledger_engaged_microdollars"),
        "series_source.source_ledger_engaged_microdollars",
        zero=True,
    )
    cap_continuation = _entier_positif(
        serie.get("continuation_cap_microdollars"),
        "series_source.continuation_cap_microdollars",
    )
    estimation = _entier_positif(
        serie.get("approved_estimate_microdollars"),
        "series_source.approved_estimate_microdollars",
    )
    _exiger(global_cap == engage + cap_continuation,
            "plafond de continuation différent du reliquat global")
    _exiger(
        lock["budget"]["cap_microdollars"] == cap_continuation
        and lock["budget"]["estimate_microdollars"] == estimation,
        "budget du lock différent de l'approbation de continuation",
    )
    fallbacks = serie.get("approved_fallback_routes")
    _exiger(isinstance(fallbacks, list), "routes fallback approuvées absentes")
    aliases_fallback: list[str] = []
    for index, fallback in enumerate(fallbacks):
        _exiger(
            isinstance(fallback, dict)
            and set(fallback) == {"alias", "provider", "endpoint_tag"},
            f"fallback approuvé invalide à l'index {index}",
        )
        for champ in ("alias", "provider", "endpoint_tag"):
            _exiger(isinstance(fallback.get(champ), str) and fallback[champ],
                    f"{champ} absent dans le fallback approuvé {index}")
        aliases_fallback.append(fallback["alias"])
    _exiger(aliases_fallback == sorted(set(aliases_fallback)),
            "fallbacks approuvés non triés ou dupliqués")

    if racine_depot is None:
        return

    confirme = _git_lire(
        racine_depot,
        ["rev-parse", "--verify", f"{commit_instrument}^{{commit}}"],
        "commit instrument",
    ).decode("ascii", errors="strict").strip()
    _exiger(confirme == commit_instrument,
            "le commit instrument ne désigne pas le commit exact")

    reference_path = resoudre_sous(racine_depot, reference_lock_path)
    _exiger(reference_path.is_file() and not reference_path.is_symlink(),
            "lock de référence absent ou lié")
    reference_data = reference_path.read_bytes()
    _exiger(sha256_octets(reference_data) == instrument["reference_lock_sha256"],
            "lock de référence modifié")
    try:
        reference_lock = json.loads(reference_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContratV2Invalide("lock de référence illisible") from exc
    valider_lock(reference_lock)
    _exiger(
        empreinte(reference_lock) == instrument["reference_campaign_lock_hash"],
        "empreinte sémantique du lock de référence invalide",
    )
    _exiger(
        reference_lock.get("repository_source", {}).get("commit")
        == commit_instrument,
        "commit instrument différent du lock de référence",
    )
    _exiger(
        lock["task"] == reference_lock["task"]
        and lock["axes"] == reference_lock["axes"],
        "instrument de continuation différent du lock de référence",
    )
    cellules_reference = {
        cellule["collection_id"]: cellule
        for cellule in reference_lock["collections"]
    }
    _exiger(
        all(cellules_reference.get(cellule["collection_id"]) == cellule
            for cellule in lock["collections"]),
        "cellule de continuation différente du lock de référence",
    )
    for entree in lock["task"]["task_tree"]:
        relatif = (
            Path(lock["task"]["task_dir"]) / entree["path"]
        ).as_posix()
        data = _git_lire(
            racine_depot,
            ["cat-file", "blob", f"{commit_instrument}:{relatif}"],
            relatif,
        )
        _exiger(
            len(data) == entree["bytes"]
            and sha256_octets(data) == entree["sha256"],
            f"actif de tâche différent du commit instrument: {relatif}",
        )
    for axe in lock["axes"]:
        for asset in axe["verify_manifest"]["assets"]:
            relatif = asset["path"]
            data = _git_lire(
                racine_depot,
                ["cat-file", "blob", f"{commit_instrument}:{relatif}"],
                relatif,
            )
            _exiger(
                len(data) == asset["bytes"]
                and sha256_octets(data) == asset["sha256"],
                f"actif juge différent du commit instrument: {relatif}",
            )
    registry = lock["registry_source"]
    registry_path = registry["path"]
    registry_data = _git_lire(
        racine_depot,
        ["cat-file", "blob", f"{commit_instrument}:{registry_path}"],
        registry_path,
    )
    _exiger(sha256_octets(registry_data) == registry["sha256"],
            "registre différent du commit instrument")

    inventory_file = resoudre_sous(racine_depot, inventory_path)
    _exiger(inventory_file.is_file() and not inventory_file.is_symlink(),
            "inventaire de série absent ou lié")
    inventory_data = inventory_file.read_bytes()
    _exiger(sha256_octets(inventory_data) == serie["inventory_sha256"],
            "inventaire de série modifié")
    try:
        inventory = json.loads(inventory_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContratV2Invalide("inventaire de série illisible") from exc
    _exiger(
        inventory.get("schema_version")
        == "benchmark-lab-x/acquisition-inventory/v1"
        and empreinte(inventory) == serie["inventory_hash"]
        and inventory.get("series_id") == serie["series_id"],
        "inventaire de série différent du lock",
    )
    inventory_reference = inventory.get("reference")
    _exiger(
        isinstance(inventory_reference, dict)
        and inventory_reference.get("campaign_lock_hash")
        == instrument["reference_campaign_lock_hash"],
        "inventaire lié à un autre lock de référence",
    )
    counts = inventory.get("counts")
    _exiger(
        isinstance(counts, dict)
        and all(isinstance(counts.get(cle), int)
                and not isinstance(counts.get(cle), bool)
                and counts[cle] >= 0
                for cle in ("total", "acquired", "pending"))
        and counts["total"] == 114
        and counts["acquired"] + counts["pending"] == counts["total"],
        "comptage de l'inventaire invalide",
    )
    slots = inventory.get("slots")
    _exiger(isinstance(slots, list), "slots absents de l'inventaire")
    pending_ids = {
        slot.get("slot_id")
        for slot in slots
        if isinstance(slot, dict) and slot.get("status") == "pending"
    }
    _exiger(
        pending_ids == {cellule["collection_id"] for cellule in lock["collections"]}
        and counts.get("pending") == len(lock["collections"]),
        "grille de continuation différente des slots pendants",
    )
    costs = inventory.get("costs")
    _exiger(
        isinstance(costs, dict)
        and costs.get("source_ledger_engaged_microdollars") == engage
        and costs.get("global_cap_microdollars") == global_cap
        and costs.get("global_cap_remaining_microdollars") == cap_continuation,
        "budget de l'inventaire différent du lock",
    )
    plans = inventory.get("route_plans")
    _exiger(isinstance(plans, dict), "plans de route absents de l'inventaire")
    attendus_fallback = []
    for alias in lock["panel"]:
        plan = plans.get(alias)
        _exiger(isinstance(plan, dict), f"plan de route absent pour {alias}")
        fallback = plan.get("fallback")
        if fallback is None:
            continue
        _exiger(isinstance(fallback, dict), f"fallback invalide pour {alias}")
        route = fallback.get("route_identity", {})
        _exiger(
            isinstance(route, dict)
            and isinstance(route.get("provider_pinned"), str)
            and isinstance(route.get("endpoint_tag"), str),
            f"identité du fallback invalide pour {alias}",
        )
        attendus_fallback.append({
            "alias": alias,
            "provider": route.get("provider_pinned"),
            "endpoint_tag": route.get("endpoint_tag"),
        })
    _exiger(sorted(attendus_fallback, key=lambda x: x["alias"]) == fallbacks,
            "approbation des fallbacks différente de l'inventaire")


def valider_environnement_observe(
    lock: dict[str, Any],
    role: str,
    environnement: dict[str, Any],
) -> None:
    _exiger(role in {"runner", "measurement"}, "rôle d'environnement inconnu")
    valider_descripteur_environnement(environnement, f"environnement observé {role}")
    attendu = lock.get("environments", {}).get(role)
    _exiger(isinstance(attendu, dict), f"environnement figé {role} absent")
    _exiger(
        environnement == attendu.get("descriptor")
        and _empreinte_contractuelle(environnement, f"environnement observé {role}")
        == attendu.get("sha256"),
        f"environnement observé {role} différent du lock",
    )


def _valider_lock_historique_v2(
    lock: dict[str, Any], racine_depot: Path | None = None
) -> dict[str, Any]:
    """Lecteur non autoritaire du lock historique, jamais utilisé pour collecter"""
    _exiger(lock.get("schema_version") == SCHEMA_LOCK_HISTORIQUE,
            "schema de lock historique v2 absent")
    _exiger(lock.get("protocol_version") == PROTOCOLE_VERSION, "protocole v2 absent du lock")
    _exiger(isinstance(lock.get("campaign_id"), str) and lock["campaign_id"],
            "campaign_id absent")
    _exiger(lock.get("paid_authorization_required") is True,
            "une autorisation payante séparée doit rester obligatoire")
    repository_source = lock.get("repository_source")
    _exiger(
        isinstance(repository_source, dict) and set(repository_source) == {"commit"},
        "commit source du dépôt absent ou ambigu",
    )
    _git_oid(repository_source.get("commit"), "repository_source.commit")
    environments = lock.get("environments")
    _exiger(
        isinstance(environments, dict) and set(environments) == {"runner", "measurement"},
        "environnements runner et measurement requis",
    )
    for role in ("runner", "measurement"):
        entree = environments.get(role)
        _exiger(
            isinstance(entree, dict) and set(entree) == {"descriptor", "sha256"},
            f"environnement figé {role} invalide",
        )
        descripteur = valider_descripteur_environnement(
            entree.get("descriptor"), f"environments.{role}.descriptor"
        )
        _sha(entree.get("sha256"), f"environments.{role}.sha256")
        _exiger(
            _empreinte_contractuelle(descripteur, f"environnement figé {role}")
            == entree["sha256"],
            f"empreinte de l'environnement figé {role} invalide",
        )
    panel = lock.get("panel")
    _exiger(isinstance(panel, list) and panel and all(isinstance(x, str) and x for x in panel),
            "panel invalide")
    _exiger(len(panel) == len(set(panel)), "alias dupliqué dans le panel")
    _exiger(tuple(panel) == PANEL_B0, "panel ou ordre différent de B0-06 approuvé")
    runs = _entier_positif(lock.get("runs"), "runs")
    _exiger(runs == 6, "protocol/v2 exige six runs")
    _exiger(lock.get("attempts_max") == 3, "protocol/v2 exige trois tentatives maximum")
    runner = lock.get("runner")
    _exiger(isinstance(runner, dict), "configuration du runner absente")
    _exiger(runner.get("concurrency") == 2,
            "concurrence différente des deux travailleurs figés")
    _exiger(runner.get("transport_timeout_s") == 600,
            "timeout transport différent des 600 s figées")

    budget = lock.get("budget")
    _exiger(isinstance(budget, dict), "budget absent")
    _exiger(budget.get("currency") == "USD", "devise du budget différente de USD")
    _exiger(budget.get("cap_microdollars") == PLAFOND_B0_HISTORIQUE,
            "plafond différent des 55 $ approuvés")
    _exiger(budget.get("estimate_microdollars") == ESTIMATION_B0_HISTORIQUE,
            "estimation différente des 31,812500 $ approuvés")

    registry_source = lock.get("registry_source")
    _exiger(isinstance(registry_source, dict), "source du registre absente")
    registry_path = chemin_relatif_sur(
        registry_source.get("path"), "registry_source.path"
    )
    _sha(registry_source.get("sha256"), "registry_source.sha256")

    route_snapshot_source = lock.get("route_snapshot_source")
    _exiger(isinstance(route_snapshot_source, dict), "source du snapshot de routes absente")
    route_snapshot_path = chemin_relatif_sur(
        route_snapshot_source.get("path"), "route_snapshot_source.path"
    )
    _sha(route_snapshot_source.get("sha256"), "route_snapshot_source.sha256")
    _exiger(
        route_snapshot_source.get("schema_version")
        == "benchmark-lab-x/route-preflight-snapshot/v1",
        "schéma du snapshot de routes invalide",
    )
    _exiger(
        route_snapshot_source.get("criterion_version")
        == "benchmark-lab-x/selection-route/v2",
        "critère du snapshot de routes invalide",
    )
    _exiger(
        isinstance(route_snapshot_source.get("observed_at"), str)
        and route_snapshot_source["observed_at"],
        "date du snapshot de routes absente",
    )
    _exiger(
        route_snapshot_source.get("budget_status") == "B0_09_UNCHANGED"
        and route_snapshot_source.get("repriced_estimate_microdollars")
        == budget["estimate_microdollars"],
        "snapshot de routes sans approbation B0-09",
    )
    _sha(
        route_snapshot_source.get("b0_09_approval_hash"),
        "route_snapshot_source.b0_09_approval_hash",
    )
    snapshot_routes: dict[str, Any] | None = None
    if racine_depot is not None:
        registry_file = resoudre_sous(racine_depot, registry_path)
        _exiger(
            registry_file.is_file()
            and sha256_fichier(registry_file) == registry_source["sha256"],
            "registre verrouillé absent ou modifié",
        )
        snapshot_file = resoudre_sous(racine_depot, route_snapshot_path)
        _exiger(snapshot_file.is_file(), "snapshot de routes verrouillé absent")
        snapshot_data = snapshot_file.read_bytes()
        _exiger(
            sha256_octets(snapshot_data) == route_snapshot_source["sha256"],
            "snapshot de routes verrouillé modifié",
        )
        try:
            snapshot = json.loads(snapshot_data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContratV2Invalide("snapshot de routes verrouillé illisible") from exc
        _exiger(isinstance(snapshot, dict), "objet attendu dans le snapshot de routes")
        snapshot_budget = snapshot.get("budget_reestimate")
        snapshot_approval = snapshot.get("b0_09_approval")
        _exiger(
            snapshot.get("schema_version") == route_snapshot_source["schema_version"]
            and snapshot.get("criterion_version") == route_snapshot_source["criterion_version"]
            and snapshot.get("observed_at") == route_snapshot_source["observed_at"]
            and snapshot.get("panel") == panel,
            "contexte du snapshot de routes différent du lock",
        )
        _exiger(
            isinstance(snapshot_budget, dict)
            and snapshot_budget.get("status") == route_snapshot_source["budget_status"]
            and snapshot_budget.get("approved_estimate_microdollars")
            == budget["estimate_microdollars"]
            and snapshot_budget.get("repriced_estimate_microdollars")
            == budget["estimate_microdollars"]
            and snapshot_budget.get("approved_cap_microdollars") == budget["cap_microdollars"],
            "recalcul B0-09 du snapshot différent du lock",
        )
        _exiger(
            isinstance(snapshot_approval, dict)
            and snapshot_approval.get("schema_version")
            == "benchmark-lab-x/b0-09-approval/v1"
            and snapshot_approval.get("decision")
            == "B0_09_REVISED_ESTIMATE_APPROVED"
            and snapshot_approval.get("approved_by") == "Ayo"
            and snapshot_approval.get("estimate_microdollars")
            == budget["estimate_microdollars"]
            and snapshot_approval.get("cap_microdollars") == budget["cap_microdollars"]
            and _empreinte_contractuelle(snapshot_approval, "approbation B0-09")
            == route_snapshot_source["b0_09_approval_hash"],
            "approbation B0-09 du snapshot différente du lock",
        )
        _exiger(
            snapshot.get("models_file") == registry_path
            and snapshot.get("models_file_sha256") == registry_source["sha256"],
            "registre du snapshot différent du lock",
        )
        snapshot_routes = snapshot.get("resolved")
        _exiger(
            isinstance(snapshot_routes, dict) and set(snapshot_routes) == set(panel),
            "routes résolues absentes du snapshot",
        )

    task = lock.get("task")
    _exiger(isinstance(task, dict), "task absente du lock")
    _exiger(task.get("task_version") == "task-v3", "task-v3 exigée")
    _sha(task.get("prompt_sha256"), "task.prompt_sha256")
    if racine_depot is not None:
        assembler_prompt_verrouille(racine_depot, task)

    cards = lock.get("score_cards")
    _exiger(isinstance(cards, list) and len(cards) == len(CARDS_V4),
            "cinq cartes de score sont requises")
    ids = []
    kinds_attendus = {
        "pentagone-api": "binary",
        "pentagone-determinisme": "binary",
        "pentagone-confinement-court": "levels",
        "pentagone-precision-24s": "levels",
        "pentagone-horizons-longs": "levels",
    }
    for i, card in enumerate(cards):
        _exiger(isinstance(card, dict), f"score_cards[{i}] invalide")
        ids.append(card.get("id"))
        _exiger(card.get("kind") in {"binary", "levels"}, f"kind invalide pour la carte {i}")
        _exiger(card.get("kind") == kinds_attendus.get(card.get("id")),
                f"kind différent du contrat pour la carte {i}")
        _exiger(card.get("verify_version") == "verify-v5", f"verify-v5 absent pour la carte {i}")
        _sha(card.get("verify_hash"), f"score_cards[{i}].verify_hash")
        chemin_relatif_sur(card.get("verifier_path"), f"score_cards[{i}].verifier_path")
        _exiger(card.get("watchdog_s") == 180, f"garde-fou différent de 180 s pour la carte {i}")
        predicats = card.get("predicates")
        _exiger(isinstance(predicats, list) and predicats
                and all(isinstance(p, str) and p for p in predicats),
                f"prédicats absents pour la carte {i}")
        _exiger(len(predicats) == len(set(predicats)), f"prédicat dupliqué pour la carte {i}")
        _exiger(tuple(predicats) == PREDICATS_V4[card["id"]],
                f"prédicats v4 différents pour {card['id']}")
        _exiger(card.get("aggregation") == {"runs": 6, "order_statistic": 4},
                f"agrégation différente de B0-05 pour {card['id']}")
        manifeste_verify = card.get("verify_manifest")
        _exiger(isinstance(manifeste_verify, dict),
                f"manifeste du vérificateur absent pour {card['id']}")
        _exiger(_empreinte_contractuelle(manifeste_verify, "manifeste du vérificateur")
                == card["verify_hash"],
                f"verify_hash incohérent pour {card['id']}")
        _exiger(manifeste_verify.get("schema_version")
                == "benchmark-lab-x/verifier-manifest/v2",
                f"schéma du manifeste invalide pour {card['id']}")
        _exiger(manifeste_verify.get("card_id") == card["id"]
                and manifeste_verify.get("verify_version") == card["verify_version"]
                and manifeste_verify.get("predicates") == predicats,
                f"manifeste du vérificateur incohérent pour {card['id']}")
        assets = manifeste_verify.get("assets")
        _exiger(isinstance(assets, list) and assets,
                f"actifs du vérificateur absents pour {card['id']}")
        chemins_assets: set[str] = set()
        ordre_assets: list[str] = []
        for j, asset in enumerate(assets):
            _exiger(isinstance(asset, dict), f"actif invalide pour {card['id']}[{j}]")
            path_asset = chemin_relatif_sur(
                asset.get("path"), f"{card['id']}.verify_manifest.assets[{j}].path"
            )
            _exiger(path_asset not in chemins_assets,
                    f"actif dupliqué pour {card['id']}: {path_asset}")
            chemins_assets.add(path_asset)
            ordre_assets.append(path_asset)
            _sha(asset.get("sha256"), f"{card['id']}.assets[{j}].sha256")
            _entier_positif(
                asset.get("bytes"), f"{card['id']}.assets[{j}].bytes", zero=True
            )
            if racine_depot is not None:
                path = resoudre_sous(racine_depot, path_asset)
                _exiger(path.is_file() and not path.is_symlink(),
                        f"actif du vérificateur absent: {path_asset}")
                data = path.read_bytes()
                _exiger(len(data) == asset["bytes"] and sha256_octets(data) == asset["sha256"],
                        f"actif du vérificateur modifié: {path_asset}")
        _exiger(ordre_assets == sorted(ordre_assets),
                f"actifs non triés par chemin pour {card['id']}")
        _exiger(card["verifier_path"] in chemins_assets,
                f"vérificateur principal absent du manifeste pour {card['id']}")
    _exiger(tuple(ids) == CARDS_V4, "identifiants ou ordre des cinq cartes v4 invalides")

    collections = lock.get("collections")
    attendu = len(panel) * runs
    _exiger(isinstance(collections, list) and len(collections) == attendu,
            f"{attendu} cellules de collecte requises")
    vus: set[str] = set()
    couples: set[tuple[str, int]] = set()
    identites: dict[str, str] = {}
    for i, cellule in enumerate(collections):
        _exiger(isinstance(cellule, dict), f"collections[{i}] invalide")
        cid = cellule.get("collection_id")
        _exiger(isinstance(cid, str) and re.fullmatch(r"[a-zA-Z0-9._-]+__r[1-6]", cid) is not None,
                f"collection_id invalide à l’index {i}")
        _exiger(cid not in vus, f"collection_id dupliqué: {cid}")
        vus.add(cid)
        alias = cellule.get("alias")
        run = cellule.get("run")
        _exiger(alias in panel, f"alias hors panel dans {cid}")
        _exiger(isinstance(run, int) and not isinstance(run, bool) and 1 <= run <= 6,
                f"run invalide dans {cid}")
        _exiger(cid == f"{alias}__r{run}", f"collection_id non canonique: {cid}")
        _exiger((alias, run) not in couples, f"cellule dupliquée: {alias} r{run}")
        couples.add((alias, run))
        _exiger(cellule.get("task_version") == "task-v3", f"task-v3 absente dans {cid}")
        _exiger(cellule.get("prompt_sha256") == task["prompt_sha256"],
                f"prompt différent dans {cid}")
        _exiger(isinstance(cellule.get("model"), str) and cellule["model"], f"modèle absent dans {cid}")
        route = cellule.get("route")
        _exiger(isinstance(route, dict), f"route absente dans {cid}")
        _exiger(route.get("metadata_status") == "resolved",
                f"ROUTE_METADATA_UNREACHABLE dans {cid}")
        _exiger(route.get("backend") == "openrouter", f"backend non résolu dans {cid}")
        for champ_route in (
            "provider", "expect_provider", "quantization", "revision",
            "criterion_version", "price_source", "price_observed_at",
        ):
            _exiger(isinstance(route.get(champ_route), str) and route[champ_route],
                    f"{champ_route} absent dans {cid}")
        if snapshot_routes is not None:
            route_snapshot = snapshot_routes.get(alias)
            _exiger(isinstance(route_snapshot, dict), f"route absente du snapshot pour {alias}")
            for champ_route in (
                "metadata_status", "provider", "quantization", "revision",
                "criterion_version", "price_source", "price_observed_at",
                "input_usd_per_million_tokens", "output_usd_per_million_tokens",
                "request_usd",
            ):
                _exiger(
                    route.get(champ_route) == route_snapshot.get(champ_route),
                    f"{champ_route} différent du snapshot dans {cid}",
                )
        params = cellule.get("parameters")
        _exiger(isinstance(params, dict), f"paramètres absents dans {cid}")
        max_tokens = _entier_positif(cellule.get("max_tokens"), f"{cid}.max_tokens")
        if snapshot_routes is not None:
            _exiger(
                snapshot_routes[alias].get("max_tokens") == max_tokens,
                f"max_tokens différent du snapshot dans {cid}",
            )
        max_cost = _entier_positif(
            cellule.get("max_cost_microdollars"), f"{cid}.max_cost_microdollars"
        )
        _exiger(max_cost <= budget["cap_microdollars"],
                f"coût maximal d'un appel supérieur au plafond dans {cid}")
        _exiger(_cout_max_depuis_route(route, max_tokens, f"{cid}.route") == max_cost,
                f"coût maximal différent des prix verrouillés dans {cid}")
        manifeste_execution = cellule.get("execution_manifest")
        _exiger(isinstance(manifeste_execution, dict), f"manifeste d’exécution absent dans {cid}")
        _sha(cellule.get("execution_manifest_hash"), f"{cid}.execution_manifest_hash")
        _exiger(_empreinte_contractuelle(manifeste_execution, "manifeste d'exécution")
                == cellule["execution_manifest_hash"],
                f"empreinte du manifeste d’exécution invalide dans {cid}")
        _exiger(manifeste_execution.get("schema_version")
                == SCHEMA_EXECUTION_HISTORIQUE
                and manifeste_execution.get("protocol_version") == PROTOCOLE_VERSION
                and manifeste_execution.get("task_version") == task["task_version"]
                and manifeste_execution.get("prompt_sha256") == task["prompt_sha256"],
                f"contexte du manifeste d'exécution invalide dans {cid}")
        route_execution = {k: v for k, v in route.items() if k != "metadata_status"}
        _exiger(manifeste_execution.get("model") == cellule["model"]
                and manifeste_execution.get("route") == route_execution
                and manifeste_execution.get("parameters") == params
                and manifeste_execution.get("max_tokens") == max_tokens
                and manifeste_execution.get("data_policy") == "allow"
                and manifeste_execution.get("runner_version") == "collect.py/v3",
                f"champs exécutés différents du manifeste dans {cid}")
        identite = _empreinte_contractuelle({
            "model": cellule["model"],
            "route": route_execution,
            "parameters": params,
            "max_tokens": max_tokens,
            "max_cost_microdollars": max_cost,
            "execution_manifest_hash": cellule["execution_manifest_hash"],
        }, f"identité de {cid}")
        _exiger(alias not in identites or identites[alias] == identite,
                f"identité différente entre les runs de {alias}")
        identites[alias] = identite
    _exiger(couples == {(alias, run) for alias in panel for run in range(1, 7)},
            "grille de collecte incomplète")
    if racine_depot is not None:
        _verifier_source_depot(lock, racine_depot)
    return lock


def valider_manifeste_execution(manifeste: dict[str, Any]) -> dict[str, Any]:
    """Valider les listes positives fermées des manifestes v3 et v4"""
    _exiger(isinstance(manifeste, dict), "manifeste d'exécution absent")
    schema = manifeste.get("schema_version")
    _exiger(schema in {SCHEMA_EXECUTION_V3, SCHEMA_EXECUTION},
            "schéma du manifeste d'exécution inconnu")
    champs = (
        CHAMPS_MANIFESTE_EXECUTION
        if schema == SCHEMA_EXECUTION
        else CHAMPS_MANIFESTE_EXECUTION_V3
    )
    _exiger(set(manifeste) == champs,
            "champs du manifeste d'exécution différents du contrat fermé")
    _exiger(manifeste.get("mode") == "direct", "seul le mode direct est implémenté")
    for champ in (
        "model_requested", "backend", "provider_pinned", "provider_expected",
        "request_adapter_version",
    ):
        _exiger(isinstance(manifeste.get(champ), str) and manifeste[champ].strip(),
                f"{champ} absent du manifeste d'exécution")
    if schema == SCHEMA_EXECUTION_V3:
        for champ in ("quantization", "revision"):
            _exiger(isinstance(manifeste.get(champ), str) and manifeste[champ].strip(),
                    f"{champ} absent du manifeste d'exécution v3")
            _exiger(manifeste[champ].strip().lower() not in {"unknown", "opaque"},
                    f"{champ} obligatoire non résolu")
    else:
        _exiger(isinstance(manifeste.get("endpoint_tag"), str)
                and manifeste["endpoint_tag"].strip(),
                "endpoint_tag de pré-vol absent")
        quantification = manifeste.get("quantization")
        _exiger(isinstance(quantification, dict), "quantification structurée absente")
        if quantification.get("status") == "declared":
            _exiger(set(quantification) == {"status", "value"},
                    "quantification declared ouverte")
            valeur = quantification.get("value")
            _exiger(isinstance(valeur, str) and valeur.strip()
                    and valeur.strip().lower() not in {
                        "unknown", "opaque", "native", "not_disclosed"
                    }, "valeur de quantification déclarée invalide")
        else:
            _exiger(
                set(quantification) == {"status", "value", "basis", "publisher"}
                and quantification.get("status") == "not_disclosed"
                and quantification.get("value") is None
                and quantification.get("basis") == "publisher_managed_api"
                and isinstance(quantification.get("publisher"), str)
                and quantification["publisher"],
                "statut not_disclosed invalide",
            )
        revision = manifeste.get("revision")
        _exiger(
            isinstance(revision, dict)
            and set(revision) == {"status", "kind", "value"}
            and revision.get("status") == "declared"
            and revision.get("kind") == "endpoint_model_id"
            and isinstance(revision.get("value"), str)
            and revision["value"],
            "révision endpoint_model_id invalide",
        )
    effort = manifeste.get("reasoning_effort")
    _exiger(effort is None or (isinstance(effort, str) and effort.strip()),
            "reasoning_effort invalide")
    _entier_positif(manifeste.get("max_tokens"), "execution_manifest.max_tokens")
    _exiger(manifeste.get("data_policy_requested") in {"allow", "deny"},
            "politique de données demandée invalide")
    _exiger(manifeste.get("tools") == [] and manifeste.get("agent") is None,
            "outil ou agent interdit en mode direct")
    _exiger(manifeste.get("local_environment") is None,
            "environnement local non causal interdit dans le manifeste direct")

    params = manifeste.get("request_parameters")
    _exiger(isinstance(params, dict), "request_parameters absent")
    _exiger(not ({"model", "messages", "max_tokens"} & set(params)),
            "model, messages et max_tokens doivent rester hors request_parameters")
    provider = params.get("provider")
    _exiger(
        isinstance(provider, dict)
        and set(provider) == {"only", "allow_fallbacks", "require_parameters", "data_collection"}
        and provider.get("only") == [manifeste["provider_pinned"]]
        and provider.get("allow_fallbacks") is False
        and provider.get("require_parameters") is True
        and provider.get("data_collection") == manifeste["data_policy_requested"],
        "paramètres provider différents du pin ou de la politique demandée",
    )
    _exiger(params.get("usage") == {"include": True},
            "usage.include doit être figé à true")
    if effort is not None:
        _exiger(params.get("reasoning") == {"effort": effort},
                "effort déclaré différent du payload")
    _empreinte_contractuelle(manifeste, f"manifeste d'exécution {schema}")
    return manifeste


def construire_payload(manifeste: dict[str, Any], prompt: str) -> bytes:
    """Produire les octets exacts de la requête sortante depuis le lock"""
    valider_manifeste_execution(manifeste)
    _exiger(isinstance(prompt, str), "prompt final non textuel")
    body = {
        "model": manifeste["model_requested"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": manifeste["max_tokens"],
        **manifeste["request_parameters"],
    }
    return json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _valider_identite_base(identite: Any, manifeste: dict[str, Any], chemin: str) -> None:
    champs = {"mode", "model_requested", "backend", "provider_pinned", "reasoning_effort"}
    if manifeste.get("schema_version") == SCHEMA_EXECUTION:
        champs.add("endpoint_tag")
    _exiger(isinstance(identite, dict) and set(identite) == champs,
            f"identité de base fermée invalide dans {chemin}")
    attendu = {champ: manifeste[champ] for champ in champs}
    _exiger(identite == attendu, f"identité de base différente du manifeste dans {chemin}")


def _valider_axe_v3(
    axe: Any, index: int, runs: int, population: int, racine_depot: Path | None
) -> None:
    _exiger(isinstance(axe, dict), f"axes[{index}] invalide")
    champs = {
        "id", "kind", "verify_version", "verify_hash", "verifier_path",
        "verify_manifest", "watchdog_s", "predicates", "aggregation",
        "audit_plan",
    }
    _exiger(set(axe) == champs, f"champs fermés invalides pour axes[{index}]")
    aid = axe.get("id")
    _exiger(aid in AXES_PENTAGONE, f"axe inconnu: {aid}")
    attendu_kind = "binary" if aid in AXES_PENTAGONE[:2] else "levels"
    _exiger(axe.get("kind") == attendu_kind, f"kind invalide pour {aid}")
    _exiger(
        isinstance(axe.get("verify_version"), str)
        and re.fullmatch(r"verify-v[1-9][0-9]*", axe["verify_version"]) is not None,
        f"version du vérificateur invalide pour {aid}",
    )
    _sha(axe.get("verify_hash"), f"axes[{index}].verify_hash")
    chemin_verifier = chemin_relatif_sur(
        axe.get("verifier_path"), f"axes[{index}].verifier_path"
    )
    _entier_positif(axe.get("watchdog_s"), f"axes[{index}].watchdog_s")
    predicats = axe.get("predicates")
    catalogue = predicats_pour_verificateur(axe["verify_version"])
    _exiger(isinstance(predicats, list) and tuple(predicats) == catalogue[aid],
            f"prédicats différents du contrat pour {aid}")
    _exiger(axe.get("aggregation") == {"runs": runs, "order_statistic": 4},
            f"agrégation v2 différente pour {aid}")
    plan_audit = axe.get("audit_plan")
    champs_audit = {
        "classes_and_boundaries", "anomalies_and_causes",
        "blind_selection_method", "sample_size", "sample_size_justification",
        "allowed_conclusion",
    }
    _exiger(isinstance(plan_audit, dict) and set(plan_audit) == champs_audit,
            f"plan d'audit fermé absent pour {aid}")
    for champ in ("classes_and_boundaries", "anomalies_and_causes"):
        valeurs = plan_audit.get(champ)
        _exiger(isinstance(valeurs, list) and valeurs
                and all(isinstance(v, str) and v.strip() for v in valeurs),
                f"{champ} invalide pour {aid}")
    for champ in (
        "blind_selection_method", "sample_size_justification", "allowed_conclusion"
    ):
        _exiger(isinstance(plan_audit.get(champ), str) and plan_audit[champ].strip(),
                f"{champ} absent pour {aid}")
    taille = _entier_positif(plan_audit.get("sample_size"), f"sample_size {aid}")
    _exiger(taille <= population, f"échantillon d'audit supérieur à la population pour {aid}")
    manifeste = axe.get("verify_manifest")
    _exiger(isinstance(manifeste, dict), f"verify_manifest absent pour {aid}")
    _exiger(_empreinte_contractuelle(manifeste, f"verify_manifest {aid}") == axe["verify_hash"],
            f"verify_hash incohérent pour {aid}")
    _exiger(
        manifeste.get("schema_version") == "benchmark-lab-x/verifier-manifest/v2"
        and manifeste.get("card_id") == aid
        and manifeste.get("verify_version") == axe["verify_version"]
        and manifeste.get("predicates") == predicats,
        f"manifeste du vérificateur incohérent pour {aid}",
    )
    assets = manifeste.get("assets")
    _exiger(isinstance(assets, list) and assets, f"actifs juge absents pour {aid}")
    chemins: list[str] = []
    for j, asset in enumerate(assets):
        _exiger(isinstance(asset, dict) and set(asset) == {"path", "sha256", "bytes"},
                f"actif invalide pour {aid}[{j}]")
        path_rel = chemin_relatif_sur(asset.get("path"), f"{aid}.assets[{j}].path")
        chemins.append(path_rel)
        _sha(asset.get("sha256"), f"{aid}.assets[{j}].sha256")
        _entier_positif(asset.get("bytes"), f"{aid}.assets[{j}].bytes", zero=True)
        if racine_depot is not None:
            path = resoudre_sous(racine_depot, path_rel)
            _exiger(path.is_file() and not path.is_symlink(),
                    f"actif juge absent ou lié: {path_rel}")
            data = path.read_bytes()
            _exiger(len(data) == asset["bytes"] and sha256_octets(data) == asset["sha256"],
                    f"actif juge modifié: {path_rel}")
    _exiger(chemins == sorted(set(chemins)), f"actifs non triés ou dupliqués pour {aid}")
    _exiger(chemin_verifier in chemins, f"vérificateur principal absent pour {aid}")


def valider_lock(lock: dict[str, Any], racine_depot: Path | None = None) -> dict[str, Any]:
    """Valider les locks actifs sans accepter un lock historique v2"""
    schema_lock = lock.get("schema_version") if isinstance(lock, dict) else None
    cible_v6 = schema_lock == SCHEMA_LOCK_CONTINUATION
    cible_continuation = schema_lock in {
        SCHEMA_LOCK_CONTINUATION_V5, SCHEMA_LOCK_CONTINUATION,
    }
    champs_lock = {
        "schema_version", "protocol_version", "campaign_id", "operation",
        "question", "created_at", "paid_authorization_required",
        "repository_source", "environments", "panel", "runs", "attempts_max",
        "runner", "quotas", "selection_policy", "task", "axes", "collections",
        "budget", "registry_source", "route_snapshot_source",
    }
    if cible_continuation:
        champs_lock |= {"instrument_source", "series_source"}
    if cible_v6:
        champs_lock.add("failure_scope_policy")
    _exiger(isinstance(lock, dict) and set(lock) == champs_lock,
            "champs du campaign-lock différents du contrat fermé")
    _exiger(schema_lock in {
        SCHEMA_LOCK_V3, SCHEMA_LOCK,
        SCHEMA_LOCK_CONTINUATION_V5, SCHEMA_LOCK_CONTINUATION,
    }, "campaign-lock/v3, v4, v5 ou v6 absent")
    cible_route_v3 = schema_lock in {
        SCHEMA_LOCK, SCHEMA_LOCK_CONTINUATION_V5, SCHEMA_LOCK_CONTINUATION,
    }
    _exiger(lock.get("protocol_version") == PROTOCOLE_VERSION, "protocole v2 absent")
    _exiger(lock.get("operation") in {
        "renotation", "reproduction", "new_collection", "longitudinal_comparison",
        "continuation_collection",
    }, "opération de campagne invalide")
    _exiger(
        lock["operation"]
        == ("continuation_collection" if cible_continuation else "new_collection"),
        "opération différente du schéma de lock",
    )
    if cible_v6:
        politique = lock.get("failure_scope_policy")
        _exiger(
            isinstance(politique, dict)
            and politique == {"version": POLITIQUE_PORTEE_ECHEC},
            "politique de portée des échecs absente ou différente",
        )
    for champ in ("campaign_id", "question", "created_at"):
        _exiger(isinstance(lock.get(champ), str) and lock[champ].strip(), f"{champ} absent")
    _exiger(lock.get("paid_authorization_required") is True,
            "autorisation payante séparée obligatoire")

    source = lock.get("repository_source")
    _exiger(isinstance(source, dict) and set(source) == {"commit"},
            "commit source absent ou ambigu")
    _git_oid(source.get("commit"), "repository_source.commit")
    environnements = lock.get("environments")
    _exiger(isinstance(environnements, dict) and set(environnements) == {"runner", "measurement"},
            "environnements runner et measurement requis")
    for role in ("runner", "measurement"):
        entree = environnements[role]
        _exiger(isinstance(entree, dict) and set(entree) == {"descriptor", "sha256"},
                f"environnement {role} invalide")
        descripteur = valider_descripteur_environnement(entree.get("descriptor"), role)
        _sha(entree.get("sha256"), f"environments.{role}.sha256")
        _exiger(_empreinte_contractuelle(descripteur, role) == entree["sha256"],
                f"empreinte de l'environnement {role} invalide")

    panel = lock.get("panel")
    _exiger(isinstance(panel, list) and panel
            and all(isinstance(alias, str) and alias for alias in panel), "panel invalide")
    _exiger(len(panel) == len(set(panel)), "alias dupliqué dans le panel")
    runs = _entier_positif(lock.get("runs"), "runs")
    _exiger(runs == 6, "pentagone-rotatif exige le plan v2 à six runs")
    _exiger(lock.get("attempts_max") == 3, "protocol/v2 exige trois tentatives maximum")
    runner = lock.get("runner")
    _exiger(isinstance(runner, dict)
            and set(runner) == {"concurrency", "transport_timeout_s"}, "runner invalide")
    concurrence = _entier_positif(runner.get("concurrency"), "runner.concurrency")
    _entier_positif(runner.get("transport_timeout_s"), "runner.transport_timeout_s")

    quotas = lock.get("quotas")
    _exiger(isinstance(quotas, dict) and set(quotas) == {
        "attempts_total_max", "in_flight_by_backend", "in_flight_by_provider"
    }, "quotas absents ou ambigus")
    total_tentatives = _entier_positif(quotas.get("attempts_total_max"),
                                      "quotas.attempts_total_max")
    _exiger(total_tentatives <= len(panel) * runs * lock["attempts_max"],
            "quota de tentatives supérieur au maximum du protocole")
    for champ in ("in_flight_by_backend", "in_flight_by_provider"):
        table = quotas.get(champ)
        _exiger(isinstance(table, dict) and table, f"quotas.{champ} absent")
        for cle, valeur in table.items():
            _exiger(isinstance(cle, str) and cle, f"clé invalide dans quotas.{champ}")
            _entier_positif(valeur, f"quotas.{champ}.{cle}")

    selection = lock.get("selection_policy")
    _exiger(isinstance(selection, dict) and set(selection) == {"version"}
            and isinstance(selection.get("version"), str) and selection["version"],
            "politique de sélection absente")
    budget = lock.get("budget")
    _exiger(isinstance(budget, dict) and set(budget) == {
        "currency", "cap_microdollars", "estimate_microdollars", "estimate_source"
    }, "budget fermé invalide")
    _exiger(budget.get("currency") == "USD", "devise différente de USD")
    cap = _entier_positif(budget.get("cap_microdollars"), "budget.cap_microdollars")
    estimation = _entier_positif(
        budget.get("estimate_microdollars"), "budget.estimate_microdollars"
    )
    _exiger(estimation <= cap, "estimation supérieure au plafond")
    _exiger(isinstance(budget.get("estimate_source"), str) and budget["estimate_source"],
            "source de l'estimation absente")

    registre = lock.get("registry_source")
    _exiger(isinstance(registre, dict) and set(registre) == {"path", "sha256"},
            "source du registre invalide")
    registry_path = chemin_relatif_sur(registre.get("path"), "registry_source.path")
    _sha(registre.get("sha256"), "registry_source.sha256")
    route_source = lock.get("route_snapshot_source")
    champs_route_source = {
        "path", "sha256", "schema_version", "criterion_version", "observed_at"
    }
    if cible_route_v3:
        champs_route_source |= {
            "budget_estimate_microdollars", "budget_cap_microdollars",
            "b0_09_approval_sha256", "b0_09_proposal_snapshot_sha256",
        }
    _exiger(isinstance(route_source, dict) and set(route_source) == champs_route_source,
            "source du snapshot de routes invalide")
    route_path = chemin_relatif_sur(route_source.get("path"), "route_snapshot_source.path")
    _sha(route_source.get("sha256"), "route_snapshot_source.sha256")
    schema_snapshot = (
        "benchmark-lab-x/route-preflight-snapshot/v3"
        if cible_route_v3
        else "benchmark-lab-x/route-preflight-snapshot/v2"
    )
    _exiger(route_source.get("schema_version") == schema_snapshot,
            f"snapshot de routes requis: {schema_snapshot}")
    _exiger(route_source.get("criterion_version") == selection["version"],
            "critère de route différent de la politique de sélection")
    _exiger(
        selection["version"]
        == ("benchmark-lab-x/selection-route/v3" if cible_route_v3
            else "benchmark-lab-x/selection-route/v2"),
        "version du critère incompatible avec le lock",
    )
    _exiger(isinstance(route_source.get("observed_at"), str) and route_source["observed_at"],
            "date du snapshot absente")
    if cible_route_v3:
        if not cible_continuation:
            _exiger(
                route_source.get("budget_estimate_microdollars") == estimation
                and route_source.get("budget_cap_microdollars") == cap,
                "budget du snapshot différent du lock",
            )
        _exiger(
            isinstance(route_source.get("budget_estimate_microdollars"), int)
            and isinstance(route_source.get("budget_cap_microdollars"), int),
            "budget du snapshot absent",
        )
        _sha(route_source.get("b0_09_approval_sha256"),
             "route_snapshot_source.b0_09_approval_sha256")
        _sha(route_source.get("b0_09_proposal_snapshot_sha256"),
             "route_snapshot_source.b0_09_proposal_snapshot_sha256")

    task = lock.get("task")
    _exiger(isinstance(task, dict) and set(task) == {
        "task_id", "task_version", "task_dir", "task_file", "task_tree",
        "prompt_sha256", "confidentiality_regime"
    }, "contrat de carte invalide")
    _exiger(isinstance(task.get("task_id"), str) and task["task_id"], "task_id absent")
    _exiger(isinstance(task.get("task_version"), str)
            and re.fullmatch(r"task-v[1-9][0-9]*", task["task_version"]),
            "task_version invalide")
    _sha(task.get("prompt_sha256"), "task.prompt_sha256")
    _exiger(task.get("confidentiality_regime") in {"expose", "retenu"},
            "régime de confidentialité de la carte invalide")

    axes = lock.get("axes")
    _exiger(isinstance(axes, list) and len(axes) == len(AXES_PENTAGONE),
            "cinq axes sont requis pour la carte pentagone-rotatif")
    for index, axe in enumerate(axes):
        _valider_axe_v3(
            axe, index, runs, len(panel) * runs,
            None if cible_continuation else racine_depot,
        )
    _exiger(tuple(axe["id"] for axe in axes) == AXES_PENTAGONE,
            "ordre des axes différent du contrat")
    version_attendue = {"task-v3": "verify-v5", "task-v4": "verify-v6"}.get(
        task["task_version"]
    )
    _exiger(
        version_attendue is not None
        and all(axe["verify_version"] == version_attendue for axe in axes),
        "couple task/verify différent des instruments versionnés",
    )

    snapshot_routes: dict[str, Any] | None = None
    prompt: str | None = None
    if racine_depot is not None:
        if not cible_continuation:
            registry_file = resoudre_sous(racine_depot, registry_path)
            _exiger(
                registry_file.is_file()
                and sha256_fichier(registry_file) == registre["sha256"],
                "registre verrouillé absent ou modifié",
            )
        snapshot_file = resoudre_sous(racine_depot, route_path)
        _exiger(snapshot_file.is_file() and not snapshot_file.is_symlink(),
                "snapshot de routes absent ou lié")
        snapshot_data = snapshot_file.read_bytes()
        _exiger(sha256_octets(snapshot_data) == route_source["sha256"],
                "snapshot de routes modifié")
        try:
            snapshot = json.loads(snapshot_data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContratV2Invalide("snapshot de routes illisible") from exc
        snapshot_panel = snapshot.get("panel") if isinstance(snapshot, dict) else None
        panel_conforme = (
            isinstance(snapshot_panel, list)
            and (
                set(panel) <= set(snapshot_panel)
                if cible_continuation else snapshot_panel == panel
            )
        )
        _exiger(isinstance(snapshot, dict)
                and snapshot.get("schema_version") == route_source["schema_version"]
                and snapshot.get("criterion_version") == route_source["criterion_version"]
                and snapshot.get("observed_at") == route_source["observed_at"]
                and panel_conforme
                and snapshot.get("models_file") == registry_path
                and snapshot.get("models_file_sha256") == registre["sha256"],
                "contexte du snapshot différent du lock")
        if cible_route_v3:
            snapshot_budget = snapshot.get("budget_reestimate")
            snapshot_approval = snapshot.get("b0_09_approval")
            proposal_source = snapshot.get("proposal_source")
            _exiger(
                snapshot.get("status") == "PREPARED_LOCAL_ONLY"
                and snapshot.get("hold_reasons") == []
                and snapshot.get("pin_changes") == []
                and isinstance(snapshot_budget, dict)
                and snapshot_budget.get("repriced_estimate_microdollars")
                == route_source["budget_estimate_microdollars"]
                and snapshot_budget.get("approved_cap_microdollars")
                == route_source["budget_cap_microdollars"]
                and isinstance(snapshot_approval, dict)
                and _empreinte_contractuelle(snapshot_approval, "approbation B0-09")
                == route_source["b0_09_approval_sha256"],
                "snapshot v3 encore en HOLD ou budget différent du lock",
            )
            _exiger(
                isinstance(proposal_source, dict)
                and set(proposal_source) == {"path", "sha256"}
                and proposal_source.get("path")
                == snapshot_approval.get("source_snapshot_path")
                and proposal_source.get("sha256")
                == snapshot_approval.get("source_snapshot_sha256")
                == route_source["b0_09_proposal_snapshot_sha256"],
                "approbation B0-09 non liée à sa proposition",
            )
            proposal_path = resoudre_sous(racine_depot, proposal_source["path"])
            _exiger(proposal_path.is_file() and not proposal_path.is_symlink(),
                    "proposition B0-09 absente ou liée")
            proposal_data = proposal_path.read_bytes()
            _exiger(sha256_octets(proposal_data) == proposal_source["sha256"],
                    "proposition B0-09 modifiée")
            try:
                proposal = json.loads(proposal_data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ContratV2Invalide("proposition B0-09 illisible") from exc
            _exiger(
                isinstance(proposal, dict)
                and proposal.get("proposal_source") is None
                and proposal.get("b0_09_approval") is None,
                "source B0-09 déjà approuvée ou invalide",
            )
            attendu_snapshot = copy.deepcopy(proposal)
            attendu_snapshot["proposal_source"] = proposal_source
            attendu_snapshot["b0_09_approval"] = snapshot_approval
            attendu_snapshot["hold_reasons"] = []
            attendu_snapshot["status"] = "PREPARED_LOCAL_ONLY"
            _exiger(attendu_snapshot == snapshot,
                    "snapshot approuvé différent de sa proposition B0-09")
        snapshot_routes = snapshot.get("resolved")
        _exiger(isinstance(snapshot_routes, dict) and set(panel) <= set(snapshot_routes),
                "routes résolues incomplètes")
        prompt, _ = assembler_prompt_verrouille(racine_depot, task)

    collections = lock.get("collections")
    _exiger(isinstance(collections, list) and len(collections) == len(panel) * runs,
            "grille de collecte incomplète")
    couples: set[tuple[str, int]] = set()
    identites: dict[str, str] = {}
    backends: set[str] = set()
    providers: set[str] = set()
    for index, cellule in enumerate(collections):
        champs_cellule = {
            "collection_id", "alias", "run", "task_version", "prompt_sha256",
            "base_identity", "route", "execution_manifest", "execution_manifest_hash",
            "payload_hash", "max_cost_microdollars",
        }
        _exiger(isinstance(cellule, dict) and set(cellule) == champs_cellule,
                f"champs fermés invalides dans collections[{index}]")
        alias = cellule.get("alias")
        run = cellule.get("run")
        cid = cellule.get("collection_id")
        _exiger(alias in panel and isinstance(run, int) and not isinstance(run, bool)
                and 1 <= run <= runs, f"alias ou run invalide dans {cid}")
        _exiger(cid == f"{alias}__r{run}", f"collection_id non canonique: {cid}")
        _exiger((alias, run) not in couples, f"collecte dupliquée: {cid}")
        couples.add((alias, run))
        _exiger(cellule.get("task_version") == task["task_version"]
                and cellule.get("prompt_sha256") == task["prompt_sha256"],
                f"contexte de tâche différent dans {cid}")

        manifeste = valider_manifeste_execution(cellule.get("execution_manifest"))
        _exiger(
            manifeste.get("schema_version")
            == (SCHEMA_EXECUTION if cible_route_v3 else SCHEMA_EXECUTION_V3),
            f"version du manifeste incompatible avec {schema_lock}",
        )
        _sha(cellule.get("execution_manifest_hash"), f"{cid}.execution_manifest_hash")
        _exiger(_empreinte_contractuelle(manifeste, f"manifeste {cid}")
                == cellule["execution_manifest_hash"],
                f"empreinte du manifeste invalide dans {cid}")
        _valider_identite_base(cellule.get("base_identity"), manifeste, cid)
        route = cellule.get("route")
        champs_route = {
            "metadata_status", "backend", "provider", "expect_provider",
            "quantization", "revision", "criterion_version", "price_source",
            "price_observed_at", "input_usd_per_million_tokens",
            "output_usd_per_million_tokens", "request_usd", "prompt_token_upper_bound",
        }
        if cible_route_v3:
            champs_route |= {"endpoint_tag", "ownership", "metadata_evidence"}
        _exiger(isinstance(route, dict) and set(route) == champs_route,
                f"route fermée invalide dans {cid}")
        _exiger(route.get("metadata_status") == "resolved", f"route non résolue dans {cid}")
        _exiger(
            route["backend"] == manifeste["backend"]
            and route["provider"] == manifeste["provider_pinned"]
            and route["expect_provider"] == manifeste["provider_expected"]
            and route["quantization"] == manifeste["quantization"]
            and route["revision"] == manifeste["revision"]
            and route["criterion_version"] == selection["version"],
            f"route différente du manifeste ou du critère dans {cid}",
        )
        if cible_route_v3:
            _exiger(route["endpoint_tag"] == manifeste["endpoint_tag"],
                    f"endpoint de pré-vol différent du manifeste dans {cid}")
            ownership = route.get("ownership")
            evidence = route.get("metadata_evidence")
            _exiger(
                isinstance(ownership, dict)
                and set(ownership) == {
                    "kind", "canonical_publisher", "provider_slug",
                    "provider_name", "endpoint_tag",
                }
                and ownership.get("provider_slug") == route["provider"]
                and ownership.get("provider_name") == route["expect_provider"]
                and ownership.get("endpoint_tag") == route["endpoint_tag"],
                f"ownership différent de la route dans {cid}",
            )
            _exiger(
                isinstance(evidence, dict)
                and set(evidence) == {"url", "observed_at", "response_sha256"}
                and evidence.get("url") == route["price_source"]
                and evidence.get("observed_at") == route["price_observed_at"],
                f"preuve de métadonnées différente de la route dans {cid}",
            )
            _sha(evidence.get("response_sha256"), f"{cid}.metadata_evidence.response_sha256")
            quantification = route["quantization"]
            if quantification.get("status") == "not_disclosed":
                _exiger(
                    ownership.get("kind") == "publisher_managed"
                    and quantification.get("publisher")
                    == ownership.get("canonical_publisher"),
                    f"not_disclosed interdit hors API éditeur dans {cid}",
                )
        _exiger(isinstance(route.get("price_source"), str) and route["price_source"]
                and isinstance(route.get("price_observed_at"), str) and route["price_observed_at"],
                f"prix non datés dans {cid}")
        max_cost = _entier_positif(
            cellule.get("max_cost_microdollars"), f"{cid}.max_cost_microdollars"
        )
        _exiger(max_cost <= cap, f"coût maximal supérieur au plafond dans {cid}")
        _exiger(_cout_max_depuis_route(route, manifeste["max_tokens"], f"{cid}.route") == max_cost,
                f"coût maximal différent des prix verrouillés dans {cid}")
        _sha(cellule.get("payload_hash"), f"{cid}.payload_hash")
        if prompt is not None:
            _exiger(sha256_octets(construire_payload(manifeste, prompt)) == cellule["payload_hash"],
                    f"payload_hash différent des octets attendus dans {cid}")
        if snapshot_routes is not None:
            attendu_route = snapshot_routes.get(alias)
            _exiger(isinstance(attendu_route, dict), f"route absente du snapshot pour {alias}")
            for champ in champs_route - {"prompt_token_upper_bound"}:
                _exiger(route.get(champ) == attendu_route.get(champ),
                        f"{champ} différent du snapshot dans {cid}")
            _exiger(attendu_route.get("max_tokens") == manifeste["max_tokens"],
                    f"max_tokens différent du snapshot dans {cid}")
        identite_hash = _empreinte_contractuelle(
            {"base_identity": cellule["base_identity"],
             "execution_manifest_hash": cellule["execution_manifest_hash"]},
            f"identité {cid}",
        )
        _exiger(alias not in identites or identites[alias] == identite_hash,
                f"configuration différente entre les runs de {alias}")
        identites[alias] = identite_hash
        backends.add(manifeste["backend"])
        providers.add(manifeste["provider_pinned"])
    _exiger(couples == {(alias, run) for alias in panel for run in range(1, runs + 1)},
            "grille de collecte incomplète")
    _exiger(set(quotas["in_flight_by_backend"]) == backends,
            "quotas backend différents des routes")
    _exiger(set(quotas["in_flight_by_provider"]) == providers,
            "quotas provider différents des routes")
    _exiger(concurrence <= sum(quotas["in_flight_by_backend"].values()),
            "concurrence supérieure aux quotas backend")
    if cible_continuation:
        _valider_sources_continuation(lock, racine_depot)
    if racine_depot is not None:
        _verifier_source_depot(lock, racine_depot)
    return lock


def empreinte_lock(lock: dict[str, Any]) -> str:
    valider_lock(lock)
    return empreinte(lock)


def valider_autorisation_payante(
    autorisation: dict[str, Any], lock_hash: str, cap_microdollars: int
) -> None:
    _exiger(autorisation.get("schema_version") == SCHEMA_PAID_AUTH,
            "autorisation payante séparée absente")
    _exiger(autorisation.get("decision") == "GO_PAID_COLLECTION",
            "B0-10 reste en HOLD")
    _exiger(autorisation.get("campaign_lock_hash") == lock_hash,
            "autorisation liée à un autre lock")
    _exiger(autorisation.get("cap_microdollars") == cap_microdollars,
            "autorisation liée à un autre plafond")
    _exiger(isinstance(autorisation.get("approved_by"), str) and autorisation["approved_by"],
            "auteur de l’autorisation absent")
    _exiger(isinstance(autorisation.get("approved_at"), str) and autorisation["approved_at"],
            "date de l’autorisation absente")


def cellule_du_lock(lock: dict[str, Any], collection_id: str) -> dict[str, Any]:
    valider_lock(lock)
    cellules = [c for c in lock["collections"] if c["collection_id"] == collection_id]
    _exiger(len(cellules) == 1, f"cellule inconnue ou dupliquée: {collection_id}")
    return cellules[0]


def decision_reprise(
    attempt: dict[str, Any],
    cellule: dict[str, Any],
    lock_hash: str,
    attempts_max: int = 3,
    failure_scope_policy: str | None = None,
) -> dict[str, str]:
    """Décision fermée, sans lire le contenu de la réponse candidate"""
    valider_recu_tentative(attempt, cellule, lock_hash)
    tentative = attempt["attempt"]
    if attempt["result"] == "COMPLETE":
        return {"action": "complete", "reason": "artefact candidat accepté"}
    if attempt["result"] == "FAILED_NON_RETRYABLE":
        if (
            failure_scope_policy == POLITIQUE_PORTEE_ECHEC
            and attempt["cause_code"] == "HTTP_NON_RETRYABLE"
            and attempt["candidate_artifact_accepted"] is False
        ):
            return {
                "action": "block_route",
                "reason": "route fournisseur indisponible",
            }
        return {"action": "hold", "reason": attempt["cause_code"]}
    if tentative >= attempts_max:
        return {"action": "infra_error", "reason": "tentatives épuisées"}
    accounting = attempt.get("cost_accounting")
    if accounting.get("status") not in {"known", "upper_bound"}:
        return {"action": "hold", "reason": "coût non opposable, réservation maximale conservée"}
    return {"action": "retry", "reason": attempt["cause_code"]}


def valider_recu_tentative(
    attempt: dict[str, Any], cellule: dict[str, Any], lock_hash: str
) -> dict[str, Any]:
    _exiger(isinstance(attempt, dict) and set(attempt) == CHAMPS_RECU_TENTATIVE,
            "champs du reçu de tentative v3 différents du contrat fermé")
    _exiger(attempt.get("schema_version") == SCHEMA_ATTEMPT,
            "attempt-receipt/v3 absent")
    _exiger(attempt.get("protocol_version") == PROTOCOLE_VERSION,
            "protocole v2 absent du reçu de tentative")
    _exiger(attempt.get("collection_id") == cellule.get("collection_id"),
            "reçu lié à une autre collecte")
    _sha(lock_hash, "campaign_lock_hash attendu")
    _exiger(attempt.get("campaign_lock_hash") == lock_hash,
            "reçu de tentative lié à un autre lock")
    tentative = _entier_positif(attempt.get("attempt"), "attempt")
    _exiger(tentative <= 3, "tentative supérieure au contrat v2")
    resultat = attempt.get("result")
    _exiger(resultat in ETATS_TENTATIVE, "état de tentative invalide")
    _exiger(attempt.get("execution_manifest_hash") == cellule.get("execution_manifest_hash"),
            "manifeste différent du lock dans le reçu de tentative")
    _exiger(attempt.get("payload_hash") == cellule.get("payload_hash"),
            "payload différent du lock dans le reçu de tentative")
    _sha(attempt.get("payload_hash"), "attempt.payload_hash")
    _exiger(isinstance(attempt.get("http_response_received"), bool),
            "statut de réponse HTTP ambigu")
    _exiger(isinstance(attempt.get("candidate_artifact_accepted"), bool),
            "statut de l'artefact candidat ambigu")
    cause = attempt.get("cause_code")
    if resultat == "COMPLETE":
        _exiger(cause is None
                and attempt["http_response_received"] is True
                and attempt["candidate_artifact_accepted"] is True,
                "tentative COMPLETE sans artefact accepté")
    elif resultat == "FAILED_RETRYABLE":
        _exiger(cause in CAUSES_REPRISE and attempt["candidate_artifact_accepted"] is False,
                "échec retryable sans cause fermée")
    else:
        _exiger(cause in CAUSES_TENTATIVE_NON_RETRYABLE,
                "échec non retryable sans cause fermée")
        _exiger(
            attempt["candidate_artifact_accepted"] is False
            or attempt["http_response_received"] is True,
            "artefact accepté sans réponse HTTP",
        )
    if cause == "TRANSPORT_NO_HTTP_RESPONSE":
        _exiger(attempt["http_response_received"] is False,
                "absence HTTP contradictoire")
    if cause in {"HTTP_429", "HTTP_503"}:
        _exiger(attempt["http_response_received"] is True,
                "réponse HTTP attendue pour 429 ou 503")
    if cause == "ROUTE_MISMATCH":
        _exiger(
            attempt["http_response_received"] is True
            and attempt["candidate_artifact_accepted"] is False,
            "identité divergente contradictoire avec l'acceptation d'un artefact",
        )
    accounting = attempt.get("cost_accounting")
    _exiger(isinstance(accounting, dict) and set(accounting) == {
        "status", "cost_microdollars", "reservation_id"
    }, "comptabilité de tentative invalide")
    _exiger(accounting.get("status") in {"known", "upper_bound", "unknown"},
            "statut de coût invalide")
    if accounting["status"] == "unknown":
        _exiger(accounting.get("cost_microdollars") is None,
                "coût inconnu ne peut porter une valeur")
    else:
        cout = _entier_positif(accounting.get("cost_microdollars"),
                               "attempt.cost_microdollars", zero=True)
        maximum = _entier_positif(
            cellule.get("max_cost_microdollars"), "cellule.max_cost_microdollars"
        )
        _exiger(cout <= maximum, "coût de tentative supérieur au maximum verrouillé")
        if accounting["status"] == "upper_bound":
            _exiger(cout == maximum, "borne de coût différente du maximum verrouillé")
    _exiger(accounting.get("reservation_id")
            == f"{cellule['collection_id']}__a{tentative}",
            "reservation_id différent de la tentative")
    _exiger(attempt.get("retry_after") is None
            or (isinstance(attempt["retry_after"], str) and attempt["retry_after"]),
            "Retry-After invalide")
    _empreinte_contractuelle(attempt, "reçu de tentative v3")
    return attempt


def _empreinte_contractuelle(objet: Any, chemin: str) -> str:
    try:
        return empreinte(objet)
    except ValueError as exc:
        raise ContratV2Invalide(f"{chemin} non canonique: {exc}") from exc


def valider_resultat_carte(
    resultat: dict[str, Any],
    card: dict[str, Any],
    *,
    champ_predicats: str = "predicats",
    champ_mesures: str = "mesures",
) -> None:
    """Recalculer la sémantique publiée d'une carte depuis ses prédicats"""
    _exiger(isinstance(resultat, dict), f"résultat invalide pour {card['id']}")
    etat = resultat.get("etat")
    _exiger(etat in {"SCORED", "UNKNOWN"}, f"état invalide pour {card['id']}")
    predicats = resultat.get(champ_predicats)
    mesures = resultat.get(champ_mesures)
    _exiger(isinstance(predicats, dict), f"prédicats absents pour {card['id']}")
    _exiger(isinstance(mesures, dict), f"mesures absentes pour {card['id']}")
    cause = resultat.get("cause_code")

    if etat == "UNKNOWN":
        _exiger(cause in CAUSES_UNKNOWN_SCORE, f"cause UNKNOWN invalide pour {card['id']}")
        _exiger(predicats == {}, f"UNKNOWN ne peut publier de prédicats pour {card['id']}")
        _exiger(resultat.get("verdict") is None, f"UNKNOWN ne peut publier de verdict pour {card['id']}")
        _exiger(resultat.get("niveau") is None, f"UNKNOWN ne peut publier de niveau pour {card['id']}")
        _exiger(resultat.get("frontiere") is None, f"UNKNOWN ne peut publier de frontière pour {card['id']}")
        return

    ordre = tuple(card["predicates"])
    _exiger(set(predicats) == set(ordre),
            f"ordre ou ensemble des prédicats différent pour {card['id']}")
    _exiger(all(isinstance(predicats[p], bool) for p in ordre),
            f"valeur de prédicat non booléenne pour {card['id']}")
    verdict_attendu = "PASS" if all(predicats.values()) else "FAIL"
    _exiger(resultat.get("verdict") == verdict_attendu,
            f"verdict incohérent avec les prédicats pour {card['id']}")

    if card["kind"] == "binary":
        _exiger(resultat.get("niveau") is None, f"niveau interdit pour la carte binaire {card['id']}")
        _exiger(resultat.get("frontiere") is None,
                f"frontière interdite pour la carte binaire {card['id']}")
    else:
        niveau_attendu = 0
        frontiere_attendue = None
        for rang, predicat in enumerate(ordre, start=1):
            if predicats[predicat] is True:
                niveau_attendu = rang
            else:
                frontiere_attendue = predicat
                break
        _exiger(resultat.get("niveau") == niveau_attendu,
                f"niveau incohérent avec les prédicats pour {card['id']}")
        _exiger(resultat.get("frontiere") == frontiere_attendue,
                f"frontière incohérente avec les prédicats pour {card['id']}")

    if verdict_attendu == "PASS":
        _exiger(cause is None, f"cause interdite sur un PASS pour {card['id']}")
    else:
        _exiger(cause in CAUSES_ECHEC_PAR_CARTE[card["id"]],
                f"cause d'échec incohérente pour {card['id']}")


def valider_diagnostic_processus_r016(observation: dict[str, Any]) -> None:
    """Valider un diagnostic de vérificateur sans interpréter son stderr"""
    diagnostic = observation.get("process_diagnostic")
    if diagnostic is None:
        return
    _exiger(
        observation.get("etat") == "UNKNOWN"
        and observation.get("cause_code") in {"VERIFY_TIMEOUT", "VERIFY_PROCESS_ERROR"},
        "diagnostic de processus R-016 interdit hors erreur de vérification",
    )
    _exiger(
        isinstance(diagnostic, dict)
        and set(diagnostic) == {
            "failure_stage", "verifier_exit_code", "stderr_redacted",
        },
        "diagnostic de processus R-016 invalide",
    )
    stage = diagnostic.get("failure_stage")
    _exiger(stage in {"spawn", "timeout", "exit", "output"},
            "phase de diagnostic R-016 invalide")
    code = diagnostic.get("verifier_exit_code")
    _exiger(code is None or (isinstance(code, int) and not isinstance(code, bool)),
            "code de sortie du vérificateur R-016 invalide")
    _exiger(isinstance(diagnostic.get("stderr_redacted"), str),
            "stderr expurgé R-016 invalide")
    if stage == "spawn":
        _exiger(code is None, "code de sortie incohérent avec la phase R-016")
    elif stage == "output":
        _exiger(code == 0, "code de sortie incohérent avec la phase R-016")
    elif stage == "exit":
        _exiger(code is not None and code != 0,
                "code de sortie incohérent avec la phase R-016")
    else:
        _exiger(code is not None,
                "code de sortie incohérent avec la phase R-016")
    _exiger(
        (observation.get("cause_code") == "VERIFY_TIMEOUT") == (stage == "timeout"),
        "cause de vérification incohérente avec la phase R-016",
    )


def valider_recu_collecte(
    collection: dict[str, Any], lock_hash: str, cellule: dict[str, Any]
) -> dict[str, Any]:
    _exiger(isinstance(collection, dict) and set(collection) == CHAMPS_RECU_COLLECTE,
            "champs du reçu de collecte v3 différents du contrat fermé")
    _exiger(collection.get("schema_version") == SCHEMA_COLLECTION,
            "collection-receipt/v3 absent")
    _exiger(collection.get("protocol_version") == PROTOCOLE_VERSION,
            "protocole v2 absent de la collecte")
    attendus = {
        "campaign_lock_hash": lock_hash,
        "collection_id": cellule["collection_id"],
        "result": "COLLECTED",
        "payload_hash": cellule["payload_hash"],
        "execution_manifest_hash": cellule["execution_manifest_hash"],
    }
    for champ, attendu in attendus.items():
        _exiger(collection.get(champ) == attendu,
                f"{champ} différent dans le reçu de collecte")
    tentative = _entier_positif(collection.get("attempt"), "collection.attempt")
    _exiger(tentative <= 3, "tentative de collecte supérieure au contrat")
    served = collection.get("served")
    _exiger(isinstance(served, dict) and set(served) == {"model", "provider"}
            and all(isinstance(served.get(k), str) and served[k] for k in served),
            "identité servie absente ou ambiguë")
    manifeste = cellule["execution_manifest"]
    normaliser = lambda valeur: re.sub(
        r"[\s_]+", "-", str(valeur).strip().lower()
    )
    _exiger(normaliser(served["model"]) == normaliser(manifeste["model_requested"]),
            "modèle servi différent du lock")
    _exiger(normaliser(served["provider"]) in {
        normaliser(manifeste["provider_pinned"]),
        normaliser(manifeste["provider_expected"]),
    }, "provider servi différent du lock")
    candidate = collection.get("candidate")
    _exiger(isinstance(candidate, dict) and set(candidate) == {
        "sha256", "bytes", "kind", "truncated"
    }, "description de l'artefact candidat invalide")
    _sha(candidate.get("sha256"), "collection.candidate.sha256")
    taille = _entier_positif(candidate.get("bytes"), "collection.candidate.bytes", zero=True)
    _exiger(candidate.get("kind") in {"content", "empty", "refusal"},
            "type d'artefact candidat inconnu")
    _exiger(isinstance(candidate.get("truncated"), bool), "signal de troncature ambigu")
    _exiger((taille == 0) == (candidate["kind"] == "empty"),
            "type empty incohérent avec la taille candidate")
    _sha(collection.get("response_json_sha256"), "collection.response_json_sha256")
    usage = collection.get("usage")
    _exiger(isinstance(usage, dict) and set(usage) == {
        "prompt_tokens", "completion_tokens", "reasoning_tokens"
    }, "usage de collecte invalide")
    for champ, valeur in usage.items():
        _exiger(valeur is None or (
            isinstance(valeur, int) and not isinstance(valeur, bool) and valeur >= 0
        ), f"collection.usage.{champ} invalide")
    accounting = collection.get("cost_accounting")
    _exiger(isinstance(accounting, dict) and set(accounting) == {
        "status", "cost_microdollars", "reservation_id"
    }, "comptabilité de collecte invalide")
    _exiger(accounting.get("status") in {"known", "upper_bound"},
            "coût de collecte non opposable")
    cout = _entier_positif(accounting.get("cost_microdollars"),
                           "collection.cost_microdollars", zero=True)
    maximum = _entier_positif(
        cellule.get("max_cost_microdollars"), "cellule.max_cost_microdollars"
    )
    _exiger(cout <= maximum, "coût de collecte supérieur au maximum verrouillé")
    if accounting["status"] == "upper_bound":
        _exiger(cout == maximum, "borne de collecte différente du maximum verrouillé")
    _exiger(accounting.get("reservation_id")
            == f"{cellule['collection_id']}__a{tentative}",
            "réservation de collecte différente de la tentative")
    _entier_positif(collection.get("duration_ns"), "collection.duration_ns", zero=True)
    _exiger(collection.get("cause_code") is None,
            "une collecte COLLECTED ne porte pas de cause d'échec")
    _empreinte_contractuelle(collection, "reçu de collecte v3")
    return collection


def valider_chaine_collecte(
    attempt: dict[str, Any],
    collection: dict[str, Any],
    lock_hash: str,
    cellule: dict[str, Any],
) -> None:
    """Lier une collecte acceptée à sa tentative terminale exacte"""
    valider_recu_tentative(attempt, cellule, lock_hash)
    valider_recu_collecte(collection, lock_hash, cellule)
    _exiger(attempt["result"] == "COMPLETE", "collecte sans tentative COMPLETE")
    _exiger(attempt["attempt"] == collection["attempt"],
            "collecte liée à une autre tentative")
    _exiger(attempt["cost_accounting"] == collection["cost_accounting"],
            "comptabilité différente entre tentative et collecte")


def valider_etat_collecte(
    etat: dict[str, Any], lock_hash: str, cellule: dict[str, Any]
) -> dict[str, Any]:
    champs = {
        "schema_version", "campaign_lock_hash", "collection_id", "state",
        "cause_code", "last_attempt",
    }
    _exiger(isinstance(etat, dict) and set(etat) == champs,
            "champs de l'état de collecte différents du contrat fermé")
    _exiger(etat.get("schema_version") == SCHEMA_COLLECTION_STATE,
            "collection-state/v1 absent")
    _exiger(etat.get("campaign_lock_hash") == lock_hash,
            "état de collecte lié à un autre lock")
    _exiger(etat.get("collection_id") == cellule.get("collection_id"),
            "état lié à une autre collecte")
    _exiger(etat.get("state") in {"INELIGIBLE", "INFRA_ERROR"},
            "état terminal de collecte invalide")
    _exiger(etat.get("cause_code") in CAUSES_COLLECTE_TERMINALE,
            "cause terminale de collecte non fermée")
    _exiger(
        (etat["state"] == "INELIGIBLE")
        == (etat["cause_code"] == "ROUTE_INELIGIBLE"),
        "cause terminale incompatible avec l'état de collecte",
    )
    tentative = etat.get("last_attempt")
    _exiger(tentative is None or (
        isinstance(tentative, int) and not isinstance(tentative, bool)
        and 1 <= tentative <= 3
    ), "dernière tentative invalide")
    _empreinte_contractuelle(etat, "état de collecte")
    return etat


def valider_recu_audit(
    receipt: dict[str, Any],
    lock_hash: str,
    axe: dict[str, Any],
    measurement_context_hash: str,
    collection_receipt_hashes: set[str],
) -> dict[str, Any]:
    champs = {
        "schema_version", "campaign_lock_hash", "axis_id", "verify_hash",
        "measurement_context_hash", "audit_plan_hash", "selection_method",
        "identity_blinded", "score_changes", "sample", "decision",
        "completed_at", "auditor_role", "conclusion",
    }
    _exiger(isinstance(receipt, dict) and set(receipt) == champs,
            "champs du reçu d'audit différents du contrat fermé")
    _exiger(receipt.get("schema_version") == SCHEMA_AUDIT,
            "axis-audit-receipt/v1 absent")
    attendus = {
        "campaign_lock_hash": lock_hash,
        "axis_id": axe["id"],
        "verify_hash": axe["verify_hash"],
        "measurement_context_hash": measurement_context_hash,
        "audit_plan_hash": _empreinte_contractuelle(
            axe["audit_plan"], f"plan d'audit {axe['id']}"
        ),
        "selection_method": axe["audit_plan"]["blind_selection_method"],
        "conclusion": axe["audit_plan"]["allowed_conclusion"],
    }
    for champ, attendu in attendus.items():
        _exiger(receipt.get(champ) == attendu, f"{champ} différent dans l'audit")
    _exiger(receipt.get("identity_blinded") is True,
            "identité du candidat visible pendant l'audit")
    _exiger(receipt.get("score_changes") == 0,
            "un audit ne modifie aucune note")
    for champ in ("completed_at", "auditor_role"):
        _exiger(isinstance(receipt.get(champ), str) and receipt[champ].strip(),
                f"{champ} absent de l'audit")
    sample = receipt.get("sample")
    _exiger(isinstance(sample, list)
            and len(sample) == axe["audit_plan"]["sample_size"],
            "taille d'échantillon différente du plan")
    vus: set[str] = set()
    conformes: list[bool] = []
    for index, unite in enumerate(sample):
        _exiger(isinstance(unite, dict) and set(unite) == {
            "collection_receipt_hash", "code_result_correct"
        }, f"unité d'audit invalide: {index}")
        recu_hash = unite.get("collection_receipt_hash")
        _sha(recu_hash, f"audit.sample[{index}].collection_receipt_hash")
        _exiger(recu_hash in collection_receipt_hashes,
                f"unité d'audit étrangère à l'axe: {index}")
        _exiger(recu_hash not in vus, f"unité d'audit dupliquée: {index}")
        vus.add(recu_hash)
        _exiger(isinstance(unite.get("code_result_correct"), bool),
                f"verdict humain ambigu: {index}")
        conformes.append(unite["code_result_correct"])
    decision = receipt.get("decision")
    _exiger(decision in {"ACCEPTED", "REJECTED"}, "décision d'audit invalide")
    _exiger((decision == "ACCEPTED") == all(conformes),
            "décision d'audit différente des observations")
    _empreinte_contractuelle(receipt, "reçu d'audit")
    return receipt


def valider_evenements_panel(
    objet: dict[str, Any], lock: dict[str, Any], lock_hash: str
) -> dict[str, Any]:
    _exiger(isinstance(objet, dict) and set(objet) == {
        "schema_version", "campaign_lock_hash", "events"
    }, "champs des événements de panel différents du contrat fermé")
    _exiger(objet.get("schema_version") == SCHEMA_PANEL_EVENTS,
            "panel-events/v1 absent")
    _exiger(objet.get("campaign_lock_hash") == lock_hash,
            "événements de panel liés à un autre lock")
    evenements = objet.get("events")
    _exiger(isinstance(evenements, list), "liste des événements de panel absente")
    vus: set[str] = set()
    for index, evenement in enumerate(evenements):
        _exiger(isinstance(evenement, dict) and set(evenement) == {
            "event", "alias", "reason", "decided_at", "decision_basis"
        }, f"événement de panel invalide: {index}")
        _exiger(evenement.get("event") == "RETIRE", f"événement inconnu: {index}")
        alias = evenement.get("alias")
        _exiger(alias in lock["panel"] and alias not in vus,
                f"alias retiré inconnu ou dupliqué: {alias}")
        vus.add(alias)
        for champ in ("reason", "decided_at"):
            _exiger(isinstance(evenement.get(champ), str) and evenement[champ].strip(),
                    f"{champ} absent de l'événement RETIRE")
        _exiger(evenement.get("decision_basis") == "independent_of_measured_result",
                "retrait non déclaré indépendant du résultat")
    _empreinte_contractuelle(objet, "événements de panel")
    return objet


def valider_hold_operateur(
    hold: dict[str, Any], lock: dict[str, Any], lock_hash: str
) -> dict[str, Any]:
    champs = {
        "schema_version", "campaign_lock_hash", "decision", "cause_code",
        "collection_id", "attempt",
    }
    _exiger(isinstance(hold, dict) and set(hold) == champs,
            "champs du HOLD opérateur différents du contrat fermé")
    _exiger(hold.get("schema_version") == SCHEMA_OPERATOR_HOLD,
            "operator-hold/v1 absent")
    _exiger(hold.get("campaign_lock_hash") == lock_hash,
            "HOLD opérateur lié à un autre lock")
    _exiger(hold.get("decision") == "HOLD", "décision opérateur différente de HOLD")
    _exiger(hold.get("cause_code") in CAUSES_HOLD_OPERATEUR,
            "cause du HOLD opérateur non fermée")
    collection_id = hold.get("collection_id")
    if collection_id is None:
        _exiger(hold.get("attempt") is None, "tentative sans collecte dans le HOLD")
    else:
        _exiger(any(c["collection_id"] == collection_id for c in lock["collections"]),
                "HOLD lié à une collecte inconnue")
        tentative = hold.get("attempt")
        _exiger(tentative is None or (
            isinstance(tentative, int) and not isinstance(tentative, bool)
            and 1 <= tentative <= 3
        ), "tentative invalide dans le HOLD")
    _empreinte_contractuelle(hold, "HOLD opérateur")
    return hold


def valider_abandon_campagne(
    abandon: dict[str, Any], hold: dict[str, Any], lock_hash: str
) -> dict[str, Any]:
    champs = {
        "schema_version", "campaign_lock_hash", "decision", "collection_id",
        "cause_code", "decided_at", "approved_by",
    }
    _exiger(isinstance(abandon, dict) and set(abandon) == champs,
            "champs de l'abandon différents du contrat fermé")
    _exiger(abandon.get("schema_version") == SCHEMA_ABANDONMENT,
            "campaign-abandonment/v1 absent")
    _exiger(abandon.get("campaign_lock_hash") == lock_hash,
            "abandon lié à un autre lock")
    _exiger(abandon.get("decision") == "ABANDON_HELD_COLLECTION",
            "décision d'abandon invalide")
    _exiger(
        hold.get("cause_code") == "ROUTE_MISMATCH"
        and abandon.get("collection_id") == hold.get("collection_id"),
        "abandon autorisé seulement pour la collecte en HOLD d'identité",
    )
    _exiger(abandon.get("cause_code") == "ABANDONED_AFTER_IDENTITY_MISMATCH",
            "cause d'abandon invalide")
    for champ in ("decided_at", "approved_by"):
        _exiger(isinstance(abandon.get(champ), str) and abandon[champ].strip(),
                f"{champ} absent de l'abandon")
    _empreinte_contractuelle(abandon, "abandon de campagne")
    return abandon


def valider_recu_score(
    score: dict[str, Any],
    lock: dict[str, Any],
    lock_hash: str,
    card: dict[str, Any],
    cellule: dict[str, Any],
    collection: dict[str, Any],
    collection_hash: str,
) -> dict[str, Any]:
    """Valider identité, contexte fermé et sémantique d'un reçu par axe"""
    _exiger(isinstance(score, dict) and set(score) == CHAMPS_RECU_SCORE,
            "champs du reçu de score v3 différents du contrat fermé")
    _exiger(score.get("schema_version") == SCHEMA_SCORE, "score-receipt/v3 absent")
    _exiger(score.get("protocol_version") == PROTOCOLE_VERSION,
            "protocole v2 absent du score")
    valider_recu_collecte(collection, lock_hash, cellule)
    _exiger(_empreinte_contractuelle(collection, "reçu de collecte") == collection_hash,
            "empreinte du reçu de collecte différente")
    _sha(collection_hash, "collection_receipt_hash")

    attendus = {
        "campaign_lock_hash": lock_hash,
        "collection_id": cellule["collection_id"],
        "collection_receipt_hash": collection_hash,
        "response_sha256": collection["candidate"]["sha256"],
        "alias": cellule["alias"],
        "run": cellule["run"],
        "axis_id": card["id"],
        "verify_version": card["verify_version"],
        "verify_hash": card["verify_hash"],
    }
    for champ, attendu in attendus.items():
        _exiger(score.get(champ) == attendu, f"{champ} différent dans le reçu de score")

    environnement = score.get("measurement_environment")
    _exiger(isinstance(environnement, dict), "environnement de mesure absent du score")
    _exiger(environnement.get("schema_version") == SCHEMA_ENVIRONMENT,
            "schéma d'environnement de mesure invalide")
    environnement_hash = _empreinte_contractuelle(environnement, "environnement de mesure")
    _sha(environnement_hash, "measurement_environment_hash")
    valider_environnement_observe(lock, "measurement", environnement)
    contexte_attendu = {
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
        "measurement_environment_hash": environnement_hash,
        "confidentiality_regime": lock["task"]["confidentiality_regime"],
    }
    contexte = score.get("measurement_context")
    _exiger(isinstance(contexte, dict) and set(contexte) == CHAMPS_CONTEXTE_MESURE
            and contexte == contexte_attendu,
            "contexte de mesure différent du lock ou de l'environnement")
    contexte_hash = _empreinte_contractuelle(contexte, "contexte de mesure")
    _sha(score.get("measurement_context_hash"), "measurement_context_hash")
    _exiger(score["measurement_context_hash"] == contexte_hash,
            "empreinte du contexte de mesure invalide")
    _exiger(score.get("etat") in {"SCORED", "UNKNOWN"},
            "un reçu de score porte seulement SCORED ou UNKNOWN")
    valider_resultat_carte(score, card)
    return score


def agreger_scores(kind: str, scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Agréger exactement six reçus, dans l’ordre des runs"""
    _exiger(kind in {"binary", "levels"}, "type de carte inconnu")
    _exiger(len(scores) == 6, "six scores sont requis")
    tries = sorted(scores, key=lambda x: x.get("run", 0))
    _exiger([s.get("run") for s in tries] == list(range(1, 7)), "runs 1 à 6 requis")
    non_scores = [s for s in tries if s.get("etat") != "SCORED"]
    if non_scores:
        return {
            "classement_valide": False,
            "blocages": [{"run": s["run"], "etat": s.get("etat"),
                           "cause_code": s.get("cause_code")} for s in non_scores],
            "distribution": [s.get("verdict") if kind == "binary" else s.get("niveau") for s in tries],
        }
    if kind == "binary":
        valeurs = [s.get("verdict") for s in tries]
        _exiger(all(v in {"PASS", "FAIL"} for v in valeurs), "verdict binaire invalide")
        pass_count = sum(v == "PASS" for v in valeurs)
        return {"classement_valide": True, "verdict_retenu": "PASS" if pass_count >= 4 else "FAIL",
                "pass_count": pass_count, "distribution": valeurs}
    niveaux = [s.get("niveau") for s in tries]
    _exiger(all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in niveaux),
            "niveau invalide")
    retenu = sorted(niveaux, reverse=True)[3]
    return {"classement_valide": True, "niveau_retenu": retenu, "distribution": niveaux,
            "libelle": "niveau franchi dans au moins quatre runs sur six"}


def valider_recu_couverture(
    receipt: dict[str, Any],
    lock: dict[str, Any],
    lock_hash: str,
    racine_depot: Path,
) -> tuple[bool, list[str]]:
    """Valider la preuve R-016 figée sans lancer Chromium"""
    motifs: list[str] = []
    try:
        _empreinte_contractuelle(receipt, "reçu R-016")
    except ContratV2Invalide as exc:
        motifs.append(str(exc))
    if receipt.get("schema_version") != SCHEMA_COVERAGE:
        motifs.append("schema de reçu R-016 invalide")
    try:
        _sha(receipt.get("campaign_lock_hash"), "lock source du reçu R-016")
    except ContratV2Invalide as exc:
        motifs.append(str(exc))
    if receipt.get("task_version") != lock.get("task", {}).get("task_version"):
        motifs.append("reçu R-016 lié à une autre tâche")
    if receipt.get("prompt_sha256") != lock.get("task", {}).get("prompt_sha256"):
        motifs.append("reçu R-016 lié à un autre prompt")
    environnement = receipt.get("measurement_environment")
    environnement_hash = receipt.get("measurement_environment_hash")
    if not isinstance(environnement, dict) or environnement.get("schema_version") != SCHEMA_ENVIRONMENT:
        motifs.append("environnement de mesure R-016 absent ou invalide")
    else:
        try:
            valider_environnement_observe(lock, "measurement", environnement)
            attendu = _empreinte_contractuelle(environnement, "environnement R-016")
            if environnement_hash != attendu:
                motifs.append("empreinte d'environnement R-016 invalide")
        except ContratV2Invalide as exc:
            motifs.append(str(exc))
    cards_receipt = receipt.get("cards")
    if not isinstance(cards_receipt, dict):
        return False, motifs + ["couverture par carte absente"]
    temoins = receipt.get("witnesses")
    if not isinstance(temoins, dict) or not temoins:
        return False, motifs + ["provenance des témoins absente"]
    observations = receipt.get("observations")
    if not isinstance(observations, dict):
        return False, motifs + ["observations des témoins absentes"]

    try:
        task_dir = resoudre_sous(
            racine_depot,
            chemin_relatif_sur(lock.get("task", {}).get("task_dir"), "task.task_dir"),
        )
    except ContratV2Invalide as exc:
        return False, motifs + [str(exc)]
    arbre = {
        entree.get("path"): entree
        for entree in lock.get("task", {}).get("task_tree", [])
        if isinstance(entree, dict)
    }
    provenance_rel = "temoins/provenance.json"
    provenance_temoins: dict[str, Any] = {}
    entree_provenance = arbre.get(provenance_rel)
    if receipt.get("provenance_path") != provenance_rel:
        motifs.append("chemin de provenance R-016 différent du contrat")
    if not isinstance(entree_provenance, dict) or entree_provenance.get("role") != "judge":
        motifs.append("provenance R-016 absente des actifs juge verrouillés")
    else:
        try:
            path_provenance = resoudre_sous(task_dir, provenance_rel)
            data_provenance = path_provenance.read_bytes()
            hash_provenance = sha256_octets(data_provenance)
            if (not path_provenance.is_file() or path_provenance.is_symlink()
                    or entree_provenance.get("sha256") != hash_provenance
                    or entree_provenance.get("bytes") != len(data_provenance)):
                raise ContratV2Invalide("provenance R-016 différente du lock")
            if receipt.get("provenance_sha256") != hash_provenance:
                raise ContratV2Invalide("empreinte de provenance R-016 différente du reçu")
            objet_provenance = json.loads(data_provenance.decode("utf-8"))
            provenance_temoins = objet_provenance.get("temoins")
            if not isinstance(provenance_temoins, dict):
                raise ContratV2Invalide("table des témoins absente de la provenance R-016")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ContratV2Invalide) as exc:
            motifs.append(str(exc))
            provenance_temoins = {}
    cartes = {axe["id"]: axe for axe in lock.get("axes", [])}
    independants = True
    attentes: dict[str, dict[str, dict[str, bool]]] = {}
    for nom, temoin in sorted(temoins.items()):
        try:
            chemin_relatif_sur(nom, f"witnesses.{nom}")
        except ContratV2Invalide as exc:
            motifs.append(str(exc))
            independants = False
            continue
        if not isinstance(temoin, dict):
            motifs.append(f"provenance invalide: {nom}")
            independants = False
            continue
        source = provenance_temoins.get(nom)
        if not isinstance(source, dict):
            motifs.append(f"provenance verrouillée absente: {nom}")
            independants = False
        else:
            correspondances = {
                "producer": source.get("producteur"),
                "access_to_verifier": source.get("acces_au_verificateur"),
                "instructions": source.get("consignes"),
                "expected_result": source.get("resultat_attendu"),
            }
            for champ, valeur in correspondances.items():
                if temoin.get(champ) != valeur:
                    motifs.append(f"{champ} différent de la provenance verrouillée: {nom}")
                    independants = False
        if temoin.get("access_to_verifier") is not False:
            motifs.append(f"producteur non aveugle: {nom}")
            independants = False
        if not isinstance(temoin.get("producer"), str) or not temoin["producer"].strip():
            motifs.append(f"producteur absent: {nom}")
            independants = False
        if not isinstance(temoin.get("instructions"), str) or not temoin["instructions"].strip():
            motifs.append(f"provenance incomplète: {nom}")
            independants = False
        try:
            temoin_hash = _sha(temoin.get("sha256"), f"witnesses.{nom}.sha256")
        except ContratV2Invalide as exc:
            motifs.append(str(exc))
            independants = False
            continue
        entree = arbre.get(nom)
        if not isinstance(entree, dict) or entree.get("role") != "judge":
            motifs.append(f"témoin absent des actifs juge verrouillés: {nom}")
            independants = False
        else:
            try:
                path = resoudre_sous(task_dir, nom)
                data = path.read_bytes()
                if not path.is_file() or path.is_symlink():
                    raise ContratV2Invalide(f"fichier témoin absent ou lié: {nom}")
                if entree.get("sha256") != temoin_hash or sha256_octets(data) != temoin_hash:
                    raise ContratV2Invalide(f"empreinte du témoin différente du lock: {nom}")
                if entree.get("bytes") != len(data):
                    raise ContratV2Invalide(f"taille du témoin différente du lock: {nom}")
            except (OSError, ContratV2Invalide) as exc:
                motifs.append(str(exc))
                independants = False
        attendu_brut = temoin.get("expected_result")
        attendu_normalise: dict[str, dict[str, bool]] = {}
        if not isinstance(attendu_brut, dict) or not attendu_brut:
            motifs.append(f"résultat attendu absent: {nom}")
            independants = False
        else:
            for cid, predicats in attendu_brut.items():
                if cid not in cartes or not isinstance(predicats, dict) or not predicats:
                    motifs.append(f"résultat attendu invalide: {nom}/{cid}")
                    independants = False
                    continue
                valides: dict[str, bool] = {}
                for predicat, valeur in predicats.items():
                    if predicat not in cartes[cid]["predicates"] or not isinstance(valeur, bool):
                        motifs.append(f"attente invalide: {nom}/{cid}/{predicat}")
                        independants = False
                    else:
                        valides[predicat] = valeur
                if valides:
                    attendu_normalise[cid] = valides
        attentes[nom] = attendu_normalise

    if set(observations) != set(temoins):
        motifs.append("ensemble des observations différent des témoins")
    couverture_calculee: dict[str, dict[str, dict[str, list[str]]]] = {
        cid: {p: {"positive": [], "negative": []} for p in card["predicates"]}
        for cid, card in cartes.items()
    }
    attentes_conformes = True
    for nom in sorted(temoins):
        par_carte = observations.get(nom)
        if not isinstance(par_carte, dict) or set(par_carte) != set(cartes):
            motifs.append(f"observations de cartes incomplètes: {nom}")
            attentes_conformes = False
            continue
        for cid, card in cartes.items():
            observation = par_carte[cid]
            if not isinstance(observation, dict):
                motifs.append(f"observation invalide: {nom}/{cid}")
                attentes_conformes = False
                continue
            liens = {
                "score_card_id": cid,
                "witness_sha256": temoins[nom].get("sha256") if isinstance(temoins[nom], dict) else None,
                "verify_hash": card["verify_hash"],
                "measurement_environment_hash": environnement_hash,
            }
            for champ, attendu in liens.items():
                if observation.get(champ) != attendu:
                    motifs.append(f"{champ} différent: {nom}/{cid}")
                    attentes_conformes = False
            try:
                valider_resultat_carte(
                    observation, card,
                    champ_predicats="predicates", champ_mesures="measurements",
                )
                valider_diagnostic_processus_r016(observation)
            except ContratV2Invalide as exc:
                motifs.append(f"{nom}/{cid}: {exc}")
                attentes_conformes = False
                continue
            observes = observation["predicates"] if observation["etat"] == "SCORED" else {}
            for predicat, valeur_attendue in attentes.get(nom, {}).get(cid, {}).items():
                if observes.get(predicat) is not valeur_attendue:
                    motifs.append(f"attente non confirmée: {nom}/{cid}/{predicat}")
                    attentes_conformes = False
                    continue
                polarite = "positive" if valeur_attendue else "negative"
                couverture_calculee[cid][predicat][polarite].append(nom)

    complete = True
    if set(cards_receipt) != set(cartes):
        motifs.append("ensemble des cartes de couverture différent du lock")
    for card in lock.get("axes", []):
        cid = card["id"]
        bloc = cards_receipt.get(cid)
        if not isinstance(bloc, dict):
            motifs.append(f"couverture absente: {cid}")
            complete = False
            continue
        if bloc.get("verify_hash") != card["verify_hash"]:
            motifs.append(f"verify_hash différent: {cid}")
        couverture = bloc.get("predicates")
        if not isinstance(couverture, dict):
            motifs.append(f"prédicats absents: {cid}")
            continue
        if set(couverture) != set(card["predicates"]):
            motifs.append(f"ensemble de prédicats différent: {cid}")
            complete = False
            continue
        for predicat in card["predicates"]:
            preuve = couverture[predicat]
            if not isinstance(preuve, dict):
                motifs.append(f"preuve invalide: {cid}/{predicat}")
                continue
            for polarite in ("positive", "negative"):
                noms = preuve.get(polarite)
                if not isinstance(noms, list) or not noms:
                    motifs.append(f"témoin {polarite} absent: {cid}/{predicat}")
                    complete = False
                    continue
                calcules = couverture_calculee[cid][predicat][polarite]
                if noms != calcules:
                    motifs.append(f"couverture déclarée différente des observations: {cid}/{predicat}/{polarite}")
                    complete = False
            positifs = preuve.get("positive") if isinstance(preuve.get("positive"), list) else []
            negatifs = preuve.get("negative") if isinstance(preuve.get("negative"), list) else []
            if set(positifs) & set(negatifs):
                motifs.append(f"même témoin positif et négatif: {cid}/{predicat}")
                complete = False
    qualifie_calcule = independants and attentes_conformes and complete
    if receipt.get("qualified") is not qualifie_calcule:
        motifs.append("drapeau qualified différent de la preuve recalculée")
    return qualifie_calcule and not motifs, motifs


class RegistreBudget:
    """Registre atomique engagé plus réservé en microdollars"""

    def __init__(self, path: Path, cap_microdollars: int, lock_hash: str):
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.cap = _entier_positif(cap_microdollars, "cap_microdollars")
        self.lock_hash = _sha(lock_hash, "campaign_lock_hash")

    def _initial(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_LEDGER,
            "campaign_lock_hash": self.lock_hash,
            "currency": "USD",
            "cap_microdollars": self.cap,
            "engaged_microdollars": 0,
            "reservations": {},
            "hold": False,
            "hold_reasons": [],
        }

    def _charger(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._initial()
        state = charger_json(self.path)
        _exiger(state.get("schema_version") == SCHEMA_LEDGER, "schema du registre budget invalide")
        _exiger(state.get("campaign_lock_hash") == self.lock_hash, "registre lié à un autre lock")
        _exiger(state.get("currency") == "USD", "devise du registre budget invalide")
        _exiger(state.get("cap_microdollars") == self.cap, "plafond du registre modifié")
        engage = _entier_positif(
            state.get("engaged_microdollars"), "engaged_microdollars", zero=True
        )
        reservations = state.get("reservations")
        _exiger(isinstance(reservations, dict), "réservations du registre invalides")
        finalises = 0
        reserves = 0
        for identifiant, entree in reservations.items():
            _exiger(isinstance(identifiant, str) and identifiant,
                    "identifiant de réservation invalide")
            _exiger(isinstance(entree, dict), f"réservation invalide: {identifiant}")
            status = entree.get("status")
            _exiger(status in {"reserved", "unknown", "finalized"},
                    f"statut de réservation invalide: {identifiant}")
            maximum = _entier_positif(
                entree.get("max_microdollars"), f"{identifiant}.max_microdollars"
            )
            _exiger(isinstance(entree.get("created_at"), str) and entree["created_at"],
                    f"date de réservation absente: {identifiant}")
            if status == "finalized":
                cout = _entier_positif(
                    entree.get("cost_microdollars"), f"{identifiant}.cost_microdollars", zero=True
                )
                _exiger(cout <= maximum, f"coût supérieur au maximum: {identifiant}")
                _exiger(isinstance(entree.get("finalized_at"), str) and entree["finalized_at"],
                        f"date de finalisation absente: {identifiant}")
                finalises += cout
            else:
                _exiger(entree.get("cost_microdollars") is None,
                        f"coût prématuré sur une réservation active: {identifiant}")
                reserves += maximum
        _exiger(engage == finalises, "engagé différent de la somme des réservations finalisées")
        _exiger(engage + reserves <= self.cap, "engagé plus réservé dépasse le plafond")
        _exiger(isinstance(state.get("hold"), bool), "indicateur HOLD du registre invalide")
        raisons = state.get("hold_reasons")
        _exiger(isinstance(raisons, list) and all(isinstance(x, str) for x in raisons),
                "motifs HOLD du registre invalides")
        _exiger(state["hold"] is bool(raisons),
                "indicateur HOLD incohérent avec ses motifs")
        _exiger(not any(r["status"] == "unknown" for r in reservations.values()) or state["hold"],
                "coût inconnu sans HOLD")
        return state

    def _ecrire(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
        os.replace(tmp, self.path)

    def _transaction(self, operation):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as verrou:
            fcntl.flock(verrou.fileno(), fcntl.LOCK_EX)
            state = self._charger()
            resultat = operation(state)
            self._ecrire(state)
            fcntl.flock(verrou.fileno(), fcntl.LOCK_UN)
            return resultat

    @staticmethod
    def _reserve_total(state: dict[str, Any]) -> int:
        return sum(r["max_microdollars"] for r in state["reservations"].values()
                   if r["status"] in {"reserved", "unknown"})

    def reserver(self, reservation_id: str, max_microdollars: int) -> dict[str, Any]:
        maximum = _entier_positif(max_microdollars, "max_microdollars")
        _exiger(isinstance(reservation_id, str) and reservation_id, "reservation_id absent")
        def operation(state):
            if state.get("hold"):
                raise PlafondDepasse("registre en HOLD")
            existante = state["reservations"].get(reservation_id)
            if existante:
                _exiger(existante["max_microdollars"] == maximum,
                        "réservation existante avec un autre maximum")
                return dict(existante)
            total = state["engaged_microdollars"] + self._reserve_total(state) + maximum
            if total > self.cap:
                raise PlafondDepasse(f"réservation refusée: {total} > {self.cap} microdollars")
            entree = {"status": "reserved", "max_microdollars": maximum,
                      "created_at": datetime.now(timezone.utc).isoformat()}
            state["reservations"][reservation_id] = entree
            return dict(entree)
        return self._transaction(operation)

    def finaliser(self, reservation_id: str, cost_microdollars: int | None) -> dict[str, Any]:
        def operation(state):
            entree = state["reservations"].get(reservation_id)
            _exiger(isinstance(entree, dict), f"réservation inconnue: {reservation_id}")
            if entree["status"] == "finalized":
                _exiger(cost_microdollars == entree["cost_microdollars"],
                        "coût finalisé différent lors d'un nouvel appel")
                return dict(entree)
            if entree["status"] == "unknown":
                _exiger(cost_microdollars is None,
                        "une télémétrie inconnue ne peut pas être réécrite")
                return dict(entree)
            maximum = entree["max_microdollars"]
            if cost_microdollars is None:
                entree["status"] = "unknown"
                state["hold"] = True
                raison = f"coût inconnu pour {reservation_id}, maximum conservé"
                if raison not in state["hold_reasons"]:
                    state["hold_reasons"].append(raison)
                return dict(entree)
            cout = _entier_positif(cost_microdollars, "cost_microdollars", zero=True)
            if cout > maximum:
                entree["status"] = "unknown"
                state["hold"] = True
                raison = f"coût {cout} supérieur à la réservation {maximum} pour {reservation_id}"
                if raison not in state["hold_reasons"]:
                    state["hold_reasons"].append(raison)
                return dict(entree)
            entree["status"] = "finalized"
            entree["cost_microdollars"] = cout
            entree["finalized_at"] = datetime.now(timezone.utc).isoformat()
            state["engaged_microdollars"] += cout
            return dict(entree)
        return self._transaction(operation)

    def etat(self) -> dict[str, Any]:
        return self._transaction(lambda state: dict(state))
