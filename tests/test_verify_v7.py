"""Preuves unitaires du noyau verify-v7 pur (mémoire, sans modalité réelle)."""

from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

from verify_v7 import (  # noqa: E402
    MARKER_ADMISSION,
    MARKER_AUTOTEST,
    MARKER_BUDGET_EXPIRED,
    MARKER_EVAL,
    MARKER_HARNESS_READY,
    MARKER_INIT,
    MARKER_LOAD,
    MARKER_PREPARE,
    MARKER_TEARDOWN,
    AcquisitionResult,
    AdapterIdentity,
    AxisExecutionRequest,
    AxisTrace,
    Incident,
    ModalityAdapter,
    ProviderEvidence,
    QualifiedBudget,
    UnitResult,
    VerifyV7ContratInvalide,
    validate_acquisition_result,
    validate_incident,
    validate_unit_result,
    verify_acquisition,
)


def _budget(**overrides) -> QualifiedBudget:
    base = dict(
        value=100,
        unit="abstract-ticks",
        budget_hash="budget-hash-qualified",
        scope="artifact",
        measurement_rule="injected-markers",
    )
    base.update(overrides)
    return QualifiedBudget(**base)


def _provider_ok() -> ProviderEvidence:
    return ProviderEvidence(
        lock_bound=True,
        payload_bound=True,
        route_pinned=True,
        provider_pinned=True,
        attempt_receipt_ref="proof:attempt",
        response_or_error_ref="proof:response",
        artifact_admissible=True,
    )


def _provider_failure() -> ProviderEvidence:
    return replace(_provider_ok(), artifact_admissible=False, response_or_error_ref="proof:error")


def _provider_incomplete() -> ProviderEvidence:
    return ProviderEvidence(
        lock_bound=True,
        payload_bound=False,
        route_pinned=True,
        provider_pinned=True,
        attempt_receipt_ref="proof:attempt",
        response_or_error_ref="proof:error",
        artifact_admissible=False,
    )


def _proof(axis_id: str, stage: str) -> str:
    return f"proof:{axis_id}:{stage}"


def _stage_proofs(axis_id: str, stages: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((stage, _proof(axis_id, stage)) for stage in stages)


def _success_trace(axis_id: str = "a1", *, verdict: str = "PASS") -> AxisTrace:
    stages = (
        MARKER_PREPARE,
        MARKER_AUTOTEST,
        MARKER_HARNESS_READY,
        MARKER_ADMISSION,
        MARKER_LOAD,
        MARKER_INIT,
        MARKER_EVAL,
        MARKER_TEARDOWN,
    )
    return AxisTrace(
        axis_id=axis_id,
        markers=stages,
        stage_proofs=_stage_proofs(axis_id, stages),
        harness_ready_proof_ref=_proof(axis_id, MARKER_HARNESS_READY),
        admission_result=True,
        evaluation_completed=True,
        verdict=verdict,
        budget_expired=False,
        observed_cost=10,
        watchdog_healthy=True,
        teardown_complete=True,
        ambiguous=False,
    )


def _reject_trace(axis_id: str = "a1") -> AxisTrace:
    stages = (
        MARKER_PREPARE,
        MARKER_AUTOTEST,
        MARKER_HARNESS_READY,
        MARKER_ADMISSION,
        MARKER_TEARDOWN,
    )
    return AxisTrace(
        axis_id=axis_id,
        markers=stages,
        stage_proofs=_stage_proofs(axis_id, stages),
        harness_ready_proof_ref=_proof(axis_id, MARKER_HARNESS_READY),
        admission_result=False,
        evaluation_completed=False,
        verdict=None,
        budget_expired=False,
        observed_cost=None,
        watchdog_healthy=True,
        teardown_complete=True,
        ambiguous=False,
    )


def _limit_trace(axis_id: str = "a1", *, observed_cost: int = 100) -> AxisTrace:
    markers = (
        MARKER_PREPARE,
        MARKER_AUTOTEST,
        MARKER_HARNESS_READY,
        MARKER_ADMISSION,
        MARKER_LOAD,
        MARKER_INIT,
        MARKER_BUDGET_EXPIRED,
        MARKER_TEARDOWN,
    )
    proofs = _stage_proofs(axis_id, markers)
    return AxisTrace(
        axis_id=axis_id,
        markers=markers,
        stage_proofs=proofs,
        harness_ready_proof_ref=_proof(axis_id, MARKER_HARNESS_READY),
        admission_result=True,
        evaluation_completed=False,
        verdict=None,
        budget_expired=True,
        observed_cost=observed_cost,
        watchdog_healthy=True,
        teardown_complete=True,
        ambiguous=False,
    )


class RecordingAdapter:
    """Faux adaptateur de test : prouve l'ordre, l'isolation et le compte d'appels."""

    def __init__(self, traces_by_axis: dict[str, AxisTrace] | None = None) -> None:
        self._identity = AdapterIdentity(
            adapter_id="fake-modality",
            adapter_version="test-1",
            adapter_hash="adapter-hash-test",
        )
        self._traces = dict(traces_by_axis or {})
        self.calls: list[AxisExecutionRequest] = []
        self.raise_on: set[str] = set()
        self.identity_raises = False

    @property
    def identity(self) -> AdapterIdentity:
        if self.identity_raises:
            raise RuntimeError("identity-boom")
        return self._identity

    def execute_axis(self, request: AxisExecutionRequest) -> AxisTrace:
        self.calls.append(request)
        if request.axis_id in self.raise_on:
            raise RuntimeError(f"adapter-boom:{request.axis_id}")
        if request.axis_id not in self._traces:
            raise AssertionError(f"trace manquante pour {request.axis_id}")
        return self._traces[request.axis_id]


def _run(
    *,
    axis_ids: tuple[str, ...] = ("a1", "a2"),
    provider: ProviderEvidence | None = None,
    adapter: ModalityAdapter | None = None,
    acquisition_id: str = "acq-1",
    artifact_proof_ref: str = "proof:artifact",
    budget: QualifiedBudget | None = None,
):
    if adapter is None:
        adapter = RecordingAdapter({aid: _success_trace(aid) for aid in axis_ids})
    return verify_acquisition(
        acquisition_id=acquisition_id,
        axis_ids=axis_ids,
        provider_evidence=provider if provider is not None else _provider_ok(),
        qualified_budget=budget if budget is not None else _budget(),
        artifact_proof_ref=artifact_proof_ref,
        adapter=adapter,
    )


class VerifyV7ProviderGates(unittest.TestCase):
    def test_zero_positive_provider_refs_are_harness_error_with_evidence_inventory(self):
        """C1: zéro ref positive => HARNESS_ERROR ACQUISITION, inventaire exact, zéro adaptateur."""
        evidence = ProviderEvidence(
            lock_bound=False,
            payload_bound=False,
            route_pinned=False,
            provider_pinned=False,
            attempt_receipt_ref=None,
            response_or_error_ref=None,
            artifact_admissible=False,
        )
        adapter = RecordingAdapter({
            "a1": _success_trace("a1"),
            "a2": _success_trace("a2"),
        })
        result = _run(provider=evidence, adapter=adapter)
        self.assertEqual(len(adapter.calls), 0)
        self.assertEqual(result.adapter_call_count, 0)
        self.assertEqual(len(result.incidents), 1)
        incident = result.incidents[0]
        self.assertEqual(incident.scope, "ACQUISITION")
        self.assertEqual(incident.causal_class, "HARNESS_ERROR")
        self.assertEqual(incident.proof_refs, ())
        self.assertEqual(
            incident.missing_evidence,
            ("attempt_receipt", "response_or_error"),
        )
        self.assertEqual(incident.diagnostic_code, "EVIDENCE_MISSING")
        self.assertEqual(incident.affected_unit_ids, ("a1", "a2"))
        for unit in result.units:
            self.assertEqual(unit.measurement_state, "NOT_SCORED")
            self.assertEqual(unit.causal_class, "HARNESS_ERROR")
            self.assertIsNone(unit.verdict)
            self.assertEqual(unit.incident_id, incident.incident_id)
        validate_acquisition_result(result)

    def test_provider_fully_proven_failure_is_acquisition_incident_without_adapter(self):
        adapter = RecordingAdapter()
        result = _run(provider=_provider_failure(), adapter=adapter)
        self.assertEqual(len(adapter.calls), 0)
        self.assertEqual(result.adapter_call_count, 0)
        self.assertEqual(len(result.incidents), 1)
        incident = result.incidents[0]
        self.assertEqual(incident.scope, "ACQUISITION")
        self.assertEqual(incident.causal_class, "PROVIDER_FAILURE")
        self.assertEqual(incident.affected_unit_ids, ("a1", "a2"))
        for unit in result.units:
            self.assertEqual(unit.measurement_state, "NOT_SCORED")
            self.assertEqual(unit.causal_class, "PROVIDER_FAILURE")
            self.assertIsNone(unit.verdict)
            self.assertEqual(unit.incident_id, incident.incident_id)
            self.assertIsNone(unit.trace)
        validate_acquisition_result(result)

    def test_provider_insufficient_proof_is_harness_error_never_provider_failure(self):
        adapter = RecordingAdapter()
        result = _run(provider=_provider_incomplete(), adapter=adapter)
        self.assertEqual(len(adapter.calls), 0)
        self.assertEqual(len(result.incidents), 1)
        self.assertEqual(result.incidents[0].causal_class, "HARNESS_ERROR")
        self.assertNotEqual(result.incidents[0].causal_class, "PROVIDER_FAILURE")
        for unit in result.units:
            self.assertEqual(unit.measurement_state, "NOT_SCORED")
            self.assertEqual(unit.causal_class, "HARNESS_ERROR")
            self.assertIsNone(unit.verdict)
        validate_acquisition_result(result)

    def test_blank_provider_refs_are_harness_error_never_provider_failure(self):
        for evidence in (
            replace(_provider_failure(), attempt_receipt_ref=""),
            replace(_provider_failure(), attempt_receipt_ref="   "),
            replace(_provider_failure(), response_or_error_ref="\t"),
            replace(_provider_failure(), response_or_error_ref=None),
        ):
            adapter = RecordingAdapter()
            result = _run(provider=evidence, adapter=adapter)
            self.assertEqual(len(adapter.calls), 0)
            self.assertEqual(result.incidents[0].causal_class, "HARNESS_ERROR")
            self.assertNotEqual(result.incidents[0].causal_class, "PROVIDER_FAILURE")

    def test_incomplete_provider_even_if_admissible_is_harness_error_without_adapter(self):
        """C1: preuve fournisseur incomplète reste HARNESS_ERROR même si admissible."""
        for evidence in (
            replace(_provider_ok(), payload_bound=False),
            replace(_provider_ok(), attempt_receipt_ref=""),
            replace(_provider_ok(), attempt_receipt_ref="   "),
            replace(_provider_ok(), response_or_error_ref=None),
            replace(_provider_ok(), response_or_error_ref="\t"),
            replace(_provider_ok(), lock_bound=False),
            replace(_provider_ok(), route_pinned=False),
            replace(_provider_ok(), provider_pinned=False),
        ):
            adapter = RecordingAdapter({
                "a1": _success_trace("a1"),
                "a2": _success_trace("a2"),
            })
            result = _run(provider=evidence, adapter=adapter)
            self.assertEqual(len(adapter.calls), 0)
            self.assertEqual(result.adapter_call_count, 0)
            self.assertEqual(len(result.incidents), 1)
            incident = result.incidents[0]
            self.assertEqual(incident.scope, "ACQUISITION")
            self.assertEqual(incident.causal_class, "HARNESS_ERROR")
            self.assertEqual(incident.affected_unit_ids, ("a1", "a2"))
            for unit in result.units:
                self.assertEqual(unit.measurement_state, "NOT_SCORED")
                self.assertEqual(unit.causal_class, "HARNESS_ERROR")
                self.assertIsNone(unit.verdict)
                self.assertEqual(unit.incident_id, incident.incident_id)
            validate_acquisition_result(result)


class VerifyV7GrammarProofs(unittest.TestCase):
    def test_duplicate_proof_ref_across_load_and_init_is_harness_error_not_exception(self):
        """D1: COMPLETE où LOAD et INIT partagent proof_ref => NOT_SCORED/HARNESS_ERROR AXIS."""
        base = _success_trace("a1")
        shared = _proof("a1", MARKER_LOAD)
        proofs = tuple(
            (stage, shared if stage in {MARKER_LOAD, MARKER_INIT} else ref)
            for stage, ref in base.stage_proofs
        )
        result = _run(
            axis_ids=("a1",),
            adapter=RecordingAdapter({"a1": replace(base, stage_proofs=proofs)}),
        )
        unit = result.units[0]
        self.assertNotEqual(unit.measurement_state, "SCORED")
        self.assertEqual(unit.measurement_state, "NOT_SCORED")
        self.assertEqual(unit.causal_class, "HARNESS_ERROR")
        self.assertIsNone(unit.verdict)
        self.assertEqual(len(result.incidents), 1)
        incident = result.incidents[0]
        self.assertEqual(incident.scope, "AXIS")
        self.assertEqual(incident.causal_class, "HARNESS_ERROR")
        self.assertEqual(incident.affected_unit_ids, ("a1",))
        validate_acquisition_result(result)

    def test_duplicate_canonical_marker_in_completed_trace_is_harness_error(self):
        """C3: chaque marqueur canonique dupliqué dans COMPLETE => NOT_SCORED/HARNESS_ERROR."""
        base = _success_trace("a1")
        for marker in (
            MARKER_PREPARE,
            MARKER_AUTOTEST,
            MARKER_HARNESS_READY,
            MARKER_ADMISSION,
            MARKER_LOAD,
            MARKER_INIT,
            MARKER_EVAL,
            MARKER_TEARDOWN,
        ):
            with self.subTest(marker=marker):
                markers = list(base.markers)
                markers.insert(markers.index(marker) + 1, marker)
                trace = replace(base, markers=tuple(markers))
                result = _run(
                    axis_ids=("a1",),
                    adapter=RecordingAdapter({"a1": trace}),
                )
                unit = result.units[0]
                self.assertEqual(unit.measurement_state, "NOT_SCORED")
                self.assertEqual(unit.causal_class, "HARNESS_ERROR")
                self.assertIsNone(unit.verdict)

    def test_double_load_never_scored(self):
        """C4: double LOAD ne produit jamais SCORED."""
        base = _success_trace("a1")
        markers = (
            MARKER_PREPARE,
            MARKER_AUTOTEST,
            MARKER_HARNESS_READY,
            MARKER_ADMISSION,
            MARKER_LOAD,
            MARKER_LOAD,
            MARKER_INIT,
            MARKER_EVAL,
            MARKER_TEARDOWN,
        )
        result = _run(
            axis_ids=("a1",),
            adapter=RecordingAdapter({"a1": replace(base, markers=markers)}),
        )
        unit = result.units[0]
        self.assertNotEqual(unit.measurement_state, "SCORED")
        self.assertEqual(unit.measurement_state, "NOT_SCORED")
        self.assertEqual(unit.causal_class, "HARNESS_ERROR")

    def test_unknown_marker_is_harness_error(self):
        """C5: marqueur inconnu produit HARNESS_ERROR."""
        base = _success_trace("a1")
        markers = base.markers + ("UNKNOWN_STAGE",)
        proofs = base.stage_proofs + (("UNKNOWN_STAGE", "proof:a1:UNKNOWN_STAGE"),)
        result = _run(
            axis_ids=("a1",),
            adapter=RecordingAdapter({
                "a1": replace(base, markers=markers, stage_proofs=proofs),
            }),
        )
        unit = result.units[0]
        self.assertEqual(unit.measurement_state, "NOT_SCORED")
        self.assertEqual(unit.causal_class, "HARNESS_ERROR")

    def test_duplicate_budget_or_candidate_in_limit_trace_is_harness_error(self):
        """C6: BUDGET_EXPIRED ou stade candidat dupliqué dans LIMIT => HARNESS_ERROR."""
        cases = (
            # BUDGET_EXPIRED dupliqué
            (
                MARKER_PREPARE,
                MARKER_AUTOTEST,
                MARKER_HARNESS_READY,
                MARKER_ADMISSION,
                MARKER_LOAD,
                MARKER_BUDGET_EXPIRED,
                MARKER_BUDGET_EXPIRED,
                MARKER_TEARDOWN,
            ),
            # LOAD dupliqué
            (
                MARKER_PREPARE,
                MARKER_AUTOTEST,
                MARKER_HARNESS_READY,
                MARKER_ADMISSION,
                MARKER_LOAD,
                MARKER_LOAD,
                MARKER_BUDGET_EXPIRED,
                MARKER_TEARDOWN,
            ),
            # INIT dupliqué
            (
                MARKER_PREPARE,
                MARKER_AUTOTEST,
                MARKER_HARNESS_READY,
                MARKER_ADMISSION,
                MARKER_LOAD,
                MARKER_INIT,
                MARKER_INIT,
                MARKER_BUDGET_EXPIRED,
                MARKER_TEARDOWN,
            ),
        )
        for markers in cases:
            with self.subTest(markers=markers):
                unique = tuple(dict.fromkeys(markers))
                trace = AxisTrace(
                    axis_id="a1",
                    markers=markers,
                    stage_proofs=_stage_proofs("a1", unique),
                    harness_ready_proof_ref=_proof("a1", MARKER_HARNESS_READY),
                    admission_result=True,
                    evaluation_completed=False,
                    verdict=None,
                    budget_expired=True,
                    observed_cost=100,
                    watchdog_healthy=True,
                    teardown_complete=True,
                )
                result = _run(
                    axis_ids=("a1",),
                    adapter=RecordingAdapter({"a1": trace}),
                    budget=_budget(value=100),
                )
                unit = result.units[0]
                self.assertEqual(unit.measurement_state, "NOT_SCORED")
                self.assertEqual(unit.causal_class, "HARNESS_ERROR")
                self.assertNotEqual(unit.causal_class, "ARTIFACT_EXECUTION_LIMIT")

    def test_expiration_during_load_only_remains_execution_limit(self):
        """C7: expiration exacte pendant LOAD seul reste ARTIFACT_EXECUTION_LIMIT."""
        markers = (
            MARKER_PREPARE,
            MARKER_AUTOTEST,
            MARKER_HARNESS_READY,
            MARKER_ADMISSION,
            MARKER_LOAD,
            MARKER_BUDGET_EXPIRED,
            MARKER_TEARDOWN,
        )
        trace = AxisTrace(
            axis_id="a1",
            markers=markers,
            stage_proofs=_stage_proofs("a1", markers),
            harness_ready_proof_ref=_proof("a1", MARKER_HARNESS_READY),
            admission_result=True,
            evaluation_completed=False,
            verdict=None,
            budget_expired=True,
            observed_cost=100,
            watchdog_healthy=True,
            teardown_complete=True,
        )
        result = _run(
            axis_ids=("a1",),
            adapter=RecordingAdapter({"a1": trace}),
            budget=_budget(value=100),
        )
        unit = result.units[0]
        self.assertEqual(unit.measurement_state, "NOT_SCORED")
        self.assertEqual(unit.causal_class, "ARTIFACT_EXECUTION_LIMIT")
        self.assertNotIn(MARKER_INIT, unit.trace.markers)
        self.assertNotIn(MARKER_EVAL, unit.trace.markers)


class VerifyV7Admission(unittest.TestCase):
    def test_negative_admission_after_harness_ready_is_single_acquisition_invalid(self):
        adapter = RecordingAdapter({"a1": _reject_trace("a1"), "a2": _success_trace("a2")})
        result = _run(adapter=adapter)
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(adapter.calls[0].axis_id, "a1")
        self.assertEqual(len(result.incidents), 1)
        incident = result.incidents[0]
        self.assertEqual(incident.scope, "ACQUISITION")
        self.assertEqual(incident.causal_class, "ARTIFACT_INVALID")
        self.assertEqual(incident.affected_unit_ids, ("a1", "a2"))
        for unit in result.units:
            self.assertEqual(unit.measurement_state, "NOT_SCORED")
            self.assertEqual(unit.causal_class, "ARTIFACT_INVALID")
            self.assertIsNone(unit.verdict)
            self.assertEqual(unit.incident_id, incident.incident_id)
        self.assertIsNotNone(result.units[0].trace)
        self.assertIsNone(result.units[1].trace)
        validate_acquisition_result(result)


class VerifyV7HarnessErrors(unittest.TestCase):
    def test_missing_harness_ready_is_harness_error(self):
        trace = AxisTrace(
            axis_id="a1",
            markers=(MARKER_PREPARE, MARKER_AUTOTEST, MARKER_TEARDOWN),
            stage_proofs=_stage_proofs("a1", (MARKER_PREPARE, MARKER_AUTOTEST, MARKER_TEARDOWN)),
            harness_ready_proof_ref="",
            admission_result=None,
            evaluation_completed=False,
            verdict=None,
            budget_expired=False,
            observed_cost=None,
            watchdog_healthy=True,
            teardown_complete=True,
            ambiguous=False,
        )
        adapter = RecordingAdapter({"a1": trace})
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
        self.assertEqual(result.units[0].measurement_state, "NOT_SCORED")

    def test_ambiguous_proof_is_harness_error(self):
        trace = replace(_success_trace("a1"), ambiguous=True)
        adapter = RecordingAdapter({"a1": trace})
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_adapter_exception_is_harness_error(self):
        adapter = RecordingAdapter({"a1": _success_trace("a1")})
        adapter.raise_on.add("a1")
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
        self.assertEqual(result.incidents[0].scope, "AXIS")

    def test_identity_exception_is_harness_error_without_leak(self):
        adapter = RecordingAdapter({"a1": _success_trace("a1")})
        adapter.identity_raises = True
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
        self.assertEqual(result.incidents[0].scope, "AXIS")
        self.assertEqual(len(adapter.calls), 0)

    def test_unhealthy_watchdog_is_harness_error(self):
        trace = replace(_success_trace("a1"), watchdog_healthy=False)
        adapter = RecordingAdapter({"a1": trace})
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_incomplete_teardown_is_harness_error(self):
        base = _success_trace("a1")
        markers = tuple(m for m in base.markers if m != MARKER_TEARDOWN)
        proofs = tuple(p for p in base.stage_proofs if p[0] != MARKER_TEARDOWN)
        trace = replace(base, teardown_complete=False, markers=markers, stage_proofs=proofs)
        adapter = RecordingAdapter({"a1": trace})
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_wrong_marker_order_is_harness_error(self):
        base = _success_trace("a1")
        trace = replace(
            base,
            markers=(
                MARKER_AUTOTEST,
                MARKER_PREPARE,
                MARKER_HARNESS_READY,
                MARKER_ADMISSION,
                MARKER_LOAD,
                MARKER_INIT,
                MARKER_EVAL,
                MARKER_TEARDOWN,
            ),
        )
        adapter = RecordingAdapter({"a1": trace})
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_wrong_candidate_order_never_scored(self):
        """C2: toute inversion de la séquence candidate autorisée reste NOT_SCORED."""
        base = _success_trace("a1")
        cases = (
            # EVAL avant ADMISSION
            (
                MARKER_PREPARE,
                MARKER_AUTOTEST,
                MARKER_HARNESS_READY,
                MARKER_EVAL,
                MARKER_ADMISSION,
                MARKER_LOAD,
                MARKER_INIT,
                MARKER_TEARDOWN,
            ),
            # INIT avant LOAD
            (
                MARKER_PREPARE,
                MARKER_AUTOTEST,
                MARKER_HARNESS_READY,
                MARKER_ADMISSION,
                MARKER_INIT,
                MARKER_LOAD,
                MARKER_EVAL,
                MARKER_TEARDOWN,
            ),
            # marqueur candidat avant HARNESS_READY
            (
                MARKER_PREPARE,
                MARKER_AUTOTEST,
                MARKER_LOAD,
                MARKER_HARNESS_READY,
                MARKER_ADMISSION,
                MARKER_INIT,
                MARKER_EVAL,
                MARKER_TEARDOWN,
            ),
        )
        for markers in cases:
            with self.subTest(markers=markers):
                adapter = RecordingAdapter({"a1": replace(base, markers=markers)})
                result = _run(axis_ids=("a1",), adapter=adapter)
                unit = result.units[0]
                self.assertEqual(unit.measurement_state, "NOT_SCORED")
                self.assertEqual(unit.causal_class, "HARNESS_ERROR")
                self.assertIsNone(unit.verdict)
                self.assertNotEqual(unit.measurement_state, "SCORED")

    def test_missing_stage_proof_is_harness_error(self):
        base = _success_trace("a1")
        proofs = tuple(p for p in base.stage_proofs if p[0] != MARKER_EVAL)
        adapter = RecordingAdapter({"a1": replace(base, stage_proofs=proofs)})
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_blank_stage_proof_is_harness_error(self):
        base = _success_trace("a1")
        proofs = tuple(
            (stage, "   " if stage == MARKER_PREPARE else ref)
            for stage, ref in base.stage_proofs
        )
        adapter = RecordingAdapter({"a1": replace(base, stage_proofs=proofs)})
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_missing_candidate_proofs_never_scored(self):
        """C2: mesure terminée exige preuves non vides/uniques de toute la séquence."""
        base = _success_trace("a1")
        cases: list[AxisTrace] = []

        # absence de preuve LOAD
        cases.append(
            replace(
                base,
                stage_proofs=tuple(p for p in base.stage_proofs if p[0] != MARKER_LOAD),
            )
        )
        # absence de preuve INIT
        cases.append(
            replace(
                base,
                stage_proofs=tuple(p for p in base.stage_proofs if p[0] != MARKER_INIT),
            )
        )
        # absence du marqueur LOAD (donc preuve LOAD absente de la séquence requise)
        stages_no_load = tuple(m for m in base.markers if m != MARKER_LOAD)
        cases.append(
            AxisTrace(
                axis_id="a1",
                markers=stages_no_load,
                stage_proofs=_stage_proofs("a1", stages_no_load),
                harness_ready_proof_ref=_proof("a1", MARKER_HARNESS_READY),
                admission_result=True,
                evaluation_completed=True,
                verdict="PASS",
                budget_expired=False,
                observed_cost=10,
                watchdog_healthy=True,
                teardown_complete=True,
            )
        )
        # référence vide
        cases.append(
            replace(
                base,
                stage_proofs=tuple(
                    (stage, "" if stage == MARKER_LOAD else ref)
                    for stage, ref in base.stage_proofs
                ),
            )
        )
        # doublon de stade
        cases.append(
            replace(
                base,
                stage_proofs=base.stage_proofs
                + ((MARKER_LOAD, _proof("a1", "LOAD-dup")),),
            )
        )
        # preuve HARNESS_READY divergente
        cases.append(
            replace(
                base,
                harness_ready_proof_ref="proof:a1:HARNESS_READY-other",
            )
        )

        for idx, trace in enumerate(cases):
            with self.subTest(case=idx):
                result = _run(
                    axis_ids=("a1",),
                    adapter=RecordingAdapter({"a1": trace}),
                )
                unit = result.units[0]
                self.assertEqual(unit.measurement_state, "NOT_SCORED")
                self.assertEqual(unit.causal_class, "HARNESS_ERROR")
                self.assertIsNone(unit.verdict)


class VerifyV7ExecutionLimit(unittest.TestCase):
    def test_proven_expiration_after_ready_with_budget_and_watchdog(self):
        adapter = RecordingAdapter({"a1": _limit_trace("a1", observed_cost=100)})
        result = _run(axis_ids=("a1",), adapter=adapter, budget=_budget(value=100))
        unit = result.units[0]
        self.assertEqual(unit.measurement_state, "NOT_SCORED")
        self.assertEqual(unit.causal_class, "ARTIFACT_EXECUTION_LIMIT")
        self.assertIsNone(unit.verdict)
        self.assertEqual(result.incidents[0].scope, "AXIS")
        validate_acquisition_result(result)

    def test_expiration_without_harness_ready_is_harness_error(self):
        trace = AxisTrace(
            axis_id="a1",
            markers=(MARKER_PREPARE, MARKER_AUTOTEST, MARKER_TEARDOWN),
            stage_proofs=_stage_proofs("a1", (MARKER_PREPARE, MARKER_AUTOTEST, MARKER_TEARDOWN))
            + ((MARKER_BUDGET_EXPIRED, _proof("a1", MARKER_BUDGET_EXPIRED)),),
            harness_ready_proof_ref=_proof("a1", MARKER_HARNESS_READY),
            admission_result=None,
            evaluation_completed=False,
            verdict=None,
            budget_expired=True,
            observed_cost=100,
            watchdog_healthy=True,
            teardown_complete=True,
            ambiguous=False,
        )
        adapter = RecordingAdapter({"a1": trace})
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_expiration_with_unhealthy_watchdog_is_harness_error(self):
        adapter = RecordingAdapter({
            "a1": replace(_limit_trace("a1"), watchdog_healthy=False),
        })
        result = _run(axis_ids=("a1",), adapter=adapter)
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_expiration_below_qualified_budget_is_harness_error(self):
        adapter = RecordingAdapter({"a1": _limit_trace("a1", observed_cost=50)})
        result = _run(axis_ids=("a1",), adapter=adapter, budget=_budget(value=100))
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_expiration_without_candidate_step_is_harness_error(self):
        markers = (
            MARKER_PREPARE,
            MARKER_AUTOTEST,
            MARKER_HARNESS_READY,
            MARKER_ADMISSION,
            MARKER_TEARDOWN,
        )
        proofs = _stage_proofs("a1", markers) + (
            (MARKER_BUDGET_EXPIRED, _proof("a1", MARKER_BUDGET_EXPIRED)),
        )
        trace = AxisTrace(
            axis_id="a1",
            markers=markers,
            stage_proofs=proofs,
            harness_ready_proof_ref=_proof("a1", MARKER_HARNESS_READY),
            admission_result=True,
            evaluation_completed=False,
            verdict=None,
            budget_expired=True,
            observed_cost=100,
            watchdog_healthy=True,
            teardown_complete=True,
        )
        result = _run(axis_ids=("a1",), adapter=RecordingAdapter({"a1": trace}))
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_limit_without_candidate_proofs_is_harness_error(self):
        """C3: ARTIFACT_EXECUTION_LIMIT exige preuves des étapes candidates présentes."""
        # LOAD présent après admission, mais sans preuve LOAD
        markers = (
            MARKER_PREPARE,
            MARKER_AUTOTEST,
            MARKER_HARNESS_READY,
            MARKER_ADMISSION,
            MARKER_LOAD,
            MARKER_BUDGET_EXPIRED,
            MARKER_TEARDOWN,
        )
        proofs = _stage_proofs(
            "a1",
            (
                MARKER_PREPARE,
                MARKER_AUTOTEST,
                MARKER_HARNESS_READY,
                MARKER_ADMISSION,
                MARKER_BUDGET_EXPIRED,
                MARKER_TEARDOWN,
            ),
        )
        missing_proof = AxisTrace(
            axis_id="a1",
            markers=markers,
            stage_proofs=proofs,
            harness_ready_proof_ref=_proof("a1", MARKER_HARNESS_READY),
            admission_result=True,
            evaluation_completed=False,
            verdict=None,
            budget_expired=True,
            observed_cost=100,
            watchdog_healthy=True,
            teardown_complete=True,
        )
        # BUDGET_EXPIRED avant l'étape candidate
        expired_before = AxisTrace(
            axis_id="a1",
            markers=(
                MARKER_PREPARE,
                MARKER_AUTOTEST,
                MARKER_HARNESS_READY,
                MARKER_ADMISSION,
                MARKER_BUDGET_EXPIRED,
                MARKER_LOAD,
                MARKER_TEARDOWN,
            ),
            stage_proofs=_stage_proofs(
                "a1",
                (
                    MARKER_PREPARE,
                    MARKER_AUTOTEST,
                    MARKER_HARNESS_READY,
                    MARKER_ADMISSION,
                    MARKER_BUDGET_EXPIRED,
                    MARKER_LOAD,
                    MARKER_TEARDOWN,
                ),
            ),
            harness_ready_proof_ref=_proof("a1", MARKER_HARNESS_READY),
            admission_result=True,
            evaluation_completed=False,
            verdict=None,
            budget_expired=True,
            observed_cost=100,
            watchdog_healthy=True,
            teardown_complete=True,
        )
        # Expiration pendant LOAD seulement : INIT/EVAL absents — doit rester LIMIT
        # (contrôle de non-sur-durcissement, via sous-cas positif séparé ci-dessous)
        for trace in (missing_proof, expired_before):
            with self.subTest(markers=trace.markers):
                result = _run(
                    axis_ids=("a1",),
                    adapter=RecordingAdapter({"a1": trace}),
                    budget=_budget(value=100),
                )
                unit = result.units[0]
                self.assertEqual(unit.measurement_state, "NOT_SCORED")
                self.assertEqual(unit.causal_class, "HARNESS_ERROR")
                self.assertNotEqual(unit.causal_class, "ARTIFACT_EXECUTION_LIMIT")

    def test_limit_during_early_candidate_step_does_not_require_full_sequence(self):
        """C3: expiration prouvée pendant LOAD n'exige pas INIT+EVAL."""
        markers = (
            MARKER_PREPARE,
            MARKER_AUTOTEST,
            MARKER_HARNESS_READY,
            MARKER_ADMISSION,
            MARKER_LOAD,
            MARKER_BUDGET_EXPIRED,
            MARKER_TEARDOWN,
        )
        trace = AxisTrace(
            axis_id="a1",
            markers=markers,
            stage_proofs=_stage_proofs("a1", markers),
            harness_ready_proof_ref=_proof("a1", MARKER_HARNESS_READY),
            admission_result=True,
            evaluation_completed=False,
            verdict=None,
            budget_expired=True,
            observed_cost=100,
            watchdog_healthy=True,
            teardown_complete=True,
        )
        result = _run(
            axis_ids=("a1",),
            adapter=RecordingAdapter({"a1": trace}),
            budget=_budget(value=100),
        )
        unit = result.units[0]
        self.assertEqual(unit.measurement_state, "NOT_SCORED")
        self.assertEqual(unit.causal_class, "ARTIFACT_EXECUTION_LIMIT")
        self.assertIsNone(unit.verdict)

    def test_zero_or_blank_budget_rejected_by_contract(self):
        adapter = RecordingAdapter({"a1": _success_trace("a1")})
        with self.assertRaises(VerifyV7ContratInvalide):
            _run(axis_ids=("a1",), adapter=adapter, budget=_budget(value=0))
        with self.assertRaises(VerifyV7ContratInvalide):
            _run(axis_ids=("a1",), adapter=adapter, budget=_budget(unit="  "))
        with self.assertRaises(VerifyV7ContratInvalide):
            _run(axis_ids=("a1",), adapter=adapter, budget=_budget(budget_hash=""))


class VerifyV7ScoredPath(unittest.TestCase):
    def test_successful_evaluation_and_teardown_is_scored_measurement_completed(self):
        adapter = RecordingAdapter({"a1": _success_trace("a1", verdict="PASS")})
        result = _run(axis_ids=("a1",), adapter=adapter)
        unit = result.units[0]
        self.assertEqual(unit.measurement_state, "SCORED")
        self.assertEqual(unit.causal_class, "MEASUREMENT_COMPLETED")
        self.assertEqual(unit.verdict, "PASS")
        self.assertIsNone(unit.incident_id)
        self.assertEqual(result.incidents, ())
        self.assertIsNotNone(unit.trace)
        self.assertIn(MARKER_HARNESS_READY, unit.trace.markers)
        self.assertIn(MARKER_EVAL, unit.trace.markers)
        self.assertIn(MARKER_TEARDOWN, unit.trace.markers)
        validate_acquisition_result(result)

    def test_functional_fail_remains_scored_measurement_completed_not_artifact_invalid(self):
        adapter = RecordingAdapter({"a1": _success_trace("a1", verdict="FAIL")})
        result = _run(axis_ids=("a1",), adapter=adapter)
        unit = result.units[0]
        self.assertEqual(unit.measurement_state, "SCORED")
        self.assertEqual(unit.causal_class, "MEASUREMENT_COMPLETED")
        self.assertEqual(unit.verdict, "FAIL")
        self.assertNotEqual(unit.causal_class, "ARTIFACT_INVALID")
        validate_acquisition_result(result)


class VerifyV7DedupAndIsolation(unittest.TestCase):
    def test_upstream_incident_is_referenced_not_duplicated(self):
        adapter = RecordingAdapter()
        result = _run(provider=_provider_failure(), adapter=adapter)
        self.assertEqual(len(result.incidents), 1)
        ids = {u.incident_id for u in result.units}
        self.assertEqual(ids, {result.incidents[0].incident_id})

    def test_each_executed_axis_has_own_trace_and_harness_ready(self):
        adapter = RecordingAdapter({
            "a1": _success_trace("a1", verdict="PASS"),
            "a2": _success_trace("a2", verdict="FAIL"),
        })
        result = _run(adapter=adapter)
        self.assertEqual(len(adapter.calls), 2)
        self.assertEqual([c.axis_id for c in adapter.calls], ["a1", "a2"])
        self.assertIsNot(adapter.calls[0], adapter.calls[1])
        ready_proofs = set()
        for unit, call in zip(result.units, adapter.calls, strict=True):
            self.assertEqual(unit.axis_id, call.axis_id)
            self.assertIsNotNone(unit.trace)
            self.assertEqual(unit.trace.axis_id, unit.axis_id)
            self.assertIn(MARKER_HARNESS_READY, unit.trace.markers)
            self.assertEqual(call.qualified_budget, _budget())
            self.assertEqual(call.adapter_identity, adapter.identity)
            ready_proofs.add(unit.trace.harness_ready_proof_ref)
        self.assertEqual(len(ready_proofs), 2)

    def test_fake_adapter_proves_prepare_autotest_before_harness_ready(self):
        adapter = RecordingAdapter({"a1": _success_trace("a1")})
        result = _run(axis_ids=("a1",), adapter=adapter)
        markers = result.units[0].trace.markers
        self.assertLess(markers.index(MARKER_PREPARE), markers.index(MARKER_AUTOTEST))
        self.assertLess(markers.index(MARKER_AUTOTEST), markers.index(MARKER_HARNESS_READY))

    def test_reused_harness_ready_proof_between_axes_is_harness_error(self):
        t1 = _success_trace("a1")
        t2 = replace(
            _success_trace("a2"),
            harness_ready_proof_ref=t1.harness_ready_proof_ref,
            stage_proofs=tuple(
                (stage, t1.harness_ready_proof_ref if stage == MARKER_HARNESS_READY else ref)
                for stage, ref in _success_trace("a2").stage_proofs
            ),
        )
        result = _run(adapter=RecordingAdapter({"a1": t1, "a2": t2}))
        self.assertEqual(result.units[0].measurement_state, "SCORED")
        self.assertEqual(result.units[1].causal_class, "HARNESS_ERROR")

    def test_reused_trace_object_between_axes_is_harness_error(self):
        shared = _success_trace("a1")
        result = _run(adapter=RecordingAdapter({"a1": shared, "a2": shared}))
        self.assertEqual(result.units[1].causal_class, "HARNESS_ERROR")

    def test_trace_axis_id_mismatch_is_harness_error(self):
        result = _run(
            axis_ids=("a1",),
            adapter=RecordingAdapter({"a1": _success_trace("other")}),
        )
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

    def test_admission_accept_then_reject_is_harness_contradiction(self):
        adapter = RecordingAdapter({
            "a1": _success_trace("a1"),
            "a2": _reject_trace("a2"),
        })
        result = _run(adapter=adapter)
        self.assertEqual(result.units[0].measurement_state, "SCORED")
        self.assertEqual(result.units[1].causal_class, "HARNESS_ERROR")
        self.assertNotEqual(result.units[1].causal_class, "ARTIFACT_INVALID")
        self.assertTrue(all(i.causal_class != "ARTIFACT_INVALID" for i in result.incidents))


class VerifyV7Determinism(unittest.TestCase):
    def test_same_inputs_same_results_and_incident_ids(self):
        adapter_a = RecordingAdapter()
        adapter_b = RecordingAdapter()
        first = _run(provider=_provider_failure(), adapter=adapter_a)
        second = _run(provider=_provider_failure(), adapter=adapter_b)
        self.assertEqual(first, second)
        self.assertEqual(first.incidents[0].incident_id, second.incidents[0].incident_id)

        ok_a = RecordingAdapter({
            "a1": _success_trace("a1"),
            "a2": _success_trace("a2", verdict="FAIL"),
        })
        ok_b = RecordingAdapter({
            "a1": _success_trace("a1"),
            "a2": _success_trace("a2", verdict="FAIL"),
        })
        scored_a = _run(adapter=ok_a)
        scored_b = _run(adapter=ok_b)
        self.assertEqual(scored_a, scored_b)


class VerifyV7Validators(unittest.TestCase):
    def test_validate_incident_accepts_harness_error_without_positive_proof(self):
        """C2: HARNESS_ERROR sans preuve positive accepté si inventaire + diagnostic."""
        ok = Incident(
            incident_id="acq-1:ACQUISITION:HARNESS_ERROR",
            stage="provider",
            scope="ACQUISITION",
            causal_class="HARNESS_ERROR",
            affected_unit_ids=("a1", "a2"),
            proof_refs=(),
            missing_evidence=("attempt_receipt", "response_or_error"),
            diagnostic_code="EVIDENCE_MISSING",
        )
        validate_incident(ok)

    def test_validate_incident_rejects_harness_error_without_evidence_or_diagnostic(self):
        """C2: refuse HARNESS_ERROR sans base de preuve, sans inventaire ou sans diagnostic."""
        base = dict(
            incident_id="x",
            stage="provider",
            scope="ACQUISITION",
            causal_class="HARNESS_ERROR",
            affected_unit_ids=("a1",),
        )
        cases = (
            # sans preuve et sans missing_evidence
            Incident(**base, proof_refs=(), missing_evidence=(), diagnostic_code="EVIDENCE_MISSING"),
            # sans missing_evidence alors que proof_refs vide
            Incident(**base, proof_refs=(), missing_evidence=(), diagnostic_code="X"),
            # sans diagnostic_code
            Incident(
                **base,
                proof_refs=(),
                missing_evidence=("attempt_receipt",),
                diagnostic_code="",
            ),
            Incident(
                **base,
                proof_refs=("proof:attempt",),
                missing_evidence=(),
                diagnostic_code="",
            ),
            Incident(
                **base,
                proof_refs=("proof:attempt",),
                missing_evidence=(),
                diagnostic_code="   ",
            ),
        )
        for incident in cases:
            with self.subTest(incident=incident):
                with self.assertRaises(VerifyV7ContratInvalide):
                    validate_incident(incident)

    def test_validate_unit_result_rejects_scored_with_invalid_trace_grammar(self):
        """C8: validate_unit_result refuse SCORED avec trace inconnue, dupliquée ou hors grammaire."""
        cases = (
            # marqueur inconnu
            replace(
                _success_trace("a1"),
                markers=_success_trace("a1").markers + ("UNKNOWN_STAGE",),
                stage_proofs=_success_trace("a1").stage_proofs
                + (("UNKNOWN_STAGE", "proof:a1:UNKNOWN_STAGE"),),
            ),
            # marqueur dupliqué
            replace(
                _success_trace("a1"),
                markers=(
                    MARKER_PREPARE,
                    MARKER_AUTOTEST,
                    MARKER_HARNESS_READY,
                    MARKER_ADMISSION,
                    MARKER_LOAD,
                    MARKER_LOAD,
                    MARKER_INIT,
                    MARKER_EVAL,
                    MARKER_TEARDOWN,
                ),
            ),
            # hors grammaire (INIT avant LOAD)
            replace(
                _success_trace("a1"),
                markers=(
                    MARKER_PREPARE,
                    MARKER_AUTOTEST,
                    MARKER_HARNESS_READY,
                    MARKER_ADMISSION,
                    MARKER_INIT,
                    MARKER_LOAD,
                    MARKER_EVAL,
                    MARKER_TEARDOWN,
                ),
            ),
        )
        for idx, trace in enumerate(cases):
            with self.subTest(case=idx):
                unit = UnitResult(
                    axis_id="a1",
                    measurement_state="SCORED",
                    causal_class="MEASUREMENT_COMPLETED",
                    verdict="PASS",
                    incident_id=None,
                    trace=trace,
                )
                with self.assertRaises(VerifyV7ContratInvalide):
                    validate_unit_result(unit)

    def test_adapter_exception_is_structured_harness_error_without_raw_leak(self):
        """C9: exception identity/execute_axis => HARNESS_ERROR structuré sans texte brut."""
        secret = "adapter-boom:SECRET-LEAK-XYZ"
        for mode in ("execute", "identity"):
            with self.subTest(mode=mode):
                adapter = RecordingAdapter({"a1": _success_trace("a1")})
                if mode == "execute":
                    adapter.raise_on.add("a1")
                else:
                    adapter.identity_raises = True
                result = _run(axis_ids=("a1",), adapter=adapter)
                unit = result.units[0]
                incident = result.incidents[0]
                self.assertEqual(unit.measurement_state, "NOT_SCORED")
                self.assertEqual(unit.causal_class, "HARNESS_ERROR")
                self.assertEqual(incident.scope, "AXIS")
                self.assertEqual(incident.proof_refs, ())
                self.assertNotEqual(incident.missing_evidence, ())
                self.assertTrue(incident.diagnostic_code.strip())
                self.assertNotIn("proof:adapter-exception", incident.proof_refs)
                self.assertNotIn("proof:missing", incident.proof_refs)
                blob = repr(result)
                self.assertNotIn(secret, blob)
                self.assertNotIn("identity-boom", blob)
                self.assertNotIn("adapter-boom", blob)
                validate_acquisition_result(result)

    def test_validate_incident_rejects_incoherence(self):
        bad = Incident(
            incident_id="x",
            stage="provider",
            scope="NOT_A_SCOPE",
            causal_class="PROVIDER_FAILURE",
            affected_unit_ids=("a1",),
            proof_refs=("p",),
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_incident(bad)

    def test_axis_provider_failure_forbidden(self):
        bad = Incident(
            incident_id="x",
            stage="provider",
            scope="AXIS",
            causal_class="PROVIDER_FAILURE",
            affected_unit_ids=("a1",),
            proof_refs=("p",),
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_incident(bad)

    def test_empty_incident_refs_forbidden(self):
        bad = Incident(
            incident_id="x",
            stage="provider",
            scope="ACQUISITION",
            causal_class="PROVIDER_FAILURE",
            affected_unit_ids=("a1",),
            proof_refs=("  ",),
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_incident(bad)

    def test_empty_incident_proof_refs_tuple_forbidden(self):
        """C6: proof_refs=() et références vides/espaces sont rejetés."""
        for proof_refs in ((), ("",), ("   ",), ("\t",), ("ok", "")):
            with self.subTest(proof_refs=proof_refs):
                bad = Incident(
                    incident_id="x",
                    stage="provider",
                    scope="ACQUISITION",
                    causal_class="PROVIDER_FAILURE",
                    affected_unit_ids=("a1",),
                    proof_refs=proof_refs,
                )
                with self.assertRaises(VerifyV7ContratInvalide):
                    validate_incident(bad)

    def test_not_scored_forbids_verdict(self):
        bad = UnitResult(
            axis_id="a1",
            measurement_state="NOT_SCORED",
            causal_class="PROVIDER_FAILURE",
            verdict="FAIL",
            incident_id="inc-1",
            trace=None,
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_unit_result(bad)

    def test_scored_forbids_non_measurement_completed(self):
        bad = UnitResult(
            axis_id="a1",
            measurement_state="SCORED",
            causal_class="ARTIFACT_INVALID",
            verdict="PASS",
            incident_id=None,
            trace=_success_trace("a1"),
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_unit_result(bad)

    def test_scored_requires_verdict(self):
        bad = UnitResult(
            axis_id="a1",
            measurement_state="SCORED",
            causal_class="MEASUREMENT_COMPLETED",
            verdict=None,
            incident_id=None,
            trace=_success_trace("a1"),
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_unit_result(bad)

    def test_scored_without_trace_forbidden(self):
        bad = UnitResult(
            axis_id="a1",
            measurement_state="SCORED",
            causal_class="MEASUREMENT_COMPLETED",
            verdict="PASS",
            incident_id=None,
            trace=None,
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_unit_result(bad)

    def test_proofless_scored_trace_rejected(self):
        """C6: SCORED exige la preuve intégrale de la séquence, pas de simples marqueurs."""
        markers = (
            MARKER_PREPARE,
            MARKER_AUTOTEST,
            MARKER_HARNESS_READY,
            MARKER_ADMISSION,
            MARKER_LOAD,
            MARKER_INIT,
            MARKER_EVAL,
            MARKER_TEARDOWN,
        )
        cases = (
            # marqueurs sans aucune preuve de stade
            AxisTrace(
                axis_id="a1",
                markers=markers,
                stage_proofs=(),
                harness_ready_proof_ref=_proof("a1", MARKER_HARNESS_READY),
                admission_result=True,
                evaluation_completed=True,
                verdict="PASS",
                budget_expired=False,
                observed_cost=10,
                watchdog_healthy=True,
                teardown_complete=True,
            ),
            # preuves partielles (EVAL manquant)
            replace(
                _success_trace("a1"),
                stage_proofs=tuple(
                    p for p in _success_trace("a1").stage_proofs if p[0] != MARKER_EVAL
                ),
            ),
            # axis_id divergent
            replace(_success_trace("a1"), axis_id="other"),
            # admission non positive
            replace(_success_trace("a1"), admission_result=False),
            # évaluation non terminée
            replace(_success_trace("a1"), evaluation_completed=False),
            # watchdog non sain
            replace(_success_trace("a1"), watchdog_healthy=False),
            # teardown incomplet
            replace(_success_trace("a1"), teardown_complete=False),
            # HARNESS_READY divergent
            replace(
                _success_trace("a1"),
                harness_ready_proof_ref="proof:a1:HARNESS_READY-other",
            ),
        )
        for idx, trace in enumerate(cases):
            with self.subTest(case=idx):
                unit = UnitResult(
                    axis_id="a1",
                    measurement_state="SCORED",
                    causal_class="MEASUREMENT_COMPLETED",
                    verdict="PASS",
                    incident_id=None,
                    trace=trace,
                )
                with self.assertRaises(VerifyV7ContratInvalide):
                    validate_unit_result(unit)
                bad = AcquisitionResult(
                    acquisition_id="acq-1",
                    units=(unit,),
                    incidents=(),
                    adapter_call_count=1,
                )
                with self.assertRaises(VerifyV7ContratInvalide):
                    validate_acquisition_result(bad)

    def test_acquisition_incident_must_cover_exactly_all_unit_ids(self):
        """D2: incident ACQUISITION qui omet une unit_id => VerifyV7ContratInvalide."""
        incident = Incident(
            incident_id="acq-1:ACQUISITION:PROVIDER_FAILURE",
            stage="provider",
            scope="ACQUISITION",
            causal_class="PROVIDER_FAILURE",
            affected_unit_ids=("a1",),
            proof_refs=("proof:attempt", "proof:error"),
        )
        unit_a1 = UnitResult(
            axis_id="a1",
            measurement_state="NOT_SCORED",
            causal_class="PROVIDER_FAILURE",
            verdict=None,
            incident_id=incident.incident_id,
            trace=None,
        )
        unit_a2 = UnitResult(
            axis_id="a2",
            measurement_state="SCORED",
            causal_class="MEASUREMENT_COMPLETED",
            verdict="PASS",
            incident_id=None,
            trace=_success_trace("a2"),
        )
        bad = AcquisitionResult(
            acquisition_id="acq-1",
            units=(unit_a1, unit_a2),
            incidents=(incident,),
            adapter_call_count=1,
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_acquisition_result(bad)

    def test_validate_acquisition_result_rejects_duplicated_upstream_incident(self):
        incident = Incident(
            incident_id="acq-1:ACQUISITION:PROVIDER_FAILURE",
            stage="provider",
            scope="ACQUISITION",
            causal_class="PROVIDER_FAILURE",
            affected_unit_ids=("a1", "a2"),
            proof_refs=("proof:attempt", "proof:error"),
        )
        duplicate = replace(incident, incident_id="acq-1:ACQUISITION:PROVIDER_FAILURE:dup")
        unit = UnitResult(
            axis_id="a1",
            measurement_state="NOT_SCORED",
            causal_class="PROVIDER_FAILURE",
            verdict=None,
            incident_id=incident.incident_id,
            trace=None,
        )
        unit2 = UnitResult(
            axis_id="a2",
            measurement_state="NOT_SCORED",
            causal_class="PROVIDER_FAILURE",
            verdict=None,
            incident_id=incident.incident_id,
            trace=None,
        )
        bad = AcquisitionResult(
            acquisition_id="acq-1",
            units=(unit, unit2),
            incidents=(incident, duplicate),
            adapter_call_count=0,
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_acquisition_result(bad)

    def test_affected_unit_must_reference_incident(self):
        incident = Incident(
            incident_id="inc-1",
            stage="provider",
            scope="ACQUISITION",
            causal_class="PROVIDER_FAILURE",
            affected_unit_ids=("a1", "a2"),
            proof_refs=("proof:attempt",),
        )
        unit_ok = UnitResult(
            axis_id="a1",
            measurement_state="NOT_SCORED",
            causal_class="PROVIDER_FAILURE",
            verdict=None,
            incident_id="inc-1",
            trace=None,
        )
        unit_bad = UnitResult(
            axis_id="a2",
            measurement_state="NOT_SCORED",
            causal_class="PROVIDER_FAILURE",
            verdict=None,
            incident_id="other",
            trace=None,
        )
        other = Incident(
            incident_id="other",
            stage="provider",
            scope="ACQUISITION",
            causal_class="HARNESS_ERROR",
            affected_unit_ids=("a2",),
            proof_refs=("proof:x",),
        )
        bad = AcquisitionResult(
            acquisition_id="acq-1",
            units=(unit_ok, unit_bad),
            incidents=(incident, other),
            adapter_call_count=0,
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_acquisition_result(bad)

    def test_scored_without_adapter_call_forbidden(self):
        unit = UnitResult(
            axis_id="a1",
            measurement_state="SCORED",
            causal_class="MEASUREMENT_COMPLETED",
            verdict="PASS",
            incident_id=None,
            trace=_success_trace("a1"),
        )
        bad = AcquisitionResult(
            acquisition_id="acq-1",
            units=(unit,),
            incidents=(),
            adapter_call_count=0,
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_acquisition_result(bad)

    def test_validators_accept_consistent_results(self):
        result = _run(provider=_provider_failure(), adapter=RecordingAdapter())
        validate_incident(result.incidents[0])
        for unit in result.units:
            validate_unit_result(unit)
        validate_acquisition_result(result)

    def test_results_are_immutable(self):
        result = _run(axis_ids=("a1",), adapter=RecordingAdapter({"a1": _success_trace("a1")}))
        with self.assertRaises(Exception):
            result.units[0].verdict = "MUTATED"  # type: ignore[misc]
        copied = copy.deepcopy(result)
        self.assertEqual(result, copied)


class VerifyV7PublicSurface(unittest.TestCase):
    def test_public_symbols_and_protocol(self):
        self.assertTrue(callable(verify_acquisition))
        self.assertTrue(callable(validate_incident))
        self.assertTrue(callable(validate_unit_result))
        self.assertTrue(callable(validate_acquisition_result))
        adapter = RecordingAdapter({"a1": _success_trace("a1")})
        self.assertIsInstance(adapter, ModalityAdapter)


if __name__ == "__main__":
    unittest.main()
