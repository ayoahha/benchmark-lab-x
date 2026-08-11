# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""Composer une série de mesure depuis des acquisitions immuables validées

La série scientifique reste distincte des lots techniques de collecte. Ce
module valide chaque acquisition dans son lock source, construit les 114 slots
de la série et prépare uniquement les slots encore absents
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tomllib
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from choisir_provider import budget_de, editeur_canonique, est_editeur, evaluer, norm  # noqa: E402
from empreintes import empreinte  # noqa: E402
from protocole_v2 import (  # noqa: E402
    ContratV2Invalide,
    POLITIQUE_PORTEE_ECHEC,
    SCHEMA_LOCK_CONTINUATION,
    charger_json,
    ecrire_json_immuable,
    empreinte_lock,
    sha256_fichier,
    sha256_octets,
    valider_chaine_collecte,
    valider_lock,
    valider_recu_tentative,
)


SCHEMA_SERIE = "benchmark-lab-x/acquisition-inventory/v1"
SCHEMA_BROUILLON_CONTINUATION = "benchmark-lab-x/continuation-draft/v1"
POLITIQUE_FALLBACK = "benchmark-lab-x/fallback-route/v1"
POLITIQUE_FACTURATION_ECHEC = "openrouter/failed-attempt-unbilled/v1"
PREUVE_FACTURATION_ECHEC = {
    "url": "https://openrouter.ai/pricing",
    "observed_at": "2026-08-10",
    "statement": (
        "No. When routing/fallback is enabled, you're billed only for the "
        "successful model run."
    ),
}


def _exiger(condition: bool, message: str) -> None:
    if not condition:
        raise ContratV2Invalide(message)


def _relatif_depot(path: Path) -> str:
    resolu = path.resolve()
    try:
        return resolu.relative_to(RACINE.resolve()).as_posix()
    except ValueError as exc:
        raise ContratV2Invalide(f"chemin hors dépôt: {path}") from exc


def _decimal_prix(value: Any, chemin: str) -> Decimal:
    try:
        prix = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ContratV2Invalide(f"prix invalide dans {chemin}") from exc
    _exiger(prix.is_finite() and prix >= 0, f"prix négatif ou non fini dans {chemin}")
    return prix


def _prix_par_million(pricing: dict[str, Any], cle: str, chemin: str) -> str:
    prix = _decimal_prix(pricing.get(cle, "0"), f"{chemin}.{cle}")
    valeur = prix * Decimal(1_000_000)
    texte = format(valeur, "f")
    return texte.rstrip("0").rstrip(".") if "." in texte else texte


def identite_modele(cellule: dict[str, Any]) -> dict[str, Any]:
    manifeste = cellule["execution_manifest"]
    return {
        "mode": manifeste["mode"],
        "model_requested": manifeste["model_requested"],
        "revision": copy.deepcopy(manifeste["revision"]),
    }


def identite_route(cellule: dict[str, Any]) -> dict[str, Any]:
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


def contrat_execution(cellule: dict[str, Any]) -> dict[str, Any]:
    manifeste = cellule["execution_manifest"]
    parametres = copy.deepcopy(manifeste["request_parameters"])
    parametres.pop("provider", None)
    return {
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
    }


def contrat_compatibilite(cellule: dict[str, Any]) -> dict[str, Any]:
    contrat = {
        "model_identity": identite_modele(cellule),
        "execution_contract": contrat_execution(cellule),
    }
    return {**contrat, "sha256": empreinte(contrat)}


def _parametres_requis(cellule: dict[str, Any]) -> set[str]:
    parametres = cellule["execution_manifest"]["request_parameters"]
    requis = {norm(cle) for cle in parametres if cle not in {"provider", "usage"}}
    requis.add(norm("max_tokens"))
    raisonnement = parametres.get("reasoning")
    if isinstance(raisonnement, dict):
        requis.add(norm("reasoning"))
        if "effort" in raisonnement:
            requis.add(norm("reasoning_effort"))
    return requis


def _identite_route_endpoint(endpoint: dict[str, Any], model: str) -> dict[str, Any]:
    tag = endpoint.get("tag")
    provider_name = endpoint.get("provider_name")
    _exiger(isinstance(tag, str) and tag, "tag de fallback absent")
    _exiger(isinstance(provider_name, str) and provider_name, "provider de fallback absent")
    provider = norm(tag.split("/")[0])
    publisher = editeur_canonique(model)
    _exiger(isinstance(publisher, str) and publisher, f"éditeur canonique absent: {model}")
    return {
        "kind": "publisher_managed" if est_editeur(endpoint, model) else "third_party",
        "canonical_publisher": publisher,
        "provider_slug": provider,
        "provider_name": provider_name,
        "endpoint_tag": tag,
    }


def selectionner_fallback(
    cellule: dict[str, Any], snapshot: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Choisir au plus un secondaire prouvé par le snapshot déjà figé"""
    manifeste = cellule["execution_manifest"]
    quantification = manifeste["quantization"]
    if quantification.get("status") != "declared":
        return None, "PRIMARY_QUANTIZATION_NOT_DISCLOSED"
    if manifeste.get("data_policy_requested") != "allow":
        return None, "SECONDARY_DATA_POLICY_NOT_PROVEN"
    model = manifeste["model_requested"]
    bloc = snapshot.get("models", {}).get(model)
    if not isinstance(bloc, dict):
        raise ContratV2Invalide(f"preuve de métadonnées absente pour {model}")
    evidence = bloc.get("metadata_evidence")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("response_body"), str):
        raise ContratV2Invalide(f"réponse de métadonnées absente pour {model}")
    _exiger(
        sha256_octets(evidence["response_body"].encode("utf-8"))
        == evidence.get("response_sha256"),
        f"preuve de métadonnées modifiée pour {model}",
    )
    try:
        endpoints = json.loads(evidence["response_body"])["data"]["endpoints"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ContratV2Invalide(f"métadonnées illisibles pour {model}") from exc
    requis = _parametres_requis(cellule)
    reference = quantification["value"]
    revision = manifeste["revision"].get("value")
    max_tokens = manifeste["max_tokens"]
    provider_primaire = norm(manifeste["provider_pinned"])
    candidats: list[tuple[tuple[Any, ...], dict[str, Any], dict[str, Any]]] = []
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            continue
        tag = endpoint.get("tag")
        provider = norm(str(tag or "").split("/")[0])
        supportes = {norm(p) for p in endpoint.get("supported_parameters") or []}
        if (
            not tag
            or provider == provider_primaire
            or endpoint.get("model_id") != revision
            or norm(endpoint.get("quantization")) != norm(reference)
            or budget_de(endpoint) < max_tokens
            or not requis.issubset(supportes)
        ):
            continue
        evaluation = evaluer(endpoint, model, reference)
        if evaluation["exclusions"]:
            continue
        pricing = endpoint.get("pricing")
        if not isinstance(pricing, dict):
            continue
        candidats.append((
            (0 if not evaluation["reserves"] else 1, evaluation["_cle"]),
            endpoint,
            evaluation,
        ))
    if not candidats:
        return None, "NO_STRICTLY_COMPATIBLE_SECONDARY_ROUTE"
    candidats.sort(key=lambda item: (item[0], str(item[1].get("tag"))))
    _, endpoint, evaluation = candidats[0]
    route_identity = _identite_route_endpoint(endpoint, model)
    fallback = {
        "policy_version": POLITIQUE_FALLBACK,
        "selection_basis": (
            "compatibilité stricte, absence de réserve dans le snapshot, "
            "puis ordre selection-route/v3"
        ),
        "activation": {
            "after_primary_attempts_exhausted": True,
            "candidate_artifact_accepted": False,
            "requires_new_locked_batch": True,
        },
        "route_identity": {
            "backend": manifeste["backend"],
            "provider_pinned": route_identity["provider_slug"],
            "provider_expected": route_identity["provider_name"],
            "endpoint_tag": route_identity["endpoint_tag"],
            "ownership": route_identity,
            "metadata_evidence": {
                "url": evidence["url"],
                "observed_at": evidence["observed_at"],
                "response_sha256": evidence["response_sha256"],
            },
        },
        "equivalence": {
            "model_revision": revision,
            "quantization": copy.deepcopy(quantification),
            "execution_max_tokens": max_tokens,
            "available_max_tokens": budget_de(endpoint),
            "required_parameters": sorted(requis),
            "data_policy_requested": manifeste["data_policy_requested"],
            "compatibility_contract_sha256": contrat_compatibilite(cellule)["sha256"],
        },
        "pricing": {
            "input_usd_per_million_tokens": _prix_par_million(
                endpoint["pricing"], "prompt", str(endpoint["tag"])
            ),
            "output_usd_per_million_tokens": _prix_par_million(
                endpoint["pricing"], "completion", str(endpoint["tag"])
            ),
            "request_usd": str(endpoint["pricing"].get("request") or "0"),
        },
        "preflight_observation": {
            "status": endpoint.get("status"),
            "uptime_last_30m": (
                str(endpoint["uptime_last_30m"])
                if endpoint.get("uptime_last_30m") is not None else None
            ),
            "reserves": evaluation["reserves"],
        },
    }
    return fallback, None


def _charger_campagne(campaign_dir: Path) -> tuple[Path, dict[str, Any], str]:
    conf_path = campaign_dir / "campaign.toml"
    _exiger(conf_path.is_file() and not conf_path.is_symlink(), f"campaign.toml absent: {campaign_dir}")
    try:
        conf = tomllib.loads(conf_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ContratV2Invalide(f"campaign.toml illisible: {campaign_dir}") from exc
    lock_name = conf.get("campaign_lock", "campaign.lock.json")
    _exiger(
        isinstance(lock_name, str)
        and Path(lock_name).name == lock_name
        and lock_name not in {"", ".", ".."},
        f"nom de lock invalide: {campaign_dir}",
    )
    lock_path = campaign_dir / lock_name
    _exiger(lock_path.is_file() and not lock_path.is_symlink(), f"lock absent: {campaign_dir}")
    lock = valider_lock(charger_json(lock_path))
    return lock_path, lock, empreinte_lock(lock)


def _preuve_acquisition(
    campaign_dir: Path,
    lock_path: Path,
    lock: dict[str, Any],
    lock_hash: str,
    cellule: dict[str, Any],
) -> dict[str, Any] | None:
    collection_dir = campaign_dir / "collections" / cellule["collection_id"]
    recus = sorted(collection_dir.glob("attempt-*/collection-receipt.json"))
    complets = [path for path in recus if (path.parent / "COMPLETE").is_file()]
    if not complets:
        return None
    _exiger(len(complets) == 1, f"plusieurs acquisitions pour {cellule['collection_id']}")
    collection_path = complets[0]
    attempt_path = collection_path.parent / "attempt-receipt.json"
    response_path = collection_path.parent / "response.md"
    raw_path = collection_path.parent / "raw.json"
    for path in (attempt_path, response_path, raw_path):
        _exiger(path.is_file() and not path.is_symlink(), f"preuve absente ou liée: {path}")
    tentative = charger_json(attempt_path)
    collecte = charger_json(collection_path)
    valider_chaine_collecte(tentative, collecte, lock_hash, cellule)
    _exiger(
        sha256_fichier(response_path) == collecte["candidate"]["sha256"],
        f"response.md modifiée: {cellule['collection_id']}",
    )
    _exiger(
        sha256_fichier(raw_path) == collecte["response_json_sha256"],
        f"raw.json modifié: {cellule['collection_id']}",
    )
    return {
        "source_campaign_id": lock["campaign_id"],
        "source_campaign_path": _relatif_depot(campaign_dir),
        "source_lock_path": _relatif_depot(lock_path),
        "source_lock_sha256": sha256_fichier(lock_path),
        "source_campaign_lock_hash": lock_hash,
        "source_collection_id": cellule["collection_id"],
        "attempt": collecte["attempt"],
        "attempt_receipt": {
            "path": _relatif_depot(attempt_path),
            "sha256": sha256_fichier(attempt_path),
        },
        "collection_receipt": {
            "path": _relatif_depot(collection_path),
            "sha256": sha256_fichier(collection_path),
        },
        "response": {
            "path": _relatif_depot(response_path),
            "sha256": collecte["candidate"]["sha256"],
        },
        "raw_response": {
            "path": _relatif_depot(raw_path),
            "sha256": collecte["response_json_sha256"],
        },
        "cost_microdollars": collecte["cost_accounting"]["cost_microdollars"],
        "served": copy.deepcopy(collecte["served"]),
        "model_identity": identite_modele(cellule),
        "route_identity": identite_route(cellule),
        "compatibility_contract_sha256": contrat_compatibilite(cellule)["sha256"],
    }


def _comptabilite_ledger_v2(
    campaign_dir: Path, lock: dict[str, Any], lock_hash: str
) -> dict[str, Any]:
    ledger_path = campaign_dir / "budget-ledger.json"
    _exiger(ledger_path.is_file() and not ledger_path.is_symlink(), f"ledger absent: {campaign_dir}")
    ledger = charger_json(ledger_path)
    _exiger(ledger.get("campaign_lock_hash") == lock_hash, f"ledger lié à un autre lock: {campaign_dir}")
    reservations = ledger.get("reservations")
    _exiger(isinstance(reservations, dict), f"réservations absentes: {campaign_dir}")
    recorded = sum(
        int(reservation["cost_microdollars"])
        for reservation in reservations.values()
        if reservation.get("status") == "finalized"
    )
    _exiger(recorded == ledger.get("engaged_microdollars"), f"total engagé incohérent: {campaign_dir}")
    cellules = {cellule["collection_id"]: cellule for cellule in lock["collections"]}
    recus: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted((campaign_dir / "collections").glob("*/attempt-*/attempt-receipt.json")):
        receipt = charger_json(path)
        accounting = receipt.get("cost_accounting") or {}
        reservation_id = accounting.get("reservation_id")
        if reservation_id not in reservations:
            continue
        cellule = cellules.get(receipt.get("collection_id"))
        _exiger(cellule is not None, f"reçu budgétaire sans cellule: {path}")
        valider_recu_tentative(receipt, cellule, lock_hash)
        _exiger(reservation_id not in recus, f"reçu budgétaire dupliqué: {reservation_id}")
        recus[reservation_id] = (path, receipt)

    adjustments = []
    for reservation_id, reservation in sorted(reservations.items()):
        if reservation.get("status") != "finalized":
            continue
        preuve = recus.get(reservation_id)
        if preuve is None:
            continue
        path, receipt = preuve
        cellule = cellules[receipt["collection_id"]]
        manifeste = cellule["execution_manifest"]
        routage = manifeste.get("request_parameters", {}).get("provider")
        accounting = receipt["cost_accounting"]
        if not (
            manifeste.get("backend") == "openrouter"
            and isinstance(routage, dict)
            and (
                receipt.get("result") == "FAILED_RETRYABLE"
                and receipt.get("cause_code") == "HTTP_429"
                or receipt.get("result") == "FAILED_NON_RETRYABLE"
                and receipt.get("cause_code") in {"HTTP_NON_RETRYABLE", "API_ERROR"}
            )
            and receipt.get("http_response_received") is True
            and receipt.get("candidate_artifact_accepted") is False
            and accounting.get("status") == "upper_bound"
        ):
            continue
        cout = int(reservation["cost_microdollars"])
        _exiger(
            cout == accounting["cost_microdollars"] == reservation["max_microdollars"],
            f"borne 429 incohérente: {reservation_id}",
        )
        adjustments.append({
            "reservation_id": reservation_id,
            "attempt_receipt_path": path.relative_to(campaign_dir).as_posix(),
            "attempt_receipt_sha256": sha256_fichier(path),
            "recorded_microdollars": cout,
            "reconciled_microdollars": 0,
            "cause_code": receipt["cause_code"],
        })
    reconciled = sum(item["recorded_microdollars"] for item in adjustments)
    preuve = copy.deepcopy(PREUVE_FACTURATION_ECHEC)
    preuve["statement_sha256"] = sha256_octets(
        preuve["statement"].encode("utf-8")
    )
    return {
        "policy_version": POLITIQUE_FACTURATION_ECHEC,
        "authority": preuve,
        "recorded_microdollars": recorded,
        "reconciled_microdollars": reconciled,
        "engaged_microdollars": recorded - reconciled,
        "adjustments": adjustments,
    }


def _acquisitions_campagne(campaign_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    lock_path, lock, lock_hash = _charger_campagne(campaign_dir)
    acquis: dict[str, dict[str, Any]] = {}
    for cellule in lock["collections"]:
        preuve = _preuve_acquisition(campaign_dir, lock_path, lock, lock_hash, cellule)
        if preuve is not None:
            acquis[cellule["collection_id"]] = {"cell": cellule, "proof": preuve}
    accounting = _comptabilite_ledger_v2(campaign_dir, lock, lock_hash)
    source = {
        "campaign_id": lock["campaign_id"],
        "path": _relatif_depot(campaign_dir),
        "lock_path": _relatif_depot(lock_path),
        "lock_sha256": sha256_fichier(lock_path),
        "campaign_lock_hash": lock_hash,
        "acquisitions": len(acquis),
        "engaged_microdollars": accounting["engaged_microdollars"],
        "ledger_recorded_microdollars": accounting["recorded_microdollars"],
        "billing_reconciliation": {
            "policy_version": accounting["policy_version"],
            "authority": accounting["authority"],
            "reconciled_microdollars": accounting["reconciled_microdollars"],
            "adjustments": accounting["adjustments"],
        },
    }
    return acquis, source


def _route_autorisee(
    source_cell: dict[str, Any], target_cell: dict[str, Any], fallback: dict[str, Any] | None
) -> str:
    source_route = identite_route(source_cell)
    if source_route == identite_route(target_cell):
        return "primary"
    if fallback is not None and source_route == fallback["route_identity"]:
        return "secondary"
    raise ContratV2Invalide(f"route non préenregistrée pour {target_cell['collection_id']}")


def _projection_microdollars(
    budget: dict[str, Any], slots_futurs: dict[str, int]
) -> int:
    if not slots_futurs:
        return 0
    par_alias = budget.get("by_alias")
    _exiger(
        isinstance(par_alias, dict) and set(slots_futurs) <= set(par_alias),
        "base B0-09 incomplète",
    )
    base = Decimal(0)
    for alias, nombre in slots_futurs.items():
        _exiger(
            isinstance(nombre, int) and not isinstance(nombre, bool) and nombre > 0,
            f"nombre de slots invalide pour {alias}",
        )
        runs_historiques = int(par_alias[alias]["runs"])
        _exiger(runs_historiques > 0, f"runs historiques absents pour {alias}")
        base += (
            Decimal(int(par_alias[alias]["repriced_microdollars"]))
            * Decimal(nombre)
            / Decimal(runs_historiques)
        )
    historique_runs = int(budget["historical_runs"])
    prompts = int(budget["historical_provider_prompts"])
    projection = base * Decimal(prompts) / Decimal(historique_runs)
    return int(projection.to_integral_value(rounding=ROUND_CEILING))


def _projection_fallback(
    budget: dict[str, Any],
    plans: dict[str, dict[str, Any]],
    slots_futurs: dict[str, int],
) -> dict[str, Any]:
    base_secondaire = Decimal(0)
    base_primaire = Decimal(0)
    aliases = []
    for alias, plan in plans.items():
        fallback = plan.get("fallback")
        if fallback is None:
            continue
        compteurs = budget["by_alias"][alias]
        nombre = slots_futurs[alias]
        runs_historiques = int(compteurs["runs"])
        prix = fallback["pricing"]
        cout = (
            _decimal_prix(prix["input_usd_per_million_tokens"], alias)
            * Decimal(compteurs["prompt_tokens"])
            + _decimal_prix(prix["output_usd_per_million_tokens"], alias)
            * Decimal(compteurs["completion_tokens"])
            + _decimal_prix(prix["request_usd"], alias)
            * Decimal(1_000_000)
            * Decimal(compteurs["runs"])
        )
        base_secondaire += cout * Decimal(nombre) / Decimal(runs_historiques)
        base_primaire += (
            Decimal(int(compteurs["repriced_microdollars"]))
            * Decimal(nombre)
            / Decimal(runs_historiques)
        )
        aliases.append(alias)
    if not aliases:
        return {
            "aliases": [],
            "slots": 0,
            "secondary_route_projection_microdollars": 0,
            "delta_vs_primary_routes_microdollars": 0,
            "excludes_failed_primary_attempt_costs": True,
        }
    facteur = (
        Decimal(budget["historical_provider_prompts"])
        / Decimal(budget["historical_runs"])
    )
    projection_secondaire = int(
        (Decimal(base_secondaire) * facteur).to_integral_value(rounding=ROUND_CEILING)
    )
    projection_primaire = int(
        (Decimal(base_primaire) * facteur).to_integral_value(rounding=ROUND_CEILING)
    )
    return {
        "aliases": sorted(aliases),
        "slots": sum(slots_futurs[alias] for alias in aliases),
        "secondary_route_projection_microdollars": projection_secondaire,
        "delta_vs_primary_routes_microdollars": projection_secondaire - projection_primaire,
        "excludes_failed_primary_attempt_costs": True,
    }


def construire_serie(
    series_id: str,
    reference_campaign: Path,
    source_campaigns: list[Path],
    route_snapshot_path: Path,
    global_cap_microdollars: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _exiger(isinstance(series_id, str) and series_id, "series_id absent")
    _exiger(global_cap_microdollars > 0, "plafond global absent")
    reference_lock_path, reference_lock, reference_hash = _charger_campagne(reference_campaign)
    _exiger(len(reference_lock["collections"]) == 114, "la série de référence ne contient pas 114 slots")
    _exiger(
        route_snapshot_path.is_file() and not route_snapshot_path.is_symlink(),
        "snapshot de routes absent ou lié",
    )
    snapshot = charger_json(route_snapshot_path)
    snapshot_hash = sha256_fichier(route_snapshot_path)
    _exiger(
        snapshot_hash == reference_lock["route_snapshot_source"]["sha256"],
        "snapshot de routes différent du lock de référence",
    )
    _exiger(
        snapshot.get("schema_version") == "benchmark-lab-x/route-preflight-snapshot/v3"
        and snapshot.get("status") == "PREPARED_LOCAL_ONLY"
        and snapshot.get("hold_reasons") == []
        and isinstance(snapshot.get("b0_09_approval"), dict),
        "snapshot de routes non approuvé ou encore en HOLD",
    )
    _exiger(snapshot.get("panel") == reference_lock["panel"], "panel du snapshot différent")

    plans: dict[str, dict[str, Any]] = {}
    cells_by_alias: dict[str, dict[str, Any]] = {}
    for cellule in reference_lock["collections"]:
        alias = cellule["alias"]
        if alias in cells_by_alias:
            _exiger(
                contrat_compatibilite(cellule) == contrat_compatibilite(cells_by_alias[alias]),
                f"contrat variable entre les runs de {alias}",
            )
            continue
        cells_by_alias[alias] = cellule
        fallback, absence = selectionner_fallback(cellule, snapshot)
        plans[alias] = {
            "model_identity": identite_modele(cellule),
            "compatibility_contract": contrat_compatibilite(cellule),
            "primary_route": identite_route(cellule),
            "fallback": fallback,
            "fallback_unavailable_reason": absence,
        }

    toutes_acquisitions: dict[str, dict[str, Any]] = {}
    sources = []
    for campaign in source_campaigns:
        acquisitions, source = _acquisitions_campagne(campaign)
        sources.append(source)
        for collection_id, acquisition in acquisitions.items():
            _exiger(collection_id not in toutes_acquisitions, f"slot acquis plusieurs fois: {collection_id}")
            toutes_acquisitions[collection_id] = acquisition

    target_ids = {cellule["collection_id"] for cellule in reference_lock["collections"]}
    hors_serie = sorted(set(toutes_acquisitions) - target_ids)
    _exiger(not hors_serie, f"acquisitions hors série: {hors_serie}")

    slots = []
    providers_by_alias: dict[str, set[str]] = {alias: set() for alias in reference_lock["panel"]}
    for target in reference_lock["collections"]:
        alias = target["alias"]
        acquisition = toutes_acquisitions.get(target["collection_id"])
        if acquisition is None:
            slots.append({
                "slot_id": target["collection_id"],
                "alias": alias,
                "run": target["run"],
                "status": "pending",
                "compatibility_contract_sha256": plans[alias]["compatibility_contract"]["sha256"],
                "route_role": None,
                "acquisition": None,
            })
            continue
        source_cell = acquisition["cell"]
        _exiger(
            contrat_compatibilite(source_cell)["sha256"]
            == plans[alias]["compatibility_contract"]["sha256"],
            f"acquisition incompatible: {target['collection_id']}",
        )
        role = _route_autorisee(source_cell, target, plans[alias]["fallback"])
        preuve = acquisition["proof"]
        providers_by_alias[alias].add(preuve["route_identity"]["provider_pinned"])
        slots.append({
            "slot_id": target["collection_id"],
            "alias": alias,
            "run": target["run"],
            "status": "acquired",
            "compatibility_contract_sha256": plans[alias]["compatibility_contract"]["sha256"],
            "route_role": role,
            "acquisition": preuve,
        })

    acquired = sum(slot["status"] == "acquired" for slot in slots)
    pending = len(slots) - acquired
    accepted_cost = sum(
        slot["acquisition"]["cost_microdollars"]
        for slot in slots if slot["acquisition"] is not None
    )
    engaged = sum(source["engaged_microdollars"] for source in sources)
    recorded = sum(source["ledger_recorded_microdollars"] for source in sources)
    reconciled = sum(
        source["billing_reconciliation"]["reconciled_microdollars"]
        for source in sources
    )

    manifest = {
        "schema_version": SCHEMA_SERIE,
        "series_id": series_id,
        "status": "complete" if pending == 0 else "incomplete",
        "reference": {
            "campaign_id": reference_lock["campaign_id"],
            "campaign_path": _relatif_depot(reference_campaign),
            "lock_path": _relatif_depot(reference_lock_path),
            "lock_sha256": sha256_fichier(reference_lock_path),
            "campaign_lock_hash": reference_hash,
        },
        "instrument_context": {
            "task": copy.deepcopy(reference_lock["task"]),
            "axes": copy.deepcopy(reference_lock["axes"]),
        },
        "panel": copy.deepcopy(reference_lock["panel"]),
        "runs": reference_lock["runs"],
        "route_snapshot": {
            "path": _relatif_depot(route_snapshot_path),
            "sha256": snapshot_hash,
            "observed_at": snapshot["observed_at"],
        },
        "fallback_policy_version": POLITIQUE_FALLBACK,
        "route_plans": plans,
        "source_batches": sorted(sources, key=lambda source: source["campaign_id"]),
        "slots": slots,
        "counts": {
            "total": len(slots),
            "acquired": acquired,
            "pending": pending,
        },
        "routing_status_by_alias": {
            alias: (
                "not-acquired" if not providers
                else "multi-route" if len(providers) > 1
                else "single-route"
            )
            for alias, providers in providers_by_alias.items()
        },
        "costs": {
            "accepted_acquisitions_microdollars": accepted_cost,
            "source_ledger_recorded_microdollars": recorded,
            "source_billing_reconciled_microdollars": reconciled,
            "source_ledger_engaged_microdollars": engaged,
            "source_non_acquisition_microdollars": engaged - accepted_cost,
            "global_cap_microdollars": global_cap_microdollars,
            "global_cap_remaining_microdollars": global_cap_microdollars - engaged,
        },
    }
    _exiger(manifest["costs"]["global_cap_remaining_microdollars"] >= 0, "plafond global déjà dépassé")

    pending_aliases = {slot["alias"] for slot in slots if slot["status"] == "pending"}
    pending_slots_by_alias = {
        alias: sum(
            slot["status"] == "pending" and slot["alias"] == alias
            for slot in slots
        )
        for alias in pending_aliases
    }
    budget = snapshot.get("budget_reestimate")
    _exiger(isinstance(budget, dict), "base B0-09 absente du snapshot")
    estimate = _projection_microdollars(budget, pending_slots_by_alias)
    continuation = {
        "schema_version": SCHEMA_BROUILLON_CONTINUATION,
        "series_id": series_id,
        "batch_id": None,
        "operation": "acquire_pending_slots",
        "source_commit": None,
        "series_manifest_sha256": empreinte(manifest),
        "reference_campaign_lock_hash": reference_hash,
        "route_snapshot": copy.deepcopy(manifest["route_snapshot"]),
        "slots": [slot["slot_id"] for slot in slots if slot["status"] == "pending"],
        "aliases": [alias for alias in reference_lock["panel"] if alias in pending_aliases],
        "routes": {
            alias: {
                "primary": plans[alias]["primary_route"],
                "fallback": plans[alias]["fallback"],
                "fallback_unavailable_reason": plans[alias]["fallback_unavailable_reason"],
            }
            for alias in reference_lock["panel"] if alias in pending_aliases
        },
        "budget": {
            "currency": "USD",
            "source_ledger_engaged_microdollars": engaged,
            "primary_routes_estimate_microdollars": estimate,
            "combined_projection_microdollars": engaged + estimate,
            "global_cap_microdollars": global_cap_microdollars,
            "continuation_cap_max_microdollars": global_cap_microdollars - engaged,
            "formula": (
                "ceil(sum(repriced_alias_4_runs * pending_slots_alias / 4) "
                "* 83/76)"
            ),
            "fallback_pricing_scenario": _projection_fallback(
                budget,
                {alias: plans[alias] for alias in pending_aliases},
                pending_slots_by_alias,
            ),
        },
        "gates": {
            "b0_08_primary_routes": "APPROVED_FROM_REFERENCE_SNAPSHOT",
            "b0_08_fallback_routes": "HOLD_EXPLICIT_APPROVAL_REQUIRED",
            "b0_09": "HOLD_EXPLICIT_APPROVAL_REQUIRED",
            "b0_10": "HOLD",
            "source_commit": "HOLD_UNCOMMITTED",
        },
    }
    return manifest, continuation


def approuver_continuation(
    continuation: dict[str, Any],
    source_commit: str,
    fallbacks_approuves: dict[str, str],
    estimation_approuvee_microdollars: int,
    approved_at: str,
) -> dict[str, Any]:
    _exiger(
        re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None,
        "commit source de continuation invalide",
    )
    _exiger(isinstance(approved_at, str) and approved_at,
            "date d'approbation absente")
    budget = continuation["budget"]
    _exiger(
        estimation_approuvee_microdollars
        == budget["primary_routes_estimate_microdollars"],
        "estimation B0-09 approuvée différente du brouillon",
    )
    attendus: dict[str, str] = {}
    approbations = []
    for alias, plan in continuation["routes"].items():
        fallback = plan.get("fallback")
        if fallback is None:
            continue
        route = fallback["route_identity"]
        attendus[alias] = route["provider_pinned"]
        approbations.append({
            "alias": alias,
            "provider": route["provider_pinned"],
            "endpoint_tag": route["endpoint_tag"],
        })
    _exiger(fallbacks_approuves == attendus,
            "approbation des fallbacks différente des routes proposées")
    continuation["source_commit"] = source_commit
    continuation["approvals"] = {
        "approved_by": "Ayo",
        "approved_at": approved_at,
        "fallback_routes": sorted(approbations, key=lambda x: x["alias"]),
        "b0_09": {
            "estimate_microdollars": estimation_approuvee_microdollars,
            "global_cap_microdollars": budget["global_cap_microdollars"],
        },
    }
    continuation["gates"] = {
        "b0_08_primary_routes": "APPROVED_FROM_REFERENCE_SNAPSHOT",
        "b0_08_fallback_routes": "APPROVED",
        "b0_09": "APPROVED",
        "b0_10": "HOLD",
        "source_commit": "LOCKED",
    }
    return continuation


def construire_lock_continuation(
    campaign_id: str,
    created_at: str,
    source_commit: str,
    reference_campaign: Path,
    inventory_path: Path,
    manifest: dict[str, Any],
    continuation: dict[str, Any],
) -> dict[str, Any]:
    reference_lock_path, reference_lock, reference_hash = _charger_campagne(
        reference_campaign
    )
    _exiger(continuation.get("gates", {}).get("b0_10") == "HOLD",
            "B0-10 doit rester en HOLD dans le lock préparé")
    _exiger(continuation.get("source_commit") == source_commit,
            "commit du brouillon différent du lock")
    target_ids = set(continuation["slots"])
    cellules = [
        copy.deepcopy(cellule)
        for cellule in reference_lock["collections"]
        if cellule["collection_id"] in target_ids
    ]
    _exiger(
        {cellule["collection_id"] for cellule in cellules} == target_ids,
        "slots de continuation absents du lock de référence",
    )
    panel = copy.deepcopy(continuation["aliases"])
    backends = sorted({
        cellule["execution_manifest"]["backend"] for cellule in cellules
    })
    providers = sorted({
        cellule["execution_manifest"]["provider_pinned"] for cellule in cellules
    })
    quotas_reference = reference_lock["quotas"]
    budget_continuation = continuation["budget"]
    approvals = continuation["approvals"]
    deferred = continuation.get("deferred_pending_slots") or {
        "slots": [], "reason": "HOLD_RUNTIME_METADATA_CONFLICT"
    }
    _exiger(
        isinstance(deferred, dict)
        and isinstance(deferred.get("slots"), list)
        and deferred.get("reason") == "HOLD_RUNTIME_METADATA_CONFLICT",
        "slots différés invalides dans le brouillon",
    )
    lock = {
        "schema_version": SCHEMA_LOCK_CONTINUATION,
        "protocol_version": reference_lock["protocol_version"],
        "failure_scope_policy": {"version": POLITIQUE_PORTEE_ECHEC},
        "campaign_id": campaign_id,
        "operation": "continuation_collection",
        "question": (
            f"Compléter les {len(cellules)} slots absents de la série "
            f"{continuation['series_id']}"
        ),
        "created_at": created_at,
        "paid_authorization_required": True,
        "repository_source": {"commit": source_commit},
        "instrument_source": {
            "commit": reference_lock["repository_source"]["commit"],
            "reference_lock_path": _relatif_depot(reference_lock_path),
            "reference_lock_sha256": sha256_fichier(reference_lock_path),
            "reference_campaign_lock_hash": reference_hash,
        },
        "series_source": {
            "series_id": continuation["series_id"],
            "inventory_path": _relatif_depot(inventory_path),
            "inventory_sha256": sha256_fichier(inventory_path),
            "inventory_hash": empreinte(manifest),
            "global_cap_microdollars": budget_continuation[
                "global_cap_microdollars"
            ],
            "source_ledger_engaged_microdollars": budget_continuation[
                "source_ledger_engaged_microdollars"
            ],
            "continuation_cap_microdollars": budget_continuation[
                "continuation_cap_max_microdollars"
            ],
            "approved_estimate_microdollars": approvals["b0_09"][
                "estimate_microdollars"
            ],
            "approved_fallback_routes": copy.deepcopy(
                approvals["fallback_routes"]
            ),
            "deferred_pending_slots": [
                {
                    "collection_id": collection_id,
                    "reason": deferred["reason"],
                }
                for collection_id in sorted(deferred["slots"])
            ],
        },
        "environments": copy.deepcopy(reference_lock["environments"]),
        "panel": panel,
        "runs": reference_lock["runs"],
        "attempts_max": reference_lock["attempts_max"],
        "runner": copy.deepcopy(reference_lock["runner"]),
        "quotas": {
            "attempts_total_max": len(cellules) * reference_lock["attempts_max"],
            "in_flight_by_backend": {
                backend: quotas_reference["in_flight_by_backend"][backend]
                for backend in backends
            },
            "in_flight_by_provider": {
                provider: quotas_reference["in_flight_by_provider"][provider]
                for provider in providers
            },
        },
        "selection_policy": copy.deepcopy(reference_lock["selection_policy"]),
        "task": copy.deepcopy(reference_lock["task"]),
        "axes": copy.deepcopy(reference_lock["axes"]),
        "collections": cellules,
        "budget": {
            "currency": "USD",
            "cap_microdollars": budget_continuation[
                "continuation_cap_max_microdollars"
            ],
            "estimate_microdollars": approvals["b0_09"][
                "estimate_microdollars"
            ],
            "estimate_source": (
                "acquisition-inventory/v1 "
                f"{empreinte(manifest)}, B0-09 approuvé"
            ),
        },
        "registry_source": copy.deepcopy(reference_lock["registry_source"]),
        "route_snapshot_source": copy.deepcopy(
            reference_lock["route_snapshot_source"]
        ),
    }
    return valider_lock(lock)


def _fallbacks_cli(valeurs: list[str]) -> dict[str, str]:
    resultat: dict[str, str] = {}
    for valeur in valeurs:
        alias, sep, provider = valeur.partition("=")
        _exiger(bool(sep) and bool(alias) and bool(provider),
                f"fallback approuvé invalide: {valeur}")
        _exiger(alias not in resultat, f"fallback approuvé dupliqué: {alias}")
        resultat[alias] = provider
    return resultat


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--series-id", required=True)
    ap.add_argument("--reference-campaign", type=Path, required=True)
    ap.add_argument("--source-campaign", type=Path, action="append", required=True)
    ap.add_argument("--route-snapshot", type=Path, required=True)
    ap.add_argument("--global-cap-microdollars", type=int, required=True)
    ap.add_argument("--expect-acquired", type=int)
    ap.add_argument("--expect-pending", type=int)
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--created-at", required=True)
    ap.add_argument("--approved-at", required=True)
    ap.add_argument("--approved-estimate-microdollars", type=int, required=True)
    ap.add_argument("--approved-fallback", action="append", default=[])
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    try:
        manifest, continuation = construire_serie(
            args.series_id,
            args.reference_campaign,
            args.source_campaign,
            args.route_snapshot,
            args.global_cap_microdollars,
        )
        if args.expect_acquired is not None:
            _exiger(
                manifest["counts"]["acquired"] == args.expect_acquired,
                "nombre d'acquisitions différent de l'attendu",
            )
        if args.expect_pending is not None:
            _exiger(
                manifest["counts"]["pending"] == args.expect_pending,
                "nombre de slots pendants différent de l'attendu",
            )
        continuation["batch_id"] = args.out_dir.name
        continuation["series_manifest_sha256"] = empreinte(manifest)
        approuver_continuation(
            continuation,
            args.source_commit,
            _fallbacks_cli(args.approved_fallback),
            args.approved_estimate_microdollars,
            args.approved_at,
        )
        inventory_path = args.out_dir / "series-manifest.v1.json"
        ecrire_json_immuable(inventory_path, manifest)
        lock = construire_lock_continuation(
            args.out_dir.name,
            args.created_at,
            args.source_commit,
            args.reference_campaign,
            inventory_path,
            manifest,
            continuation,
        )
        valider_lock(lock, RACINE)
        lock_path = args.out_dir / "campaign.lock.v6.json"
        ecrire_json_immuable(lock_path, lock)
        continuation["campaign_lock"] = {
            "path": _relatif_depot(lock_path),
            "sha256": sha256_fichier(lock_path),
            "campaign_lock_hash": empreinte_lock(lock),
        }
        ecrire_json_immuable(
            args.out_dir / "continuation-draft.v1.json", continuation
        )
    except (ContratV2Invalide, OSError) as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "PREPARED_LOCAL_ONLY",
        "series_manifest_sha256": empreinte(manifest),
        "slots": manifest["counts"],
        "primary_routes_estimate_microdollars": continuation["budget"][
            "primary_routes_estimate_microdollars"
        ],
        "combined_projection_microdollars": continuation["budget"][
            "combined_projection_microdollars"
        ],
        "campaign_lock_hash": empreinte_lock(lock),
        "source_commit": args.source_commit,
        "b0_10": "HOLD",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
