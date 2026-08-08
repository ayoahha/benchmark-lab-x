# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""Figer les métadonnées publiques des routes et recalculer B0-09"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import tomllib
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any

import requests

from choisir_provider import CRITERE_VERSION, budget_de, evaluer, norm
from protocole_v2 import (
    B0_CAP_MICRODOLLARS,
    B0_ESTIMATE_MICRODOLLARS,
    PANEL_B0,
    ecrire_json_immuable,
)


SCHEMA = "benchmark-lab-x/route-preflight-snapshot/v1"
API_MODELE = "https://openrouter.ai/api/v1/models/{model}/endpoints"
PLANCHER_TOKENS = 65_536
ESTIMATION_APPROUVEE = B0_ESTIMATE_MICRODOLLARS
ESTIMATION_PRECEDENTE = 31_778_838
PLAFOND_APPROUVE = B0_CAP_MICRODOLLARS
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
    manque = [alias for alias in PANEL_B0 if not isinstance(objet.get(alias), dict)]
    if manque:
        raise SnapshotRoutesInvalide(f"alias du panel absents: {manque}")
    return objet


def lire_endpoint(model: str) -> tuple[dict[str, Any], str, str]:
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
    return objet, empreinte_octets(data), url


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
        objet, response_hash, url = lire_endpoint(model)
        endpoints = ((objet.get("data") or {}).get("endpoints") or [])
        if not isinstance(endpoints, list) or not endpoints:
            raise SnapshotRoutesInvalide(f"aucun endpoint: {model}")
        classes = [evaluer(ep, PLANCHER_TOKENS, model, reference) for ep in endpoints]
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
        if max_tokens < PLANCHER_TOKENS:
            raise SnapshotRoutesInvalide(f"budget sous le plancher: {model}/{tag}")
        route_commune = {
            "metadata_status": "resolved",
            "selected_tag": tag,
            "provider_name": endpoint.get("provider_name") or "opaque",
            "quantization": endpoint.get("quantization") or "unknown",
            "revision": endpoint.get("model_name") or endpoint.get("model_id") or "opaque",
            "criterion_version": CRITERE_VERSION,
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
        results = json.loads(results_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotRoutesInvalide("résultats historiques illisibles") from exc
    retenus = [r for r in results.get("runs", []) if r.get("tentative_retenue") is True]
    if len(retenus) != 76:
        raise SnapshotRoutesInvalide(f"76 runs historiques attendus, trouvé {len(retenus)}")
    par_alias: dict[str, dict[str, int | str]] = {}
    total_reprice = Decimal(0)
    total_historique = Decimal(0)
    for run in retenus:
        alias = run["alias"]
        route = snapshot["resolved"].get(alias)
        if not isinstance(route, dict):
            raise SnapshotRoutesInvalide(f"route résolue absente: {alias}")
        meta_path = chemin_run_historique(historique, run)
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotRoutesInvalide(f"reçu historique illisible: {meta_path}") from exc
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

    prompts = results.get("cycle_de_vie", {}).get("prompts_partis")
    runs_attendus = results.get("cycle_de_vie", {}).get("runs_attendus")
    if prompts != 83 or runs_attendus != 76:
        raise SnapshotRoutesInvalide("facteur historique 83/76 absent")
    projection = total_reprice * Decimal(6) / Decimal(4) * Decimal(prompts) / Decimal(runs_attendus)
    projection_micro = int(
        (projection * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING)
    )
    delta = projection_micro - ESTIMATION_APPROUVEE
    return {
        "historical_source": str(results_path),
        "historical_source_sha256": empreinte_octets(results_path.read_bytes()),
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
        "criterion_version": CRITERE_VERSION,
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
    if snapshot.get("criterion_version") != CRITERE_VERSION:
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
        if not isinstance(route.get("max_tokens"), int) or route["max_tokens"] < PLANCHER_TOKENS:
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


def main() -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
