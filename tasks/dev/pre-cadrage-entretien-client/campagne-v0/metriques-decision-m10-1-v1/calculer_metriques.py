import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_AXES = [
    {"direction": "MAXIMIZE", "metric": "OFFICIAL_ACCEPTANCE_RATE"},
    {
        "direction": "MINIMIZE",
        "metric": "SUPPLIER_COST_PER_OFFICIALLY_ACCEPTABLE_OUTPUT",
    },
    {
        "direction": "MINIMIZE",
        "metric": "LATENCY_UNDER_PREREGISTERED_RULE",
    },
]
EFFORT_COMPONENTS = (
    "configuration",
    "integration",
    "execution",
    "human_review",
    "verification",
    "maintenance",
    "report_production",
)
OUTCOME_KEYS = (
    "OFFICIALLY_ACCEPTABLE",
    "CANDIDATE_NOT_ACCEPTABLE",
    "HARNESS_ERROR",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_input(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    require(isinstance(data, dict), "input must be a JSON object")
    require(
        data.get("schema_version") == "campaign-v0-m10-1-linked-inputs/v1",
        "unexpected input schema",
    )
    require(data.get("candidate_content_copied") is False, "candidate content copy forbidden")
    require(
        data.get("calculation_conventions", {}).get("no_imputation") is True,
        "no-imputation convention required",
    )
    require(
        data.get("metric_rules", {}).get("pareto", {}).get("axes") == EXPECTED_AXES,
        "the ordered three-axis Pareto contract is not exact",
    )
    require(
        data.get("metric_rules", {}).get("pareto", {}).get("global_score")
        == "FORBIDDEN",
        "global score must be forbidden",
    )
    return data


def derive_official_outcome(configuration: dict[str, Any]) -> str:
    m7 = configuration["m7_observations"]
    m8 = configuration["m8_automatic_outcome"]
    m9 = configuration["m9_review_eligibility_outcome"]
    incident = m7["incident"]["value"]
    automatic_status = m8["status"]
    if incident == "HARNESS_ERROR":
        require(automatic_status == "ABSENT", "HARNESS_ERROR cannot carry an automatic verdict")
        require(m9["eligible"] is False, "HARNESS_ERROR cannot be review eligible")
        require(m9["human_verdict"] == "ABSENT", "HARNESS_ERROR cannot carry a human verdict")
        return "HARNESS_ERROR"
    if automatic_status == "FAIL":
        require(m9["eligible"] is False, "automatic FAIL cannot be review eligible")
        require(m9["review_action"] == "EXCLUDED", "automatic FAIL must be excluded from review")
        require(m9["human_verdict"] == "ABSENT", "automatic FAIL cannot carry a human verdict")
        return "CANDIDATE_NOT_ACCEPTABLE"
    if automatic_status == "PASS":
        require(m9["eligible"] is True, "automatic PASS must be review eligible")
        if m9["human_verdict"] == "ACCEPTABLE":
            return "OFFICIALLY_ACCEPTABLE"
        if m9["human_verdict"] == "NOT_ACCEPTABLE":
            return "CANDIDATE_NOT_ACCEPTABLE"
        raise ValueError("automatic PASS lacks a supported frozen human verdict")
    raise ValueError("unsupported automatic outcome")


def outcome_counts(outcomes: list[str]) -> dict[str, int]:
    counts = Counter(outcomes)
    require(set(counts).issubset(OUTCOME_KEYS), "unsupported official outcome")
    return {key: counts.get(key, 0) for key in OUTCOME_KEYS}


def exact_fraction(numerator: int, denominator: int) -> dict[str, Any]:
    require(numerator >= 0, "fraction numerator cannot be negative")
    require(denominator >= 0, "fraction denominator cannot be negative")
    require(numerator <= denominator, "fraction numerator cannot exceed denominator")
    if denominator == 0:
        return {
            "denominator": 0,
            "exact_fraction": "NON_DEFINI",
            "numerator": numerator,
            "state": "NON_DEFINI",
            "value": "NON_DEFINI",
        }
    return {
        "denominator": denominator,
        "exact_fraction": f"{numerator}/{denominator}",
        "numerator": numerator,
        "state": "OBSERVED",
    }


def derive_supplier_cost(observations: list[dict[str, Any]]) -> dict[str, Any]:
    currencies: set[str] = set()
    total_minor = 0
    for observation in observations:
        value = observation["value_minor"]
        currency = observation["currency"]
        if value == "INCONNU" or currency == "INCONNU":
            return {
                "currency": "INCONNU",
                "state": "INCONNU",
                "value": "INCONNU",
                "value_minor": "INCONNU",
            }
        require(type(value) is int and value >= 0, "supplier cost must be non-negative")
        require(isinstance(currency, str) and currency, "supplier cost currency missing")
        currencies.add(currency)
        total_minor += value
    require(len(currencies) == 1, "supplier costs do not share one observed currency")
    return {
        "currency": next(iter(currencies)),
        "state": "OBSERVED",
        "value_minor": total_minor,
    }


def derive_cost_per_acceptable(
    supplier_total: dict[str, Any], acceptable_outputs: int
) -> dict[str, Any]:
    if acceptable_outputs == 0:
        return {
            "reason": "ZERO_OFFICIALLY_ACCEPTABLE_OUTPUTS",
            "state": "NON_DEFINI",
            "value": "NON_DEFINI",
        }
    if supplier_total["state"] == "INCONNU":
        return {
            "reason": "SUPPLIER_COST_INCONNU_NO_IMPUTATION",
            "state": "INCONNU",
            "value": "INCONNU",
        }
    return {
        "currency": supplier_total["currency"],
        "denominator": acceptable_outputs,
        "exact_fraction_minor_units": f'{supplier_total["value_minor"]}/{acceptable_outputs}',
        "numerator_minor_units": supplier_total["value_minor"],
        "state": "OBSERVED",
    }


def derive_effort(raw_effort: dict[str, Any]) -> dict[str, Any]:
    require(set(raw_effort) == set(EFFORT_COMPONENTS), "the seven effort components are not exact")
    result: dict[str, Any] = {}
    for component in EFFORT_COMPONENTS:
        observation = raw_effort[component]
        minutes = observation["minutes"]
        if minutes == "INCONNU":
            result[component] = {
                "source_state": observation["state"],
                "state": "INCONNU",
                "value_minutes": "INCONNU",
            }
        else:
            require(type(minutes) is int and minutes >= 0, "effort minutes must be non-negative")
            result[component] = {
                "source_state": observation["state"],
                "state": "OBSERVED",
                "value_minutes": minutes,
            }
    return result


def aggregate_effort(configurations: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for component in EFFORT_COMPONENTS:
        entries = [configuration["effort_minutes"][component] for configuration in configurations]
        if any(entry["state"] == "INCONNU" for entry in entries):
            result[component] = {"state": "INCONNU", "value_minutes": "INCONNU"}
        else:
            result[component] = {
                "state": "OBSERVED",
                "value_minutes": sum(entry["value_minutes"] for entry in entries),
            }
    return result


def derive_identity_and_provenance(raw_identity: dict[str, Any]) -> dict[str, Any]:
    expected_fields = {
        "served_model",
        "served_parameters",
        "served_provider",
        "served_route",
    }
    require(set(raw_identity) == expected_fields, "served identity/provenance fields are not exact")
    fields: dict[str, Any] = {}
    overall_state = "OBSERVED"
    for name in sorted(expected_fields):
        observation = raw_identity[name]
        value = observation["value"]
        field_state = "INCONNU" if value == "INCONNU" else "OBSERVED"
        if field_state == "INCONNU":
            overall_state = "INCONNU"
        fields[name] = {
            "source_state": observation["state"],
            "state": field_state,
            "value": value,
        }
    return {"fields": fields, "state": overall_state}


def derive_freshness(checkpoint: Any) -> dict[str, Any]:
    if checkpoint == "INCONNU":
        return {"state": "INCONNU", "value": "INCONNU"}
    return {"state": "OBSERVED", "value": checkpoint}


def derive_latency(configuration: dict[str, Any]) -> dict[str, Any]:
    m7 = configuration["m7_observations"]
    m8 = configuration["m8_automatic_outcome"]
    incident = m7["incident"]["value"]
    latency = m7["latency_ms"]
    require(latency["state"] == "OBSERVED", "latency source state must be OBSERVED")
    require(type(latency["value"]) is int and latency["value"] >= 0, "latency must be an integer")
    candidate_complete = (
        m7["candidate_output_state"] == "OBSERVED"
        and m8["candidate_output_state"] == "OBSERVED"
        and incident not in {"HARNESS_ERROR", "PROVIDER_FAILURE"}
    )
    if candidate_complete:
        return {
            "pareto_axis": {
                "metric": "LATENCY_UNDER_PREREGISTERED_RULE",
                "raw_singleton_ms": [latency["value"]],
                "state": "OBSERVED",
                "unit": "INTEGER_MILLISECONDS",
            },
            "terminal_technical_elapsed_ms": {
                "state": "NOT_APPLICABLE",
                "value": "NOT_APPLICABLE",
            },
        }
    return {
        "pareto_axis": {
            "metric": "LATENCY_UNDER_PREREGISTERED_RULE",
            "reason": "NO_COMPLETE_CANDIDATE",
            "state": "INCONNU",
            "value": "INCONNU",
        },
        "terminal_technical_elapsed_ms": {
            "excluded_from_pareto_axis": True,
            "state": "OBSERVED",
            "value": latency["value"],
        },
    }


def is_covered(outcome: str, incident: str) -> bool:
    return outcome in {
        "OFFICIALLY_ACCEPTABLE",
        "CANDIDATE_NOT_ACCEPTABLE",
    } or incident == "PROVIDER_FAILURE"


def build_configuration_metrics(
    configuration: dict[str, Any], decidable_outcomes: set[str]
) -> dict[str, Any]:
    require(
        configuration["planned_slot"]["count"] == 1,
        "each configuration must have one planned slot",
    )
    outcome = derive_official_outcome(configuration)
    counts = outcome_counts([outcome])
    decidable_denominator = int(outcome in decidable_outcomes)
    official_rate = exact_fraction(
        counts["OFFICIALLY_ACCEPTABLE"], decidable_denominator
    )
    covered = int(
        is_covered(
            outcome,
            configuration["m7_observations"]["incident"]["value"],
        )
    )
    coverage = exact_fraction(
        covered,
        configuration["planned_slot"]["count"],
    )
    supplier_total = derive_supplier_cost(
        [configuration["m7_observations"]["supplier_cost"]]
    )
    cost_per_acceptable = derive_cost_per_acceptable(
        supplier_total,
        counts["OFFICIALLY_ACCEPTABLE"],
    )
    return {
        "configuration_id": configuration["configuration_id"],
        "coverage": coverage,
        "decidable_denominator": decidable_denominator,
        "effort_minutes": derive_effort(
            configuration["m7_observations"]["effort"]
        ),
        "freshness": derive_freshness(
            configuration["m7_observations"]["freshness_checkpoint"]
        ),
        "latency": derive_latency(configuration),
        "official_acceptance_rate": official_rate,
        "official_outcome": outcome,
        "outcome_counts": counts,
        "planned_slot": configuration["planned_slot"],
        "served_identity_and_provenance": derive_identity_and_provenance(
            configuration["m7_observations"]["served_identity_and_provenance"]
        ),
        "supplier_cost_per_officially_acceptable_output": cost_per_acceptable,
        "supplier_cost_total": supplier_total,
    }


def derive_pareto_entry(configuration: dict[str, Any]) -> dict[str, Any]:
    axis_states = {
        "OFFICIAL_ACCEPTANCE_RATE": configuration[
            "official_acceptance_rate"
        ]["state"],
        "SUPPLIER_COST_PER_OFFICIALLY_ACCEPTABLE_OUTPUT": configuration[
            "supplier_cost_per_officially_acceptable_output"
        ]["state"],
        "LATENCY_UNDER_PREREGISTERED_RULE": configuration[
            "latency"
        ]["pareto_axis"]["state"],
    }
    missing_axes = [
        axis["metric"]
        for axis in EXPECTED_AXES
        if axis_states[axis["metric"]] != "OBSERVED"
    ]
    blockers: list[str] = []
    if configuration["official_acceptance_rate"]["state"] == "NON_DEFINI":
        blockers.append("ZERO_DECIDABLE_OUTCOMES")
    cost_state = configuration[
        "supplier_cost_per_officially_acceptable_output"
    ]["state"]
    if cost_state == "NON_DEFINI":
        blockers.append("ZERO_OFFICIALLY_ACCEPTABLE_OUTPUTS")
    elif cost_state == "INCONNU":
        blockers.append("SUPPLIER_COST_INCONNU")
    if configuration["latency"]["pareto_axis"]["state"] == "INCONNU":
        blockers.append("NO_COMPLETE_CANDIDATE_LATENCY_INCONNU")
    if (
        configuration["coverage"]["numerator"]
        < configuration["coverage"]["denominator"]
    ):
        blockers.append("INCOMPLETE_COVERAGE")
    if configuration["served_identity_and_provenance"]["state"] == "INCONNU":
        blockers.append("SERVED_IDENTITY_PROVENANCE_INCONNU")
    if configuration["freshness"]["state"] == "INCONNU":
        blockers.append("FRESHNESS_INCONNU")
    return {
        "blockers": blockers,
        "configuration_id": configuration["configuration_id"],
        "missing_axes": missing_axes,
        "three_axes_complete": not missing_axes,
    }


def build_table(data: dict[str, Any]) -> dict[str, Any]:
    raw_configurations = data.get("configurations")
    require(
        isinstance(raw_configurations, list) and raw_configurations,
        "configurations missing",
    )
    identifiers = [
        configuration["configuration_id"]
        for configuration in raw_configurations
    ]
    require(
        len(identifiers) == len(set(identifiers)),
        "duplicate configuration identifier",
    )
    decidable_outcomes = set(
        data["calculation_conventions"]["decidable_outcomes"]
    )
    require(
        decidable_outcomes
        == {"OFFICIALLY_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE"},
        "decidable outcomes are not exact",
    )
    configurations = [
        build_configuration_metrics(configuration, decidable_outcomes)
        for configuration in raw_configurations
    ]
    aggregate_counts = outcome_counts(
        [
            configuration["official_outcome"]
            for configuration in configurations
        ]
    )
    aggregate_decidable = sum(
        configuration["decidable_denominator"]
        for configuration in configurations
    )
    aggregate_coverage_numerator = sum(
        configuration["coverage"]["numerator"]
        for configuration in configurations
    )
    aggregate_coverage_denominator = sum(
        configuration["coverage"]["denominator"]
        for configuration in configurations
    )
    aggregate_supplier_total = derive_supplier_cost(
        [
            configuration["m7_observations"]["supplier_cost"]
            for configuration in raw_configurations
        ]
    )
    aggregate = {
        "coverage": exact_fraction(
            aggregate_coverage_numerator,
            aggregate_coverage_denominator,
        ),
        "decidable_denominator": aggregate_decidable,
        "effort_minutes": aggregate_effort(configurations),
        "official_acceptance_rate": exact_fraction(
            aggregate_counts["OFFICIALLY_ACCEPTABLE"],
            aggregate_decidable,
        ),
        "outcome_counts": aggregate_counts,
        "supplier_cost_per_officially_acceptable_output": (
            derive_cost_per_acceptable(
                aggregate_supplier_total,
                aggregate_counts["OFFICIALLY_ACCEPTABLE"],
            )
        ),
        "supplier_cost_total": aggregate_supplier_total,
    }
    aggregate_evidence = data["aggregate_evidence"]
    require(
        aggregate_supplier_total["state"]
        == aggregate_evidence["m7_supplier_cost_total"]["state"],
        "aggregate supplier cost conflicts with linked evidence",
    )
    require(
        aggregate["coverage"]["exact_fraction"]
        == aggregate_evidence["m8_planned_output_coverage"],
        "aggregate coverage conflicts with linked evidence",
    )
    require(
        aggregate_evidence["m9_human_verdicts"] == 0,
        "unexpected M9 human verdict",
    )
    require(
        aggregate_evidence["m9_review_dossiers"] == 0,
        "unexpected M9 review dossier",
    )
    pareto_entries = [
        derive_pareto_entry(configuration)
        for configuration in configurations
    ]
    require(
        not any(entry["three_axes_complete"] for entry in pareto_entries),
        "current evidence unexpectedly permits a full three-axis front",
    )
    return {
        "aggregate": aggregate,
        "authority_roots": data["authority_roots"],
        "configurations": configurations,
        "decision_outputs": {
            "global_score": "FORBIDDEN",
            "m10_2_recommendation": "NOT_PRODUCED",
            "winner": "NOT_PRODUCED",
        },
        "evidence_contract": {
            "candidate_content_copied": data["candidate_content_copied"],
            "no_imputation": data["calculation_conventions"]["no_imputation"],
            "public_source_binding_count": len(
                data["public_evidence"]["source_bindings"]
            ),
        },
        "frozen_contract_sha256": data["frozen_contract_sha256"],
        "pareto": {
            "axes": data["metric_rules"]["pareto"]["axes"],
            "front": [],
            "per_configuration": pareto_entries,
            "status": "FULL_THREE_AXIS_FRONT_NOT_COMPUTABLE",
        },
        "schema_version": "campaign-v0-m10-1-decision-metrics-table/v1",
        "scope": data["scope"],
        "status": "OFFLINE_METRICS_COMPUTED",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute M10.1 offline decision metrics"
    )
    parser.add_argument("--input", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    table = build_table(load_input(arguments.input))
    serialized = json.dumps(
        table,
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    sys.stdout.write(serialized + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
