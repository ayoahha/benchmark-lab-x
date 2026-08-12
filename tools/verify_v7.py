"""Noyau verify-v7 pur en mémoire, propriétaire des octets candidats."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Callable, Protocol, Sequence, runtime_checkable


MARKER_PREPARE = "PREPARE"
MARKER_AUTOTEST = "AUTOTEST"
MARKER_HARNESS_READY = "HARNESS_READY"
MARKER_ADMISSION = "ADMISSION"
MARKER_LOAD = "LOAD"
MARKER_INIT = "INIT"
MARKER_EVAL = "EVAL"
MARKER_TEARDOWN = "TEARDOWN"
MARKER_BUDGET_EXPIRED = "BUDGET_EXPIRED"

CANDIDATE_MARKERS = frozenset({MARKER_LOAD, MARKER_INIT, MARKER_EVAL})
KNOWN_MARKERS = frozenset({
    MARKER_PREPARE,
    MARKER_AUTOTEST,
    MARKER_HARNESS_READY,
    MARKER_ADMISSION,
    MARKER_LOAD,
    MARKER_INIT,
    MARKER_EVAL,
    MARKER_TEARDOWN,
    MARKER_BUDGET_EXPIRED,
})
COMPLETED_MEASUREMENT_ORDER = (
    MARKER_PREPARE,
    MARKER_AUTOTEST,
    MARKER_HARNESS_READY,
    MARKER_ADMISSION,
    MARKER_LOAD,
    MARKER_INIT,
    MARKER_EVAL,
    MARKER_TEARDOWN,
)
LIMIT_MEASUREMENT_ORDERS = tuple(
    (
        MARKER_PREPARE,
        MARKER_AUTOTEST,
        MARKER_HARNESS_READY,
        MARKER_ADMISSION,
        *candidate_prefix,
        MARKER_BUDGET_EXPIRED,
        MARKER_TEARDOWN,
    )
    for candidate_prefix in (
        (MARKER_LOAD,),
        (MARKER_LOAD, MARKER_INIT),
        (MARKER_LOAD, MARKER_INIT, MARKER_EVAL),
    )
)
INVALID_ADMISSION_ORDER = (
    MARKER_PREPARE,
    MARKER_AUTOTEST,
    MARKER_HARNESS_READY,
    MARKER_ADMISSION,
    MARKER_TEARDOWN,
)

MEASUREMENT_STATES = frozenset({"SCORED", "NOT_SCORED"})
CAUSAL_CLASSES = frozenset({
    "MEASUREMENT_COMPLETED",
    "PROVIDER_FAILURE",
    "ARTIFACT_INVALID",
    "ARTIFACT_EXECUTION_LIMIT",
    "HARNESS_ERROR",
})
INCIDENT_SCOPES = frozenset({"ACQUISITION", "AXIS"})
HARNESS_DIAGNOSTIC_CODES = frozenset({
    "ATTESTATION_INVALID",
    "ATTESTATION_BINDING_MISMATCH",
    "CANDIDATE_GATE_ORDER",
    "OBSERVATION_TYPE_INVALID",
    "STATE_CONTRADICTION",
    "ADAPTER_EXCEPTION",
    "CONFINEMENT_UNHEALTHY",
    "EVIDENCE_MISSING",
})
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
COUNTER_RULE = "monotonic-end-minus-start/v1"
CANONICAL_JSON_VERSION = "verify-v7-canonical-json/v1"
ENVIRONMENT_SCHEMA_VERSION = "verify-v7-environment/v1"
HTML_ADMISSION_RULE = "verify-v7-html-static-admission/v1"


class VerifyV7ContratInvalide(ValueError):
    """Entrée appelant mal formée ou résultat public incohérent"""


class _HarnessFailure(Exception):
    def __init__(
        self,
        code: str,
        missing: tuple[str, ...],
        *,
        stage: str = "harness",
    ) -> None:
        super().__init__(code)
        self.code = code
        self.missing = missing
        self.stage = stage


def _strict_bool(value: object) -> bool:
    return type(value) is bool


def _strict_int(value: object) -> bool:
    return type(value) is int


def _strict_string(value: object) -> bool:
    return type(value) is str and value != "" and value == value.strip()


def _digest_string(value: object) -> bool:
    return _strict_string(value) and DIGEST_RE.fullmatch(value) is not None


def _proof_ref(value: object) -> bool:
    return _strict_string(value)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyV7ContratInvalide(message)


def _canonical_json(value: object) -> bytes:
    def validate(item: object) -> None:
        if type(item) in {str, bool, int}:
            return
        if isinstance(item, list) or isinstance(item, tuple):
            for child in item:
                validate(child)
            return
        if isinstance(item, dict):
            for key, child in item.items():
                if type(key) is not str:
                    raise TypeError("canonical object key")
                validate(child)
            return
        raise TypeError("canonical scalar")

    validate(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _bytes_digest(content: bytes) -> str:
    return f"sha256:{sha256(content).hexdigest()}"


def _value_digest(value: object) -> str:
    return _bytes_digest(_canonical_json(value))


@dataclass(frozen=True)
class AdapterIdentity:
    adapter_id: str
    adapter_version: str
    adapter_hash: str


@dataclass(frozen=True)
class QualifiedBudget:
    value: int
    unit: str
    budget_hash: str
    scope: str
    measurement_rule: str


@dataclass(frozen=True)
class ProviderEvidence:
    lock_bound: bool
    payload_bound: bool
    route_pinned: bool
    provider_pinned: bool
    attempt_receipt_ref: str | None
    response_or_error_ref: str | None
    artifact_admissible: bool


@dataclass(frozen=True)
class Artifact:
    content: bytes = field(repr=False)
    digest: str
    proof_ref: str


@dataclass(frozen=True)
class RuntimeIdentity:
    id: str
    version: str
    digest: str


@dataclass(frozen=True)
class EnvironmentManifest:
    schema_version: str
    python_runtime: RuntimeIdentity
    operating_system: RuntimeIdentity
    modality_runtime: RuntimeIdentity
    dependencies: tuple[RuntimeIdentity, ...]
    influential_configuration: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class HarnessExpectations:
    adapter_identity: AdapterIdentity
    environment_manifest: EnvironmentManifest
    core_digest: str


@dataclass(frozen=True)
class MonotonicCounter:
    source_id: str
    unit: str
    rule: str
    read: Callable[[], int] = field(repr=False, compare=False)


@dataclass(frozen=True)
class AxisExecutionRequest:
    acquisition_id: str
    axis_id: str
    artifact_digest: str
    artifact_proof_ref: str
    qualified_budget: QualifiedBudget
    budget_digest: str
    adapter_identity: AdapterIdentity
    environment_digest: str
    core_digest: str


@dataclass(frozen=True)
class HarnessPreparation:
    session_id: str
    axis_id: str
    adapter_identity: AdapterIdentity
    environment_digest: str
    budget_digest: str
    core_digest: str
    artifact_digest: str
    artifact_proof_ref: str
    bootstrap_success: bool
    autotest_success: bool
    stage_proofs: tuple[tuple[str, str], ...]
    watchdog_healthy: bool
    ambiguous: bool = False


@dataclass(frozen=True)
class TemporalMarker:
    source_id: str
    unit: str
    rule: str
    value: int
    axis_id: str
    session_id: str
    boundary: str
    proof_ref: str


@dataclass(frozen=True)
class HarnessReadyAttestation:
    session_id: str
    acquisition_id: str
    axis_id: str
    adapter_identity: AdapterIdentity
    environment_digest: str
    budget_digest: str
    artifact_digest: str
    artifact_proof_ref: str
    core_digest: str
    bootstrap_proof_ref: str
    autotest_proof_ref: str
    start_marker: TemporalMarker
    receipt_ref: str


@dataclass(frozen=True)
class StaticAdmissionAttestation:
    rule: str
    artifact_digest: str
    artifact_proof_ref: str
    adapter_identity: AdapterIdentity
    accepted: bool
    dynamic_confinement_claimed: bool
    proof_ref: str


@dataclass
class _AdmissionState:
    attestation: StaticAdmissionAttestation | None = None
    inspection_count: int = 0


class CandidatePermit:
    """Capacité émise par le noyau après READY, jamais persistée dans le résultat"""

    __slots__ = (
        "ready_attestation",
        "_artifact",
        "_adapter_identity",
        "_admission_state",
        "_authorized",
    )

    def __init__(
        self,
        *,
        ready_attestation: HarnessReadyAttestation,
        artifact: Artifact,
        adapter_identity: AdapterIdentity,
        admission_state: _AdmissionState,
    ) -> None:
        self.ready_attestation = ready_attestation
        self._artifact = artifact
        self._adapter_identity = adapter_identity
        self._admission_state = admission_state
        self._authorized = False

    def inspect(
        self,
        *,
        rule: str,
        predicate: Callable[[bytes], bool],
    ) -> StaticAdmissionAttestation:
        if rule != HTML_ADMISSION_RULE:
            raise _HarnessFailure(
                "CANDIDATE_GATE_ORDER",
                ("static_admission_rule",),
                stage="admission",
            )
        attestation = self._admission_state.attestation
        if attestation is None:
            content = self._artifact.content
            if _bytes_digest(content) != self._artifact.digest:
                raise _HarnessFailure(
                    "ATTESTATION_BINDING_MISMATCH",
                    ("artifact_digest",),
                    stage="admission",
                )
            try:
                accepted = predicate(content)
            except Exception:
                accepted = False
            if not _strict_bool(accepted):
                accepted = False
            payload = {
                "accepted": accepted,
                "adapter_identity": _adapter_payload(self._adapter_identity),
                "artifact_digest": self._artifact.digest,
                "artifact_proof_ref": self._artifact.proof_ref,
                "dynamic_confinement_claimed": False,
                "rule": rule,
            }
            attestation = StaticAdmissionAttestation(
                rule=rule,
                artifact_digest=self._artifact.digest,
                artifact_proof_ref=self._artifact.proof_ref,
                adapter_identity=self._adapter_identity,
                accepted=accepted,
                dynamic_confinement_claimed=False,
                proof_ref=_value_digest(payload),
            )
            self._admission_state.attestation = attestation
            self._admission_state.inspection_count += 1
        elif (
            attestation.rule != rule
            or attestation.adapter_identity != self._adapter_identity
            or attestation.artifact_digest != self._artifact.digest
            or attestation.artifact_proof_ref != self._artifact.proof_ref
        ):
            raise _HarnessFailure(
                "ATTESTATION_BINDING_MISMATCH",
                ("static_admission_binding",),
                stage="admission",
            )
        self._authorized = attestation.accepted
        return attestation

    @property
    def candidate_bytes(self) -> bytes:
        if not self._authorized:
            raise _HarnessFailure(
                "CANDIDATE_GATE_ORDER",
                ("static_admission",),
                stage="admission",
            )
        return self._artifact.content


@dataclass(frozen=True)
class AxisObservation:
    session_id: str
    axis_id: str
    ready_receipt_ref: str
    artifact_digest: str
    artifact_proof_ref: str
    budget_digest: str
    environment_digest: str
    admission_result: bool
    admission_attestation: StaticAdmissionAttestation
    admission_stage_proof_ref: str
    stage_proofs: tuple[tuple[str, str], ...]
    evaluation_completed: bool
    verdict: str | None
    budget_expired: bool
    watchdog_healthy: bool
    ambiguous: bool
    network_attempted: bool
    confinement_healthy: bool
    confinement_ambiguous: bool


@dataclass(frozen=True)
class TeardownObservation:
    session_id: str
    axis_id: str
    proof_ref: str
    complete: bool
    watchdog_healthy: bool
    ambiguous: bool = False


@runtime_checkable
class AxisSession(Protocol):
    def prepare(self) -> HarnessPreparation: ...

    def inspect_and_execute(self, permit: CandidatePermit) -> AxisObservation: ...

    def teardown(self) -> TeardownObservation: ...


@runtime_checkable
class ModalityAdapter(Protocol):
    @property
    def identity(self) -> AdapterIdentity: ...

    def open_axis(self, request: AxisExecutionRequest) -> AxisSession: ...


@dataclass(frozen=True)
class VerificationContext:
    acquisition_id: str
    axis_ids: tuple[str, ...]
    adapter_identity: AdapterIdentity
    artifact_digest: str
    artifact_proof_ref: str
    qualified_budget: QualifiedBudget
    budget_digest: str
    environment_manifest: EnvironmentManifest
    environment_digest: str
    core_digest: str
    counter_source_id: str
    counter_unit: str
    counter_rule: str


@dataclass(frozen=True)
class AxisTrace:
    axis_id: str
    session_id: str
    markers: tuple[str, ...]
    stage_proofs: tuple[tuple[str, str], ...]
    ready_attestation: HarnessReadyAttestation
    observation: AxisObservation
    teardown_observation: TeardownObservation
    admission_result: bool
    admission_attestation: StaticAdmissionAttestation
    evaluation_completed: bool
    verdict: str | None
    budget_expired: bool
    observed_cost: int | None
    start_marker: TemporalMarker
    end_marker: TemporalMarker | None
    qualified_budget: QualifiedBudget
    context_digest: str
    watchdog_healthy: bool
    teardown_complete: bool
    ambiguous: bool


@dataclass(frozen=True)
class Incident:
    incident_id: str
    stage: str
    scope: str
    causal_class: str
    affected_unit_ids: tuple[str, ...]
    proof_refs: tuple[str, ...]
    context_digest: str
    missing_evidence: tuple[str, ...] = ()
    diagnostic_code: str = ""


@dataclass(frozen=True)
class UnitResult:
    axis_id: str
    measurement_state: str
    causal_class: str
    verdict: str | None
    incident_id: str | None
    context_digest: str
    trace: AxisTrace | None


@dataclass(frozen=True)
class AcquisitionResult:
    acquisition_id: str
    units: tuple[UnitResult, ...]
    incidents: tuple[Incident, ...]
    adapter_call_count: int
    verification_context: VerificationContext
    context_digest: str
    ready_attestations: tuple[HarnessReadyAttestation, ...]
    admission_attestation: StaticAdmissionAttestation | None
    static_admission_count: int


@dataclass(frozen=True)
class _TraceDecision:
    measurement_state: str
    causal_class: str
    verdict: str | None
    proof_refs: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    diagnostic_code: str
    stage: str


def _adapter_payload(identity: AdapterIdentity) -> dict[str, object]:
    return {
        "adapter_hash": identity.adapter_hash,
        "adapter_id": identity.adapter_id,
        "adapter_version": identity.adapter_version,
    }


def _runtime_payload(identity: RuntimeIdentity) -> dict[str, object]:
    return {"digest": identity.digest, "id": identity.id, "version": identity.version}


def _environment_payload(manifest: EnvironmentManifest) -> dict[str, object]:
    return {
        "dependencies": [_runtime_payload(item) for item in manifest.dependencies],
        "influential_configuration": [list(item) for item in manifest.influential_configuration],
        "modality_runtime": _runtime_payload(manifest.modality_runtime),
        "operating_system": _runtime_payload(manifest.operating_system),
        "python_runtime": _runtime_payload(manifest.python_runtime),
        "schema_version": manifest.schema_version,
    }


def _budget_payload(budget: QualifiedBudget) -> dict[str, object]:
    return {
        "measurement_rule": budget.measurement_rule,
        "scope": budget.scope,
        "unit": budget.unit,
        "value": budget.value,
    }


def _marker_payload(marker: TemporalMarker) -> dict[str, object]:
    return {
        "axis_id": marker.axis_id,
        "boundary": marker.boundary,
        "rule": marker.rule,
        "session_id": marker.session_id,
        "source_id": marker.source_id,
        "unit": marker.unit,
        "value": marker.value,
    }


def _attestation_payload(attestation: HarnessReadyAttestation) -> dict[str, object]:
    return {
        "acquisition_id": attestation.acquisition_id,
        "adapter_identity": _adapter_payload(attestation.adapter_identity),
        "artifact_digest": attestation.artifact_digest,
        "artifact_proof_ref": attestation.artifact_proof_ref,
        "autotest_proof_ref": attestation.autotest_proof_ref,
        "axis_id": attestation.axis_id,
        "bootstrap_proof_ref": attestation.bootstrap_proof_ref,
        "budget_digest": attestation.budget_digest,
        "core_digest": attestation.core_digest,
        "environment_digest": attestation.environment_digest,
        "session_id": attestation.session_id,
        "start_marker": {**_marker_payload(attestation.start_marker), "proof_ref": attestation.start_marker.proof_ref},
    }


def _admission_payload(attestation: StaticAdmissionAttestation) -> dict[str, object]:
    return {
        "accepted": attestation.accepted,
        "adapter_identity": _adapter_payload(attestation.adapter_identity),
        "artifact_digest": attestation.artifact_digest,
        "artifact_proof_ref": attestation.artifact_proof_ref,
        "dynamic_confinement_claimed": attestation.dynamic_confinement_claimed,
        "rule": attestation.rule,
    }


def _context_payload(context: VerificationContext) -> dict[str, object]:
    return {
        "acquisition_id": context.acquisition_id,
        "adapter_identity": _adapter_payload(context.adapter_identity),
        "artifact_digest": context.artifact_digest,
        "artifact_proof_ref": context.artifact_proof_ref,
        "axis_ids": list(context.axis_ids),
        "budget_digest": context.budget_digest,
        "core_digest": context.core_digest,
        "counter_rule": context.counter_rule,
        "counter_source_id": context.counter_source_id,
        "counter_unit": context.counter_unit,
        "environment_digest": context.environment_digest,
        "environment_manifest": _environment_payload(context.environment_manifest),
        "qualified_budget": {
            **_budget_payload(context.qualified_budget),
            "budget_hash": context.qualified_budget.budget_hash,
        },
    }


def _validate_adapter_identity(identity: object) -> None:
    _require(isinstance(identity, AdapterIdentity), "adapter identity requise")
    _require(_strict_string(identity.adapter_id), "adapter_id invalide")
    _require(_strict_string(identity.adapter_version), "adapter_version invalide")
    _require(_digest_string(identity.adapter_hash), "adapter_hash invalide")


def _validate_runtime_identity(identity: object) -> None:
    _require(isinstance(identity, RuntimeIdentity), "runtime identity requise")
    _require(_strict_string(identity.id), "runtime id invalide")
    _require(_strict_string(identity.version), "runtime version invalide")
    _require(_digest_string(identity.digest), "runtime digest invalide")


def _validate_environment(manifest: object) -> None:
    _require(isinstance(manifest, EnvironmentManifest), "environment manifest requis")
    _require(manifest.schema_version == ENVIRONMENT_SCHEMA_VERSION, "environment schema")
    for identity in (
        manifest.python_runtime,
        manifest.operating_system,
        manifest.modality_runtime,
    ):
        _validate_runtime_identity(identity)
    _require(type(manifest.dependencies) is tuple, "dependencies tuple")
    for identity in manifest.dependencies:
        _validate_runtime_identity(identity)
    dependency_keys = tuple(item.id for item in manifest.dependencies)
    _require(dependency_keys == tuple(sorted(dependency_keys)), "dependencies triées")
    _require(len(dependency_keys) == len(set(dependency_keys)), "dependencies uniques")
    _require(
        type(manifest.influential_configuration) is tuple,
        "configuration tuple",
    )
    config_keys: list[str] = []
    for item in manifest.influential_configuration:
        _require(type(item) is tuple and len(item) == 2, "configuration entry")
        key, digest = item
        _require(_strict_string(key), "configuration key")
        _require(_digest_string(digest), "configuration digest")
        config_keys.append(key)
    _require(tuple(config_keys) == tuple(sorted(config_keys)), "configuration triée")
    _require(len(config_keys) == len(set(config_keys)), "configuration unique")


def _validate_budget(budget: object) -> None:
    _require(isinstance(budget, QualifiedBudget), "qualified_budget requis")
    _require(_strict_int(budget.value) and budget.value > 0, "budget value invalide")
    _require(_strict_string(budget.unit), "budget unit invalide")
    _require(_digest_string(budget.budget_hash), "budget_hash invalide")
    _require(_strict_string(budget.scope), "budget scope invalide")
    _require(_strict_string(budget.measurement_rule), "measurement_rule invalide")


def _validate_provider(evidence: object) -> None:
    _require(isinstance(evidence, ProviderEvidence), "provider_evidence requis")
    for value in (
        evidence.lock_bound,
        evidence.payload_bound,
        evidence.route_pinned,
        evidence.provider_pinned,
        evidence.artifact_admissible,
    ):
        _require(_strict_bool(value), "provider boolean invalide")
    for value in (evidence.attempt_receipt_ref, evidence.response_or_error_ref):
        _require(value is None or _proof_ref(value), "provider ref invalide")


def _provider_complete(evidence: ProviderEvidence) -> bool:
    return (
        evidence.lock_bound
        and evidence.payload_bound
        and evidence.route_pinned
        and evidence.provider_pinned
        and evidence.attempt_receipt_ref is not None
        and evidence.response_or_error_ref is not None
    )


def _provider_refs(evidence: ProviderEvidence) -> tuple[str, ...]:
    return tuple(
        value
        for value in (evidence.attempt_receipt_ref, evidence.response_or_error_ref)
        if value is not None
    )


def _provider_missing(evidence: ProviderEvidence) -> tuple[str, ...]:
    missing: list[str] = []
    for proven, name in (
        (evidence.lock_bound, "lock_binding"),
        (evidence.payload_bound, "payload_binding"),
        (evidence.route_pinned, "route_pin"),
        (evidence.provider_pinned, "provider_pin"),
        (evidence.attempt_receipt_ref is not None, "attempt_receipt"),
        (evidence.response_or_error_ref is not None, "response_or_error"),
    ):
        if not proven:
            missing.append(name)
    return tuple(missing)


def _validate_artifact(artifact: object) -> None:
    _require(isinstance(artifact, Artifact), "artifact requis")
    _require(type(artifact.content) is bytes, "artifact content bytes")
    _require(_digest_string(artifact.digest), "artifact digest invalide")
    _require(_proof_ref(artifact.proof_ref), "artifact proof ref invalide")


def _validate_counter(counter: object) -> None:
    _require(isinstance(counter, MonotonicCounter), "counter requis")
    _require(_strict_string(counter.source_id), "counter source_id invalide")
    _require(_strict_string(counter.unit), "counter unit invalide")
    _require(_strict_string(counter.rule), "counter rule invalide")
    _require(callable(counter.read), "counter read invalide")


def _validate_expectations(expectations: object) -> None:
    _require(isinstance(expectations, HarnessExpectations), "harness expectations")
    _validate_adapter_identity(expectations.adapter_identity)
    _validate_environment(expectations.environment_manifest)
    _require(_digest_string(expectations.core_digest), "core_digest invalide")


def _context_digest(context: VerificationContext) -> str:
    return _value_digest(_context_payload(context))


def _make_marker(
    *,
    counter: MonotonicCounter,
    value: int,
    axis_id: str,
    session_id: str,
    boundary: str,
) -> TemporalMarker:
    payload = {
        "axis_id": axis_id,
        "boundary": boundary,
        "rule": counter.rule,
        "session_id": session_id,
        "source_id": counter.source_id,
        "unit": counter.unit,
        "value": value,
    }
    return TemporalMarker(
        source_id=counter.source_id,
        unit=counter.unit,
        rule=counter.rule,
        value=value,
        axis_id=axis_id,
        session_id=session_id,
        boundary=boundary,
        proof_ref=_value_digest(payload),
    )


def _read_marker(
    *,
    counter: MonotonicCounter,
    axis_id: str,
    session_id: str,
    boundary: str,
) -> TemporalMarker:
    try:
        value = counter.read()
    except Exception as exc:
        raise _HarnessFailure(
            "EVIDENCE_MISSING",
            (f"counter_{boundary}",),
            stage="counter",
        ) from exc
    if not _strict_int(value):
        raise _HarnessFailure(
            "OBSERVATION_TYPE_INVALID",
            (f"counter_{boundary}",),
            stage="counter",
        )
    return _make_marker(
        counter=counter,
        value=value,
        axis_id=axis_id,
        session_id=session_id,
        boundary=boundary,
    )


def _validate_marker(marker: object, *, boundary: str) -> bool:
    return (
        isinstance(marker, TemporalMarker)
        and _strict_string(marker.source_id)
        and _strict_string(marker.unit)
        and marker.rule == COUNTER_RULE
        and _strict_int(marker.value)
        and _strict_string(marker.axis_id)
        and _strict_string(marker.session_id)
        and marker.boundary == boundary
        and _digest_string(marker.proof_ref)
        and marker.proof_ref == _value_digest(_marker_payload(marker))
    )


def _validate_preparation(
    preparation: object,
    *,
    request: AxisExecutionRequest,
) -> HarnessPreparation:
    if not isinstance(preparation, HarnessPreparation):
        raise _HarnessFailure(
            "OBSERVATION_TYPE_INVALID",
            ("harness_preparation",),
            stage="prepare",
        )
    boolean_fields = (
        preparation.bootstrap_success,
        preparation.autotest_success,
        preparation.watchdog_healthy,
        preparation.ambiguous,
    )
    if not all(_strict_bool(value) for value in boolean_fields):
        raise _HarnessFailure(
            "OBSERVATION_TYPE_INVALID",
            ("preparation_boolean",),
            stage="prepare",
        )
    if not _strict_string(preparation.session_id):
        raise _HarnessFailure("ATTESTATION_INVALID", ("session_id",), stage="prepare")
    bindings_match = (
        preparation.axis_id == request.axis_id
        and preparation.adapter_identity == request.adapter_identity
        and preparation.environment_digest == request.environment_digest
        and preparation.budget_digest == request.budget_digest
        and preparation.core_digest == request.core_digest
        and preparation.artifact_digest == request.artifact_digest
        and preparation.artifact_proof_ref == request.artifact_proof_ref
    )
    if not bindings_match:
        raise _HarnessFailure(
            "ATTESTATION_BINDING_MISMATCH",
            ("preparation_binding",),
            stage="prepare",
        )
    if not preparation.bootstrap_success or not preparation.autotest_success:
        missing = tuple(
            name
            for success, name in (
                (preparation.bootstrap_success, "bootstrap_success"),
                (preparation.autotest_success, "autotest_success"),
            )
            if not success
        )
        raise _HarnessFailure("EVIDENCE_MISSING", missing, stage="prepare")
    if not preparation.watchdog_healthy or preparation.ambiguous:
        raise _HarnessFailure(
            "ATTESTATION_INVALID",
            ("preparation_health",),
            stage="prepare",
        )
    expected_stages = (MARKER_PREPARE, MARKER_AUTOTEST)
    if type(preparation.stage_proofs) is not tuple:
        raise _HarnessFailure(
            "OBSERVATION_TYPE_INVALID",
            ("preparation_stage_proofs",),
            stage="prepare",
        )
    try:
        stages = tuple(stage for stage, _ in preparation.stage_proofs)
        refs = tuple(ref for _, ref in preparation.stage_proofs)
    except Exception as exc:
        raise _HarnessFailure(
            "OBSERVATION_TYPE_INVALID",
            ("preparation_stage_proofs",),
            stage="prepare",
        ) from exc
    if (
        stages != expected_stages
        or not all(_proof_ref(ref) for ref in refs)
        or len(refs) != len(set(refs))
    ):
        raise _HarnessFailure(
            "ATTESTATION_INVALID",
            ("preparation_stage_proofs",),
            stage="prepare",
        )
    return preparation


def _make_ready_attestation(
    *,
    acquisition_id: str,
    request: AxisExecutionRequest,
    preparation: HarnessPreparation,
    start_marker: TemporalMarker,
) -> HarnessReadyAttestation:
    proofs = dict(preparation.stage_proofs)
    provisional = HarnessReadyAttestation(
        session_id=preparation.session_id,
        acquisition_id=acquisition_id,
        axis_id=request.axis_id,
        adapter_identity=request.adapter_identity,
        environment_digest=request.environment_digest,
        budget_digest=request.budget_digest,
        artifact_digest=request.artifact_digest,
        artifact_proof_ref=request.artifact_proof_ref,
        core_digest=request.core_digest,
        bootstrap_proof_ref=proofs[MARKER_PREPARE],
        autotest_proof_ref=proofs[MARKER_AUTOTEST],
        start_marker=start_marker,
        receipt_ref="sha256:" + "0" * 64,
    )
    return HarnessReadyAttestation(
        **{
            **provisional.__dict__,
            "receipt_ref": _value_digest(_attestation_payload(provisional)),
        }
    )


def _valid_ready_attestation(attestation: object) -> bool:
    if not isinstance(attestation, HarnessReadyAttestation):
        return False
    try:
        _validate_adapter_identity(attestation.adapter_identity)
    except VerifyV7ContratInvalide:
        return False
    return (
        _strict_string(attestation.session_id)
        and _strict_string(attestation.acquisition_id)
        and _strict_string(attestation.axis_id)
        and _digest_string(attestation.environment_digest)
        and _digest_string(attestation.budget_digest)
        and _digest_string(attestation.artifact_digest)
        and _proof_ref(attestation.artifact_proof_ref)
        and _digest_string(attestation.core_digest)
        and _proof_ref(attestation.bootstrap_proof_ref)
        and _proof_ref(attestation.autotest_proof_ref)
        and _validate_marker(attestation.start_marker, boundary="start")
        and attestation.start_marker.axis_id == attestation.axis_id
        and attestation.start_marker.session_id == attestation.session_id
        and _digest_string(attestation.receipt_ref)
        and attestation.receipt_ref == _value_digest(_attestation_payload(attestation))
    )


def _valid_admission_attestation(attestation: object) -> bool:
    if not isinstance(attestation, StaticAdmissionAttestation):
        return False
    try:
        _validate_adapter_identity(attestation.adapter_identity)
    except VerifyV7ContratInvalide:
        return False
    return (
        attestation.rule == HTML_ADMISSION_RULE
        and _digest_string(attestation.artifact_digest)
        and _proof_ref(attestation.artifact_proof_ref)
        and _strict_bool(attestation.accepted)
        and attestation.dynamic_confinement_claimed is False
        and _digest_string(attestation.proof_ref)
        and attestation.proof_ref == _value_digest(_admission_payload(attestation))
    )


def _admission_stage_proof(
    *,
    attestation: StaticAdmissionAttestation,
    ready: HarnessReadyAttestation,
) -> str:
    return _value_digest({
        "admission_proof_ref": attestation.proof_ref,
        "axis_id": ready.axis_id,
        "ready_receipt_ref": ready.receipt_ref,
        "session_id": ready.session_id,
        "stage": MARKER_ADMISSION,
    })


def admission_stage_proof(
    *,
    attestation: StaticAdmissionAttestation,
    ready: HarnessReadyAttestation,
) -> str:
    """Construit la preuve de stade d'axe liée à l'admission d'acquisition"""
    return _admission_stage_proof(attestation=attestation, ready=ready)


def _trace_proof_refs(trace: AxisTrace) -> tuple[str, ...]:
    refs = [ref for _, ref in trace.stage_proofs if _proof_ref(ref)]
    if trace.admission_attestation.proof_ref not in refs:
        refs.append(trace.admission_attestation.proof_ref)
    if trace.start_marker.proof_ref not in refs:
        refs.append(trace.start_marker.proof_ref)
    if trace.end_marker is not None and trace.end_marker.proof_ref not in refs:
        refs.append(trace.end_marker.proof_ref)
    return tuple(refs)


def _harness_decision(
    *,
    proof_refs: tuple[str, ...] = (),
    missing: tuple[str, ...] = ("structured_observation",),
    code: str = "EVIDENCE_MISSING",
    stage: str = "harness",
) -> _TraceDecision:
    return _TraceDecision(
        measurement_state="NOT_SCORED",
        causal_class="HARNESS_ERROR",
        verdict=None,
        proof_refs=proof_refs,
        missing_evidence=missing,
        diagnostic_code=code,
        stage=stage,
    )


def _valid_stage_proofs(
    markers: tuple[str, ...],
    proofs: tuple[tuple[str, str], ...],
) -> bool:
    if type(markers) is not tuple or type(proofs) is not tuple:
        return False
    try:
        proof_markers = tuple(stage for stage, _ in proofs)
        proof_refs = tuple(ref for _, ref in proofs)
    except Exception:
        return False
    return (
        markers == proof_markers
        and all(marker in KNOWN_MARKERS for marker in markers)
        and len(markers) == len(set(markers))
        and all(_proof_ref(ref) for ref in proof_refs)
        and len(proof_refs) == len(set(proof_refs))
    )


def _decide_trace(trace: object, *, axis_id: str) -> _TraceDecision:
    if not isinstance(trace, AxisTrace):
        return _harness_decision(code="OBSERVATION_TYPE_INVALID")
    refs = _trace_proof_refs(trace)
    obs = trace.observation
    if not isinstance(obs, AxisObservation):
        return _harness_decision(proof_refs=refs, code="OBSERVATION_TYPE_INVALID")
    bool_values = (
        obs.admission_result,
        obs.evaluation_completed,
        obs.budget_expired,
        obs.watchdog_healthy,
        obs.ambiguous,
        obs.network_attempted,
        obs.confinement_healthy,
        obs.confinement_ambiguous,
        trace.admission_result,
        trace.evaluation_completed,
        trace.budget_expired,
        trace.watchdog_healthy,
        trace.teardown_complete,
        trace.ambiguous,
    )
    if not all(_strict_bool(value) for value in bool_values):
        return _harness_decision(
            proof_refs=refs,
            missing=("strict_boolean",),
            code="OBSERVATION_TYPE_INVALID",
        )
    if trace.axis_id != axis_id or obs.axis_id != axis_id:
        return _harness_decision(
            proof_refs=refs,
            missing=("axis_binding",),
            code="ATTESTATION_BINDING_MISMATCH",
        )
    if not _valid_ready_attestation(trace.ready_attestation):
        return _harness_decision(
            proof_refs=refs,
            missing=("ready_attestation",),
            code="ATTESTATION_INVALID",
        )
    if not _valid_admission_attestation(trace.admission_attestation):
        return _harness_decision(
            proof_refs=refs,
            missing=("admission_attestation",),
            code="ATTESTATION_INVALID",
        )
    expected_bindings = (
        trace.session_id == trace.ready_attestation.session_id == obs.session_id
        and obs.ready_receipt_ref == trace.ready_attestation.receipt_ref
        and obs.artifact_digest == trace.ready_attestation.artifact_digest
        and obs.artifact_proof_ref == trace.ready_attestation.artifact_proof_ref
        and obs.budget_digest == trace.ready_attestation.budget_digest
        and obs.environment_digest == trace.ready_attestation.environment_digest
        and obs.admission_attestation == trace.admission_attestation
        and obs.admission_result == trace.admission_result
        and obs.evaluation_completed == trace.evaluation_completed
        and obs.verdict == trace.verdict
        and obs.budget_expired == trace.budget_expired
        and trace.admission_attestation.adapter_identity
        == trace.ready_attestation.adapter_identity
        and trace.admission_attestation.artifact_digest
        == trace.ready_attestation.artifact_digest
        and trace.admission_attestation.artifact_proof_ref
        == trace.ready_attestation.artifact_proof_ref
        and obs.admission_stage_proof_ref
        == _admission_stage_proof(
            attestation=trace.admission_attestation,
            ready=trace.ready_attestation,
        )
        and trace.teardown_observation.session_id == trace.session_id
        and trace.teardown_observation.axis_id == trace.axis_id
        and _proof_ref(trace.teardown_observation.proof_ref)
        and trace.teardown_observation.complete == trace.teardown_complete
        and trace.teardown_observation.watchdog_healthy
        and not trace.teardown_observation.ambiguous
    )
    if not expected_bindings:
        return _harness_decision(
            proof_refs=refs,
            missing=("observation_binding",),
            code="ATTESTATION_BINDING_MISMATCH",
        )
    if not _valid_stage_proofs(trace.markers, trace.stage_proofs):
        return _harness_decision(
            proof_refs=refs,
            missing=("stage_proof",),
            code="ATTESTATION_INVALID",
        )
    expected_stage_proofs = (
        (MARKER_PREPARE, trace.ready_attestation.bootstrap_proof_ref),
        (MARKER_AUTOTEST, trace.ready_attestation.autotest_proof_ref),
        (MARKER_HARNESS_READY, trace.ready_attestation.receipt_ref),
        (MARKER_ADMISSION, trace.observation.admission_stage_proof_ref),
        *trace.observation.stage_proofs,
        (MARKER_TEARDOWN, trace.teardown_observation.proof_ref),
    )
    if trace.stage_proofs != expected_stage_proofs:
        return _harness_decision(
            proof_refs=refs,
            missing=("stage_proof_binding",),
            code="ATTESTATION_BINDING_MISMATCH",
        )
    if trace.start_marker != trace.ready_attestation.start_marker:
        return _harness_decision(
            proof_refs=refs,
            missing=("start_marker_binding",),
            code="ATTESTATION_BINDING_MISMATCH",
        )
    if not _validate_marker(trace.start_marker, boundary="start"):
        return _harness_decision(
            proof_refs=refs,
            missing=("start_marker",),
            code="ATTESTATION_INVALID",
        )
    if not trace.watchdog_healthy or not trace.teardown_complete or trace.ambiguous:
        return _harness_decision(
            proof_refs=refs,
            missing=("healthy_unambiguous_teardown",),
            code="STATE_CONTRADICTION",
        )
    if not obs.confinement_healthy or obs.confinement_ambiguous:
        return _harness_decision(
            proof_refs=refs,
            missing=("dynamic_confinement",),
            code="CONFINEMENT_UNHEALTHY",
            stage="confinement",
        )
    if trace.admission_result is False:
        contradiction = (
            trace.admission_attestation.accepted is not False
            or trace.markers != INVALID_ADMISSION_ORDER
            or bool(obs.stage_proofs)
            or trace.evaluation_completed
            or trace.verdict is not None
            or trace.budget_expired
            or trace.observed_cost is not None
            or trace.end_marker is not None
            or obs.network_attempted
        )
        if contradiction:
            return _harness_decision(
                proof_refs=refs,
                missing=("negative_admission_state",),
                code="STATE_CONTRADICTION",
                stage="admission",
            )
        return _TraceDecision(
            "NOT_SCORED",
            "ARTIFACT_INVALID",
            None,
            (trace.admission_attestation.proof_ref,),
            (),
            "",
            "admission",
        )
    if trace.admission_result is not True or trace.admission_attestation.accepted is not True:
        return _harness_decision(
            proof_refs=refs,
            missing=("admission_result",),
            code="STATE_CONTRADICTION",
            stage="admission",
        )
    if trace.end_marker is None or not _validate_marker(trace.end_marker, boundary="end"):
        return _harness_decision(
            proof_refs=refs,
            missing=("end_marker",),
            code="ATTESTATION_INVALID",
            stage="counter",
        )
    marker_binding = (
        trace.end_marker.axis_id == trace.axis_id
        and trace.end_marker.session_id == trace.session_id
        and trace.start_marker.source_id == trace.end_marker.source_id
        and trace.start_marker.unit == trace.end_marker.unit
        and trace.start_marker.rule == trace.end_marker.rule == COUNTER_RULE
        and trace.start_marker.unit == trace.qualified_budget.unit
        and trace.qualified_budget.measurement_rule == COUNTER_RULE
        and _strict_int(trace.observed_cost)
        and trace.end_marker.value >= trace.start_marker.value
        and trace.observed_cost == trace.end_marker.value - trace.start_marker.value
    )
    if not marker_binding:
        return _harness_decision(
            proof_refs=refs,
            missing=("counter_binding",),
            code="STATE_CONTRADICTION",
            stage="counter",
        )
    candidate_stages = tuple(
        stage
        for stage in trace.markers
        if stage in CANDIDATE_MARKERS or stage == MARKER_BUDGET_EXPIRED
    )
    if trace.evaluation_completed and trace.budget_expired:
        return _harness_decision(
            proof_refs=refs,
            missing=("exclusive_terminal_state",),
            code="STATE_CONTRADICTION",
        )
    if trace.evaluation_completed and not _proof_ref(trace.verdict):
        return _harness_decision(
            proof_refs=refs,
            missing=("evaluation_verdict",),
            code="EVIDENCE_MISSING",
        )
    if not trace.evaluation_completed and trace.verdict is not None:
        return _harness_decision(
            proof_refs=refs,
            missing=("evaluation_state",),
            code="STATE_CONTRADICTION",
        )
    has_expiration_proof = MARKER_BUDGET_EXPIRED in trace.markers
    if trace.budget_expired:
        if (
            trace.markers not in LIMIT_MEASUREMENT_ORDERS
            or not has_expiration_proof
            or not any(stage in CANDIDATE_MARKERS for stage in candidate_stages)
            or trace.observed_cost < trace.qualified_budget.value
        ):
            return _harness_decision(
                proof_refs=refs,
                missing=("budget_expiration",),
                code="STATE_CONTRADICTION",
                stage="artifact-budget",
            )
        return _TraceDecision(
            "NOT_SCORED",
            "ARTIFACT_EXECUTION_LIMIT",
            None,
            refs,
            (),
            "",
            "artifact-budget",
        )
    if has_expiration_proof:
        return _harness_decision(
            proof_refs=refs,
            missing=("budget_expired_binding",),
            code="STATE_CONTRADICTION",
            stage="artifact-budget",
        )
    if obs.network_attempted and not trace.evaluation_completed:
        return _harness_decision(
            proof_refs=refs,
            missing=("completed_network_attempt",),
            code="EVIDENCE_MISSING",
            stage="confinement",
        )
    if trace.markers != COMPLETED_MEASUREMENT_ORDER or not trace.evaluation_completed:
        return _harness_decision(
            proof_refs=refs,
            missing=("completed_evaluation",),
            code="EVIDENCE_MISSING",
            stage="evaluation",
        )
    verdict = "FAIL" if obs.network_attempted and axis_id == "pentagone-api" else trace.verdict
    return _TraceDecision(
        "SCORED",
        "MEASUREMENT_COMPLETED",
        verdict,
        refs,
        (),
        "",
        "evaluation",
    )


def _incident_id(
    acquisition_id: str,
    scope: str,
    causal_class: str,
    axis_id: str | None = None,
) -> str:
    parts = (acquisition_id, scope, causal_class)
    return ":".join((*parts, axis_id) if axis_id is not None else parts)


def _make_context(
    *,
    acquisition_id: str,
    axes: tuple[str, ...],
    artifact: Artifact,
    budget: QualifiedBudget,
    expectations: HarnessExpectations,
    counter: MonotonicCounter,
) -> VerificationContext:
    return VerificationContext(
        acquisition_id=acquisition_id,
        axis_ids=axes,
        adapter_identity=expectations.adapter_identity,
        artifact_digest=artifact.digest,
        artifact_proof_ref=artifact.proof_ref,
        qualified_budget=budget,
        budget_digest=_value_digest(_budget_payload(budget)),
        environment_manifest=expectations.environment_manifest,
        environment_digest=_value_digest(_environment_payload(expectations.environment_manifest)),
        core_digest=expectations.core_digest,
        counter_source_id=counter.source_id,
        counter_unit=counter.unit,
        counter_rule=counter.rule,
    )


def _terminal_result(
    *,
    context: VerificationContext,
    causal_class: str,
    stage: str,
    proof_refs: tuple[str, ...],
    adapter_call_count: int,
    ready_attestations: tuple[HarnessReadyAttestation, ...] = (),
    admission_attestation: StaticAdmissionAttestation | None = None,
    static_admission_count: int = 0,
    traces: dict[str, AxisTrace | None] | None = None,
    missing: tuple[str, ...] = (),
    diagnostic_code: str = "",
) -> AcquisitionResult:
    digest = _context_digest(context)
    incident = Incident(
        incident_id=_incident_id(context.acquisition_id, "ACQUISITION", causal_class),
        stage=stage,
        scope="ACQUISITION",
        causal_class=causal_class,
        affected_unit_ids=context.axis_ids,
        proof_refs=proof_refs,
        context_digest=digest,
        missing_evidence=missing,
        diagnostic_code=diagnostic_code,
    )
    traces = traces or {}
    units = tuple(
        UnitResult(
            axis_id=axis_id,
            measurement_state="NOT_SCORED",
            causal_class=causal_class,
            verdict=None,
            incident_id=incident.incident_id,
            context_digest=digest,
            trace=traces.get(axis_id),
        )
        for axis_id in context.axis_ids
    )
    return AcquisitionResult(
        acquisition_id=context.acquisition_id,
        units=units,
        incidents=(incident,),
        adapter_call_count=adapter_call_count,
        verification_context=context,
        context_digest=digest,
        ready_attestations=ready_attestations,
        admission_attestation=admission_attestation,
        static_admission_count=static_admission_count,
    )


def _axis_harness_result(
    *,
    context: VerificationContext,
    axis_id: str,
    failure: _HarnessFailure,
    trace: AxisTrace | None,
) -> tuple[UnitResult, Incident]:
    digest = _context_digest(context)
    proof_refs = _trace_proof_refs(trace) if trace is not None else ()
    incident_id = _incident_id(
        context.acquisition_id,
        "AXIS",
        "HARNESS_ERROR",
        axis_id,
    )
    incident = Incident(
        incident_id=incident_id,
        stage=failure.stage,
        scope="AXIS",
        causal_class="HARNESS_ERROR",
        affected_unit_ids=(axis_id,),
        proof_refs=proof_refs,
        context_digest=digest,
        missing_evidence=failure.missing,
        diagnostic_code=failure.code,
    )
    unit = UnitResult(
        axis_id=axis_id,
        measurement_state="NOT_SCORED",
        causal_class="HARNESS_ERROR",
        verdict=None,
        incident_id=incident_id,
        context_digest=digest,
        trace=trace,
    )
    return unit, incident


def _build_trace(
    *,
    context: VerificationContext,
    preparation: HarnessPreparation,
    ready: HarnessReadyAttestation,
    observation: AxisObservation,
    end_marker: TemporalMarker | None,
    teardown: TeardownObservation,
) -> AxisTrace:
    stage_proofs = [
        *preparation.stage_proofs,
        (MARKER_HARNESS_READY, ready.receipt_ref),
        (MARKER_ADMISSION, observation.admission_stage_proof_ref),
        *observation.stage_proofs,
        (MARKER_TEARDOWN, teardown.proof_ref),
    ]
    cost = (
        end_marker.value - ready.start_marker.value
        if observation.admission_result is True and end_marker is not None
        else None
    )
    return AxisTrace(
        axis_id=observation.axis_id,
        session_id=preparation.session_id,
        markers=tuple(stage for stage, _ in stage_proofs),
        stage_proofs=tuple(stage_proofs),
        ready_attestation=ready,
        observation=observation,
        teardown_observation=teardown,
        admission_result=observation.admission_result,
        admission_attestation=observation.admission_attestation,
        evaluation_completed=observation.evaluation_completed,
        verdict=observation.verdict,
        budget_expired=observation.budget_expired,
        observed_cost=cost,
        start_marker=ready.start_marker,
        end_marker=end_marker if observation.admission_result is True else None,
        qualified_budget=context.qualified_budget,
        context_digest=_context_digest(context),
        watchdog_healthy=(
            preparation.watchdog_healthy
            and observation.watchdog_healthy
            and teardown.watchdog_healthy
        ),
        teardown_complete=teardown.complete,
        ambiguous=(preparation.ambiguous or observation.ambiguous or teardown.ambiguous),
    )


def verify_acquisition(
    *,
    acquisition_id: str,
    axis_ids: Sequence[str],
    provider_evidence: ProviderEvidence,
    artifact: Artifact,
    qualified_budget: QualifiedBudget,
    harness_expectations: HarnessExpectations,
    counter: MonotonicCounter,
    adapter: ModalityAdapter,
) -> AcquisitionResult:
    """Orchestre une acquisition sans navigateur, fichier, réseau ni horloge interne"""
    _require(_strict_string(acquisition_id), "acquisition_id invalide")
    _require(not isinstance(axis_ids, (str, bytes)), "axis_ids invalides")
    try:
        axes = tuple(axis_ids)
    except TypeError as exc:
        raise VerifyV7ContratInvalide("axis_ids invalides") from exc
    _require(len(axes) > 0, "axis_ids vides")
    _require(all(_strict_string(axis_id) for axis_id in axes), "axis_id invalide")
    _require(len(axes) == len(set(axes)), "axis_ids dupliqués")
    _validate_provider(provider_evidence)
    _validate_artifact(artifact)
    _validate_budget(qualified_budget)
    _validate_expectations(harness_expectations)
    _validate_counter(counter)

    context = _make_context(
        acquisition_id=acquisition_id,
        axes=axes,
        artifact=artifact,
        budget=qualified_budget,
        expectations=harness_expectations,
        counter=counter,
    )
    if not _provider_complete(provider_evidence):
        result = _terminal_result(
            context=context,
            causal_class="HARNESS_ERROR",
            stage="provider",
            proof_refs=_provider_refs(provider_evidence),
            adapter_call_count=0,
            missing=_provider_missing(provider_evidence),
            diagnostic_code="EVIDENCE_MISSING",
        )
        validate_acquisition_result(result)
        return result
    if not provider_evidence.artifact_admissible:
        result = _terminal_result(
            context=context,
            causal_class="PROVIDER_FAILURE",
            stage="provider",
            proof_refs=_provider_refs(provider_evidence),
            adapter_call_count=0,
        )
        validate_acquisition_result(result)
        return result
    if (
        counter.rule != COUNTER_RULE
        or qualified_budget.measurement_rule != COUNTER_RULE
        or counter.unit != qualified_budget.unit
    ):
        result = _terminal_result(
            context=context,
            causal_class="HARNESS_ERROR",
            stage="counter",
            proof_refs=(),
            adapter_call_count=0,
            missing=("counter_budget_binding",),
            diagnostic_code="ATTESTATION_BINDING_MISMATCH",
        )
        validate_acquisition_result(result)
        return result

    try:
        actual_identity = adapter.identity
        _validate_adapter_identity(actual_identity)
    except Exception:
        result = _terminal_result(
            context=context,
            causal_class="HARNESS_ERROR",
            stage="adapter",
            proof_refs=(),
            adapter_call_count=0,
            missing=("adapter_identity",),
            diagnostic_code="ADAPTER_EXCEPTION",
        )
        validate_acquisition_result(result)
        return result
    if actual_identity != harness_expectations.adapter_identity:
        result = _terminal_result(
            context=context,
            causal_class="HARNESS_ERROR",
            stage="adapter",
            proof_refs=(),
            adapter_call_count=0,
            missing=("adapter_identity_binding",),
            diagnostic_code="ATTESTATION_BINDING_MISMATCH",
        )
        validate_acquisition_result(result)
        return result

    units: list[UnitResult] = []
    incidents: list[Incident] = []
    ready_attestations: list[HarnessReadyAttestation] = []
    traces: dict[str, AxisTrace | None] = {}
    admission_state = _AdmissionState()
    call_count = 0
    seen_session_objects: set[int] = set()
    seen_session_ids: set[str] = set()
    seen_preparation_proofs: set[str] = set()
    seen_trace_proofs: set[str] = set()

    for axis_id in axes:
        request = AxisExecutionRequest(
            acquisition_id=acquisition_id,
            axis_id=axis_id,
            artifact_digest=artifact.digest,
            artifact_proof_ref=artifact.proof_ref,
            qualified_budget=qualified_budget,
            budget_digest=context.budget_digest,
            adapter_identity=actual_identity,
            environment_digest=context.environment_digest,
            core_digest=context.core_digest,
        )
        session: AxisSession | None = None
        preparation: HarnessPreparation | None = None
        ready: HarnessReadyAttestation | None = None
        observation: AxisObservation | None = None
        end_marker: TemporalMarker | None = None
        teardown: TeardownObservation | None = None
        failure: _HarnessFailure | None = None
        trace: AxisTrace | None = None

        try:
            session = adapter.open_axis(request)
            call_count += 1
            if id(session) in seen_session_objects:
                raise _HarnessFailure(
                    "ATTESTATION_BINDING_MISMATCH",
                    ("axis_session_unique",),
                    stage="adapter",
                )
            seen_session_objects.add(id(session))
            raw_preparation = session.prepare()
            preparation = _validate_preparation(raw_preparation, request=request)
            if preparation.session_id in seen_session_ids:
                raise _HarnessFailure(
                    "ATTESTATION_BINDING_MISMATCH",
                    ("session_id_unique",),
                    stage="prepare",
                )
            preparation_refs = {ref for _, ref in preparation.stage_proofs}
            if preparation_refs & seen_preparation_proofs:
                raise _HarnessFailure(
                    "ATTESTATION_BINDING_MISMATCH",
                    ("preparation_proof_unique",),
                    stage="prepare",
                )
            seen_session_ids.add(preparation.session_id)
            seen_preparation_proofs.update(preparation_refs)
            start_marker = _read_marker(
                counter=counter,
                axis_id=axis_id,
                session_id=preparation.session_id,
                boundary="start",
            )
            ready = _make_ready_attestation(
                acquisition_id=acquisition_id,
                request=request,
                preparation=preparation,
                start_marker=start_marker,
            )
            ready_attestations.append(ready)
            permit = CandidatePermit(
                ready_attestation=ready,
                artifact=artifact,
                adapter_identity=actual_identity,
                admission_state=admission_state,
            )
            raw_observation = session.inspect_and_execute(permit)
            if not isinstance(raw_observation, AxisObservation):
                raise _HarnessFailure(
                    "OBSERVATION_TYPE_INVALID",
                    ("axis_observation",),
                    stage="candidate",
                )
            observation = raw_observation
            if observation.admission_result is True:
                end_marker = _read_marker(
                    counter=counter,
                    axis_id=axis_id,
                    session_id=preparation.session_id,
                    boundary="end",
                )
        except _HarnessFailure as exc:
            failure = exc
        except Exception:
            failure = _HarnessFailure(
                "ADAPTER_EXCEPTION",
                ("adapter_observation",),
                stage="adapter",
            )
        finally:
            if session is not None:
                try:
                    raw_teardown = session.teardown()
                    if not isinstance(raw_teardown, TeardownObservation):
                        raise _HarnessFailure(
                            "OBSERVATION_TYPE_INVALID",
                            ("teardown_observation",),
                            stage="teardown",
                        )
                    if not all(
                        _strict_bool(value)
                        for value in (
                            raw_teardown.complete,
                            raw_teardown.watchdog_healthy,
                            raw_teardown.ambiguous,
                        )
                    ):
                        raise _HarnessFailure(
                            "OBSERVATION_TYPE_INVALID",
                            ("teardown_boolean",),
                            stage="teardown",
                        )
                    if (
                        raw_teardown.session_id != preparation.session_id
                        if preparation is not None
                        else not _strict_string(raw_teardown.session_id)
                    ) or raw_teardown.axis_id != axis_id or not _proof_ref(raw_teardown.proof_ref):
                        raise _HarnessFailure(
                            "ATTESTATION_BINDING_MISMATCH",
                            ("teardown_binding",),
                            stage="teardown",
                        )
                    teardown = raw_teardown
                except _HarnessFailure as exc:
                    failure = exc
                except Exception:
                    failure = _HarnessFailure(
                        "ADAPTER_EXCEPTION",
                        ("teardown_observation",),
                        stage="teardown",
                    )

        if (
            preparation is not None
            and ready is not None
            and observation is not None
            and teardown is not None
        ):
            try:
                trace = _build_trace(
                    context=context,
                    preparation=preparation,
                    ready=ready,
                    observation=observation,
                    end_marker=end_marker,
                    teardown=teardown,
                )
            except Exception:
                failure = _HarnessFailure(
                    "OBSERVATION_TYPE_INVALID",
                    ("axis_trace",),
                    stage="candidate",
                )
        traces[axis_id] = trace
        if failure is not None:
            unit, incident = _axis_harness_result(
                context=context,
                axis_id=axis_id,
                failure=failure,
                trace=trace,
            )
            units.append(unit)
            incidents.append(incident)
            continue
        if trace is None:
            unit, incident = _axis_harness_result(
                context=context,
                axis_id=axis_id,
                failure=_HarnessFailure(
                    "EVIDENCE_MISSING",
                    ("axis_trace",),
                    stage="candidate",
                ),
                trace=None,
            )
            units.append(unit)
            incidents.append(incident)
            continue

        decision = _decide_trace(trace, axis_id=axis_id)
        trace_refs = {ref for _, ref in trace.stage_proofs}
        relation_failure = False
        if trace_refs & seen_trace_proofs:
            relation_failure = True
            decision = _harness_decision(
                proof_refs=_trace_proof_refs(trace),
                missing=("stage_proof_unique",),
                code="ATTESTATION_BINDING_MISMATCH",
            )
        else:
            seen_trace_proofs.update(trace_refs)
        if decision.causal_class == "ARTIFACT_INVALID":
            for remaining_axis in axes[len(units) + 1 :]:
                traces.setdefault(remaining_axis, None)
            result = _terminal_result(
                context=context,
                causal_class="ARTIFACT_INVALID",
                stage="admission",
                proof_refs=decision.proof_refs,
                adapter_call_count=call_count,
                ready_attestations=tuple(ready_attestations),
                admission_attestation=admission_state.attestation,
                static_admission_count=admission_state.inspection_count,
                traces=traces,
            )
            validate_acquisition_result(result)
            return result
        if decision.measurement_state == "SCORED":
            units.append(UnitResult(
                axis_id=axis_id,
                measurement_state="SCORED",
                causal_class="MEASUREMENT_COMPLETED",
                verdict=decision.verdict,
                incident_id=None,
                context_digest=_context_digest(context),
                trace=trace,
            ))
            continue
        incident_id = _incident_id(
            acquisition_id,
            "AXIS",
            decision.causal_class,
            axis_id,
        )
        incident = Incident(
            incident_id=incident_id,
            stage=decision.stage,
            scope="AXIS",
            causal_class=decision.causal_class,
            affected_unit_ids=(axis_id,),
            proof_refs=decision.proof_refs,
            context_digest=_context_digest(context),
            missing_evidence=decision.missing_evidence,
            diagnostic_code=decision.diagnostic_code,
        )
        incidents.append(incident)
        units.append(UnitResult(
            axis_id=axis_id,
            measurement_state="NOT_SCORED",
            causal_class=decision.causal_class,
            verdict=None,
            incident_id=incident_id,
            context_digest=_context_digest(context),
            trace=None if relation_failure else trace,
        ))

    result = AcquisitionResult(
        acquisition_id=acquisition_id,
        units=tuple(units),
        incidents=tuple(incidents),
        adapter_call_count=call_count,
        verification_context=context,
        context_digest=_context_digest(context),
        ready_attestations=tuple(ready_attestations),
        admission_attestation=admission_state.attestation,
        static_admission_count=admission_state.inspection_count,
    )
    validate_acquisition_result(result)
    return result


def _validate_context(context: object) -> None:
    _require(isinstance(context, VerificationContext), "verification_context requis")
    _require(_strict_string(context.acquisition_id), "context acquisition_id")
    _require(type(context.axis_ids) is tuple and len(context.axis_ids) > 0, "context axes")
    _require(all(_strict_string(axis) for axis in context.axis_ids), "context axis")
    _require(len(context.axis_ids) == len(set(context.axis_ids)), "context axes uniques")
    _validate_adapter_identity(context.adapter_identity)
    _require(_digest_string(context.artifact_digest), "context artifact_digest")
    _require(_proof_ref(context.artifact_proof_ref), "context artifact_proof_ref")
    _validate_budget(context.qualified_budget)
    _require(
        context.budget_digest == _value_digest(_budget_payload(context.qualified_budget)),
        "context budget_digest",
    )
    _validate_environment(context.environment_manifest)
    _require(
        context.environment_digest
        == _value_digest(_environment_payload(context.environment_manifest)),
        "context environment_digest",
    )
    _require(_digest_string(context.core_digest), "context core_digest")
    _require(_strict_string(context.counter_source_id), "context counter source")
    _require(_strict_string(context.counter_unit), "context counter unit")
    _require(_strict_string(context.counter_rule), "context counter rule")


def validate_incident(incident: Incident) -> None:
    _require(isinstance(incident, Incident), "incident requis")
    _require(_strict_string(incident.incident_id), "incident_id")
    _require(_strict_string(incident.stage), "incident stage")
    _require(incident.scope in INCIDENT_SCOPES, "incident scope")
    _require(incident.causal_class in CAUSAL_CLASSES - {"MEASUREMENT_COMPLETED"}, "incident class")
    _require(
        type(incident.affected_unit_ids) is tuple
        and len(incident.affected_unit_ids) > 0
        and all(_strict_string(axis) for axis in incident.affected_unit_ids),
        "incident affected units",
    )
    _require(len(incident.affected_unit_ids) == len(set(incident.affected_unit_ids)), "incident axes uniques")
    _require(type(incident.proof_refs) is tuple, "incident proof_refs")
    _require(all(_proof_ref(ref) for ref in incident.proof_refs), "incident proof ref")
    _require(len(incident.proof_refs) == len(set(incident.proof_refs)), "incident proof refs uniques")
    _require(_digest_string(incident.context_digest), "incident context_digest")
    _require(type(incident.missing_evidence) is tuple, "incident missing_evidence")
    _require(all(_strict_string(item) for item in incident.missing_evidence), "incident missing")
    _require(len(incident.missing_evidence) == len(set(incident.missing_evidence)), "incident missing unique")
    if incident.causal_class == "HARNESS_ERROR":
        _require(incident.diagnostic_code in HARNESS_DIAGNOSTIC_CODES, "diagnostic_code")
        _require(bool(incident.missing_evidence), "harness missing_evidence")
    else:
        _require(incident.diagnostic_code == "", "non-harness diagnostic")
        _require(incident.missing_evidence == (), "non-harness missing")
        _require(bool(incident.proof_refs), "non-harness proof")
    if incident.scope == "AXIS":
        _require(len(incident.affected_unit_ids) == 1, "axis incident cardinality")
        _require(incident.causal_class != "PROVIDER_FAILURE", "axis provider failure")
    else:
        _require(
            incident.causal_class in {"PROVIDER_FAILURE", "ARTIFACT_INVALID", "HARNESS_ERROR"},
            "acquisition incident class",
        )


def validate_unit_result(unit: UnitResult) -> None:
    _require(isinstance(unit, UnitResult), "unit requis")
    _require(_strict_string(unit.axis_id), "unit axis_id")
    _require(unit.measurement_state in MEASUREMENT_STATES, "unit measurement_state")
    _require(unit.causal_class in CAUSAL_CLASSES, "unit causal_class")
    _require(_digest_string(unit.context_digest), "unit context_digest")
    if unit.measurement_state == "SCORED":
        _require(unit.causal_class == "MEASUREMENT_COMPLETED", "scored causal class")
        _require(_proof_ref(unit.verdict), "scored verdict")
        _require(unit.incident_id is None, "scored incident")
        _require(isinstance(unit.trace, AxisTrace), "scored trace")
        decision = _decide_trace(unit.trace, axis_id=unit.axis_id)
        _require(decision.measurement_state == "SCORED", "scored trace decision")
        _require(decision.verdict == unit.verdict, "scored verdict binding")
        _require(unit.trace.context_digest == unit.context_digest, "scored context binding")
    else:
        _require(unit.verdict is None, "not scored verdict")
        _require(unit.causal_class != "MEASUREMENT_COMPLETED", "not scored causal class")
        _require(_proof_ref(unit.incident_id), "not scored incident_id")
        if unit.trace is not None:
            decision = _decide_trace(unit.trace, axis_id=unit.axis_id)
            _require(decision.causal_class == unit.causal_class, "not scored trace class")
            _require(unit.trace.context_digest == unit.context_digest, "not scored context binding")


def validate_acquisition_result(result: AcquisitionResult) -> None:
    _require(isinstance(result, AcquisitionResult), "acquisition result requis")
    _validate_context(result.verification_context)
    context = result.verification_context
    digest = _context_digest(context)
    _require(result.context_digest == digest, "result context_digest")
    _require(result.acquisition_id == context.acquisition_id, "result acquisition binding")
    _require(type(result.units) is tuple and len(result.units) > 0, "result units")
    _require(tuple(unit.axis_id for unit in result.units) == context.axis_ids, "result axes binding")
    _require(type(result.incidents) is tuple, "result incidents")
    _require(
        _strict_int(result.adapter_call_count)
        and 0 <= result.adapter_call_count <= len(context.axis_ids),
        "result adapter_call_count",
    )
    _require(type(result.ready_attestations) is tuple, "result ready_attestations")
    _require(
        _strict_int(result.static_admission_count)
        and result.static_admission_count in {0, 1},
        "result static_admission_count",
    )
    ready_by_receipt: dict[str, HarnessReadyAttestation] = {}
    seen_sessions: set[str] = set()
    seen_marker_refs: set[str] = set()
    for attestation in result.ready_attestations:
        _require(_valid_ready_attestation(attestation), "ready attestation invalide")
        _require(attestation.acquisition_id == context.acquisition_id, "ready acquisition binding")
        _require(attestation.axis_id in context.axis_ids, "ready axis binding")
        _require(attestation.adapter_identity == context.adapter_identity, "ready adapter binding")
        _require(attestation.environment_digest == context.environment_digest, "ready environment binding")
        _require(attestation.budget_digest == context.budget_digest, "ready budget binding")
        _require(attestation.artifact_digest == context.artifact_digest, "ready artifact digest binding")
        _require(attestation.artifact_proof_ref == context.artifact_proof_ref, "ready artifact proof binding")
        _require(attestation.core_digest == context.core_digest, "ready core binding")
        _require(attestation.receipt_ref not in ready_by_receipt, "ready receipt unique")
        _require(attestation.session_id not in seen_sessions, "ready session unique")
        _require(attestation.start_marker.proof_ref not in seen_marker_refs, "ready marker unique")
        ready_by_receipt[attestation.receipt_ref] = attestation
        seen_sessions.add(attestation.session_id)
        seen_marker_refs.add(attestation.start_marker.proof_ref)
    if result.admission_attestation is not None:
        _require(result.static_admission_count == 1, "admission count binding")
        _require(_valid_admission_attestation(result.admission_attestation), "admission attestation")
        _require(result.admission_attestation.adapter_identity == context.adapter_identity, "admission adapter binding")
        _require(result.admission_attestation.artifact_digest == context.artifact_digest, "admission digest binding")
        _require(result.admission_attestation.artifact_proof_ref == context.artifact_proof_ref, "admission proof binding")
    else:
        _require(result.static_admission_count == 0, "absent admission count")
    seen_stage_refs: set[str] = set()
    seen_end_markers: set[str] = set()
    for unit in result.units:
        validate_unit_result(unit)
        _require(unit.context_digest == digest, "unit result context binding")
        if unit.trace is None:
            continue
        trace = unit.trace
        _require(trace.context_digest == digest, "trace context binding")
        _require(trace.qualified_budget == context.qualified_budget, "trace budget binding")
        _require(
            trace.ready_attestation.adapter_identity == context.adapter_identity,
            "trace adapter binding",
        )
        _require(
            trace.ready_attestation.environment_digest == context.environment_digest,
            "trace environment binding",
        )
        _require(
            trace.ready_attestation.artifact_digest == context.artifact_digest,
            "trace artifact digest binding",
        )
        _require(
            trace.ready_attestation.artifact_proof_ref == context.artifact_proof_ref,
            "trace artifact proof binding",
        )
        _require(trace.ready_attestation.receipt_ref in ready_by_receipt, "trace ready receipt")
        _require(ready_by_receipt[trace.ready_attestation.receipt_ref] == trace.ready_attestation, "trace ready binding")
        _require(result.admission_attestation == trace.admission_attestation, "trace admission binding")
        refs = {ref for _, ref in trace.stage_proofs}
        _require(not (refs & seen_stage_refs), "stage proof reused")
        seen_stage_refs.update(refs)
        if trace.end_marker is not None:
            _require(trace.end_marker.proof_ref not in seen_end_markers, "end marker reused")
            seen_end_markers.add(trace.end_marker.proof_ref)
    incident_by_id: dict[str, Incident] = {}
    for incident in result.incidents:
        validate_incident(incident)
        _require(incident.context_digest == digest, "incident context binding")
        _require(incident.incident_id not in incident_by_id, "incident id unique")
        incident_by_id[incident.incident_id] = incident
        _require(set(incident.affected_unit_ids) <= set(context.axis_ids), "incident axes binding")
        if incident.scope == "ACQUISITION":
            _require(incident.affected_unit_ids == context.axis_ids, "acquisition incident coverage")
    for unit in result.units:
        if unit.incident_id is None:
            continue
        _require(unit.incident_id in incident_by_id, "unit incident exists")
        incident = incident_by_id[unit.incident_id]
        _require(unit.axis_id in incident.affected_unit_ids, "unit incident axis")
        _require(unit.causal_class == incident.causal_class, "unit incident class")
    if any(unit.measurement_state == "SCORED" for unit in result.units):
        _require(result.adapter_call_count > 0, "scored adapter call")
