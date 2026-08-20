from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


RACINE = Path(__file__).resolve().parents[1]
PLAN_PAR_DEFAUT = RACINE / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/plan-acquisition-v1/plan-acquisition.json"
EMPREINTE_PLAN_ATTENDUE = "7a6580a41e5e8f795f0ffe50ca0263050b78ba82ca1c052f8a140254ea403e2a"

AUTORITES_ATTENDUES = {
    "recommended_bundle": {
        "author": "ayoahha", "comment_id": 5354264344,
        "node_id": "IC_kwDOTswBxM8AAAABPyOXGA",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/67#issuecomment-5354264344",
        "created_at": "2026-08-20T09:49:56Z", "updated_at": "2026-08-20T09:49:56Z",
        "body_sha256": "7454a44ea57839e3e8311103f2d8ca87e8c85ffeac195921312a002dbc11ecc3",
    },
    "owner_acceptance": {
        "author": "ayoahha", "comment_id": 5354857642,
        "node_id": "IC_kwDOTswBxM8AAAABPyykqg",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/67#issuecomment-5354857642",
        "created_at": "2026-08-20T10:48:33Z", "updated_at": "2026-08-20T10:48:33Z",
        "authority_value": "M6_4_OWNER_DECISION = ACCEPT_RECOMMENDED_BUNDLE",
        "body_sha256": "985d344b312afec4632be7f46498f0d9e025224597fb3ba6809da4d4d04dda4d",
    },
}

PREDECESSEURS_ATTENDUS = {
    "m6_1_authorities": {"path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/autorites-v1/autorites.json", "sha256": "d551362f35a9e650d78330e79b757bb3e63c892b92fcaa08b48f86599d951d82"},
    "m6_2_version_contracts": {"path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/contrats-versionnes-v1/contrats-versionnes.json", "sha256": "cf4c2784039edb5cb2be43911d7f3fbc52ff66612c4a4436094602a3dd8d1fcd"},
    "m6_3_panel_identities": {"path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/panel-identites-v1/panel-identites.json", "sha256": "c6d31dbc7953f3c21d9f5e3b5ff42d38b8171eab2e5dee52ecfb10920cc849d0"},
}

SLOTS_ATTENDUS = [
    {"acquisition_id": "ACQ-GROK46-PRIMARY-001", "configuration_id": "grok46_xai_build_oauth", "role": "PRIMARY", "count": 1},
    {"acquisition_id": "ACQ-KIMIK3-PRIMARY-001", "configuration_id": "kimi_k3_cursor_cli", "role": "PRIMARY", "count": 1},
]

INCIDENTS_ATTENDUS = {
    "provider_failure": {"definition": "ATTRIBUTABLE_PROVIDER_OPERATION_WITHOUT_REQUIRED_OUTPUT", "effect": "TERMINAL_SLOT_COUNTS_AS_CONFIGURATION_FAILURE_RETAIN_ATTRIBUTABLE_COST_CONTINUE_OTHER_PLANNED_SLOT"},
    "harness_error": {"definition": "LOCAL_OR_UNATTRIBUTABLE_FAILURE", "effect": "NO_CONFIGURATION_PENALTY_REDUCE_COVERAGE_STOP_CAMPAIGN"},
    "identity_mismatch": {"definition": "IDENTITY_MISMATCH", "effect": "OBSERVED_VALUE_CONFLICTS_WITH_LOCK_HOLD_AND_STOP"},
    "missing_observation": {"definition": "MISSING_OBSERVATION", "effect": "INCONNU_PRESERVE_RECEIPT_CONFIGURATION_NOT_OFFICIALLY_COMPARABLE"},
}

SOURCES_ATTENDUES = [
    {"role": "APPLICABLE_ROUTE_REGIME", "url": "https://docs.x.ai/grok/faq"},
    {"role": "APPLICABLE_ROUTE_AUTHENTICATION", "url": "https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/docs/user-guide/02-authentication.md"},
    {"role": "APPLICABLE_ROUTE_BILLING_IMPLEMENTATION", "url": "https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-shell/src/extensions/billing.rs"},
    {"role": "REFERENCE_ONLY_NON_APPLICABLE", "url": "https://docs.x.ai/developers/pricing"},
    {"role": "APPLICABLE_ROUTE_REGIME", "url": "https://cursor.com/docs/models-and-pricing"},
    {"role": "APPLICABLE_ROUTE_TERMS", "url": "https://cursor.com/terms/pricing/2026-03-25"},
    {"role": "REFERENCE_ONLY_NON_APPLICABLE", "url": "https://forum.moonshot.ai/t/kimi-k3-is-here-our-most-capable-model/480"},
]


class ErreurPlanAcquisition(ValueError):
    pass


def _sha256(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _ferme(valeur: object, champs: tuple[str, ...], emplacement: str) -> dict[str, object]:
    if not isinstance(valeur, dict) or set(valeur) != set(champs):
        raise ErreurPlanAcquisition(f"schéma fermé divergent: {emplacement}")
    return valeur


def _egal(observe: object, attendu: object, emplacement: str) -> None:
    if observe != attendu:
        raise ErreurPlanAcquisition(f"valeur divergente: {emplacement}")


def _reference(reference: object, racine: Path, emplacement: str) -> None:
    entree = _ferme(reference, ("path", "sha256"), emplacement)
    chemin_brut, empreinte = entree["path"], entree["sha256"]
    if not isinstance(chemin_brut, str) or not isinstance(empreinte, str):
        raise ErreurPlanAcquisition(f"référence non textuelle: {emplacement}")
    relatif = PurePosixPath(chemin_brut)
    if relatif.is_absolute() or ".." in relatif.parts:
        raise ErreurPlanAcquisition(f"référence non sûre: {emplacement}")
    chemin = racine.joinpath(*relatif.parts)
    try:
        chemin.resolve(strict=True).relative_to(racine.resolve(strict=True))
        contenu = chemin.read_bytes()
    except (OSError, ValueError) as exc:
        raise ErreurPlanAcquisition(f"référence inaccessible: {emplacement}") from exc
    if _sha256(contenu) != empreinte:
        raise ErreurPlanAcquisition(f"empreinte divergente: {emplacement}")


def valider_plan_acquisition_campagne_v0(plan: Path = PLAN_PAR_DEFAUT, racine: Path = RACINE) -> dict[str, object]:
    try:
        contenu = plan.read_bytes()
        document = json.loads(contenu)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErreurPlanAcquisition("plan illisible ou JSON invalide") from exc

    racine_document = _ferme(document, (
        "schema_version", "scope", "hash_conventions", "owner_authorities",
        "decision_contract_sha256", "predecessor_artifacts", "acquisition_plan",
        "incident_policy", "evidence_states", "pricing", "blind_order",
        "immutability", "exclusions",
    ), "racine")
    _egal(racine_document["schema_version"], "campaign-v0-acquisition-plan/v1", "schema_version")
    _egal(_ferme(racine_document["scope"], ("issue_number", "issue_url", "parent_issue_number", "parent_issue_url", "product_version", "git_base"), "scope"), {
        "issue_number": 67, "issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/67",
        "parent_issue_number": 19, "parent_issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/19",
        "product_version": "V0", "git_base": "021388917824aec5b6dcb1617b68f031337e0e38",
    }, "scope")
    _egal(racine_document["hash_conventions"], {
        "file_sha256": "sha256 of exact file bytes",
        "github_body_sha256": "sha256 of the exact UTF-8 body returned by the GitHub API, with exactly one trailing newline appended",
    }, "hash_conventions")
    _egal(racine_document["owner_authorities"], AUTORITES_ATTENDUES, "owner_authorities")
    _egal(racine_document["decision_contract_sha256"], "ea07f5691249f648a939d1ca6bac26eaf38cea7bd2f7e3593add17a55184c704", "decision_contract_sha256")

    _egal(racine_document["predecessor_artifacts"], PREDECESSEURS_ATTENDUS, "predecessor_artifacts")
    for nom, reference in PREDECESSEURS_ATTENDUS.items():
        _reference(reference, racine, f"predecessor_artifacts.{nom}")

    acquisition = _ferme(racine_document["acquisition_plan"], ("campaign_input", "stimulus", "plan", "planned_acquisitions", "replications", "automatic_retries", "manual_retries", "fallbacks", "slots"), "acquisition_plan")
    _egal({cle: acquisition[cle] for cle in ("campaign_input", "plan", "planned_acquisitions", "replications", "automatic_retries", "manual_retries", "fallbacks")}, {
        "campaign_input": "APPROVED_STIMULUS_ONLY", "plan": "ONE_PRIMARY_PER_CONFIGURATION",
        "planned_acquisitions": 2, "replications": 0, "automatic_retries": 0,
        "manual_retries": 0, "fallbacks": "NONE",
    }, "acquisition_plan.cardinality")
    _egal(acquisition["stimulus"], {"path": "tasks/dev/pre-cadrage-entretien-client/stimulus.md", "sha256": "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4"}, "acquisition_plan.stimulus")
    _reference(acquisition["stimulus"], racine, "acquisition_plan.stimulus")
    _egal(acquisition["slots"], SLOTS_ATTENDUS, "acquisition_plan.slots")
    _egal(sum(slot["count"] for slot in acquisition["slots"]), 2, "acquisition_plan.slots.count")

    _egal(racine_document["incident_policy"], INCIDENTS_ATTENDUS, "incident_policy")
    etats = _ferme(racine_document["evidence_states"], ("separation", "absent_observation", "promotion_expected_or_requested_to_observed", "future_observations"), "evidence_states")
    _egal({cle: etats[cle] for cle in ("separation", "absent_observation", "promotion_expected_or_requested_to_observed")}, {
        "separation": "STRICT_EXPECTED_REQUESTED_OBSERVED", "absent_observation": "INCONNU",
        "promotion_expected_or_requested_to_observed": "FORBIDDEN",
    }, "evidence_states")
    observations = _ferme(etats["future_observations"], ("served_model", "served_provider", "served_route", "served_parameters", "provider_cost"), "evidence_states.future_observations")
    for nom, observation in observations.items():
        _egal(observation, {"state": "OBSERVED", "value": "INCONNU"}, f"future_observations.{nom}")

    prix = _ferme(racine_document["pricing"], ("observed_at", "account_observation", "grok_build", "kimi_cursor", "cost_observation", "official_sources"), "pricing")
    _egal(prix["observed_at"], "2026-08-20T09:42:31Z", "pricing.observed_at")
    _egal(prix["account_observation"], "NOT_INSPECTED_NOT_ASSERTED", "pricing.account_observation")
    _egal(prix["grok_build"], {"billing_regime": "SHARED_WEEKLY_PRODUCT_POOL", "route_unit_price": "INCONNU_IF_UNPUBLISHED", "direct_api_price": "REFERENCE_ONLY_NON_APPLICABLE"}, "pricing.grok_build")
    _egal(prix["kimi_cursor"], {"billing_regime": "CURSOR_OTHER_MODELS", "route_unit_price": "INCONNU_IF_UNPUBLISHED", "moonshot_direct_api_price": "REFERENCE_ONLY_NON_APPLICABLE"}, "pricing.kimi_cursor")
    _egal(prix["cost_observation"], {"observed_provider_cost": "PROVIDER_REPORTED_OR_EXPORT_ATTRIBUTABLE_TO_ACQUISITION_ONLY", "unobserved_provider_cost": "INCONNU", "subscription_allocation": "FORBIDDEN", "zero_cost_inference_from_no_new_purchase": "FORBIDDEN"}, "pricing.cost_observation")
    _egal(prix["official_sources"], SOURCES_ATTENDUES, "pricing.official_sources")

    _egal(racine_document["blind_order"], {
        "method": "SECRET_SALT_SHA256_SORT", "salt": "DEFERRED_TO_M6_6_RANDOM_32_BYTES_BEFORE_ANY_ACQUISITION",
        "commitments": "DEFERRED_TO_M6_6_SALT_SHA256_AND_ORDER_MANIFEST_SHA256",
        "sort_key": "SHA256_SALT_CAMPAIGN_ID_ACQUISITION_ID", "presentation": "OPAQUE_ITEM_IDS_ONLY",
        "reveal": "AFTER_ALL_HUMAN_VERDICTS_FROZEN", "salt_material_present": False, "order_mapping_present": False,
    }, "blind_order")
    _egal(racine_document["immutability"], {"mode": "APPEND_ONLY_CONTENT_ADDRESSED_PREDECESSOR_CHAIN", "predecessor_chain_required": True, "mutation_of_receipts": "FORBIDDEN"}, "immutability")
    _egal(racine_document["exclusions"], {
        "m6_5_dimensions": ["BUDGET", "FRESHNESS", "LATENCY", "PREFERENCE"],
        "campaign_execution": "NOT_AUTHORIZED", "provider_attempts": "NOT_AUTHORIZED",
        "account_or_billing_inspection": "NOT_PERFORMED", "historical_p2_p3_authority": "FORBIDDEN",
    }, "exclusions")

    empreinte = _sha256(contenu)
    if empreinte != EMPREINTE_PLAN_ATTENDUE:
        raise ErreurPlanAcquisition("plan ou citations divergents")
    return {"status": "PLAN_ACQUISITION_CAMPAGNE_V0_OK", "plan_sha256": empreinte, "planned_acquisitions": 2, "automatic_retries": 0}


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument("plan", nargs="?", type=Path, default=PLAN_PAR_DEFAUT)
    arguments = analyseur.parse_args(argv)
    try:
        recu = valider_plan_acquisition_campagne_v0(arguments.plan)
    except ErreurPlanAcquisition as exc:
        print(f"HOLD_CAMPAIGN_LOCK: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(recu, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
