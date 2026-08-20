from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import re
from types import MappingProxyType


INCONNU = "INCONNU"
STIMULUS_SHA256 = "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4"
RECEIPT_SCHEMA = "campaign-v0-acquisition-receipt/v1"
DECISION_VIEW_SCHEMA = "campaign-v0-decision-view/v1"

SLOTS = {
    "grok46_xai_build_oauth": "ACQ-GROK46-PRIMARY-001",
    "kimi_k3_cursor_cli": "ACQ-KIMIK3-PRIMARY-001",
}
INCIDENTS = {
    "PROVIDER_FAILURE": "TERMINAL_SLOT_COUNTS_AS_CONFIGURATION_FAILURE_RETAIN_ATTRIBUTABLE_COST_CONTINUE_OTHER_PLANNED_SLOT",
    "HARNESS_ERROR": "NO_CONFIGURATION_PENALTY_REDUCE_COVERAGE_STOP_CAMPAIGN",
    "IDENTITY_MISMATCH": "OBSERVED_VALUE_CONFLICTS_WITH_LOCK_HOLD_AND_STOP",
    "MISSING_OBSERVATION": "INCONNU_PRESERVE_RECEIPT_CONFIGURATION_NOT_OFFICIALLY_COMPARABLE",
}
EFFORT_COMPONENTS = (
    "configuration",
    "integration",
    "execution",
    "human_review",
    "verification",
    "maintenance",
    "report_production",
)
OBSERVATION_FIELDS = {
    "candidate_content",
    "effort_minutes",
    "incident_facts",
    "latency_ms",
    "provider_cost",
    "served_model",
    "served_parameters",
    "served_provider",
    "served_route",
}
INCIDENT_FACT_FIELDS = {
    "identity_mismatch",
    "local_or_unattributable_failure",
    "missing_required_observation",
    "provider_attribution_proven",
    "provider_operation_failed",
}
BLIND_FORBIDDEN_FIELDS = {
    "acquisition_id",
    "configuration",
    "configuration_id",
    "cost",
    "latency",
    "latency_ms",
    "model",
    "provider",
    "provider_cost",
    "route",
    "served_model",
    "served_provider",
    "served_route",
    "usage",
}
BLIND_FORBIDDEN_TOKENS = (
    "acquisition",
    "configuration",
    "cost",
    "latency",
    "mapping",
    "model",
    "provider",
    "route",
    "usage",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ITEM_ID = re.compile(r"^ITEM-[0-9]{3}$")


class PreparationContractError(ValueError):
    pass


def _strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _closed(value: object, fields: set[str], name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise PreparationContractError(f"closed schema mismatch: {name}")
    return value


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise PreparationContractError("JSON object keys must be text")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                _json_value(value),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as exc:
        raise PreparationContractError("non-canonical JSON value") from exc


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _observed(value: object = INCONNU) -> dict[str, object]:
    return {"state": "OBSERVED", "value": value}


def classify_incident(facts: Mapping[str, object]) -> str:
    checked = _closed(facts, INCIDENT_FACT_FIELDS, "incident_facts")
    if any(type(checked[field]) is not bool for field in INCIDENT_FACT_FIELDS):
        raise PreparationContractError("incident facts must be booleans")
    if checked["identity_mismatch"]:
        return "IDENTITY_MISMATCH"
    if checked["local_or_unattributable_failure"]:
        return "HARNESS_ERROR"
    if checked["provider_operation_failed"]:
        if checked["provider_attribution_proven"]:
            return "PROVIDER_FAILURE"
        return "HARNESS_ERROR"
    if checked["missing_required_observation"]:
        return "MISSING_OBSERVATION"
    return INCONNU


def _normalise_cost(value: object) -> dict[str, object]:
    if value is None:
        return {
            "attributable_evidence_sha256": INCONNU,
            "currency": INCONNU,
            "state": "OBSERVED",
            "value_minor": INCONNU,
        }
    checked = _closed(
        value,
        {"attributable_evidence_sha256", "currency", "value_minor"},
        "provider_cost",
    )
    evidence = checked["attributable_evidence_sha256"]
    amount = checked["value_minor"]
    currency = checked["currency"]
    if (
        not isinstance(evidence, str)
        or _SHA256.fullmatch(evidence) is None
        or not _strict_int(amount)
        or amount < 0
        or not isinstance(currency, str)
        or not currency
    ):
        raise PreparationContractError("attributable provider cost evidence required")
    return {
        "attributable_evidence_sha256": evidence,
        "currency": currency,
        "state": "OBSERVED",
        "value_minor": amount,
    }


def _normalise_effort(value: object) -> dict[str, object]:
    supplied = {} if value is None else value
    if not isinstance(supplied, Mapping) or not set(supplied).issubset(EFFORT_COMPONENTS):
        raise PreparationContractError("effort components mismatch")
    result: dict[str, object] = {}
    for component in EFFORT_COMPONENTS:
        minutes = supplied.get(component, INCONNU)
        if minutes != INCONNU and (not _strict_int(minutes) or minutes < 0):
            raise PreparationContractError("effort must be non-negative integer minutes")
        result[component] = {"minutes": minutes, "state": "OBSERVED"}
    return result


def normalise_observations(supplied: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(supplied, Mapping) or not set(supplied).issubset(OBSERVATION_FIELDS):
        raise PreparationContractError("observation fields mismatch")
    latency = supplied.get("latency_ms", INCONNU)
    if latency != INCONNU and (not _strict_int(latency) or latency < 0):
        raise PreparationContractError("latency must be non-negative integer milliseconds")
    candidate_content = supplied.get("candidate_content", INCONNU)
    if candidate_content != INCONNU and not isinstance(candidate_content, str):
        raise PreparationContractError("candidate content must be text")
    candidate_sha256 = (
        INCONNU
        if candidate_content == INCONNU
        else hashlib.sha256(candidate_content.encode("utf-8")).hexdigest()
    )
    incident_facts = supplied.get("incident_facts")
    incident = INCONNU if incident_facts is None else classify_incident(incident_facts)
    result = {
        "candidate": {
            "content": candidate_content,
            "sha256": candidate_sha256,
            "state": "OBSERVED",
        },
        "effort": _normalise_effort(supplied.get("effort_minutes")),
        "incident": {
            "effect": INCIDENTS.get(incident, INCONNU),
            "state": "OBSERVED",
            "value": incident,
        },
        "latency_ms": _observed(latency),
        "provider_cost": _normalise_cost(supplied.get("provider_cost")),
        "served_model": _observed(supplied.get("served_model", INCONNU)),
        "served_parameters": _observed(supplied.get("served_parameters", INCONNU)),
        "served_provider": _observed(supplied.get("served_provider", INCONNU)),
        "served_route": _observed(supplied.get("served_route", INCONNU)),
    }
    return _freeze(result)


def build_receipt(
    configuration_id: str,
    command_descriptor: Mapping[str, object],
    supplied_observations: Mapping[str, object],
    predecessor_content_sha256: str | None,
) -> Mapping[str, object]:
    if configuration_id not in SLOTS:
        raise PreparationContractError("configuration outside locked panel")
    if predecessor_content_sha256 is not None and (
        not isinstance(predecessor_content_sha256, str)
        or _SHA256.fullmatch(predecessor_content_sha256) is None
    ):
        raise PreparationContractError("invalid predecessor content address")
    descriptor = _closed(
        command_descriptor,
        {"argv", "configuration_id", "schema_version", "state", "workspace"},
        "command_descriptor",
    )
    if descriptor["configuration_id"] != configuration_id or descriptor["state"] != "REQUESTED":
        raise PreparationContractError("requested descriptor identity mismatch")
    payload = {
        "acquisition_id": SLOTS[configuration_id],
        "configuration_id": configuration_id,
        "observations": normalise_observations(supplied_observations),
        "predecessor_content_sha256": predecessor_content_sha256,
        "request": {"command_descriptor": descriptor, "state": "REQUESTED"},
        "stimulus": {"sha256": STIMULUS_SHA256, "state": "EXPECTED"},
    }
    receipt = {
        "content_address": {
            "algorithm": "SHA256",
            "sha256": canonical_sha256(payload),
        },
        "payload": payload,
        "schema_version": RECEIPT_SCHEMA,
    }
    validate_receipt(receipt)
    return _freeze(receipt)


def validate_receipt(receipt: Mapping[str, object]) -> None:
    checked = _closed(receipt, {"content_address", "payload", "schema_version"}, "receipt")
    if checked["schema_version"] != RECEIPT_SCHEMA:
        raise PreparationContractError("receipt schema mismatch")
    address = _closed(checked["content_address"], {"algorithm", "sha256"}, "content_address")
    if address["algorithm"] != "SHA256" or address["sha256"] != canonical_sha256(checked["payload"]):
        raise PreparationContractError("receipt content address mismatch")
    payload = _closed(
        checked["payload"],
        {
            "acquisition_id",
            "configuration_id",
            "observations",
            "predecessor_content_sha256",
            "request",
            "stimulus",
        },
        "receipt.payload",
    )
    configuration_id = payload["configuration_id"]
    if configuration_id not in SLOTS or payload["acquisition_id"] != SLOTS[configuration_id]:
        raise PreparationContractError("receipt slot mismatch")
    predecessor = payload["predecessor_content_sha256"]
    if predecessor is not None and (
        not isinstance(predecessor, str) or _SHA256.fullmatch(predecessor) is None
    ):
        raise PreparationContractError("invalid receipt predecessor")
    request = _closed(payload["request"], {"command_descriptor", "state"}, "receipt.request")
    descriptor = _closed(
        request["command_descriptor"],
        {"argv", "configuration_id", "schema_version", "state", "workspace"},
        "receipt.command_descriptor",
    )
    if (
        request["state"] != "REQUESTED"
        or descriptor["state"] != "REQUESTED"
        or descriptor["schema_version"] != "campaign-v0-command-descriptor/v1"
        or descriptor["configuration_id"] != configuration_id
        or not isinstance(descriptor["argv"], (tuple, list))
        or not descriptor["argv"]
        or any(not isinstance(item, str) for item in descriptor["argv"])
        or descriptor["workspace"] != "__ISOLATED_WORKSPACE__"
    ):
        raise PreparationContractError("receipt request mismatch")
    stimulus = _closed(payload["stimulus"], {"sha256", "state"}, "receipt.stimulus")
    if stimulus != {"sha256": STIMULUS_SHA256, "state": "EXPECTED"}:
        raise PreparationContractError("receipt stimulus mismatch")
    observations = _closed(
        payload["observations"],
        {
            "candidate",
            "effort",
            "incident",
            "latency_ms",
            "provider_cost",
            "served_model",
            "served_parameters",
            "served_provider",
            "served_route",
        },
        "receipt.observations",
    )
    candidate = _closed(observations["candidate"], {"content", "sha256", "state"}, "receipt.candidate")
    content = candidate["content"]
    expected_candidate_hash = (
        INCONNU
        if content == INCONNU
        else hashlib.sha256(str(content).encode("utf-8")).hexdigest()
    )
    if (
        candidate["state"] != "OBSERVED"
        or not isinstance(content, str)
        or candidate["sha256"] != expected_candidate_hash
    ):
        raise PreparationContractError("receipt candidate mismatch")
    effort = _closed(observations["effort"], set(EFFORT_COMPONENTS), "receipt.effort")
    for component in EFFORT_COMPONENTS:
        envelope = _closed(effort[component], {"minutes", "state"}, f"receipt.effort.{component}")
        minutes = envelope["minutes"]
        if (
            envelope["state"] != "OBSERVED"
            or (minutes != INCONNU and (not _strict_int(minutes) or minutes < 0))
        ):
            raise PreparationContractError("receipt effort mismatch")
    incident = _closed(observations["incident"], {"effect", "state", "value"}, "receipt.incident")
    if (
        incident["state"] != "OBSERVED"
        or incident["value"] not in {*INCIDENTS, INCONNU}
        or incident["effect"] != INCIDENTS.get(incident["value"], INCONNU)
    ):
        raise PreparationContractError("receipt incident mismatch")
    for field in (
        "latency_ms",
        "served_model",
        "served_parameters",
        "served_provider",
        "served_route",
    ):
        envelope = _closed(observations[field], {"state", "value"}, f"receipt.{field}")
        if envelope["state"] != "OBSERVED":
            raise PreparationContractError("receipt observation state mismatch")
    latency = observations["latency_ms"]["value"]
    if latency != INCONNU and (not _strict_int(latency) or latency < 0):
        raise PreparationContractError("receipt latency mismatch")
    cost = _closed(
        observations["provider_cost"],
        {"attributable_evidence_sha256", "currency", "state", "value_minor"},
        "receipt.provider_cost",
    )
    if cost["state"] != "OBSERVED":
        raise PreparationContractError("receipt cost state mismatch")
    if cost["value_minor"] == INCONNU:
        if cost != {
            "attributable_evidence_sha256": INCONNU,
            "currency": INCONNU,
            "state": "OBSERVED",
            "value_minor": INCONNU,
        }:
            raise PreparationContractError("receipt unknown cost imputed")
    else:
        _normalise_cost(
            {
                "attributable_evidence_sha256": cost["attributable_evidence_sha256"],
                "currency": cost["currency"],
                "value_minor": cost["value_minor"],
            }
        )


def _reject_blind_leakage(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in BLIND_FORBIDDEN_FIELDS or any(
                token in lowered for token in BLIND_FORBIDDEN_TOKENS
            ):
                raise PreparationContractError("blind view field leakage")
            _reject_blind_leakage(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _reject_blind_leakage(item)


def build_blind_decision_view(
    receipt: Mapping[str, object],
    item_id: str,
    rubric: object,
    automatic_controls: Mapping[str, object],
) -> Mapping[str, object]:
    validate_receipt(receipt)
    if not isinstance(item_id, str) or _ITEM_ID.fullmatch(item_id) is None:
        raise PreparationContractError("opaque item identity required")
    expected_controls = {f"G-{index:03d}" for index in range(1, 6)}
    if not isinstance(automatic_controls, Mapping) or set(automatic_controls) != expected_controls:
        raise PreparationContractError("automatic controls G-001 through G-005 required")
    if any(value not in {True, False, INCONNU} for value in automatic_controls.values()):
        raise PreparationContractError("invalid automatic control result")
    _reject_blind_leakage(rubric)
    candidate = receipt["payload"]["observations"]["candidate"]
    view = {
        "automatic_controls": [
            {"control_id": control_id, "result": automatic_controls[control_id]}
            for control_id in sorted(automatic_controls)
        ],
        "candidate_content": candidate["content"],
        "candidate_sha256": candidate["sha256"],
        "human_review": {"frozen": False, "notes": INCONNU, "verdict": INCONNU},
        "item_id": item_id,
        "rubric": rubric,
        "schema_version": DECISION_VIEW_SCHEMA,
    }
    _reject_blind_leakage(view)
    return _freeze(view)
