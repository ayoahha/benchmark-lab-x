"""Noyau verify-v7 pur en mémoire, indépendant de toute modalité réelle.

Orchestre stades, preuves injectées, incidents et résultats d'acquisition.
Aucune horloge, sous-processus, fichier ou réseau : budgets, marqueurs et
preuves sont injectés. L'adaptateur de modalité fournit une trace structurée
expurgée ; seul ce noyau valide les preuves et décide la classe causale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable


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

# Grammaire exacte MEASUREMENT_COMPLETED
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

# Préfixes candidats exacts pour ARTIFACT_EXECUTION_LIMIT.
_LIMIT_CANDIDATE_PREFIXES = (
    (MARKER_LOAD,),
    (MARKER_LOAD, MARKER_INIT),
    (MARKER_LOAD, MARKER_INIT, MARKER_EVAL),
)

LIMIT_MEASUREMENT_ORDERS = tuple(
    (
        MARKER_PREPARE,
        MARKER_AUTOTEST,
        MARKER_HARNESS_READY,
        MARKER_ADMISSION,
        *prefix,
        MARKER_BUDGET_EXPIRED,
        MARKER_TEARDOWN,
    )
    for prefix in _LIMIT_CANDIDATE_PREFIXES
)

# Admission négative prouvée (ARTIFACT_INVALID).
_INVALID_ADMISSION_ORDER = (
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
PENALIZING_OR_HARNESS = frozenset({
    "PROVIDER_FAILURE",
    "ARTIFACT_INVALID",
    "ARTIFACT_EXECUTION_LIMIT",
    "HARNESS_ERROR",
})


class VerifyV7ContratInvalide(ValueError):
    """Incohérence de contrat verify-v7 : jamais un résultat pénalisant silencieux"""


@dataclass(frozen=True)
class AdapterIdentity:
    adapter_id: str
    adapter_version: str
    adapter_hash: str


@dataclass(frozen=True)
class QualifiedBudget:
    """Budget artefact qualifié — aucune valeur par défaut autorisée"""

    value: int
    unit: str
    budget_hash: str
    scope: str
    measurement_rule: str


@dataclass(frozen=True)
class ProviderEvidence:
    """Preuves injectées sur la route ou le fournisseur avant tout artefact"""

    lock_bound: bool
    payload_bound: bool
    route_pinned: bool
    provider_pinned: bool
    attempt_receipt_ref: str | None
    response_or_error_ref: str | None
    artifact_admissible: bool


@dataclass(frozen=True)
class AxisExecutionRequest:
    acquisition_id: str
    axis_id: str
    artifact_proof_ref: str
    qualified_budget: QualifiedBudget
    adapter_identity: AdapterIdentity


@dataclass(frozen=True)
class AxisTrace:
    """Trace structurée et expurgée. L'adaptateur ne choisit jamais la classe"""

    axis_id: str
    markers: tuple[str, ...]
    stage_proofs: tuple[tuple[str, str], ...]
    harness_ready_proof_ref: str
    admission_result: bool | None
    evaluation_completed: bool
    verdict: str | None
    budget_expired: bool
    observed_cost: int | None
    watchdog_healthy: bool
    teardown_complete: bool
    ambiguous: bool = False


@runtime_checkable
class ModalityAdapter(Protocol):
    """Interface minimale : identité immuable et exécution d'un axe"""

    @property
    def identity(self) -> AdapterIdentity: ...

    def execute_axis(self, request: AxisExecutionRequest) -> AxisTrace: ...


@dataclass(frozen=True)
class Incident:
    incident_id: str
    stage: str
    scope: str
    causal_class: str
    affected_unit_ids: tuple[str, ...]
    proof_refs: tuple[str, ...]
    missing_evidence: tuple[str, ...] = ()
    diagnostic_code: str = ""


@dataclass(frozen=True)
class UnitResult:
    axis_id: str
    measurement_state: str
    causal_class: str
    verdict: str | None
    incident_id: str | None
    trace: AxisTrace | None


@dataclass(frozen=True)
class AcquisitionResult:
    acquisition_id: str
    units: tuple[UnitResult, ...]
    incidents: tuple[Incident, ...]
    adapter_call_count: int


@dataclass(frozen=True)
class _TraceDecision:
    """Décision canonique privée de trace — autorité unique d'attribution"""

    measurement_state: str
    causal_class: str
    verdict: str | None
    proof_refs: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    diagnostic_code: str
    stage: str


def _exiger(cond: bool, message: str) -> None:
    if not cond:
        raise VerifyV7ContratInvalide(message)


def _nonempty_ref(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _validate_qualified_budget(budget: QualifiedBudget) -> None:
    _exiger(isinstance(budget, QualifiedBudget), "qualified_budget requis")
    _exiger(isinstance(budget.value, int) and budget.value > 0, "budget value invalide")
    _exiger(_nonempty_ref(budget.unit), "budget unit vide")
    _exiger(_nonempty_ref(budget.budget_hash), "budget_hash vide")
    _exiger(_nonempty_ref(budget.scope), "budget scope vide")
    _exiger(_nonempty_ref(budget.measurement_rule), "measurement_rule vide")


def _provider_fully_proven(evidence: ProviderEvidence) -> bool:
    return (
        evidence.lock_bound
        and evidence.payload_bound
        and evidence.route_pinned
        and evidence.provider_pinned
        and _nonempty_ref(evidence.attempt_receipt_ref)
        and _nonempty_ref(evidence.response_or_error_ref)
    )


def _incident_id(
    acquisition_id: str,
    scope: str,
    causal_class: str,
    *,
    axis_id: str | None = None,
) -> str:
    parts = [acquisition_id, scope, causal_class]
    if axis_id is not None:
        parts.append(axis_id)
    return ":".join(parts)


def _provider_proof_refs(evidence: ProviderEvidence) -> tuple[str, ...]:
    refs: list[str] = []
    if _nonempty_ref(evidence.attempt_receipt_ref):
        refs.append(str(evidence.attempt_receipt_ref).strip())
    if _nonempty_ref(evidence.response_or_error_ref):
        refs.append(str(evidence.response_or_error_ref).strip())
    return tuple(refs)


def _provider_missing_evidence(evidence: ProviderEvidence) -> tuple[str, ...]:
    missing: list[str] = []
    if not _nonempty_ref(evidence.attempt_receipt_ref):
        missing.append("attempt_receipt")
    if not _nonempty_ref(evidence.response_or_error_ref):
        missing.append("response_or_error")
    return tuple(missing)


def _normalize_ref_tuple(values: tuple[str, ...]) -> tuple[str, ...] | None:
    """Normalise, refuse vide/espace, et impose l'unicité. None si invalide"""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not _nonempty_ref(value):
            return None
        key = value.strip()
        if key in seen:
            return None
        seen.add(key)
        out.append(key)
    return tuple(out)


def _stage_proof_map(trace: AxisTrace) -> dict[str, str] | None:
    proofs: dict[str, str] = {}
    seen_refs: set[str] = set()
    for stage, ref in trace.stage_proofs:
        if not _nonempty_ref(stage) or not _nonempty_ref(ref):
            return None
        key = stage.strip()
        val = ref.strip()
        if key in proofs or val in seen_refs:
            return None
        proofs[key] = val
        seen_refs.add(val)
    return proofs


def _trace_proof_refs(trace: AxisTrace) -> tuple[str, ...]:
    refs: list[str] = []
    seen: set[str] = set()
    for _, ref in trace.stage_proofs:
        if not _nonempty_ref(ref):
            continue
        key = ref.strip()
        if key in seen:
            continue
        seen.add(key)
        refs.append(key)
    if _nonempty_ref(trace.harness_ready_proof_ref):
        ready = trace.harness_ready_proof_ref.strip()
        if ready not in seen:
            refs.append(ready)
    return tuple(refs)


def _harness_decision(
    *,
    proof_refs: tuple[str, ...],
    missing_evidence: tuple[str, ...] = ("trace_grammar",),
    diagnostic_code: str = "TRACE_INVALID",
    stage: str = "harness",
) -> _TraceDecision:
    if not proof_refs and not missing_evidence:
        missing_evidence = ("trace_grammar",)
    return _TraceDecision(
        measurement_state="NOT_SCORED",
        causal_class="HARNESS_ERROR",
        verdict=None,
        proof_refs=proof_refs,
        missing_evidence=missing_evidence,
        diagnostic_code=diagnostic_code,
        stage=stage,
    )


def _markers_exact(markers: tuple[str, ...], expected: tuple[str, ...]) -> bool:
    return markers == expected


def _proofs_match_markers(
    markers: tuple[str, ...],
    proofs: dict[str, str],
) -> bool:
    if set(markers) != set(proofs):
        return False
    return all(marker in proofs for marker in markers)


def _grammar_structural_ok(markers: tuple[str, ...]) -> bool | None:
    """True si grammaire exacte connue, False si structure invalide, None si autre"""
    if any(marker not in KNOWN_MARKERS for marker in markers):
        return False
    if len(markers) != len(set(markers)):
        return False
    if MARKER_INIT in markers and MARKER_LOAD not in markers:
        return False
    if MARKER_EVAL in markers and MARKER_INIT not in markers:
        return False
    if markers.count(MARKER_BUDGET_EXPIRED) > 1:
        return False
    if MARKER_BUDGET_EXPIRED in markers:
        expired_idx = markers.index(MARKER_BUDGET_EXPIRED)
        if any(
            marker in CANDIDATE_MARKERS and idx > expired_idx
            for idx, marker in enumerate(markers)
        ):
            return False
    return None


def _decide_trace(
    trace: AxisTrace,
    *,
    axis_id: str,
    qualified_budget: QualifiedBudget | None,
) -> _TraceDecision:
    """Décision canonique privée — unique autorité pour acquisition et validate_unit_result"""
    if not isinstance(trace, AxisTrace):
        return _harness_decision(
            proof_refs=(),
            missing_evidence=("structured_trace",),
            diagnostic_code="TRACE_MALFORMED",
        )
    proof_refs = _trace_proof_refs(trace) if isinstance(trace, AxisTrace) else ()

    if trace.ambiguous:
        return _harness_decision(
            proof_refs=proof_refs,
            missing_evidence=("unambiguous_attribution",),
            diagnostic_code="PROOF_AMBIGUOUS",
        )
    if trace.axis_id != axis_id:
        return _harness_decision(
            proof_refs=proof_refs,
            missing_evidence=("axis_id_match",),
            diagnostic_code="AXIS_MISMATCH",
        )
    if not _nonempty_ref(trace.harness_ready_proof_ref):
        return _harness_decision(
            proof_refs=proof_refs,
            missing_evidence=("harness_ready_proof",),
            diagnostic_code="EVIDENCE_MISSING",
        )

    proofs = _stage_proof_map(trace)
    if proofs is None:
        return _harness_decision(
            proof_refs=proof_refs,
            missing_evidence=("stage_proof_unique",),
            diagnostic_code="PROOF_DUPLICATE_OR_BLANK",
        )

    structural = _grammar_structural_ok(trace.markers)
    if structural is False:
        return _harness_decision(
            proof_refs=proof_refs,
            missing_evidence=("trace_grammar",),
            diagnostic_code="TRACE_GRAMMAR",
        )

    if not _proofs_match_markers(trace.markers, proofs):
        return _harness_decision(
            proof_refs=proof_refs,
            missing_evidence=("stage_proof_coverage",),
            diagnostic_code="EVIDENCE_MISSING",
        )

    ready_proof = trace.harness_ready_proof_ref.strip()
    if MARKER_HARNESS_READY not in proofs or proofs[MARKER_HARNESS_READY] != ready_proof:
        return _harness_decision(
            proof_refs=proof_refs,
            missing_evidence=("harness_ready_proof",),
            diagnostic_code="PROOF_INCONSISTENT",
        )

    if not trace.watchdog_healthy:
        return _harness_decision(
            proof_refs=proof_refs,
            missing_evidence=("watchdog_health",),
            diagnostic_code="WATCHDOG_UNHEALTHY",
        )
    if not trace.teardown_complete:
        return _harness_decision(
            proof_refs=proof_refs,
            missing_evidence=("teardown",),
            diagnostic_code="TEARDOWN_INCOMPLETE",
        )

    # Admission négative prouvée.
    if trace.admission_result is False:
        if not _markers_exact(trace.markers, _INVALID_ADMISSION_ORDER):
            return _harness_decision(
                proof_refs=proof_refs,
                missing_evidence=("admission_grammar",),
                diagnostic_code="TRACE_GRAMMAR",
            )
        return _TraceDecision(
            measurement_state="NOT_SCORED",
            causal_class="ARTIFACT_INVALID",
            verdict=None,
            proof_refs=proof_refs,
            missing_evidence=(),
            diagnostic_code="",
            stage="admission",
        )

    if trace.admission_result is not True:
        return _harness_decision(
            proof_refs=proof_refs,
            missing_evidence=("admission_result",),
            diagnostic_code="EVIDENCE_MISSING",
        )

    # Expiration budgétaire : grammaire LIMIT exacte
    if trace.budget_expired:
        if qualified_budget is None:
            return _harness_decision(
                proof_refs=proof_refs,
                missing_evidence=("qualified_budget",),
                diagnostic_code="EVIDENCE_MISSING",
            )
        matched_limit = next(
            (
                order
                for order in LIMIT_MEASUREMENT_ORDERS
                if _markers_exact(trace.markers, order)
            ),
            None,
        )
        if matched_limit is None:
            return _harness_decision(
                proof_refs=proof_refs,
                missing_evidence=("limit_grammar",),
                diagnostic_code="TRACE_GRAMMAR",
            )
        if not isinstance(trace.observed_cost, int):
            return _harness_decision(
                proof_refs=proof_refs,
                missing_evidence=("observed_cost",),
                diagnostic_code="EVIDENCE_MISSING",
            )
        if trace.observed_cost < qualified_budget.value:
            return _harness_decision(
                proof_refs=proof_refs,
                missing_evidence=("budget_threshold",),
                diagnostic_code="BUDGET_NOT_REACHED",
            )
        return _TraceDecision(
            measurement_state="NOT_SCORED",
            causal_class="ARTIFACT_EXECUTION_LIMIT",
            verdict=None,
            proof_refs=proof_refs,
            missing_evidence=(),
            diagnostic_code="",
            stage="artifact-budget",
        )

    # Mesure terminée : grammaire COMPLETE exacte.
    if _markers_exact(trace.markers, COMPLETED_MEASUREMENT_ORDER):
        if not trace.evaluation_completed or not _nonempty_ref(trace.verdict):
            return _harness_decision(
                proof_refs=proof_refs,
                missing_evidence=("evaluation_verdict",),
                diagnostic_code="EVIDENCE_MISSING",
            )
        return _TraceDecision(
            measurement_state="SCORED",
            causal_class="MEASUREMENT_COMPLETED",
            verdict=str(trace.verdict).strip(),
            proof_refs=proof_refs,
            missing_evidence=(),
            diagnostic_code="",
            stage="evaluation",
        )

    return _harness_decision(
        proof_refs=proof_refs,
        missing_evidence=("trace_grammar",),
        diagnostic_code="TRACE_GRAMMAR",
    )


def _trace_proves_completed_measurement(trace: AxisTrace, *, axis_id: str) -> bool:
    decision = _decide_trace(trace, axis_id=axis_id, qualified_budget=None)
    return (
        decision.measurement_state == "SCORED"
        and decision.causal_class == "MEASUREMENT_COMPLETED"
    )


def _attribute_trace(
    trace: AxisTrace,
    *,
    axis_id: str,
    qualified_budget: QualifiedBudget,
) -> _TraceDecision:
    return _decide_trace(trace, axis_id=axis_id, qualified_budget=qualified_budget)

def _acquisition_terminal(
    *,
    acquisition_id: str,
    axis_ids: tuple[str, ...],
    causal_class: str,
    stage: str,
    proof_refs: tuple[str, ...],
    adapter_call_count: int,
    traces: dict[str, AxisTrace | None] | None = None,
    missing_evidence: tuple[str, ...] = (),
    diagnostic_code: str = "",
) -> AcquisitionResult:
    incident = Incident(
        incident_id=_incident_id(acquisition_id, "ACQUISITION", causal_class),
        stage=stage,
        scope="ACQUISITION",
        causal_class=causal_class,
        affected_unit_ids=axis_ids,
        proof_refs=proof_refs,
        missing_evidence=missing_evidence,
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
            trace=traces.get(axis_id),
        )
        for axis_id in axis_ids
    )
    return AcquisitionResult(
        acquisition_id=acquisition_id,
        units=units,
        incidents=(incident,),
        adapter_call_count=adapter_call_count,
    )


def _axis_harness_error(
    *,
    acquisition_id: str,
    axis_id: str,
    proof_refs: tuple[str, ...],
    trace: AxisTrace | None,
    stage: str = "harness",
    missing_evidence: tuple[str, ...] = ("adapter_observation",),
    diagnostic_code: str = "ADAPTER_EXCEPTION",
) -> tuple[UnitResult, Incident]:
    incident = Incident(
        incident_id=_incident_id(
            acquisition_id, "AXIS", "HARNESS_ERROR", axis_id=axis_id
        ),
        stage=stage,
        scope="AXIS",
        causal_class="HARNESS_ERROR",
        affected_unit_ids=(axis_id,),
        proof_refs=proof_refs,
        missing_evidence=missing_evidence,
        diagnostic_code=diagnostic_code,
    )
    unit = UnitResult(
        axis_id=axis_id,
        measurement_state="NOT_SCORED",
        causal_class="HARNESS_ERROR",
        verdict=None,
        incident_id=incident.incident_id,
        trace=trace,
    )
    return unit, incident


def _isolation_reused(
    *,
    trace: AxisTrace,
    seen_trace_ids: set[int],
    seen_ready_proofs: set[str],
    seen_stage_proofs: set[str],
) -> bool:
    ready = (
        trace.harness_ready_proof_ref.strip()
        if _nonempty_ref(trace.harness_ready_proof_ref)
        else ""
    )
    stage_refs = {
        ref.strip() for _, ref in trace.stage_proofs if _nonempty_ref(ref)
    }
    return (
        id(trace) in seen_trace_ids
        or (ready != "" and ready in seen_ready_proofs)
        or bool(stage_refs & seen_stage_proofs)
    )


def _remember_isolation(
    *,
    trace: AxisTrace,
    seen_trace_ids: set[int],
    seen_ready_proofs: set[str],
    seen_stage_proofs: set[str],
) -> None:
    seen_trace_ids.add(id(trace))
    if _nonempty_ref(trace.harness_ready_proof_ref):
        seen_ready_proofs.add(trace.harness_ready_proof_ref.strip())
    for _, ref in trace.stage_proofs:
        if _nonempty_ref(ref):
            seen_stage_proofs.add(ref.strip())


def verify_acquisition(
    *,
    acquisition_id: str,
    axis_ids: Sequence[str],
    provider_evidence: ProviderEvidence,
    qualified_budget: QualifiedBudget,
    artifact_proof_ref: str,
    adapter: ModalityAdapter,
) -> AcquisitionResult:
    """Exécute l'attribution fail-closed d'une acquisition purement en mémoire"""
    _exiger(_nonempty_ref(acquisition_id), "acquisition_id requis")
    _validate_qualified_budget(qualified_budget)
    _exiger(_nonempty_ref(artifact_proof_ref), "artifact_proof_ref requis")
    axes = tuple(axis_ids)
    _exiger(len(axes) > 0, "axis_ids non vide")
    _exiger(all(_nonempty_ref(axis_id) for axis_id in axes), "axis_id vide")
    _exiger(len(set(axes)) == len(axes), "axis_ids uniques")
    acquisition_key = acquisition_id.strip()
    artifact_ref = artifact_proof_ref.strip()

    if not _provider_fully_proven(provider_evidence):
        proof_refs = _provider_proof_refs(provider_evidence)
        missing = _provider_missing_evidence(provider_evidence)
        result = _acquisition_terminal(
            acquisition_id=acquisition_key,
            axis_ids=axes,
            causal_class="HARNESS_ERROR",
            stage="provider",
            proof_refs=proof_refs,
            adapter_call_count=0,
            missing_evidence=missing,
            diagnostic_code="EVIDENCE_MISSING",
        )
        validate_acquisition_result(result)
        return result

    if not provider_evidence.artifact_admissible:
        result = _acquisition_terminal(
            acquisition_id=acquisition_key,
            axis_ids=axes,
            causal_class="PROVIDER_FAILURE",
            stage="provider",
            proof_refs=_provider_proof_refs(provider_evidence),
            adapter_call_count=0,
        )
        validate_acquisition_result(result)
        return result

    units: list[UnitResult] = []
    incidents: list[Incident] = []
    call_count = 0
    traces_so_far: dict[str, AxisTrace | None] = {}
    seen_trace_ids: set[int] = set()
    seen_ready_proofs: set[str] = set()
    seen_stage_proofs: set[str] = set()
    admission_accepted = False

    for axis_id in axes:
        trace: AxisTrace | None = None
        counted = False
        try:
            identity = adapter.identity
            request = AxisExecutionRequest(
                acquisition_id=acquisition_key,
                axis_id=axis_id,
                artifact_proof_ref=artifact_ref,
                qualified_budget=qualified_budget,
                adapter_identity=identity,
            )
            trace = adapter.execute_axis(request)
            call_count += 1
            counted = True
            if not isinstance(trace, AxisTrace):
                decision = _harness_decision(
                    proof_refs=(),
                    missing_evidence=("structured_trace",),
                    diagnostic_code="TRACE_MALFORMED",
                    stage="adapter",
                )
            else:
                decision = _attribute_trace(
                    trace,
                    axis_id=axis_id,
                    qualified_budget=qualified_budget,
                )
                if _isolation_reused(
                    trace=trace,
                    seen_trace_ids=seen_trace_ids,
                    seen_ready_proofs=seen_ready_proofs,
                    seen_stage_proofs=seen_stage_proofs,
                ):
                    decision = _harness_decision(
                        proof_refs=_trace_proof_refs(trace),
                        missing_evidence=("axis_isolation",),
                        diagnostic_code="ISOLATION_REUSED",
                    )
                else:
                    _remember_isolation(
                        trace=trace,
                        seen_trace_ids=seen_trace_ids,
                        seen_ready_proofs=seen_ready_proofs,
                        seen_stage_proofs=seen_stage_proofs,
                    )
                if (
                    decision.causal_class == "ARTIFACT_INVALID"
                    and admission_accepted
                ):
                    decision = _harness_decision(
                        proof_refs=_trace_proof_refs(trace),
                        missing_evidence=("admission_consistency",),
                        diagnostic_code="ADMISSION_CONTRADICTION",
                    )
        except Exception:
            if not counted:
                call_count += 1
            unit, incident = _axis_harness_error(
                acquisition_id=acquisition_key,
                axis_id=axis_id,
                proof_refs=(),
                missing_evidence=("adapter_observation",),
                diagnostic_code="ADAPTER_EXCEPTION",
                trace=None,
                stage="adapter",
            )
            incidents.append(incident)
            units.append(unit)
            traces_so_far[axis_id] = None
            continue

        traces_so_far[axis_id] = trace
        state = decision.measurement_state
        causal = decision.causal_class
        verdict = decision.verdict

        if causal == "ARTIFACT_INVALID":
            remaining = axes[axes.index(axis_id) + 1 :]
            for skipped in remaining:
                traces_so_far.setdefault(skipped, None)
            result = _acquisition_terminal(
                acquisition_id=acquisition_key,
                axis_ids=axes,
                causal_class="ARTIFACT_INVALID",
                stage=decision.stage,
                proof_refs=decision.proof_refs,
                adapter_call_count=call_count,
                traces=traces_so_far,
            )
            validate_acquisition_result(result)
            return result

        if state == "SCORED" and causal == "MEASUREMENT_COMPLETED":
            admission_accepted = True
            units.append(
                UnitResult(
                    axis_id=axis_id,
                    measurement_state="SCORED",
                    causal_class="MEASUREMENT_COMPLETED",
                    verdict=verdict,
                    incident_id=None,
                    trace=trace,
                )
            )
            continue

        if trace is not None and trace.admission_result is True:
            admission_accepted = True

        incident = Incident(
            incident_id=_incident_id(
                acquisition_key, "AXIS", causal, axis_id=axis_id
            ),
            stage=decision.stage,
            scope="AXIS",
            causal_class=causal,
            affected_unit_ids=(axis_id,),
            proof_refs=decision.proof_refs,
            missing_evidence=decision.missing_evidence,
            diagnostic_code=decision.diagnostic_code,
        )
        incidents.append(incident)
        units.append(
            UnitResult(
                axis_id=axis_id,
                measurement_state="NOT_SCORED",
                causal_class=causal,
                verdict=None,
                incident_id=incident.incident_id,
                trace=trace,
            )
        )

    result = AcquisitionResult(
        acquisition_id=acquisition_key,
        units=tuple(units),
        incidents=tuple(incidents),
        adapter_call_count=call_count,
    )
    validate_acquisition_result(result)
    return result


def validate_incident(incident: Incident) -> None:
    _exiger(isinstance(incident, Incident), "incident requis")
    _exiger(_nonempty_ref(incident.incident_id), "incident_id")
    _exiger(_nonempty_ref(incident.stage), "stage")
    _exiger(incident.scope in INCIDENT_SCOPES, f"portée invalide: {incident.scope}")
    _exiger(
        incident.causal_class in PENALIZING_OR_HARNESS,
        f"classe d'incident invalide: {incident.causal_class}",
    )
    _exiger(
        isinstance(incident.affected_unit_ids, tuple) and len(incident.affected_unit_ids) > 0,
        "affected_unit_ids",
    )
    _exiger(
        all(_nonempty_ref(axis_id) for axis_id in incident.affected_unit_ids),
        "affected_unit_ids vides",
    )
    _exiger(isinstance(incident.proof_refs, tuple), "proof_refs")
    _exiger(isinstance(incident.missing_evidence, tuple), "missing_evidence")
    _exiger(isinstance(incident.diagnostic_code, str), "diagnostic_code")
    normalized_proofs = _normalize_ref_tuple(incident.proof_refs)
    _exiger(normalized_proofs is not None, "proof_refs invalides")
    _exiger(normalized_proofs == incident.proof_refs, "proof_refs non normalises")
    normalized_missing = _normalize_ref_tuple(incident.missing_evidence)
    _exiger(normalized_missing is not None, "missing_evidence invalides")
    _exiger(
        normalized_missing == incident.missing_evidence,
        "missing_evidence non normalises",
    )
    if incident.causal_class == "HARNESS_ERROR":
        _exiger(_nonempty_ref(incident.diagnostic_code), "diagnostic_code")
        if len(incident.proof_refs) == 0:
            _exiger(len(incident.missing_evidence) > 0, "missing_evidence")
    else:
        _exiger(len(incident.proof_refs) > 0, "proof_refs vides")
        _exiger(len(incident.missing_evidence) == 0, "missing_evidence")
        _exiger(incident.diagnostic_code == "", "diagnostic_code")
    if incident.causal_class == "PROVIDER_FAILURE":
        _exiger(
            incident.scope == "ACQUISITION",
            "PROVIDER_FAILURE seulement au scope ACQUISITION",
        )
    if incident.scope == "AXIS":
        _exiger(
            incident.causal_class != "PROVIDER_FAILURE",
            "AXIS/PROVIDER_FAILURE interdit",
        )
        _exiger(
            len(incident.affected_unit_ids) == 1,
            "incident AXIS affecte exactement une unité",
        )
    if incident.scope == "ACQUISITION":
        _exiger(
            incident.causal_class in {"PROVIDER_FAILURE", "ARTIFACT_INVALID", "HARNESS_ERROR"},
            "classe ACQUISITION incohérente",
        )


def validate_unit_result(unit: UnitResult) -> None:
    _exiger(isinstance(unit, UnitResult), "unit requis")
    _exiger(_nonempty_ref(unit.axis_id), "axis_id")
    _exiger(unit.measurement_state in MEASUREMENT_STATES, "état de mesure")
    _exiger(unit.causal_class in CAUSAL_CLASSES, "classe causale")

    if unit.measurement_state == "NOT_SCORED":
        _exiger(unit.verdict is None, "NOT_SCORED interdit verdict/niveau")
        _exiger(unit.causal_class != "MEASUREMENT_COMPLETED", "NOT_SCORED sans mesure")
        _exiger(_nonempty_ref(unit.incident_id), "NOT_SCORED exige incident_id")
    else:
        _exiger(
            unit.causal_class == "MEASUREMENT_COMPLETED",
            "SCORED interdit une classe autre que MEASUREMENT_COMPLETED",
        )
        _exiger(_nonempty_ref(unit.verdict), "SCORED exige un verdict")
        _exiger(unit.incident_id is None, "SCORED n'a pas d'incident")
        _exiger(isinstance(unit.trace, AxisTrace), "SCORED exige une trace")
        _exiger(
            _trace_proves_completed_measurement(unit.trace, axis_id=unit.axis_id),
            "SCORED exige une trace prouvant la mesure terminée",
        )


def validate_acquisition_result(result: AcquisitionResult) -> None:
    _exiger(isinstance(result, AcquisitionResult), "resultat requis")
    _exiger(_nonempty_ref(result.acquisition_id), "acquisition_id")
    _exiger(isinstance(result.units, tuple) and len(result.units) > 0, "units")
    _exiger(isinstance(result.incidents, tuple), "incidents")
    _exiger(isinstance(result.adapter_call_count, int) and result.adapter_call_count >= 0, "calls")

    seen_axes: set[str] = set()
    for unit in result.units:
        validate_unit_result(unit)
        _exiger(unit.axis_id not in seen_axes, f"unité dupliquée: {unit.axis_id}")
        seen_axes.add(unit.axis_id)
        if unit.measurement_state == "SCORED":
            _exiger(
                result.adapter_call_count > 0,
                "SCORED exige une preuve d'appel adaptateur",
            )

    for incident in result.incidents:
        validate_incident(incident)
        for axis_id in incident.affected_unit_ids:
            _exiger(axis_id in seen_axes, f"unité inconnue dans incident: {axis_id}")
        if incident.scope == "ACQUISITION":
            _exiger(
                set(incident.affected_unit_ids) == seen_axes,
                "incident ACQUISITION doit couvrir toutes les unités",
            )

    acquisition_keys = [
        (incident.scope, incident.causal_class, incident.stage)
        for incident in result.incidents
        if incident.scope == "ACQUISITION"
    ]
    _exiger(
        len(acquisition_keys) == len(set(acquisition_keys)),
        "incident amont dupliqué",
    )

    incident_by_id = {incident.incident_id: incident for incident in result.incidents}
    _exiger(len(incident_by_id) == len(result.incidents), "incident_id dupliqué")

    units_by_id = {unit.axis_id: unit for unit in result.units}
    for incident in result.incidents:
        for axis_id in incident.affected_unit_ids:
            unit = units_by_id[axis_id]
            _exiger(
                unit.incident_id == incident.incident_id,
                "unité affectée sans référence à l'incident",
            )

    for unit in result.units:
        if unit.incident_id is None:
            continue
        _exiger(unit.incident_id in incident_by_id, f"incident manquant: {unit.incident_id}")
        incident = incident_by_id[unit.incident_id]
        _exiger(unit.axis_id in incident.affected_unit_ids, "unité absente de l'incident")
        _exiger(unit.causal_class == incident.causal_class, "classe unité/incident divergente")
