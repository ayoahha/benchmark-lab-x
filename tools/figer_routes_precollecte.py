# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""Figer les métadonnées publiques des routes d'une intention de campagne v3"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import tomllib
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any

import requests

from choisir_provider import (
    CRITERE_VERSION,
    CRITERE_VERSION_HISTORIQUE,
    budget_de,
    contrat_quantification,
    editeur_canonique,
    est_editeur,
    evaluer,
    norm,
)
from protocole_v2 import (
    ContratV2Invalide,
    ESTIMATION_B0_HISTORIQUE,
    PANEL_B0,
    PLAFOND_B0_HISTORIQUE,
    ecrire_json_immuable,
    resoudre_sous,
)


SCHEMA = "benchmark-lab-x/route-preflight-snapshot/v1"
SCHEMA_CIBLE = "benchmark-lab-x/route-preflight-snapshot/v3"
SCHEMA_CIBLE_HISTORIQUE = "benchmark-lab-x/route-preflight-snapshot/v2"
API_MODELE = "https://openrouter.ai/api/v1/models/{model}/endpoints"
ESTIMATION_APPROUVEE = ESTIMATION_B0_HISTORIQUE
ESTIMATION_PRECEDENTE = 31_778_838
PLAFOND_APPROUVE = PLAFOND_B0_HISTORIQUE
SNAPSHOT_PRECEDENT_SHA256 = "a066652cc46a53a307a7e96da86fc334c898523ae10b031c6786fba6b078b169"
HTTP_TIMEOUT_S = 20


class SnapshotRoutesInvalide(ValueError):
    """Le snapshot ne permet pas de soutenir la porte précollecte"""


def empreinte_octets(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decimal_str(value: Decimal) -> str:
    texte = format(value, "f")
    return texte.rstrip("0").rstrip(".") if "." in texte else texte


def prix_par_million(pricing: dict[str, Any], cle: str) -> str:
    brut = pricing.get(cle)
    if brut in (None, ""):
        return "0"
    try:
        valeur = Decimal(str(brut)) * Decimal(1_000_000)
    except Exception as exc:
        raise SnapshotRoutesInvalide(f"prix {cle} non décimal: {brut}") from exc
    if not valeur.is_finite() or valeur < 0:
        raise SnapshotRoutesInvalide(f"prix {cle} négatif ou non fini")
    return decimal_str(valeur)


def charger_registre(path: Path) -> dict[str, dict[str, Any]]:
    try:
        objet = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SnapshotRoutesInvalide(f"registre illisible: {path}") from exc
    if not isinstance(objet, dict):
        raise SnapshotRoutesInvalide("registre de modèles invalide")
    return objet


def lire_endpoint(model: str) -> tuple[dict[str, Any], str, str, str]:
    url = API_MODELE.format(model=model)
    try:
        reponse = requests.get(url, headers={"Accept": "application/json"}, timeout=HTTP_TIMEOUT_S)
        reponse.raise_for_status()
    except requests.RequestException as exc:
        raise SnapshotRoutesInvalide(f"ROUTE_METADATA_UNREACHABLE: {model}") from exc
    data = reponse.content
    try:
        objet = reponse.json()
    except ValueError as exc:
        raise SnapshotRoutesInvalide(f"métadonnées JSON invalides: {model}") from exc
    if not isinstance(objet, dict):
        raise SnapshotRoutesInvalide(f"objet de métadonnées invalide: {model}")
    try:
        brut = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SnapshotRoutesInvalide(f"métadonnées non UTF-8: {model}") from exc
    return objet, empreinte_octets(data), url, brut


def selectionner_routes(registre: dict[str, dict[str, Any]], observe_at: str) -> dict[str, Any]:
    par_modele: dict[str, list[str]] = {}
    for alias in PANEL_B0:
        par_modele.setdefault(registre[alias]["model"], []).append(alias)

    modeles: dict[str, Any] = {}
    resolved: dict[str, Any] = {}
    for model, aliases in par_modele.items():
        reference = next(
            (registre[a].get("format_reference") for a in aliases if registre[a].get("format_reference")),
            None,
        )
        objet, response_hash, url, _ = lire_endpoint(model)
        endpoints = ((objet.get("data") or {}).get("endpoints") or [])
        if not isinstance(endpoints, list) or not endpoints:
            raise SnapshotRoutesInvalide(f"aucun endpoint: {model}")
        classes = [evaluer(ep, model, reference) for ep in endpoints]
        eligibles = sorted((x for x in classes if not x["exclusions"]), key=lambda x: x["_cle"])
        if not eligibles:
            raise SnapshotRoutesInvalide(f"aucune route conforme: {model}")
        tag = eligibles[0]["tag"]
        endpoint = next((ep for ep in endpoints if ep.get("tag") == tag), None)
        if not isinstance(endpoint, dict):
            raise SnapshotRoutesInvalide(f"endpoint recommandé introuvable: {model}/{tag}")
        pricing = endpoint.get("pricing")
        if not isinstance(pricing, dict):
            raise SnapshotRoutesInvalide(f"prix absents: {model}/{tag}")
        max_tokens = budget_de(endpoint)
        if max_tokens < 1:
            raise SnapshotRoutesInvalide(f"budget de sortie non positif: {model}/{tag}")
        route_commune = {
            "metadata_status": "resolved",
            "selected_tag": tag,
            "provider_name": endpoint.get("provider_name") or "opaque",
            "quantization": endpoint.get("quantization") or "unknown",
            "revision": endpoint.get("model_name") or endpoint.get("model_id") or "opaque",
            "criterion_version": CRITERE_VERSION_HISTORIQUE,
            "price_source": url,
            "price_observed_at": observe_at,
            "input_usd_per_million_tokens": prix_par_million(pricing, "prompt"),
            "output_usd_per_million_tokens": prix_par_million(pricing, "completion"),
            "request_usd": decimal_str(Decimal(str(pricing.get("request") or "0"))),
            "max_tokens": max_tokens,
        }
        pins = {}
        for alias in aliases:
            pin = registre[alias].get("provider")
            correspond = norm(pin) in {
                norm(tag),
                norm(str(tag).split("/")[0]),
                norm(endpoint.get("provider_name")),
            }
            pins[alias] = {"provider": pin, "matches_recommendation": correspond}
            if not correspond:
                raise SnapshotRoutesInvalide(f"pin différent du critère: {alias}: {pin} != {tag}")
            resolved[alias] = {**route_commune, "provider": pin}
        routes_publiees = []
        for route in classes:
            copie = {k: v for k, v in route.items() if k != "_cle"}
            routes_publiees.append(copie)
        modeles[model] = {
            "metadata_url": url,
            "metadata_response_sha256": response_hash,
            "format_reference": reference,
            "recommended_tag": tag,
            "pins": pins,
            "routes": routes_publiees,
            "selected_pricing_raw": pricing,
        }
    return {"models": modeles, "resolved": resolved}


def chemin_run_historique(racine: Path, run: dict[str, Any]) -> Path:
    tentative = int(run.get("tentative") or 1)
    nom = f"pentagone-rotatif__{run['alias']}__r{run['run']}"
    if tentative > 1:
        nom += f"__a{tentative}"
    return racine / nom / "meta.json"


def recalculer_budget(snapshot: dict[str, Any], historique: Path) -> dict[str, Any]:
    results_path = historique / "results-data.json"
    try:
        results_data = results_path.read_bytes()
        results = json.loads(results_data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotRoutesInvalide("résultats historiques illisibles") from exc
    retenus = [r for r in results.get("runs", []) if r.get("tentative_retenue") is True]
    if len(retenus) != 76:
        raise SnapshotRoutesInvalide(f"76 runs historiques attendus, trouvé {len(retenus)}")
    par_alias: dict[str, dict[str, int | str]] = {}
    sources = [{
        "kind": "results_data",
        "path": results_path.as_posix(),
        "sha256": empreinte_octets(results_data),
    }]
    total_reprice = Decimal(0)
    total_historique = Decimal(0)
    for run in retenus:
        alias = run["alias"]
        route = snapshot["resolved"].get(alias)
        if not isinstance(route, dict):
            raise SnapshotRoutesInvalide(f"route résolue absente: {alias}")
        meta_path = chemin_run_historique(historique, run)
        try:
            meta_data = meta_path.read_bytes()
            meta = json.loads(meta_data.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SnapshotRoutesInvalide(f"reçu historique illisible: {meta_path}") from exc
        sources.append({
            "kind": "run_metadata",
            "path": meta_path.as_posix(),
            "sha256": empreinte_octets(meta_data),
            "alias": alias,
            "run": run["run"],
            "attempt": int(run.get("tentative") or 1),
        })
        usage = meta.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        if not isinstance(prompt_tokens, int) or not isinstance(completion_tokens, int):
            raise SnapshotRoutesInvalide(f"jetons historiques absents: {meta_path}")
        entree = Decimal(route["input_usd_per_million_tokens"]) / Decimal(1_000_000)
        sortie = Decimal(route["output_usd_per_million_tokens"]) / Decimal(1_000_000)
        requete = Decimal(route["request_usd"])
        courant = entree * prompt_tokens + sortie * completion_tokens + requete
        ancien = Decimal(str(meta.get("cost_usd") or 0))
        total_reprice += courant
        total_historique += ancien
        bloc = par_alias.setdefault(alias, {
            "runs": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "historical_microdollars": 0,
            "repriced_microdollars": 0,
        })
        bloc["runs"] = int(bloc["runs"]) + 1
        bloc["prompt_tokens"] = int(bloc["prompt_tokens"]) + prompt_tokens
        bloc["completion_tokens"] = int(bloc["completion_tokens"]) + completion_tokens
        bloc["historical_microdollars"] = int(bloc["historical_microdollars"]) + math.ceil(ancien * 1_000_000)
        bloc["repriced_microdollars"] = int(bloc["repriced_microdollars"]) + math.ceil(courant * 1_000_000)

    for alias, bloc in par_alias.items():
        route = snapshot["resolved"][alias]
        cout_alias = (
            Decimal(route["input_usd_per_million_tokens"])
            / Decimal(1_000_000) * int(bloc["prompt_tokens"])
            + Decimal(route["output_usd_per_million_tokens"])
            / Decimal(1_000_000) * int(bloc["completion_tokens"])
            + Decimal(route["request_usd"]) * int(bloc["runs"])
        )
        bloc["repriced_microdollars"] = int(
            (cout_alias * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING)
        )

    prompts = results.get("cycle_de_vie", {}).get("prompts_partis")
    runs_attendus = results.get("cycle_de_vie", {}).get("runs_attendus")
    if prompts != 83 or runs_attendus != 76:
        raise SnapshotRoutesInvalide("facteur historique 83/76 absent")
    projection = total_reprice * Decimal(6) / Decimal(4) * Decimal(prompts) / Decimal(runs_attendus)
    projection_micro = int(
        (projection * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING)
    )
    delta = projection_micro - ESTIMATION_APPROUVEE
    sources = [sources[0], *sorted(sources[1:], key=lambda entree: entree["path"])]
    sources_hash = empreinte_octets(json.dumps(
        sources, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))
    return {
        "historical_source": str(results_path),
        "historical_source_sha256": empreinte_octets(results_data),
        "historical_inputs": sources,
        "historical_inputs_sha256": sources_hash,
        "historical_runs": 76,
        "historical_provider_prompts": 83,
        "historical_recorded_microdollars": int(
            (total_historique * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING)
        ),
        "same_76_repriced_microdollars": int(
            (total_reprice * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING)
        ),
        "projection_method": "prix courants × jetons historiques × 6/4 × 83/76",
        "approved_estimate_microdollars": ESTIMATION_APPROUVEE,
        "repriced_estimate_microdollars": projection_micro,
        "delta_microdollars": delta,
        "approved_cap_microdollars": PLAFOND_APPROUVE,
        "margin_to_cap_microdollars": PLAFOND_APPROUVE - projection_micro,
        "status": (
            "B0_09_UNCHANGED"
            if delta == 0
            else "HOLD_B0_09_REAPPROVAL_REQUIRED"
        ),
        "by_alias": par_alias,
    }


def produire(models_file: Path, historique: Path) -> dict[str, Any]:
    observe_at = datetime.now(timezone.utc).isoformat()
    registre = charger_registre(models_file)
    snapshot = {
        "schema_version": SCHEMA,
        "observed_at": observe_at,
        "criterion_version": CRITERE_VERSION_HISTORIQUE,
        "models_file": str(models_file),
        "models_file_sha256": empreinte_octets(models_file.read_bytes()),
        "panel": list(PANEL_B0),
        **selectionner_routes(registre, observe_at),
    }
    snapshot["budget_reestimate"] = recalculer_budget(snapshot, historique)
    valider(snapshot)
    return snapshot


def valider(
    snapshot: dict[str, Any],
    estimation_approuvee: int = ESTIMATION_APPROUVEE,
) -> dict[str, Any]:
    if snapshot.get("schema_version") != SCHEMA:
        raise SnapshotRoutesInvalide("schéma de snapshot invalide")
    if snapshot.get("criterion_version") != CRITERE_VERSION_HISTORIQUE:
        raise SnapshotRoutesInvalide("critère de route différent")
    if tuple(snapshot.get("panel") or ()) != PANEL_B0:
        raise SnapshotRoutesInvalide("panel différent de B0-06")
    resolved = snapshot.get("resolved")
    if not isinstance(resolved, dict) or set(resolved) != set(PANEL_B0):
        raise SnapshotRoutesInvalide("résolution des 19 alias incomplète")
    modeles = snapshot.get("models")
    if not isinstance(modeles, dict) or len(modeles) != 13:
        raise SnapshotRoutesInvalide("résolution des 13 modèles incomplète")
    for model, bloc in modeles.items():
        empreinte = bloc.get("metadata_response_sha256") if isinstance(bloc, dict) else None
        if not isinstance(empreinte, str) or len(empreinte) != 64:
            raise SnapshotRoutesInvalide(f"empreinte de métadonnées absente: {model}")
        pins = bloc.get("pins")
        if not isinstance(pins, dict) or not all(
            isinstance(pin, dict) and pin.get("matches_recommendation") is True
            for pin in pins.values()
        ):
            raise SnapshotRoutesInvalide(f"pin non conforme au critère: {model}")
    for alias, route in resolved.items():
        if route.get("metadata_status") != "resolved" or not route.get("selected_tag"):
            raise SnapshotRoutesInvalide(f"route non résolue: {alias}")
        for cle in (
            "provider", "quantization", "revision", "criterion_version", "price_source",
            "price_observed_at", "input_usd_per_million_tokens",
            "output_usd_per_million_tokens", "request_usd",
        ):
            if not isinstance(route.get(cle), str) or not route[cle]:
                raise SnapshotRoutesInvalide(f"{cle} absent: {alias}")
        if not isinstance(route.get("max_tokens"), int) or route["max_tokens"] < 1:
            raise SnapshotRoutesInvalide(f"max_tokens invalide: {alias}")
    budget = snapshot.get("budget_reestimate")
    if not isinstance(budget, dict):
        raise SnapshotRoutesInvalide("recalcul budgétaire absent")
    par_alias = budget.get("by_alias")
    if not isinstance(par_alias, dict) or set(par_alias) != set(PANEL_B0):
        raise SnapshotRoutesInvalide("base de recalcul par alias incomplète")
    total_reprice = Decimal(0)
    for alias, compteurs in par_alias.items():
        route = resolved[alias]
        if not isinstance(compteurs, dict) or compteurs.get("runs") != 4:
            raise SnapshotRoutesInvalide(f"quatre runs historiques absents: {alias}")
        entree = Decimal(route["input_usd_per_million_tokens"]) / Decimal(1_000_000)
        sortie = Decimal(route["output_usd_per_million_tokens"]) / Decimal(1_000_000)
        requete = Decimal(route["request_usd"])
        total_reprice += (
            entree * compteurs["prompt_tokens"]
            + sortie * compteurs["completion_tokens"]
            + requete * compteurs["runs"]
        )
    meme_76 = int(
        (total_reprice * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING)
    )
    projection = int(
        (
            total_reprice
            * Decimal(6) / Decimal(4)
            * Decimal(83) / Decimal(76)
            * Decimal(1_000_000)
        ).to_integral_value(rounding=ROUND_CEILING)
    )
    if budget.get("same_76_repriced_microdollars") != meme_76:
        raise SnapshotRoutesInvalide("recalcul des 76 runs incohérent")
    if budget.get("repriced_estimate_microdollars") != projection:
        raise SnapshotRoutesInvalide("projection B0-09 incohérente")
    if budget.get("approved_estimate_microdollars") != estimation_approuvee:
        raise SnapshotRoutesInvalide("estimation approuvée incohérente")
    attendu_delta = budget.get("repriced_estimate_microdollars") - estimation_approuvee
    if budget.get("delta_microdollars") != attendu_delta:
        raise SnapshotRoutesInvalide("delta budgétaire incohérent")
    attendu_status = "B0_09_UNCHANGED" if attendu_delta == 0 else "HOLD_B0_09_REAPPROVAL_REQUIRED"
    if budget.get("status") != attendu_status or budget.get("approved_cap_microdollars") != PLAFOND_APPROUVE:
        raise SnapshotRoutesInvalide("porte B0-09 incohérente")
    approbation = snapshot.get("b0_09_approval")
    if approbation is not None:
        if not isinstance(approbation, dict):
            raise SnapshotRoutesInvalide("approbation B0-09 invalide")
        if (
            approbation.get("schema_version")
            != "benchmark-lab-x/b0-09-approval/v1"
            or approbation.get("decision") != "B0_09_REVISED_ESTIMATE_APPROVED"
            or approbation.get("approved_by") != "Ayo"
            or not isinstance(approbation.get("approved_at"), str)
            or not approbation["approved_at"]
            or approbation.get("estimate_microdollars") != estimation_approuvee
            or approbation.get("cap_microdollars") != PLAFOND_APPROUVE
            or approbation.get("source_snapshot_sha256") != SNAPSHOT_PRECEDENT_SHA256
        ):
            raise SnapshotRoutesInvalide("approbation B0-09 incohérente")
    return {
        "status": budget["status"],
        "aliases_resolved": len(resolved),
        "models_resolved": len(snapshot.get("models") or {}),
        "repriced_estimate_microdollars": budget["repriced_estimate_microdollars"],
        "approved_cap_microdollars": budget["approved_cap_microdollars"],
    }


def approuver_snapshot(source_path: Path, approved_at: str) -> dict[str, Any]:
    data = source_path.read_bytes()
    if empreinte_octets(data) != SNAPSHOT_PRECEDENT_SHA256:
        raise SnapshotRoutesInvalide("snapshot source différent de la porte B0-09 approuvée")
    try:
        source = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotRoutesInvalide("snapshot source illisible") from exc
    valider(source, ESTIMATION_PRECEDENTE)
    snapshot = copy.deepcopy(source)
    budget = snapshot["budget_reestimate"]
    budget["approved_estimate_microdollars"] = ESTIMATION_APPROUVEE
    budget["delta_microdollars"] = (
        budget["repriced_estimate_microdollars"] - ESTIMATION_APPROUVEE
    )
    budget["status"] = (
        "B0_09_UNCHANGED"
        if budget["delta_microdollars"] == 0
        else "HOLD_B0_09_REAPPROVAL_REQUIRED"
    )
    snapshot["b0_09_approval"] = {
        "schema_version": "benchmark-lab-x/b0-09-approval/v1",
        "decision": "B0_09_REVISED_ESTIMATE_APPROVED",
        "approved_by": "Ayo",
        "approved_at": approved_at,
        "estimate_microdollars": ESTIMATION_APPROUVEE,
        "cap_microdollars": PLAFOND_APPROUVE,
        "source_snapshot_path": source_path.as_posix(),
        "source_snapshot_sha256": SNAPSHOT_PRECEDENT_SHA256,
        "scope": "local_lock_only_no_chromium_no_paid_collection_no_git_publication",
    }
    valider(snapshot)
    return snapshot


def main_historique() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--check", type=Path)
    ap.add_argument("--approve-from", type=Path)
    ap.add_argument("--approved-at")
    ap.add_argument("--models-file", type=Path, default=Path("models.toml"))
    ap.add_argument(
        "--historical",
        type=Path,
        default=Path("runs/2026-08-06-reference-v2"),
    )
    args = ap.parse_args()
    try:
        if args.check:
            snapshot = json.loads(args.check.read_text(encoding="utf-8"))
            resultat = valider(snapshot)
        elif args.approve_from:
            if not args.approved_at:
                raise SnapshotRoutesInvalide("--approved-at requis avec --approve-from")
            snapshot = approuver_snapshot(args.approve_from, args.approved_at)
            ecrire_json_immuable(args.out, snapshot)
            resultat = valider(snapshot)
        else:
            snapshot = produire(args.models_file, args.historical)
            ecrire_json_immuable(args.out, snapshot)
            resultat = valider(snapshot)
    except (SnapshotRoutesInvalide, OSError, json.JSONDecodeError, TypeError) as exc:
        print(f"HOLD: {exc}")
        return 2
    print(json.dumps(resultat, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if resultat["status"] == "B0_09_UNCHANGED" else 2


def _selectionner_routes_cible_v2(
    registre: dict[str, dict[str, Any]], panel: list[str], observed_at: str
) -> dict[str, Any]:
    par_modele: dict[str, list[str]] = {}
    for alias in panel:
        entree = registre.get(alias)
        if not isinstance(entree, dict) or not isinstance(entree.get("model"), str):
            raise SnapshotRoutesInvalide(f"alias absent du registre: {alias}")
        par_modele.setdefault(entree["model"], []).append(alias)

    modeles: dict[str, Any] = {}
    resolved: dict[str, Any] = {}
    for model, aliases in par_modele.items():
        reference = next(
            (registre[a].get("format_reference") for a in aliases
             if registre[a].get("format_reference")),
            None,
        )
        objet, response_hash, url, _ = lire_endpoint(model)
        endpoints = ((objet.get("data") or {}).get("endpoints") or [])
        if not isinstance(endpoints, list) or not endpoints:
            raise SnapshotRoutesInvalide(f"aucun endpoint: {model}")
        classes = [evaluer(endpoint, model, reference) for endpoint in endpoints]
        eligibles = sorted(
            (route for route in classes if not route["exclusions"]),
            key=lambda route: route["_cle"],
        )
        if not eligibles:
            raise SnapshotRoutesInvalide(f"aucune route conforme: {model}")
        tag = eligibles[0]["tag"]
        endpoint = next((ep for ep in endpoints if ep.get("tag") == tag), None)
        if not isinstance(endpoint, dict):
            raise SnapshotRoutesInvalide(f"endpoint sélectionné absent: {model}/{tag}")
        pricing = endpoint.get("pricing")
        if not isinstance(pricing, dict):
            raise SnapshotRoutesInvalide(f"prix absents: {model}/{tag}")
        max_tokens = budget_de(endpoint)
        if max_tokens < 1:
            raise SnapshotRoutesInvalide(f"budget de sortie non positif: {model}/{tag}")
        quantification = endpoint.get("quantization")
        revision = endpoint.get("model_name") or endpoint.get("model_id")
        if not isinstance(quantification, str) or quantification.lower() in {"unknown", "opaque"}:
            raise SnapshotRoutesInvalide(f"quantification obligatoire non résolue: {model}/{tag}")
        if not isinstance(revision, str) or revision.lower() in {"unknown", "opaque"}:
            raise SnapshotRoutesInvalide(f"révision obligatoire non résolue: {model}/{tag}")
        provider_name = endpoint.get("provider_name")
        for alias in aliases:
            pin = registre[alias].get("provider")
            correspond = norm(pin) in {
                norm(tag), norm(str(tag).split("/")[0]), norm(provider_name)
            }
            if not correspond:
                raise SnapshotRoutesInvalide(
                    f"pin différent du critère: {alias}: {pin} != {tag}"
                )
            resolved[alias] = {
                "metadata_status": "resolved",
                "backend": "openrouter",
                "provider": pin,
                "expect_provider": registre[alias].get("expect_provider") or provider_name or pin,
                "quantization": quantification,
                "revision": revision,
                "criterion_version": CRITERE_VERSION_HISTORIQUE,
                "price_source": url,
                "price_observed_at": observed_at,
                "input_usd_per_million_tokens": prix_par_million(pricing, "prompt"),
                "output_usd_per_million_tokens": prix_par_million(pricing, "completion"),
                "request_usd": decimal_str(Decimal(str(pricing.get("request") or "0"))),
                "max_tokens": max_tokens,
            }
        modeles[model] = {
            "metadata_url": url,
            "metadata_response_sha256": response_hash,
            "selected_tag": tag,
        }
    return {"models": modeles, "resolved": resolved}


def valider_cible_historique_v2(snapshot: dict[str, Any]) -> dict[str, Any]:
    champs = {
        "schema_version", "panel", "observed_at", "criterion_version",
        "models_file", "models_file_sha256", "models", "resolved",
    }
    if not isinstance(snapshot, dict) or set(snapshot) != champs:
        raise SnapshotRoutesInvalide("champs du snapshot v2 différents du contrat fermé")
    if snapshot.get("schema_version") != SCHEMA_CIBLE_HISTORIQUE:
        raise SnapshotRoutesInvalide("route-preflight-snapshot/v2 absent")
    panel = snapshot.get("panel")
    if not isinstance(panel, list) or not panel or len(panel) != len(set(panel)):
        raise SnapshotRoutesInvalide("panel du snapshot invalide")
    if snapshot.get("criterion_version") != CRITERE_VERSION_HISTORIQUE:
        raise SnapshotRoutesInvalide("critère du snapshot différent")
    if not isinstance(snapshot.get("observed_at"), str) or not snapshot["observed_at"]:
        raise SnapshotRoutesInvalide("date d'observation absente")
    if not isinstance(snapshot.get("models_file"), str) or not snapshot["models_file"]:
        raise SnapshotRoutesInvalide("registre source absent")
    empreinte_models = snapshot.get("models_file_sha256")
    if not isinstance(empreinte_models, str) or len(empreinte_models) != 64:
        raise SnapshotRoutesInvalide("empreinte du registre invalide")
    resolved = snapshot.get("resolved")
    if not isinstance(resolved, dict) or set(resolved) != set(panel):
        raise SnapshotRoutesInvalide("routes résolues incomplètes")
    for alias, route in resolved.items():
        requis_textes = {
            "backend", "provider", "expect_provider", "quantization", "revision",
            "criterion_version", "price_source", "price_observed_at",
            "input_usd_per_million_tokens", "output_usd_per_million_tokens", "request_usd",
        }
        if route.get("metadata_status") != "resolved":
            raise SnapshotRoutesInvalide(f"route non résolue: {alias}")
        if any(not isinstance(route.get(cle), str) or not route[cle] for cle in requis_textes):
            raise SnapshotRoutesInvalide(f"route incomplète: {alias}")
        if route["quantization"].lower() in {"unknown", "opaque"}:
            raise SnapshotRoutesInvalide(f"quantification non résolue: {alias}")
        if route["revision"].lower() in {"unknown", "opaque"}:
            raise SnapshotRoutesInvalide(f"révision non résolue: {alias}")
        if not isinstance(route.get("max_tokens"), int) or route["max_tokens"] < 1:
            raise SnapshotRoutesInvalide(f"max_tokens invalide: {alias}")
    return {
        "status": "PREPARED_LOCAL_ONLY",
        "aliases_resolved": len(resolved),
        "models_resolved": len(snapshot.get("models") or {}),
    }


def _revision_endpoint(endpoint: dict[str, Any], model: str, tag: str) -> dict[str, str]:
    valeur = endpoint.get("model_id")
    if not isinstance(valeur, str) or not valeur.strip() or norm(valeur) in {"unknown", "opaque"}:
        raise SnapshotRoutesInvalide(f"révision endpoint_model_id absente: {model}/{tag}")
    return {"status": "declared", "kind": "endpoint_model_id", "value": valeur.strip()}


def _route_identity(endpoint: dict[str, Any], model: str, tag: str) -> dict[str, str]:
    provider_name = endpoint.get("provider_name")
    if not isinstance(provider_name, str) or not provider_name.strip():
        raise SnapshotRoutesInvalide(f"provider_name absent: {model}/{tag}")
    provider_slug = norm(str(tag).split("/")[0])
    publisher = editeur_canonique(model)
    if not provider_slug or publisher is None:
        raise SnapshotRoutesInvalide(f"identité éditeur non résolue: {model}/{tag}")
    return {
        "kind": "publisher_managed" if est_editeur(endpoint, model) else "third_party",
        "canonical_publisher": publisher,
        "provider_slug": provider_slug,
        "provider_name": provider_name.strip(),
        "endpoint_tag": tag,
    }


def selectionner_routes_cible(
    registre: dict[str, dict[str, Any]], panel: list[str], observed_at: str
) -> dict[str, Any]:
    """Résoudre les routes v3 et consigner les dérives de pin sans les appliquer"""
    par_modele: dict[str, list[str]] = {}
    for alias in panel:
        entree = registre.get(alias)
        if not isinstance(entree, dict) or not isinstance(entree.get("model"), str):
            raise SnapshotRoutesInvalide(f"alias absent du registre: {alias}")
        par_modele.setdefault(entree["model"], []).append(alias)

    modeles: dict[str, Any] = {}
    resolved: dict[str, Any] = {}
    pin_changes: list[dict[str, str]] = []
    for model, aliases in par_modele.items():
        reference = next(
            (registre[alias].get("format_reference") for alias in aliases
             if registre[alias].get("format_reference")),
            None,
        )
        objet, response_hash, url, response_body = lire_endpoint(model)
        endpoints = ((objet.get("data") or {}).get("endpoints") or [])
        if not isinstance(endpoints, list) or not endpoints:
            raise SnapshotRoutesInvalide(f"aucun endpoint: {model}")
        classes = [evaluer(endpoint, model, reference) for endpoint in endpoints]
        eligibles = sorted(
            (route for route in classes if not route["exclusions"]),
            key=lambda route: route["_cle"],
        )
        if not eligibles:
            raise SnapshotRoutesInvalide(f"aucune route conforme: {model}")
        tag = eligibles[0]["tag"]
        correspondants = [endpoint for endpoint in endpoints if endpoint.get("tag") == tag]
        if len(correspondants) != 1:
            raise SnapshotRoutesInvalide(f"endpoint sélectionné non unique: {model}/{tag}")
        endpoint = correspondants[0]
        pricing = endpoint.get("pricing")
        if not isinstance(pricing, dict):
            raise SnapshotRoutesInvalide(f"prix absents: {model}/{tag}")
        max_tokens = budget_de(endpoint)
        if max_tokens < 1:
            raise SnapshotRoutesInvalide(f"budget de sortie non positif: {model}/{tag}")
        identity = _route_identity(endpoint, model, tag)
        try:
            quantification = contrat_quantification(endpoint, model)
        except ValueError as exc:
            raise SnapshotRoutesInvalide(f"{exc}: {model}/{tag}") from exc
        if quantification["status"] == "not_disclosed" and identity["kind"] != "publisher_managed":
            raise SnapshotRoutesInvalide(f"not_disclosed interdit hors API éditeur: {model}/{tag}")
        revision = _revision_endpoint(endpoint, model, tag)
        evidence_modele = {
            "url": url,
            "observed_at": observed_at,
            "response_sha256": response_hash,
            "response_body": response_body,
        }
        evidence_route = {
            "url": url,
            "observed_at": observed_at,
            "response_sha256": response_hash,
        }
        route_commune = {
            "metadata_status": "resolved",
            "backend": "openrouter",
            "endpoint_tag": tag,
            "provider": identity["provider_slug"],
            "expect_provider": identity["provider_name"],
            "ownership": identity,
            "quantization": quantification,
            "revision": revision,
            "metadata_evidence": evidence_route,
            "criterion_version": CRITERE_VERSION,
            "price_source": url,
            "price_observed_at": observed_at,
            "input_usd_per_million_tokens": prix_par_million(pricing, "prompt"),
            "output_usd_per_million_tokens": prix_par_million(pricing, "completion"),
            "request_usd": decimal_str(Decimal(str(pricing.get("request") or "0"))),
            "max_tokens": max_tokens,
        }
        for alias in aliases:
            pin = registre[alias].get("provider")
            if not isinstance(pin, str) or not pin.strip():
                raise SnapshotRoutesInvalide(f"pin absent du registre: {alias}")
            if norm(pin) != identity["provider_slug"]:
                pin_changes.append({
                    "alias": alias,
                    "current_provider": pin,
                    "recommended_provider": identity["provider_slug"],
                    "endpoint_tag": tag,
                    "reason": "selection-route/v3",
                })
            resolved[alias] = dict(route_commune)
        modeles[model] = {
            "metadata_evidence": evidence_modele,
            "selected_route_identity": identity,
            "quantization": quantification,
            "revision": revision,
        }
    return {
        "models": modeles,
        "resolved": resolved,
        "pin_changes": sorted(pin_changes, key=lambda entree: entree["alias"]),
    }


def _valider_quantification(
    quantification: Any, ownership: dict[str, Any], chemin: str
) -> None:
    if not isinstance(quantification, dict):
        raise SnapshotRoutesInvalide(f"quantification structurée absente: {chemin}")
    if quantification.get("status") == "declared":
        if set(quantification) != {"status", "value"}:
            raise SnapshotRoutesInvalide(f"quantification declared ouverte: {chemin}")
        valeur = quantification.get("value")
        if not isinstance(valeur, str) or not valeur.strip() or norm(valeur) in {
            "unknown", "opaque", "native", "not-disclosed"
        }:
            raise SnapshotRoutesInvalide(f"valeur de quantification invalide: {chemin}")
        return
    attendu = {
        "status", "value", "basis", "publisher"
    }
    if (
        set(quantification) != attendu
        or quantification.get("status") != "not_disclosed"
        or quantification.get("value") is not None
        or quantification.get("basis") != "publisher_managed_api"
        or ownership.get("kind") != "publisher_managed"
        or quantification.get("publisher") != ownership.get("canonical_publisher")
    ):
        raise SnapshotRoutesInvalide(f"not_disclosed non autorisé: {chemin}")


def _valider_budget_cible(snapshot: dict[str, Any]) -> None:
    budget = snapshot.get("budget_reestimate")
    if not isinstance(budget, dict):
        raise SnapshotRoutesInvalide("recalcul B0-09 absent")
    sources = budget.get("historical_inputs")
    if not isinstance(sources, list) or len(sources) != 77:
        raise SnapshotRoutesInvalide("manifeste des 77 sources historiques incomplet")
    serialise = json.dumps(
        sources, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if budget.get("historical_inputs_sha256") != empreinte_octets(serialise):
        raise SnapshotRoutesInvalide("empreinte du manifeste historique invalide")
    if sources[0] != {
        "kind": "results_data",
        "path": budget.get("historical_source"),
        "sha256": budget.get("historical_source_sha256"),
    }:
        raise SnapshotRoutesInvalide("source results-data non liée au manifeste")
    meta_sources = sources[1:]
    if any(
        not isinstance(source, dict)
        or set(source) != {"kind", "path", "sha256", "alias", "run", "attempt"}
        or source.get("kind") != "run_metadata"
        or not isinstance(source.get("path"), str)
        or re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256"))) is None
        for source in meta_sources
    ):
        raise SnapshotRoutesInvalide("source meta historique invalide")
    if [source["path"] for source in meta_sources] != sorted(
        {source["path"] for source in meta_sources}
    ):
        raise SnapshotRoutesInvalide("sources meta non triées ou dupliquées")

    resolved = snapshot["resolved"]
    par_alias = budget.get("by_alias")
    if not isinstance(par_alias, dict) or set(par_alias) != set(snapshot["panel"]):
        raise SnapshotRoutesInvalide("base de recalcul par alias incomplète")
    total = Decimal(0)
    for alias, compteurs in par_alias.items():
        route = resolved[alias]
        if not isinstance(compteurs, dict) or compteurs.get("runs") != 4:
            raise SnapshotRoutesInvalide(f"quatre runs historiques absents: {alias}")
        entree = Decimal(route["input_usd_per_million_tokens"]) / Decimal(1_000_000)
        sortie = Decimal(route["output_usd_per_million_tokens"]) / Decimal(1_000_000)
        requete = Decimal(route["request_usd"])
        cout = (
            entree * compteurs["prompt_tokens"]
            + sortie * compteurs["completion_tokens"]
            + requete * compteurs["runs"]
        )
        total += cout
        attendu_alias = int(
            (cout * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING)
        )
        if compteurs.get("repriced_microdollars") != attendu_alias:
            raise SnapshotRoutesInvalide(f"recalcul par alias incohérent: {alias}")
    meme_76 = int((total * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING))
    projection = int((
        total * Decimal(6) / Decimal(4) * Decimal(83) / Decimal(76)
        * Decimal(1_000_000)
    ).to_integral_value(rounding=ROUND_CEILING))
    if (
        budget.get("historical_runs") != 76
        or budget.get("historical_provider_prompts") != 83
        or budget.get("same_76_repriced_microdollars") != meme_76
        or budget.get("repriced_estimate_microdollars") != projection
        or budget.get("approved_estimate_microdollars") != ESTIMATION_APPROUVEE
        or budget.get("delta_microdollars") != projection - ESTIMATION_APPROUVEE
        or budget.get("approved_cap_microdollars") != PLAFOND_APPROUVE
        or budget.get("margin_to_cap_microdollars") != PLAFOND_APPROUVE - projection
    ):
        raise SnapshotRoutesInvalide("recalcul B0-09 incohérent")
    attendu_status = (
        "B0_09_UNCHANGED"
        if projection == ESTIMATION_APPROUVEE
        else "HOLD_B0_09_REAPPROVAL_REQUIRED"
    )
    if budget.get("status") != attendu_status:
        raise SnapshotRoutesInvalide("statut B0-09 incohérent")


def _raisons_hold_cible(snapshot: dict[str, Any]) -> list[str]:
    raisons = []
    if snapshot.get("pin_changes"):
        raisons.append("HOLD_B0_08_PIN_DRIFT")
    budget = snapshot.get("budget_reestimate") or {}
    if snapshot.get("b0_09_approval") is None:
        raisons.append(
            "HOLD_B0_09_SNAPSHOT_APPROVAL_REQUIRED"
            if budget.get("status") == "B0_09_UNCHANGED"
            else "HOLD_B0_09_REAPPROVAL_REQUIRED"
        )
    return raisons


def _source_proposition(
    snapshot: dict[str, Any], racine: Path | None
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    approbation = snapshot.get("b0_09_approval")
    source = snapshot.get("proposal_source")
    if approbation is None:
        if source is not None:
            raise SnapshotRoutesInvalide("source de proposition présente sans approbation B0-09")
        return None
    if (
        not isinstance(approbation, dict)
        or set(approbation) != {
            "schema_version", "decision", "approved_by", "approved_at",
            "estimate_microdollars", "cap_microdollars",
            "source_snapshot_path", "source_snapshot_sha256",
        }
        or approbation.get("schema_version") != "benchmark-lab-x/b0-09-approval/v2"
        or approbation.get("decision") != "B0_09_REVISED_ESTIMATE_APPROVED"
        or approbation.get("approved_by") != "Ayo"
        or not isinstance(approbation.get("approved_at"), str)
        or not approbation["approved_at"]
        or approbation.get("estimate_microdollars")
        != snapshot["budget_reestimate"]["repriced_estimate_microdollars"]
        or approbation.get("cap_microdollars") != PLAFOND_APPROUVE
    ):
        raise SnapshotRoutesInvalide("approbation B0-09 v2 invalide")
    if (
        not isinstance(source, dict)
        or set(source) != {"path", "sha256"}
        or source.get("path") != approbation.get("source_snapshot_path")
        or source.get("sha256") != approbation.get("source_snapshot_sha256")
        or re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256"))) is None
    ):
        raise SnapshotRoutesInvalide("approbation B0-09 non liée à sa proposition")
    chemin_relatif = Path(str(source["path"]))
    if chemin_relatif.is_absolute() or ".." in chemin_relatif.parts or racine is None:
        raise SnapshotRoutesInvalide("chemin de proposition B0-09 non vérifiable")
    try:
        source_path = resoudre_sous(racine, str(source["path"]))
    except ContratV2Invalide as exc:
        raise SnapshotRoutesInvalide("chemin de proposition B0-09 non vérifiable") from exc
    if not source_path.is_file() or source_path.is_symlink():
        raise SnapshotRoutesInvalide("proposition B0-09 absente ou liée")
    data = source_path.read_bytes()
    if empreinte_octets(data) != source["sha256"]:
        raise SnapshotRoutesInvalide("empreinte de la proposition B0-09 différente")
    try:
        proposition = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotRoutesInvalide("proposition B0-09 illisible") from exc
    if proposition.get("b0_09_approval") is not None or proposition.get("proposal_source") is not None:
        raise SnapshotRoutesInvalide("la source B0-09 n'est pas un snapshot proposé")
    return proposition, source


def valider_cible(
    snapshot: dict[str, Any], racine: Path | None = None, exiger_lockable: bool = False
) -> dict[str, Any]:
    champs = {
        "schema_version", "panel", "observed_at", "criterion_version",
        "models_file", "models_file_sha256", "status", "hold_reasons",
        "models", "resolved", "pin_changes", "budget_reestimate",
        "proposal_source", "b0_09_approval",
    }
    if not isinstance(snapshot, dict) or set(snapshot) != champs:
        raise SnapshotRoutesInvalide("champs du snapshot v3 différents du contrat fermé")
    if snapshot.get("schema_version") != SCHEMA_CIBLE:
        raise SnapshotRoutesInvalide("route-preflight-snapshot/v3 absent")
    panel = snapshot.get("panel")
    if tuple(panel or ()) != PANEL_B0:
        raise SnapshotRoutesInvalide("panel différent des 19 alias B0-06")
    if snapshot.get("criterion_version") != CRITERE_VERSION:
        raise SnapshotRoutesInvalide("selection-route/v3 absent")
    if not isinstance(snapshot.get("observed_at"), str) or not snapshot["observed_at"]:
        raise SnapshotRoutesInvalide("date d'observation absente")
    if re.fullmatch(r"[0-9a-f]{64}", str(snapshot.get("models_file_sha256"))) is None:
        raise SnapshotRoutesInvalide("empreinte du registre invalide")

    modeles = snapshot.get("models")
    resolved = snapshot.get("resolved")
    if not isinstance(modeles, dict) or not isinstance(resolved, dict):
        raise SnapshotRoutesInvalide("résolution de routes absente")
    if set(resolved) != set(panel):
        raise SnapshotRoutesInvalide("résolution des 19 alias incomplète")
    for model, bloc in modeles.items():
        if not isinstance(bloc, dict) or set(bloc) != {
            "metadata_evidence", "selected_route_identity", "quantization", "revision"
        }:
            raise SnapshotRoutesInvalide(f"bloc modèle ouvert ou incomplet: {model}")
        evidence = bloc["metadata_evidence"]
        if (
            not isinstance(evidence, dict)
            or set(evidence) != {"url", "observed_at", "response_sha256", "response_body"}
            or evidence.get("observed_at") != snapshot["observed_at"]
            or re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("response_sha256"))) is None
            or not isinstance(evidence.get("url"), str)
            or not evidence["url"]
            or not isinstance(evidence.get("response_body"), str)
            or empreinte_octets(evidence["response_body"].encode("utf-8"))
            != evidence.get("response_sha256")
        ):
            raise SnapshotRoutesInvalide(f"preuve de métadonnées invalide: {model}")
        try:
            brut_modele = json.loads(evidence["response_body"])
        except json.JSONDecodeError as exc:
            raise SnapshotRoutesInvalide(f"réponse de métadonnées illisible: {model}") from exc
        identity = bloc["selected_route_identity"]
        if not isinstance(identity, dict) or set(identity) != {
            "kind", "canonical_publisher", "provider_slug", "provider_name", "endpoint_tag"
        }:
            raise SnapshotRoutesInvalide(f"identité de route invalide: {model}")
        if identity.get("kind") not in {"publisher_managed", "third_party"}:
            raise SnapshotRoutesInvalide(f"type de route invalide: {model}")
        if any(not isinstance(identity.get(cle), str) or not identity[cle] for cle in {
            "canonical_publisher", "provider_slug", "provider_name", "endpoint_tag"
        }):
            raise SnapshotRoutesInvalide(f"tuple de route incomplet: {model}")
        if identity["canonical_publisher"] != editeur_canonique(model):
            raise SnapshotRoutesInvalide(f"éditeur canonique différent du critère: {model}")
        identite_endpoint = {
            "provider_name": identity["provider_name"],
            "tag": identity["endpoint_tag"],
        }
        if identity["kind"] == "publisher_managed" and (
            not est_editeur(identite_endpoint, model)
            or identity["provider_slug"] != identity["canonical_publisher"]
        ):
            raise SnapshotRoutesInvalide(f"premier tiers non démontré: {model}")
        if identity["kind"] == "third_party" and est_editeur(identite_endpoint, model):
            raise SnapshotRoutesInvalide(f"route éditeur classée tierce: {model}")
        _valider_quantification(bloc["quantization"], identity, model)
        revision = bloc["revision"]
        if (
            not isinstance(revision, dict)
            or set(revision) != {"status", "kind", "value"}
            or revision.get("status") != "declared"
            or revision.get("kind") != "endpoint_model_id"
            or not isinstance(revision.get("value"), str)
            or not revision["value"]
        ):
            raise SnapshotRoutesInvalide(f"révision invalide: {model}")
        endpoints_bruts = [
            endpoint for endpoint in ((brut_modele.get("data") or {}).get("endpoints") or [])
            if isinstance(endpoint, dict)
            and endpoint.get("tag") == identity["endpoint_tag"]
        ]
        if len(endpoints_bruts) != 1:
            raise SnapshotRoutesInvalide(f"endpoint absent de la preuve brute: {model}")
        endpoint_brut = endpoints_bruts[0]
        if (
            endpoint_brut.get("provider_name") != identity["provider_name"]
            or endpoint_brut.get("model_id") != revision["value"]
        ):
            raise SnapshotRoutesInvalide(f"tuple de route différent de la preuve brute: {model}")
        quantification = bloc["quantization"]
        quantification_brute = endpoint_brut.get("quantization")
        if quantification["status"] == "declared":
            if quantification_brute != quantification["value"]:
                raise SnapshotRoutesInvalide(f"quantification différente de la preuve brute: {model}")
        elif (
            isinstance(quantification_brute, str)
            and quantification_brute.strip()
            and norm(quantification_brute) not in {"unknown", "opaque"}
        ):
            raise SnapshotRoutesInvalide(f"not_disclosed contredit par la preuve brute: {model}")

    route_fields = {
        "metadata_status", "backend", "endpoint_tag", "provider", "expect_provider",
        "ownership", "quantization", "revision", "metadata_evidence",
        "criterion_version", "price_source", "price_observed_at",
        "input_usd_per_million_tokens", "output_usd_per_million_tokens",
        "request_usd", "max_tokens",
    }
    for alias, route in resolved.items():
        if not isinstance(route, dict) or set(route) != route_fields:
            raise SnapshotRoutesInvalide(f"route fermée invalide: {alias}")
        if route.get("metadata_status") != "resolved" or route.get("backend") != "openrouter":
            raise SnapshotRoutesInvalide(f"route non résolue: {alias}")
        if route.get("criterion_version") != CRITERE_VERSION:
            raise SnapshotRoutesInvalide(f"critère différent: {alias}")
        identity = route.get("ownership")
        if not isinstance(identity, dict) or route.get("endpoint_tag") != identity.get("endpoint_tag"):
            raise SnapshotRoutesInvalide(f"endpoint non lié à l'identité: {alias}")
        if route.get("provider") != identity.get("provider_slug"):
            raise SnapshotRoutesInvalide(f"provider non lié à l'identité: {alias}")
        _valider_quantification(route.get("quantization"), identity, alias)
        evidence_route = route.get("metadata_evidence")
        if (
            not isinstance(evidence_route, dict)
            or set(evidence_route) != {"url", "observed_at", "response_sha256"}
            or re.fullmatch(r"[0-9a-f]{64}", str(evidence_route.get("response_sha256"))) is None
            or evidence_route.get("observed_at") != snapshot["observed_at"]
        ):
            raise SnapshotRoutesInvalide(f"référence de métadonnées invalide: {alias}")
        if not isinstance(route.get("max_tokens"), int) or route["max_tokens"] < 1:
            raise SnapshotRoutesInvalide(f"max_tokens invalide: {alias}")

    pin_changes = snapshot.get("pin_changes")
    if not isinstance(pin_changes, list) or pin_changes != sorted(
        pin_changes, key=lambda entree: entree.get("alias", "") if isinstance(entree, dict) else ""
    ):
        raise SnapshotRoutesInvalide("dérives de pin non triées")
    for change in pin_changes:
        if not isinstance(change, dict) or set(change) != {
            "alias", "current_provider", "recommended_provider", "endpoint_tag", "reason"
        } or change.get("alias") not in panel or change.get("reason") != "selection-route/v3":
            raise SnapshotRoutesInvalide("dérive de pin invalide")
    _valider_budget_cible(snapshot)

    source_proposition = _source_proposition(snapshot, racine)
    if source_proposition is not None:
        proposition, source = source_proposition
        valider_cible(proposition, racine)
        attendu = copy.deepcopy(proposition)
        attendu["proposal_source"] = source
        attendu["b0_09_approval"] = snapshot["b0_09_approval"]
        attendu["hold_reasons"] = _raisons_hold_cible(attendu)
        attendu["status"] = "PREPARED_LOCAL_ONLY" if not attendu["hold_reasons"] else "HOLD"
        if attendu != snapshot:
            raise SnapshotRoutesInvalide("snapshot approuvé différent de sa proposition B0-09")

    raisons = _raisons_hold_cible(snapshot)
    attendu_status = "PREPARED_LOCAL_ONLY" if not raisons else "HOLD"
    if snapshot.get("status") != attendu_status or snapshot.get("hold_reasons") != raisons:
        raise SnapshotRoutesInvalide("statut de pré-vol incohérent")

    if racine is not None:
        models_path = racine / snapshot["models_file"]
        if (
            not models_path.is_file()
            or models_path.is_symlink()
            or empreinte_octets(models_path.read_bytes()) != snapshot["models_file_sha256"]
        ):
            raise SnapshotRoutesInvalide("registre source absent ou modifié")
        registre = charger_registre(models_path)
        modeles_attendus = {registre[alias]["model"] for alias in panel}
        if set(modeles) != modeles_attendus:
            raise SnapshotRoutesInvalide("modèles résolus différents du registre")
        for model, bloc in modeles.items():
            aliases_modele = [
                alias for alias in panel if registre[alias]["model"] == model
            ]
            references = {
                registre[alias]["format_reference"]
                for alias in aliases_modele
                if registre[alias].get("format_reference")
            }
            if len(references) > 1:
                raise SnapshotRoutesInvalide(f"formats de référence divergents: {model}")
            reference = next(iter(references), None)
            brut = json.loads(bloc["metadata_evidence"]["response_body"])
            endpoints = ((brut.get("data") or {}).get("endpoints") or [])
            classes = [evaluer(endpoint, model, reference) for endpoint in endpoints]
            eligibles = sorted(
                (route for route in classes if not route["exclusions"]),
                key=lambda route: route["_cle"],
            )
            if (
                not eligibles
                or eligibles[0]["tag"]
                != bloc["selected_route_identity"]["endpoint_tag"]
            ):
                raise SnapshotRoutesInvalide(f"route différente de selection-route/v3: {model}")
        attendus = []
        for alias in panel:
            pin = registre[alias].get("provider")
            route = resolved[alias]
            bloc = modeles[registre[alias]["model"]]
            evidence_modele = bloc["metadata_evidence"]
            evidence_attendue = {
                "url": evidence_modele["url"],
                "observed_at": evidence_modele["observed_at"],
                "response_sha256": evidence_modele["response_sha256"],
            }
            if (
                route["ownership"] != bloc["selected_route_identity"]
                or route["quantization"] != bloc["quantization"]
                or route["revision"] != bloc["revision"]
                or route["metadata_evidence"] != evidence_attendue
            ):
                raise SnapshotRoutesInvalide(f"route non liée au bloc modèle: {alias}")
            if norm(pin) != route["provider"]:
                attendus.append({
                    "alias": alias,
                    "current_provider": pin,
                    "recommended_provider": route["provider"],
                    "endpoint_tag": route["endpoint_tag"],
                    "reason": "selection-route/v3",
                })
        if sorted(attendus, key=lambda entree: entree["alias"]) != pin_changes:
            raise SnapshotRoutesInvalide("dérives de pin différentes du registre")
        sources_octets: dict[str, bytes] = {}
        for source in snapshot["budget_reestimate"]["historical_inputs"]:
            source_path = racine / source["path"]
            if not source_path.is_file() or source_path.is_symlink():
                raise SnapshotRoutesInvalide(f"source historique absente ou modifiée: {source['path']}")
            source_data = source_path.read_bytes()
            if empreinte_octets(source_data) != source["sha256"]:
                raise SnapshotRoutesInvalide(f"source historique absente ou modifiée: {source['path']}")
            sources_octets[source["path"]] = source_data
        try:
            results = json.loads(
                sources_octets[snapshot["budget_reestimate"]["historical_source"]].decode("utf-8")
            )
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SnapshotRoutesInvalide("results-data historique non reproductible") from exc
        retenus = [run for run in results.get("runs", []) if run.get("tentative_retenue") is True]
        if len(retenus) != 76:
            raise SnapshotRoutesInvalide("76 runs retenus absents de results-data")
        attendus_meta = sorted((
            run["alias"], run["run"], int(run.get("tentative") or 1),
            chemin_run_historique(Path(snapshot["budget_reestimate"]["historical_source"]).parent, run).as_posix(),
        ) for run in retenus)
        observes_meta = sorted((
            source["alias"], source["run"], source["attempt"], source["path"]
        ) for source in snapshot["budget_reestimate"]["historical_inputs"][1:])
        if attendus_meta != observes_meta:
            raise SnapshotRoutesInvalide("manifeste meta différent des 76 runs retenus")
        recompte = {
            alias: {"runs": 0, "prompt_tokens": 0, "completion_tokens": 0,
                    "historical_microdollars": 0}
            for alias in panel
        }
        total_historique = Decimal(0)
        for source in snapshot["budget_reestimate"]["historical_inputs"][1:]:
            try:
                meta = json.loads(sources_octets[source["path"]].decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SnapshotRoutesInvalide(f"meta historique illisible: {source['path']}") from exc
            usage = meta.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            if not isinstance(prompt_tokens, int) or not isinstance(completion_tokens, int):
                raise SnapshotRoutesInvalide(f"usage historique absent: {source['path']}")
            cout_historique = Decimal(str(meta.get("cost_usd") or 0))
            bloc = recompte[source["alias"]]
            bloc["runs"] += 1
            bloc["prompt_tokens"] += prompt_tokens
            bloc["completion_tokens"] += completion_tokens
            bloc["historical_microdollars"] += math.ceil(cout_historique * 1_000_000)
            total_historique += cout_historique
        for alias, bloc in recompte.items():
            conserve = snapshot["budget_reestimate"]["by_alias"][alias]
            for champ, valeur in bloc.items():
                if conserve.get(champ) != valeur:
                    raise SnapshotRoutesInvalide(f"recompte historique différent: {alias}/{champ}")
        total_micro = int(
            (total_historique * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING)
        )
        if snapshot["budget_reestimate"].get("historical_recorded_microdollars") != total_micro:
            raise SnapshotRoutesInvalide("coût historique total différent des reçus")
    if exiger_lockable and raisons:
        raise SnapshotRoutesInvalide(", ".join(raisons))
    return {
        "status": attendu_status,
        "hold_reasons": raisons,
        "aliases_resolved": len(resolved),
        "models_resolved": len(modeles),
        "repriced_estimate_microdollars": snapshot["budget_reestimate"]["repriced_estimate_microdollars"],
        "approved_cap_microdollars": snapshot["budget_reestimate"]["approved_cap_microdollars"],
    }


def approuver_snapshot_cible(
    source_path: Path, approved_at: str, racine: Path
) -> dict[str, Any]:
    if source_path.is_symlink() or not source_path.is_file():
        raise SnapshotRoutesInvalide("snapshot proposé absent ou lié")
    try:
        relatif = source_path.resolve().relative_to(racine.resolve()).as_posix()
    except ValueError as exc:
        raise SnapshotRoutesInvalide("snapshot proposé hors du dépôt") from exc
    try:
        source_resolue = resoudre_sous(racine, relatif)
    except ContratV2Invalide as exc:
        raise SnapshotRoutesInvalide("snapshot proposé lié ou hors du dépôt") from exc
    if source_resolue != source_path.resolve():
        raise SnapshotRoutesInvalide("snapshot proposé différent du chemin canonique")
    data = source_path.read_bytes()
    try:
        proposition = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotRoutesInvalide("snapshot proposé illisible") from exc
    valider_cible(proposition, racine)
    if proposition.get("b0_09_approval") is not None or proposition.get("proposal_source") is not None:
        raise SnapshotRoutesInvalide("la source B0-09 doit être une proposition non approuvée")
    source = {"path": relatif, "sha256": empreinte_octets(data)}
    snapshot = copy.deepcopy(proposition)
    snapshot["proposal_source"] = source
    snapshot["b0_09_approval"] = {
        "schema_version": "benchmark-lab-x/b0-09-approval/v2",
        "decision": "B0_09_REVISED_ESTIMATE_APPROVED",
        "approved_by": "Ayo",
        "approved_at": approved_at,
        "estimate_microdollars": snapshot["budget_reestimate"][
            "repriced_estimate_microdollars"
        ],
        "cap_microdollars": PLAFOND_APPROUVE,
        "source_snapshot_path": relatif,
        "source_snapshot_sha256": source["sha256"],
    }
    snapshot["hold_reasons"] = _raisons_hold_cible(snapshot)
    snapshot["status"] = "PREPARED_LOCAL_ONLY" if not snapshot["hold_reasons"] else "HOLD"
    valider_cible(snapshot, racine)
    return snapshot


def main() -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--check", type=Path)
    ap.add_argument("--approve-from", type=Path)
    ap.add_argument("--approved-at")
    ap.add_argument("--models-file", type=Path, default=Path("models.toml"))
    ap.add_argument("--alias", action="append", dest="aliases")
    ap.add_argument("--observed-at")
    ap.add_argument(
        "--historical",
        type=Path,
        default=Path("runs/2026-08-06-reference-v2"),
    )
    args = ap.parse_args()
    try:
        if args.check:
            snapshot = json.loads(args.check.read_text(encoding="utf-8"))
        elif args.approve_from:
            if not args.approved_at:
                raise SnapshotRoutesInvalide("--approved-at requis avec --approve-from")
            snapshot = approuver_snapshot_cible(
                args.approve_from, args.approved_at, Path.cwd()
            )
            ecrire_json_immuable(args.out, snapshot)
        else:
            if not args.aliases or not args.observed_at:
                raise SnapshotRoutesInvalide("--alias et --observed-at sont requis avec --out")
            registre = charger_registre(args.models_file)
            selection = selectionner_routes_cible(registre, args.aliases, args.observed_at)
            snapshot = {
                "schema_version": SCHEMA_CIBLE,
                "panel": args.aliases,
                "observed_at": args.observed_at,
                "criterion_version": CRITERE_VERSION,
                "models_file": args.models_file.as_posix(),
                "models_file_sha256": empreinte_octets(args.models_file.read_bytes()),
                "status": "HOLD",
                "hold_reasons": [],
                "proposal_source": None,
                "b0_09_approval": None,
                **selection,
            }
            snapshot["budget_reestimate"] = recalculer_budget(snapshot, args.historical)
            snapshot["hold_reasons"] = _raisons_hold_cible(snapshot)
            if not snapshot["hold_reasons"]:
                snapshot["status"] = "PREPARED_LOCAL_ONLY"
            ecrire_json_immuable(args.out, snapshot)
        resultat = valider_cible(snapshot, Path.cwd())
    except (SnapshotRoutesInvalide, OSError, json.JSONDecodeError, TypeError) as exc:
        print(f"HOLD: {exc}")
        return 2
    print(json.dumps(resultat, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if resultat["status"] == "PREPARED_LOCAL_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
