from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


RACINE = Path(__file__).resolve().parents[1]
POLITIQUE_PAR_DEFAUT = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "politique-decision-v1/politique-decision.json"
)
EMPREINTE_POLITIQUE_ATTENDUE = (
    "c378f180f93cb9f2ad481137618a8cd1fe2077f97389283ab13567fe6b857000"
)

AUTORITES_ATTENDUES = {
    "recommended_bundle": {
        "author": "ayoahha",
        "comment_id": 5355903801,
        "node_id": "IC_kwDOTswBxM8AAAABPzybOQ",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/68#issuecomment-5355903801",
        "created_at": "2026-08-20T12:30:23Z",
        "updated_at": "2026-08-20T12:30:23Z",
        "body_sha256": "4c27ea493b4e2e5b8dc1f5996259d88dc2bf21c29fcd528d01e8aa31b0c19cd2",
    },
    "owner_acceptance": {
        "author": "ayoahha",
        "comment_id": 5355931331,
        "node_id": "IC_kwDOTswBxM8AAAABPz0Gww",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/68#issuecomment-5355931331",
        "created_at": "2026-08-20T12:32:56Z",
        "updated_at": "2026-08-20T12:32:56Z",
        "authority_value": "M6_5_OWNER_DECISION = ACCEPT_RECOMMENDED_BUNDLE",
        "body_sha256": "3b208241a4793f874eadca3295d4e81b03933564ba176f72cd302bed11f9342c",
    },
}

PREDECESSEURS_ATTENDUS = {
    "m6_1_authorities": {
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/autorites-v1/autorites.json",
        "sha256": "d551362f35a9e650d78330e79b757bb3e63c892b92fcaa08b48f86599d951d82",
    },
    "m6_2_version_contracts": {
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/contrats-versionnes-v1/contrats-versionnes.json",
        "sha256": "cf4c2784039edb5cb2be43911d7f3fbc52ff66612c4a4436094602a3dd8d1fcd",
    },
    "m6_3_panel_identities": {
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/panel-identites-v1/panel-identites.json",
        "sha256": "c6d31dbc7953f3c21d9f5e3b5ff42d38b8171eab2e5dee52ecfb10920cc849d0",
    },
    "m6_4_acquisition_plan": {
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/plan-acquisition-v1/plan-acquisition.json",
        "sha256": "7a6580a41e5e8f795f0ffe50ca0263050b78ba82ca1c052f8a140254ea403e2a",
    },
}

AXES_ATTENDUS = [
    {"metric": "OFFICIAL_ACCEPTANCE_RATE", "direction": "MAXIMIZE"},
    {
        "metric": "SUPPLIER_COST_PER_OFFICIALLY_ACCEPTABLE_OUTPUT",
        "direction": "MINIMIZE",
    },
    {
        "metric": "LATENCY_UNDER_PREREGISTERED_RULE",
        "direction": "MINIMIZE",
    },
]

CAS_ABSTENTION_ATTENDUS = [
    {"case_id": "ABSENT_OR_NON_DECISIVE_PREFERENCE", "effect": "ABSTAIN_UNIQUE_RECOMMENDATION"},
    {"case_id": "UNKNOWN_COST_OR_LATENCY", "effect": "FULL_THREE_AXIS_FRONT_NOT_COMPUTABLE_ABSTAIN"},
    {"case_id": "ZERO_OFFICIALLY_ACCEPTABLE_OUTPUTS", "effect": "COST_PER_ACCEPTABLE_OUTPUT_NON_DEFINI_RETAIN_TOTAL_COST_ABSTAIN"},
    {"case_id": "HARNESS_ERROR_UNABLE_TO_JUDGE_OR_MISSING_EVIDENCE", "effect": "INCOMPLETE_COVERAGE_ABSTAIN"},
    {"case_id": "AMBIGUOUS_IDENTITY_OR_PROVENANCE", "effect": "ABSTAIN_IDENTITY_MISMATCH_HOLD_STOP"},
    {"case_id": "MATERIAL_CHANGE_BETWEEN_CHECKPOINTS", "effect": "HOLD_STOP_NO_CROSS_EVENT_COMPARISON"},
]


class ErreurPolitiqueDecision(ValueError):
    pass


def _sha256(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _ferme(valeur: object, champs: tuple[str, ...], emplacement: str) -> dict[str, object]:
    if not isinstance(valeur, dict) or set(valeur) != set(champs):
        raise ErreurPolitiqueDecision(f"schéma fermé divergent: {emplacement}")
    return valeur


def _egal(observe: object, attendu: object, emplacement: str) -> None:
    if observe != attendu:
        raise ErreurPolitiqueDecision(f"valeur divergente: {emplacement}")


def _reference(reference: object, racine: Path, emplacement: str) -> None:
    entree = _ferme(reference, ("path", "sha256"), emplacement)
    chemin_brut, empreinte = entree["path"], entree["sha256"]
    if not isinstance(chemin_brut, str) or not isinstance(empreinte, str):
        raise ErreurPolitiqueDecision(f"référence non textuelle: {emplacement}")
    relatif = PurePosixPath(chemin_brut)
    if relatif.is_absolute() or ".." in relatif.parts:
        raise ErreurPolitiqueDecision(f"référence non sûre: {emplacement}")
    chemin = racine.joinpath(*relatif.parts)
    try:
        chemin.resolve(strict=True).relative_to(racine.resolve(strict=True))
        contenu = chemin.read_bytes()
    except (OSError, ValueError) as exc:
        raise ErreurPolitiqueDecision(f"référence inaccessible: {emplacement}") from exc
    if _sha256(contenu) != empreinte:
        raise ErreurPolitiqueDecision(f"empreinte divergente: {emplacement}")


def _valider_schema_ferme(document: object) -> dict[str, object]:
    racine = _ferme(document, (
        "schema_version", "scope", "hash_conventions", "owner_authorities",
        "predecessor_artifacts", "evidence_states", "decision_budget",
        "freshness", "latency", "pareto", "coverage", "missing_value_rules",
        "recommendation", "abstention_cases", "authorizations", "immutability",
    ), "racine")
    sections = {
        "scope": ("issue_number", "issue_url", "parent_issue_number", "parent_issue_url", "product_version", "git_base"),
        "hash_conventions": ("file_sha256", "github_body_sha256"),
        "owner_authorities": ("recommended_bundle", "owner_acceptance"),
        "predecessor_artifacts": tuple(PREDECESSEURS_ATTENDUS),
        "evidence_states": ("DECIDED", "EXPECTED", "OBSERVED", "INCONNU", "NON_DEFINI", "promotion_expected_or_decided_to_observed"),
        "decision_budget": ("state", "effect", "authorizes_execution_or_spend"),
        "freshness": ("rule", "day_threshold", "checkpoints", "material_change_event", "material_change_effect", "unobservable", "elapsed_time_alone_invalidates_evidence"),
        "latency": ("clock", "unit", "success_start", "success_end", "report", "distribution_per_configuration", "provider_failure", "harness_validation_human", "n1_interpretation"),
        "pareto": ("axes", "axis_count", "coverage_is_axis", "budget_is_axis", "global_score", "preference", "unique_winner_without_explicit_sufficient_preference"),
        "coverage": ("eligibility_per_configuration", "covered_slot", "harness_error_unable_to_judge_or_missing_evidence"),
        "missing_value_rules": ("missing_served_identity_or_provenance", "identity_mismatch", "missing_attributable_provider_cost", "zero_acceptable_outputs_cost_metric", "unknown_or_undefined_cost_axis", "unknown_latency_axis"),
        "recommendation": ("configuration", "abstain", "abstention_output"),
        "authorizations": ("execution", "spend_or_quota", "acquisition", "provider_operation", "m6_6"),
        "immutability": ("mode", "predecessor_chain_required"),
    }
    for nom, champs in sections.items():
        _ferme(racine[nom], champs, nom)
    for nom, autorite in racine["owner_authorities"].items():
        _ferme(autorite, tuple(AUTORITES_ATTENDUES[nom]), f"owner_authorities.{nom}")
    for index, axe in enumerate(racine["pareto"]["axes"]):
        _ferme(axe, ("metric", "direction"), f"pareto.axes.{index}")
    for index, cas in enumerate(racine["abstention_cases"]):
        _ferme(cas, ("case_id", "effect"), f"abstention_cases.{index}")
    return racine


def valider_politique_decision_campagne_v0(
    politique: Path = POLITIQUE_PAR_DEFAUT, racine: Path = RACINE
) -> dict[str, object]:
    try:
        contenu = politique.read_bytes()
        document = json.loads(contenu)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErreurPolitiqueDecision("politique illisible ou JSON invalide") from exc

    politique_document = _valider_schema_ferme(document)
    _egal(politique_document["schema_version"], "campaign-v0-decision-policy/v1", "schema_version")
    _egal(politique_document["scope"], {
        "issue_number": 68,
        "issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/68",
        "parent_issue_number": 19,
        "parent_issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/19",
        "product_version": "V0",
        "git_base": "8793e3b9281420966aae183c75b228220ecaa390",
    }, "scope")
    _egal(politique_document["hash_conventions"], {
        "file_sha256": "sha256 of exact file bytes",
        "github_body_sha256": "sha256 of the exact UTF-8 body returned by the GitHub API, without an added newline",
    }, "hash_conventions")
    _egal(politique_document["owner_authorities"], AUTORITES_ATTENDUES, "owner_authorities")
    _egal(politique_document["predecessor_artifacts"], PREDECESSEURS_ATTENDUS, "predecessor_artifacts")
    for nom, reference in PREDECESSEURS_ATTENDUS.items():
        _reference(reference, racine, f"predecessor_artifacts.{nom}")

    _egal(politique_document["evidence_states"], {
        "DECIDED": "OWNER_RULE_FIXED_NEVER_AN_OBSERVATION",
        "EXPECTED": "ANTICIPATED_VALUE_NEVER_AN_OBSERVATION",
        "OBSERVED": "ACTUALLY_MEASURED_OR_REPORTED_VALUE_ONLY",
        "INCONNU": "MISSING_OBSERVATION_NO_IMPUTATION",
        "NON_DEFINI": "METRIC_UNDEFINED_NO_REPLACEMENT_VALUE",
        "promotion_expected_or_decided_to_observed": "FORBIDDEN",
    }, "evidence_states")
    _egal(politique_document["decision_budget"], {
        "state": "ABSENT_VOLUNTARILY",
        "effect": "NO_FILTER_NO_EXCLUSION_NO_IMPLICIT_THRESHOLD",
        "authorizes_execution_or_spend": "NO",
    }, "decision_budget")
    _egal(politique_document["freshness"], {
        "rule": "EXACT_LOCK_EVENT_BASED_NO_TTL",
        "day_threshold": "NONE",
        "checkpoints": ["PRE_ACQUISITION_LOCK_AND_KNOWN_ROUTE_FACTS", "PRE_DECISION_OBSERVED_IDENTITY_PROVENANCE_BILLING_AND_PRICE_FACTS"],
        "material_change_event": "CHANGE_TO_LOCKED_ARTIFACT_CONFIGURATION_HARNESS_ADAPTER_ROUTE_SERVED_IDENTITY_BILLING_REGIME_OR_APPLICABLE_PRICE_FACT",
        "material_change_effect": "HOLD_STOP_NO_CROSS_EVENT_COMPARISON",
        "unobservable": "INCONNU_ABSTAIN",
        "elapsed_time_alone_invalidates_evidence": "NO",
    }, "freshness")
    _egal(politique_document["latency"], {
        "clock": "MONOTONIC",
        "unit": "INTEGER_MILLISECONDS",
        "success_start": "IMMEDIATELY_BEFORE_LOCKED_ROUTE_INVOCATION_WITH_FINAL_SERIALIZED_REQUEST",
        "success_end": "COMPLETE_REQUIRED_CANDIDATE_OUTPUT_RECEIVED",
        "report": "FULL_DISTRIBUTION_RAW_PRIMARY_ROUTE_ELAPSED_MS",
        "distribution_per_configuration": "SINGLETON",
        "provider_failure": "TERMINAL_OPERATION_DURATION_REPORTED_SEPARATELY_AXIS_INCONNU",
        "harness_validation_human": "REPORTED_SEPARATELY_NOT_PARETO_AXIS",
        "n1_interpretation": "FEASIBILITY_ONLY_NO_VARIANCE_RELIABILITY_OR_GENERALIZATION_CLAIM",
    }, "latency")
    _egal(politique_document["pareto"]["axes"], AXES_ATTENDUS, "pareto.axes")
    _egal({cle: politique_document["pareto"][cle] for cle in politique_document["pareto"] if cle != "axes"}, {
        "axis_count": 3,
        "coverage_is_axis": "NO",
        "budget_is_axis": "NO",
        "global_score": "FORBIDDEN",
        "preference": "ABSENT_VOLUNTARILY",
        "unique_winner_without_explicit_sufficient_preference": "FORBIDDEN",
    }, "pareto.rules")
    _egal(politique_document["coverage"], {
        "eligibility_per_configuration": "ONE_OF_ONE_PLANNED_SLOT_COVERED",
        "covered_slot": "OFFICIAL_DECISION_OR_ATTRIBUTABLE_PROVIDER_FAILURE",
        "harness_error_unable_to_judge_or_missing_evidence": "INCOMPLETE_COVERAGE_ABSTAIN",
    }, "coverage")
    _egal(politique_document["missing_value_rules"], {
        "missing_served_identity_or_provenance": "NOT_OFFICIALLY_COMPARABLE_ABSTAIN",
        "identity_mismatch": "HOLD_STOP",
        "missing_attributable_provider_cost": "INCONNU_NO_IMPUTATION",
        "zero_acceptable_outputs_cost_metric": "NON_DEFINI_RETAIN_TOTAL_COST",
        "unknown_or_undefined_cost_axis": "FULL_THREE_AXIS_FRONT_NOT_COMPUTABLE_ABSTAIN",
        "unknown_latency_axis": "FULL_THREE_AXIS_FRONT_NOT_COMPUTABLE_ABSTAIN",
    }, "missing_value_rules")
    _egal(politique_document["recommendation"], {
        "configuration": "ONLY_IF_ELIGIBILITY_AND_THREE_AXES_COMPLETE_AND_EXPLICIT_OWNER_PREFERENCE_SELECTS_EXACTLY_ONE_PARETO_POINT",
        "abstain": "NO_ELIGIBLE_CONFIGURATION_OR_STALE_OR_INCOMPARABLE_EVIDENCE_OR_INCOMPLETE_COVERAGE_OR_AMBIGUOUS_IDENTITY_OR_MISSING_AXIS_OR_MISSING_OR_NON_DECISIVE_PREFERENCE",
        "abstention_output": "NAME_EXACT_MISSING_EVIDENCE_AND_POSSIBLE_HUMAN_ACTION_NO_REPLACEMENT_VALUE",
    }, "recommendation")
    _egal(politique_document["abstention_cases"], CAS_ABSTENTION_ATTENDUS, "abstention_cases")
    _egal(politique_document["authorizations"], {
        "execution": "NOT_GRANTED",
        "spend_or_quota": "NOT_GRANTED",
        "acquisition": "NOT_GRANTED",
        "provider_operation": "NOT_GRANTED",
        "m6_6": "NOT_GRANTED",
    }, "authorizations")
    _egal(politique_document["immutability"], {
        "mode": "APPEND_ONLY_CONTENT_ADDRESSED_PREDECESSOR_CHAIN",
        "predecessor_chain_required": True,
    }, "immutability")

    empreinte = _sha256(contenu)
    if empreinte != EMPREINTE_POLITIQUE_ATTENDUE:
        raise ErreurPolitiqueDecision("politique ou citations divergentes")
    return {
        "status": "POLITIQUE_DECISION_CAMPAGNE_V0_OK",
        "policy_sha256": empreinte,
        "pareto_axis_count": 3,
        "abstention_case_count": 6,
        "owner_preference": "ABSENT_VOLUNTARILY",
    }


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument("politique", nargs="?", type=Path, default=POLITIQUE_PAR_DEFAUT)
    arguments = analyseur.parse_args(argv)
    try:
        recu = valider_politique_decision_campagne_v0(arguments.politique)
    except ErreurPolitiqueDecision as exc:
        print(f"HOLD_CAMPAIGN_LOCK: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(recu, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
