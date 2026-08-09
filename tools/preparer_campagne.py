# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Construire hors ligne un campaign.lock v3 autoritaire

Le brouillon TOML doit déjà contenir les métadonnées de route, les prix
maximaux et leurs sources. Cet outil ne les cherche jamais sur le réseau. Une
valeur absente ou non résolue produit un HOLD avant toute tentative

Usage:
    uv run tools/preparer_campagne.py campaign-v3.toml --out campaign.lock.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from empreintes import empreinte  # noqa: E402
from moteur_rendu import descripteur as descripteur_mesure  # noqa: E402
from protocole_v2 import (  # noqa: E402
    AXES_PENTAGONE,
    CARDS_V4,
    ESTIMATION_B0_HISTORIQUE,
    PANEL_B0,
    PLAFOND_B0_HISTORIQUE,
    PREDICATS_V4,
    PREDICATS_V5,
    PROTOCOLE_VERSION,
    SCHEMA_EXECUTION,
    SCHEMA_EXECUTION_V3,
    SCHEMA_LOCK,
    SCHEMA_LOCK_HISTORIQUE,
    SCHEMA_LOCK_V3,
    ContratV2Invalide,
    assembler_prompt_verrouille,
    chemin_relatif_sur,
    construire_payload,
    descripteur_environnement_runner,
    ecrire_json_immuable,
    resoudre_sous,
    sha256_fichier,
    valider_lock,
)
from figer_routes_precollecte import (  # noqa: E402
    SnapshotRoutesInvalide,
    valider_cible,
    valider_cible_historique_v2,
)


def _charger_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ContratV2Invalide(f"brouillon TOML illisible: {exc}") from exc


def _role_fichier(relatif: str, task_file: str, visible_inputs: set[str]) -> str:
    if relatif == task_file:
        return "instructions"
    if relatif in visible_inputs:
        return "input"
    if relatif == "task.md":
        return "historical"
    if relatif.startswith("anchor-") or relatif.startswith("temoins/"):
        return "judge"
    if relatif in {"oracle-cache.json"}:
        return "judge"
    return "control"


def _arbre_tache(task_dir: Path, task_file: str, visible_inputs: list[str]) -> list[dict[str, Any]]:
    visibles = set(visible_inputs)
    fichiers: list[dict[str, Any]] = []
    for path in sorted(task_dir.rglob("*")):
        if path.is_symlink():
            raise ContratV2Invalide(f"lien symbolique interdit dans la tâche: {path}")
        if not path.is_file():
            continue
        relatif = path.relative_to(task_dir).as_posix()
        data = path.read_bytes()
        fichiers.append({
            "path": relatif,
            "sha256": sha256_fichier(path),
            "bytes": len(data),
            "role": _role_fichier(relatif, task_file, visibles),
        })
    roles_instructions = [f for f in fichiers if f["role"] == "instructions"]
    roles_inputs = [f for f in fichiers if f["role"] == "input"]
    if len(roles_instructions) != 1:
        raise ContratV2Invalide("une source d’instructions exacte est requise")
    if {f["path"] for f in roles_inputs} != visibles:
        raise ContratV2Invalide("un fichier visible déclaré est absent de la tâche")
    return fichiers


def _manifeste_verificateur(
    card_id: str,
    assets: list[str],
    verify_version: str = "verify-v5",
    predicates: dict[str, tuple[str, ...]] = PREDICATS_V4,
) -> dict[str, Any]:
    if len(assets) != len(set(assets)):
        raise ContratV2Invalide("actif du vérificateur dupliqué")
    lignes = []
    for relatif in sorted(assets):
        path = resoudre_sous(RACINE, relatif)
        if not path.is_file():
            raise ContratV2Invalide(f"actif du vérificateur absent: {relatif}")
        lignes.append({"path": relatif, "sha256": sha256_fichier(path), "bytes": path.stat().st_size})
    return {
        "schema_version": "benchmark-lab-x/verifier-manifest/v2",
        "card_id": card_id,
        "verify_version": verify_version,
        "predicates": list(predicates[card_id]),
        "assets": lignes,
    }


def _actifs_calibrage(task_dir_rel: str) -> list[str]:
    task_dir = resoudre_sous(RACINE, task_dir_rel)
    provenance_rel = "temoins/provenance.json"
    provenance_path = resoudre_sous(task_dir, provenance_rel)
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContratV2Invalide("provenance R-016 illisible") from exc
    qualification = provenance.get("qualification_set")
    if (
        not isinstance(qualification, list)
        or not qualification
        or len(qualification) != len(set(qualification))
    ):
        raise ContratV2Invalide("qualification_set R-016 absente ou invalide")
    actifs = [f"{task_dir_rel}/{provenance_rel}"]
    for i, nom in enumerate(qualification):
        relatif = chemin_relatif_sur(nom, f"qualification_set[{i}]")
        if Path(relatif).parts[0] != "temoins" or Path(relatif).suffix != ".md":
            raise ContratV2Invalide(f"témoin qualifiant hors de temoins/: {relatif}")
        path = resoudre_sous(task_dir, relatif)
        if not path.is_file() or path.is_symlink():
            raise ContratV2Invalide(f"témoin qualifiant absent ou lié: {relatif}")
        actifs.append(f"{task_dir_rel}/{relatif}")
    return actifs


def _charger_snapshot_routes_historique_v1(
    draft: dict[str, Any], panel: list[str], models_file: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    relatif = chemin_relatif_sur(
        draft.get("route_snapshot_file"), "route_snapshot_file"
    )
    attendu = draft.get("route_snapshot_sha256")
    if (
        not isinstance(attendu, str)
        or len(attendu) != 64
        or any(c not in "0123456789abcdef" for c in attendu)
    ):
        raise ContratV2Invalide("route_snapshot_sha256 invalide")
    path = resoudre_sous(RACINE, relatif)
    if not path.is_file() or path.is_symlink():
        raise ContratV2Invalide("snapshot de routes absent ou lié")
    if sha256_fichier(path) != attendu:
        raise ContratV2Invalide("snapshot de routes différent de son empreinte")
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContratV2Invalide("snapshot de routes illisible") from exc
    if snapshot.get("schema_version") != "benchmark-lab-x/route-preflight-snapshot/v1":
        raise ContratV2Invalide("schéma du snapshot de routes invalide")
    if snapshot.get("panel") != panel:
        raise ContratV2Invalide("panel du snapshot de routes différent de B0-06")
    if snapshot.get("criterion_version") != "benchmark-lab-x/selection-route/v2":
        raise ContratV2Invalide("critère du snapshot de routes invalide")
    budget = snapshot.get("budget_reestimate")
    if not isinstance(budget, dict):
        raise ContratV2Invalide("recalcul B0-09 absent du snapshot de routes")
    if budget.get("status") != "B0_09_UNCHANGED":
        raise ContratV2Invalide("B0-09 exige une nouvelle approbation")
    if (
        budget.get("approved_estimate_microdollars")
        != draft.get("estimate_microdollars")
        or budget.get("repriced_estimate_microdollars")
        != draft.get("estimate_microdollars")
        or budget.get("approved_cap_microdollars") != draft.get("cap_microdollars")
    ):
        raise ContratV2Invalide("budget du snapshot différent de B0-09 approuvé")
    approbation = snapshot.get("b0_09_approval")
    if (
        not isinstance(approbation, dict)
        or approbation.get("schema_version")
        != "benchmark-lab-x/b0-09-approval/v1"
        or approbation.get("decision") != "B0_09_REVISED_ESTIMATE_APPROVED"
        or approbation.get("approved_by") != "Ayo"
        or not isinstance(approbation.get("approved_at"), str)
        or not approbation["approved_at"]
        or approbation.get("estimate_microdollars") != draft.get("estimate_microdollars")
        or approbation.get("cap_microdollars") != draft.get("cap_microdollars")
    ):
        raise ContratV2Invalide("approbation B0-09 absente ou différente du brouillon")
    models_rel = models_file.relative_to(RACINE).as_posix()
    if (
        snapshot.get("models_file") != models_rel
        or snapshot.get("models_file_sha256") != sha256_fichier(models_file)
    ):
        raise ContratV2Invalide("registre du snapshot différent du registre verrouillé")
    resolved = snapshot.get("resolved")
    if not isinstance(resolved, dict) or set(resolved) != set(panel):
        raise ContratV2Invalide("résolution du panel absente du snapshot")
    if draft.get("resolved") not in (None, resolved):
        raise ContratV2Invalide("routes saisies différentes du snapshot figé")
    source = {
        "path": relatif,
        "sha256": attendu,
        "schema_version": snapshot["schema_version"],
        "observed_at": snapshot.get("observed_at"),
        "criterion_version": snapshot["criterion_version"],
        "budget_status": budget["status"],
        "repriced_estimate_microdollars": budget["repriced_estimate_microdollars"],
        "b0_09_approval_hash": empreinte(approbation),
    }
    return resolved, source


def _charger_snapshot_routes(
    draft: dict[str, Any], panel: list[str], models_file: Path, cible_v4: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Lire le snapshot cible sans importer les décisions budgétaires B0"""
    relatif = chemin_relatif_sur(draft.get("route_snapshot_file"), "route_snapshot_file")
    attendu = draft.get("route_snapshot_sha256")
    if (
        not isinstance(attendu, str)
        or re.fullmatch(r"[0-9a-f]{64}", attendu) is None
    ):
        raise ContratV2Invalide("route_snapshot_sha256 invalide")
    path = resoudre_sous(RACINE, relatif)
    if not path.is_file() or path.is_symlink() or sha256_fichier(path) != attendu:
        raise ContratV2Invalide("snapshot de routes absent, lié ou modifié")
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContratV2Invalide("snapshot de routes illisible") from exc
    schema_attendu = (
        "benchmark-lab-x/route-preflight-snapshot/v3"
        if cible_v4
        else "benchmark-lab-x/route-preflight-snapshot/v2"
    )
    if snapshot.get("schema_version") != schema_attendu:
        raise ContratV2Invalide(f"{schema_attendu} requis")
    if snapshot.get("panel") != panel:
        raise ContratV2Invalide("panel du snapshot différent du brouillon")
    critere = snapshot.get("criterion_version")
    if not isinstance(critere, str) or not critere:
        raise ContratV2Invalide("critère du snapshot absent")
    observe_at = snapshot.get("observed_at")
    if not isinstance(observe_at, str) or not observe_at:
        raise ContratV2Invalide("date du snapshot absente")
    models_rel = models_file.relative_to(RACINE).as_posix()
    if (
        snapshot.get("models_file") != models_rel
        or snapshot.get("models_file_sha256") != sha256_fichier(models_file)
    ):
        raise ContratV2Invalide("registre du snapshot différent du registre verrouillé")
    resolved = snapshot.get("resolved")
    if not isinstance(resolved, dict) or set(resolved) != set(panel):
        raise ContratV2Invalide("résolution du panel absente du snapshot")
    if draft.get("resolved") not in (None, resolved):
        raise ContratV2Invalide("routes saisies différentes du snapshot figé")
    try:
        if cible_v4:
            valider_cible(snapshot, RACINE, exiger_lockable=True)
        else:
            valider_cible_historique_v2(snapshot)
    except SnapshotRoutesInvalide as exc:
        raise ContratV2Invalide(f"snapshot de routes non verrouillable: {exc}") from exc
    source = {
        "path": relatif,
        "sha256": attendu,
        "schema_version": snapshot["schema_version"],
        "criterion_version": critere,
        "observed_at": observe_at,
    }
    if cible_v4:
        budget = snapshot["budget_reestimate"]
        approbation = snapshot["b0_09_approval"]
        proposal_source = snapshot["proposal_source"]
        source.update({
            "budget_estimate_microdollars": budget["repriced_estimate_microdollars"],
            "budget_cap_microdollars": budget["approved_cap_microdollars"],
            "b0_09_approval_sha256": empreinte(approbation),
            "b0_09_proposal_snapshot_sha256": proposal_source["sha256"],
        })
    return resolved, source


def cout_max_microdollars(route: dict[str, Any], prompt_token_upper_bound: int, max_tokens: int) -> int:
    """Calcul conservateur depuis les prix figés en dollars par million"""
    try:
        entree = Decimal(route["input_usd_per_million_tokens"])
        sortie = Decimal(route["output_usd_per_million_tokens"])
        requete = Decimal(route.get("request_usd", "0"))
    except (KeyError, InvalidOperation, TypeError) as exc:
        raise ContratV2Invalide("prix de route absents ou non décimaux") from exc
    if any(v < 0 for v in (entree, sortie, requete)):
        raise ContratV2Invalide("prix de route négatif")
    microdollars = (
        entree * prompt_token_upper_bound
        + sortie * max_tokens
        + requete * Decimal(1_000_000)
    )
    return int(microdollars.to_integral_value(rounding=ROUND_CEILING))


def _construire_lock_historique_v2(draft: dict[str, Any]) -> dict[str, Any]:
    if draft.get("schema_version") != "benchmark-lab-x/campaign-draft/v2":
        raise ContratV2Invalide("schema_version du brouillon v2 absent")
    if draft.get("protocol_version") != PROTOCOLE_VERSION:
        raise ContratV2Invalide("protocol_version v2 absent du brouillon")
    panel = draft.get("candidates")
    if tuple(panel or ()) != PANEL_B0:
        raise ContratV2Invalide("panel du brouillon différent de B0-06")
    if draft.get("runs") != 6 or draft.get("attempts_max") != 3:
        raise ContratV2Invalide("B0 exige six runs et trois tentatives maximum")
    if draft.get("concurrence") != 2:
        raise ContratV2Invalide("concurrence différente des deux travailleurs figés")
    if draft.get("timeout") != 600:
        raise ContratV2Invalide("timeout transport différent des 600 s du collecteur v3")
    if draft.get("cap_microdollars") != PLAFOND_B0_HISTORIQUE:
        raise ContratV2Invalide("plafond différent des 55 $ approuvés")
    if draft.get("estimate_microdollars") != ESTIMATION_B0_HISTORIQUE:
        raise ContratV2Invalide("estimation différente des 31,812500 $ approuvés")
    if not isinstance(draft.get("created_at"), str) or not draft["created_at"]:
        raise ContratV2Invalide("created_at doit être préenregistré")
    source_commit = draft.get("source_commit")
    if (
        not isinstance(source_commit, str)
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", source_commit) is None
    ):
        raise ContratV2Invalide("source_commit Git complet requis avant le lock autoritaire")

    task_dir_rel = draft.get("task_dir")
    task_file = draft.get("task_file")
    visible_inputs = draft.get("visible_inputs")
    if task_dir_rel != "tasks/dev/pentagone-rotatif" or task_file != "task-v3.md":
        raise ContratV2Invalide("task-v3 du pentagone attendue")
    if visible_inputs != ["donnees.md"]:
        raise ContratV2Invalide("la liste visible approuvée contient seulement donnees.md")
    task_dir = resoudre_sous(RACINE, task_dir_rel)
    task_tree = _arbre_tache(task_dir, task_file, visible_inputs)
    task = {
        "task_id": "pentagone-rotatif",
        "task_version": "task-v3",
        "task_dir": task_dir_rel,
        "task_file": task_file,
        "task_tree": task_tree,
        "prompt_sha256": "0" * 64,
    }
    prompt, _ = assembler_prompt_verrouille(
        RACINE, task, verifier_arbre=True, verifier_prompt=False
    )
    task["prompt_sha256"] = __import__("hashlib").sha256(prompt.encode("utf-8")).hexdigest()
    assembler_prompt_verrouille(RACINE, task, verifier_arbre=True)
    prompt_token_upper_bound = len(prompt.encode("utf-8"))

    assets = [
        "tools/verifier_pentagone_v5.py",
        "tools/oracle_pentagone.py",
        "tools/moteur_rendu.py",
        "tools/protocole_v2.py",
        "tools/qualifier_temoins.py",
        "tasks/dev/pentagone-rotatif/oracle-cache.json",
    ] + _actifs_calibrage(task_dir_rel)
    kinds = {
        "pentagone-api": "binary",
        "pentagone-determinisme": "binary",
        "pentagone-confinement-court": "levels",
        "pentagone-precision-24s": "levels",
        "pentagone-horizons-longs": "levels",
    }
    score_cards = []
    for card_id in CARDS_V4:
        manifeste = _manifeste_verificateur(card_id, assets)
        score_cards.append({
            "id": card_id,
            "kind": kinds[card_id],
            "verify_version": "verify-v5",
            "verifier_path": "tools/verifier_pentagone_v5.py",
            "verify_manifest": manifeste,
            "verify_hash": empreinte(manifeste),
            "watchdog_s": 180,
            "predicates": list(PREDICATS_V4[card_id]),
            "aggregation": {"runs": 6, "order_statistic": 4},
        })

    models_file = resoudre_sous(RACINE, draft.get("models_file", "models.toml"))
    try:
        registry = tomllib.loads(models_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ContratV2Invalide(f"registre modèles illisible: {exc}") from exc
    resolved, route_snapshot_source = _charger_snapshot_routes_historique_v1(
        draft, panel, models_file
    )

    collections = []
    for alias in panel:
        modele = registry.get(alias)
        route = resolved.get(alias)
        if not isinstance(modele, dict) or not isinstance(route, dict):
            raise ContratV2Invalide(f"résolution absente pour {alias}")
        if route.get("metadata_status") != "resolved":
            raise ContratV2Invalide(f"ROUTE_METADATA_UNREACHABLE pour {alias}")
        if route.get("provider") != modele.get("provider"):
            raise ContratV2Invalide(f"provider résolu différent du registre pour {alias}")
        for champ in (
            "quantization", "revision", "criterion_version",
            "price_source", "price_observed_at",
        ):
            if not isinstance(route.get(champ), str) or not route[champ]:
                raise ContratV2Invalide(f"{champ} absent pour {alias}")
        max_tokens = route.get("max_tokens")
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            raise ContratV2Invalide(f"max_tokens invalide pour {alias}")
        max_cost = cout_max_microdollars(route, prompt_token_upper_bound, max_tokens)
        if max_cost < 1:
            raise ContratV2Invalide(f"coût maximal nul pour {alias}")
        if route.get("max_cost_microdollars") not in (None, max_cost):
            raise ContratV2Invalide(f"max_cost_microdollars saisi différent du calcul pour {alias}")
        omit = modele.get("omit_params") or []
        if not isinstance(omit, list) or any(x not in {"seed", "top_p", "temperature"} for x in omit):
            raise ContratV2Invalide(f"omit_params invalide pour {alias}")
        parameters: dict[str, Any] = {"temperature": 0, "top_p": 1, "seed": 42}
        for nom in omit:
            parameters.pop(nom, None)
        if modele.get("reasoning_effort") is not None:
            parameters["reasoning"] = {"effort": modele["reasoning_effort"]}
        elif modele.get("reasoning_max_tokens") is not None:
            parameters["reasoning"] = {"max_tokens": modele["reasoning_max_tokens"]}
        execution = {
            "schema_version": "benchmark-lab-x/execution-manifest/v2",
            "protocol_version": PROTOCOLE_VERSION,
            "task_version": "task-v3",
            "prompt_sha256": task["prompt_sha256"],
            "model": modele.get("model"),
            "route": {
                "backend": "openrouter",
                "provider": route["provider"],
                "expect_provider": modele.get("expect_provider") or route["provider"],
                "quantization": route["quantization"],
                "revision": route["revision"],
                "criterion_version": route.get("criterion_version"),
                "price_source": route["price_source"],
                "price_observed_at": route["price_observed_at"],
                "input_usd_per_million_tokens": route["input_usd_per_million_tokens"],
                "output_usd_per_million_tokens": route["output_usd_per_million_tokens"],
                "request_usd": route.get("request_usd", "0"),
                "prompt_token_upper_bound": prompt_token_upper_bound,
            },
            "parameters": parameters,
            "max_tokens": max_tokens,
            "data_policy": "allow",
            "runner_version": "collect.py/v3",
        }
        if not isinstance(execution["model"], str) or not execution["model"]:
            raise ContratV2Invalide(f"modèle absent du registre pour {alias}")
        execution_hash = empreinte(execution)
        for run in range(1, 7):
            collections.append({
                "collection_id": f"{alias}__r{run}",
                "alias": alias,
                "run": run,
                "task_version": "task-v3",
                "prompt_sha256": task["prompt_sha256"],
                "model": execution["model"],
                "route": {**execution["route"], "metadata_status": "resolved"},
                "parameters": parameters,
                "max_tokens": max_tokens,
                "max_cost_microdollars": max_cost,
                "execution_manifest": execution,
                "execution_manifest_hash": execution_hash,
            })

    environnement_runner = descripteur_environnement_runner()
    environnement_mesure = descripteur_mesure()
    lock = {
        "schema_version": SCHEMA_LOCK_HISTORIQUE,
        "protocol_version": PROTOCOLE_VERSION,
        "campaign_id": draft.get("campaign_id"),
        "question": draft.get("question"),
        "created_at": draft["created_at"],
        "paid_authorization_required": True,
        "repository_source": {"commit": source_commit},
        "environments": {
            "runner": {
                "descriptor": environnement_runner,
                "sha256": empreinte(environnement_runner),
            },
            "measurement": {
                "descriptor": environnement_mesure,
                "sha256": empreinte(environnement_mesure),
            },
        },
        "panel": panel,
        "runs": 6,
        "attempts_max": 3,
        "runner": {
            "concurrency": 2,
            "transport_timeout_s": 600,
        },
        "task": task,
        "score_cards": score_cards,
        "collections": collections,
        "budget": {
            "currency": "USD",
            "cap_microdollars": PLAFOND_B0_HISTORIQUE,
            "estimate_microdollars": ESTIMATION_B0_HISTORIQUE,
        },
        "registry_source": {
            "path": models_file.relative_to(RACINE).as_posix(),
            "sha256": sha256_fichier(models_file),
        },
        "route_snapshot_source": route_snapshot_source,
    }
    valider_lock(lock, RACINE)
    return lock


def construire_lock(draft: dict[str, Any]) -> dict[str, Any]:
    """Construire le lock cible depuis une intention et un snapshot déjà figés"""
    schema_draft = draft.get("schema_version")
    if schema_draft not in {
        "benchmark-lab-x/campaign-draft/v3",
        "benchmark-lab-x/campaign-draft/v4",
    }:
        raise ContratV2Invalide("campaign-draft/v3 ou v4 requis")
    cible_v4 = schema_draft == "benchmark-lab-x/campaign-draft/v4"
    if cible_v4:
        champs_brouillon_v4 = {
            "schema_version", "protocol_version", "operation", "campaign_id",
            "question", "created_at", "source_commit", "task_dir", "task_file",
            "visible_inputs", "confidentiality_regime", "data_policy_requested",
            "models_file", "runs", "attempts_max", "concurrence", "timeout",
            "cap_microdollars", "estimate_microdollars", "estimate_source",
            "b0_08_status", "b0_09_status", "b0_10_status",
            "route_snapshot_file", "route_snapshot_sha256", "campaign_lock",
            "paid_authorization", "budget_ledger", "candidates", "quotas",
            "audit_plans",
        }
        if set(draft) != champs_brouillon_v4:
            raise ContratV2Invalide("champs du campaign-draft/v4 différents du contrat fermé")
        if draft.get("b0_08_status") != "APPROVED":
            raise ContratV2Invalide("B0-08 reste en HOLD")
        if draft.get("b0_09_status") != "APPROVED":
            raise ContratV2Invalide("B0-09 reste en HOLD")
        if draft.get("b0_10_status") != "HOLD":
            raise ContratV2Invalide("le brouillon ne peut pas autoriser B0-10")
        cap = draft.get("cap_microdollars")
        if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1:
            raise ContratV2Invalide("plafond B0 invalide")
        if draft.get("campaign_lock") != "campaign.lock.v4.json":
            raise ContratV2Invalide("nom du campaign-lock/v4 invalide")
        for champ in ("paid_authorization", "budget_ledger", "estimate_source"):
            if not isinstance(draft.get(champ), str) or not draft[champ].strip():
                raise ContratV2Invalide(f"{champ} absent du brouillon v4")
    if draft.get("protocol_version") != PROTOCOLE_VERSION:
        raise ContratV2Invalide("protocol/v2 absent du brouillon")
    if draft.get("operation") != "new_collection":
        raise ContratV2Invalide("le préparateur actif accepte seulement new_collection")
    panel = draft.get("candidates")
    if (
        not isinstance(panel, list)
        or not panel
        or any(not isinstance(alias, str) or not alias for alias in panel)
        or len(panel) != len(set(panel))
    ):
        raise ContratV2Invalide("panel du brouillon invalide")
    if draft.get("runs") != 6 or draft.get("attempts_max") != 3:
        raise ContratV2Invalide("pentagone exige six runs et protocol/v2 trois tentatives")
    concurrence = draft.get("concurrence")
    timeout = draft.get("timeout")
    if not isinstance(concurrence, int) or isinstance(concurrence, bool) or concurrence < 1:
        raise ContratV2Invalide("concurrence explicite positive requise")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
        raise ContratV2Invalide("timeout transport explicite positif requis")
    if not isinstance(draft.get("created_at"), str) or not draft["created_at"]:
        raise ContratV2Invalide("created_at doit être préenregistré")
    source_commit = draft.get("source_commit")
    if (
        not isinstance(source_commit, str)
        or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", source_commit) is None
    ):
        raise ContratV2Invalide("source_commit Git complet requis")

    task_dir_rel = chemin_relatif_sur(draft.get("task_dir"), "task_dir")
    task_file = chemin_relatif_sur(draft.get("task_file"), "task_file")
    if Path(task_dir_rel).name != "pentagone-rotatif":
        raise ContratV2Invalide("ce préparateur instrumente seulement pentagone-rotatif")
    match_version = re.fullmatch(r"(task-v[1-9][0-9]*)\.md", task_file)
    if match_version is None:
        raise ContratV2Invalide("task_file doit porter un compteur task-vN")
    task_version = match_version.group(1)
    visible_inputs = draft.get("visible_inputs")
    if not isinstance(visible_inputs, list) or not visible_inputs:
        raise ContratV2Invalide("liste fermée des entrées visibles absente")
    task_dir = resoudre_sous(RACINE, task_dir_rel)
    task_tree = _arbre_tache(task_dir, task_file, visible_inputs)
    task = {
        "task_id": "pentagone-rotatif",
        "task_version": task_version,
        "task_dir": task_dir_rel,
        "task_file": task_file,
        "task_tree": task_tree,
        "prompt_sha256": "0" * 64,
        "confidentiality_regime": draft.get("confidentiality_regime"),
    }
    if task["confidentiality_regime"] not in {"expose", "retenu"}:
        raise ContratV2Invalide("confidentiality_regime doit être explicite")
    prompt, _ = assembler_prompt_verrouille(
        RACINE, task, verifier_arbre=True, verifier_prompt=False
    )
    task["prompt_sha256"] = __import__("hashlib").sha256(prompt.encode("utf-8")).hexdigest()
    assembler_prompt_verrouille(RACINE, task, verifier_arbre=True)
    prompt_token_upper_bound = len(prompt.encode("utf-8"))

    instruments = {
        "task-v3": ("verify-v5", "tools/verifier_pentagone_v5.py", PREDICATS_V4),
        "task-v4": ("verify-v6", "tools/verifier_pentagone_v6.py", PREDICATS_V5),
    }
    instrument = instruments.get(task_version)
    if instrument is None:
        raise ContratV2Invalide(f"instrument absent pour {task_version}")
    verify_version, verifier_path, predicates = instrument

    assets = [
        verifier_path,
        "tools/oracle_pentagone.py",
        "tools/moteur_rendu.py",
        "tools/protocole_v2.py",
        "tools/qualifier_temoins.py",
        "tasks/dev/pentagone-rotatif/oracle-cache.json",
    ] + _actifs_calibrage(task_dir_rel)
    kinds = {
        aid: "binary" if aid in AXES_PENTAGONE[:2] else "levels"
        for aid in AXES_PENTAGONE
    }
    audit_plans = draft.get("audit_plans")
    if not isinstance(audit_plans, dict) or set(audit_plans) != set(AXES_PENTAGONE):
        raise ContratV2Invalide("un plan d'audit explicite est requis pour chaque axe")
    axes = []
    for axis_id in AXES_PENTAGONE:
        manifeste_verify = _manifeste_verificateur(
            axis_id, assets, verify_version, predicates
        )
        axes.append({
            "id": axis_id,
            "kind": kinds[axis_id],
            "verify_version": verify_version,
            "verify_hash": empreinte(manifeste_verify),
            "verifier_path": verifier_path,
            "verify_manifest": manifeste_verify,
            "watchdog_s": 180,
            "predicates": list(predicates[axis_id]),
            "aggregation": {"runs": 6, "order_statistic": 4},
            "audit_plan": audit_plans[axis_id],
        })

    models_file = resoudre_sous(RACINE, draft.get("models_file", "models.toml"))
    try:
        registry = tomllib.loads(models_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ContratV2Invalide(f"registre modèles illisible: {exc}") from exc
    resolved, route_snapshot_source = _charger_snapshot_routes(
        draft, panel, models_file, cible_v4
    )
    if cible_v4 and (
        draft.get("estimate_microdollars")
        != route_snapshot_source["budget_estimate_microdollars"]
        or draft.get("cap_microdollars")
        != route_snapshot_source["budget_cap_microdollars"]
    ):
        raise ContratV2Invalide("budget du brouillon différent du snapshot approuvé")
    data_policy = draft.get("data_policy_requested")
    if data_policy not in {"allow", "deny"}:
        raise ContratV2Invalide("data_policy_requested doit être explicite")
    if task["confidentiality_regime"] == "retenu" and data_policy != "deny":
        raise ContratV2Invalide("une carte retenue exige data_policy_requested=deny")

    collections = []
    for alias in panel:
        modele = registry.get(alias)
        route = resolved.get(alias)
        if not isinstance(modele, dict) or not isinstance(route, dict):
            raise ContratV2Invalide(f"résolution absente pour {alias}")
        if route.get("metadata_status") != "resolved":
            raise ContratV2Invalide(f"route non résolue pour {alias}")
        for champ in (
            "backend", "provider", "expect_provider", "criterion_version",
            "price_source", "price_observed_at", "input_usd_per_million_tokens",
            "output_usd_per_million_tokens",
        ):
            if not isinstance(route.get(champ), str) or not route[champ]:
                raise ContratV2Invalide(f"{champ} absent pour {alias}")
        if cible_v4:
            if not isinstance(route.get("endpoint_tag"), str) or not route["endpoint_tag"]:
                raise ContratV2Invalide(f"endpoint_tag absent pour {alias}")
            if not isinstance(route.get("quantization"), dict):
                raise ContratV2Invalide(f"quantification structurée absente pour {alias}")
            if not isinstance(route.get("revision"), dict):
                raise ContratV2Invalide(f"révision structurée absente pour {alias}")
            if not isinstance(route.get("ownership"), dict):
                raise ContratV2Invalide(f"ownership absent pour {alias}")
            if not isinstance(route.get("metadata_evidence"), dict):
                raise ContratV2Invalide(f"preuve de métadonnées absente pour {alias}")
        else:
            for champ in ("quantization", "revision"):
                if not isinstance(route.get(champ), str) or not route[champ]:
                    raise ContratV2Invalide(f"{champ} absent pour {alias}")
        max_tokens = route.get("max_tokens")
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            raise ContratV2Invalide(f"max_tokens invalide pour {alias}")
        omit = modele.get("omit_params") or []
        if not isinstance(omit, list) or any(
            nom not in {"seed", "top_p", "temperature"} for nom in omit
        ):
            raise ContratV2Invalide(f"omit_params invalide pour {alias}")
        request_parameters: dict[str, Any] = {
            "temperature": 0,
            "top_p": 1,
            "seed": 42,
            "provider": {
                "only": [route["provider"]],
                "allow_fallbacks": False,
                "require_parameters": True,
                "data_collection": data_policy,
            },
            "usage": {"include": True},
        }
        for nom in omit:
            request_parameters.pop(nom, None)
        effort = modele.get("reasoning_effort")
        reasoning_max = modele.get("reasoning_max_tokens")
        if effort is not None and reasoning_max is not None:
            raise ContratV2Invalide(f"deux contrats de raisonnement pour {alias}")
        if effort is not None:
            if not isinstance(effort, str) or not effort.strip():
                raise ContratV2Invalide(f"reasoning_effort invalide pour {alias}")
            request_parameters["reasoning"] = {"effort": effort.strip()}
            effort = effort.strip()
        elif reasoning_max is not None:
            if not isinstance(reasoning_max, int) or isinstance(reasoning_max, bool) or reasoning_max < 1:
                raise ContratV2Invalide(f"reasoning_max_tokens invalide pour {alias}")
            request_parameters["reasoning"] = {"max_tokens": reasoning_max}
        execution = {
            "schema_version": SCHEMA_EXECUTION if cible_v4 else SCHEMA_EXECUTION_V3,
            "mode": "direct",
            "model_requested": modele.get("model"),
            "backend": route["backend"],
            "provider_pinned": route["provider"],
            "provider_expected": route["expect_provider"],
            "quantization": route["quantization"],
            "revision": route["revision"],
            "reasoning_effort": effort,
            "request_parameters": request_parameters,
            "max_tokens": max_tokens,
            "data_policy_requested": data_policy,
            "request_adapter_version": f"{route['backend']}-chat-completions/v1",
            "tools": [],
            "agent": None,
            "local_environment": None,
        }
        if cible_v4:
            execution["endpoint_tag"] = route["endpoint_tag"]
        if not isinstance(execution["model_requested"], str) or not execution["model_requested"]:
            raise ContratV2Invalide(f"modèle absent du registre pour {alias}")
        route_lock = {
            "metadata_status": "resolved",
            "backend": route["backend"],
            "provider": route["provider"],
            "expect_provider": route["expect_provider"],
            "quantization": route["quantization"],
            "revision": route["revision"],
            "criterion_version": route["criterion_version"],
            "price_source": route["price_source"],
            "price_observed_at": route["price_observed_at"],
            "input_usd_per_million_tokens": route["input_usd_per_million_tokens"],
            "output_usd_per_million_tokens": route["output_usd_per_million_tokens"],
            "request_usd": route.get("request_usd", "0"),
            "prompt_token_upper_bound": prompt_token_upper_bound,
        }
        if cible_v4:
            route_lock.update({
                "endpoint_tag": route["endpoint_tag"],
                "ownership": route["ownership"],
                "metadata_evidence": route["metadata_evidence"],
            })
        max_cost = cout_max_microdollars(route_lock, prompt_token_upper_bound, max_tokens)
        execution_hash = empreinte(execution)
        payload_hash = __import__("hashlib").sha256(
            construire_payload(execution, prompt)
        ).hexdigest()
        base_identity = {
            "mode": "direct",
            "model_requested": execution["model_requested"],
            "backend": execution["backend"],
            "provider_pinned": execution["provider_pinned"],
            "reasoning_effort": effort,
        }
        if cible_v4:
            base_identity["endpoint_tag"] = route["endpoint_tag"]
        for run in range(1, 7):
            collections.append({
                "collection_id": f"{alias}__r{run}",
                "alias": alias,
                "run": run,
                "task_version": task_version,
                "prompt_sha256": task["prompt_sha256"],
                "base_identity": base_identity,
                "route": route_lock,
                "execution_manifest": execution,
                "execution_manifest_hash": execution_hash,
                "payload_hash": payload_hash,
                "max_cost_microdollars": max_cost,
            })

    quotas = draft.get("quotas")
    if not isinstance(quotas, dict):
        raise ContratV2Invalide("quotas explicites absents du brouillon")
    budget = {
        "currency": "USD",
        "cap_microdollars": draft.get("cap_microdollars"),
        "estimate_microdollars": draft.get("estimate_microdollars"),
        "estimate_source": draft.get("estimate_source"),
    }
    environnement_runner = descripteur_environnement_runner()
    environnement_mesure = descripteur_mesure()
    lock = {
        "schema_version": SCHEMA_LOCK if cible_v4 else SCHEMA_LOCK_V3,
        "protocol_version": PROTOCOLE_VERSION,
        "campaign_id": draft.get("campaign_id"),
        "operation": "new_collection",
        "question": draft.get("question"),
        "created_at": draft["created_at"],
        "paid_authorization_required": True,
        "repository_source": {"commit": source_commit},
        "environments": {
            "runner": {"descriptor": environnement_runner, "sha256": empreinte(environnement_runner)},
            "measurement": {"descriptor": environnement_mesure, "sha256": empreinte(environnement_mesure)},
        },
        "panel": panel,
        "runs": 6,
        "attempts_max": 3,
        "runner": {"concurrency": concurrence, "transport_timeout_s": timeout},
        "quotas": quotas,
        "selection_policy": {"version": route_snapshot_source["criterion_version"]},
        "task": task,
        "axes": axes,
        "collections": collections,
        "budget": budget,
        "registry_source": {
            "path": models_file.relative_to(RACINE).as_posix(),
            "sha256": sha256_fichier(models_file),
        },
        "route_snapshot_source": route_snapshot_source,
    }
    valider_lock(lock, RACINE)
    return lock


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    try:
        lock = construire_lock(_charger_toml(args.draft))
        ecrire_json_immuable(args.out, lock)
    except ContratV2Invalide as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "PREPARED_LOCAL_ONLY",
        "campaign_lock": str(args.out),
        "campaign_lock_hash": empreinte(lock),
        "collections": len(lock["collections"]),
        "axes": len(lock["axes"]),
        "cap_microdollars": lock["budget"]["cap_microdollars"],
        "paid_collection": "HOLD",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
