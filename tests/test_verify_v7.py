"""Régressions publiques du noyau verify-v7 après migration open_axis."""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace


RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

from verify_v7 import (  # noqa: E402
    AcquisitionResult,
    AxisSession,
    HarnessReadyAttestation,
    Incident,
    ModalityAdapter,
    MonotonicCounter,
    VerifyV7ContratInvalide,
    validate_acquisition_result,
    validate_incident,
    validate_unit_result,
    verify_acquisition,
)
from verify_v7_html import HtmlModalityAdapter  # noqa: E402

from tests.test_verify_v7_html import (  # noqa: E402
    ARTIFACT,
    EXPECTATIONS,
    IDENTITY,
    FakeHtmlRuntimePort,
    _budget,
    _digest,
    _provider_ok,
)


class VerifyV7PublicContract(unittest.TestCase):
    def _run(
        self,
        *,
        port: FakeHtmlRuntimePort | None = None,
        readings: tuple[object, ...] = (10, 13),
        provider=None,
        axis_ids: tuple[str, ...] = ("pentagone-api",),
    ) -> AcquisitionResult:
        from verify_v7 import MonotonicCounter

        values = iter(readings)
        runtime_port = port if port is not None else FakeHtmlRuntimePort([])
        return verify_acquisition(
            acquisition_id="acq-core",
            axis_ids=axis_ids,
            provider_evidence=provider if provider is not None else _provider_ok(),
            artifact=ARTIFACT,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=lambda: next(values),
            ),
            adapter=HtmlModalityAdapter(identity=IDENTITY, runtime_port=runtime_port),
        )

    def test_public_entry_and_protocols_exclude_execute_axis(self):
        self.assertEqual(
            tuple(inspect.signature(verify_acquisition).parameters),
            (
                "acquisition_id",
                "axis_ids",
                "provider_evidence",
                "artifact",
                "qualified_budget",
                "harness_expectations",
                "counter",
                "adapter",
            ),
        )
        self.assertNotIn("execute_axis", ModalityAdapter.__dict__)
        self.assertIn("open_axis", ModalityAdapter.__dict__)
        self.assertIn("prepare", AxisSession.__dict__)
        self.assertIn("inspect_and_execute", AxisSession.__dict__)
        self.assertIn("teardown", AxisSession.__dict__)
        self.assertTrue(callable(HarnessReadyAttestation))
        self.assertTrue(callable(validate_unit_result))
        self.assertTrue(callable(validate_incident))
        self.assertTrue(callable(validate_acquisition_result))

    def test_provider_states_stop_before_adapter_access(self):
        incomplete = replace(_provider_ok(), payload_bound=False)
        failed = replace(_provider_ok(), artifact_admissible=False)
        for provider, causal_class in (
            (incomplete, "HARNESS_ERROR"),
            (failed, "PROVIDER_FAILURE"),
        ):
            with self.subTest(causal_class=causal_class):
                port = FakeHtmlRuntimePort([])
                result = self._run(port=port, readings=(), provider=provider)
                self.assertEqual(result.adapter_call_count, 0)
                self.assertEqual(port.requests, [])
                self.assertEqual(result.units[0].measurement_state, "NOT_SCORED")
                self.assertEqual(result.units[0].causal_class, causal_class)
                validate_incident(result.incidents[0])
                validate_unit_result(result.units[0])
                validate_acquisition_result(result)

    def test_results_are_frozen_redacted_and_mutually_coherent(self):
        result = self._run(axis_ids=("pentagone-api", "pentagone-determinisme"), readings=(10, 13, 20, 23))
        for unit in result.units:
            validate_unit_result(unit)
        for incident in result.incidents:
            validate_incident(incident)
        validate_acquisition_result(result)
        self.assertNotIn(ARTIFACT.content.decode(), repr(result))
        self.assertNotIn("candidate_bytes", repr(result))
        with self.assertRaises(Exception):
            result.units[0].verdict = "MUTATED"  # type: ignore[misc]

        bad_unit = replace(
            result.units[0],
            context_digest=_digest("wrong-unit-context"),
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_unit_result(bad_unit)
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_acquisition_result(
                replace(result, units=(bad_unit, result.units[1]))
            )

    def test_caller_strings_are_strict_and_adapter_is_never_opened(self):
        from verify_v7 import MonotonicCounter

        for acquisition_id in ("", " acq-core", "acq-core ", 1):
            with self.subTest(acquisition_id=acquisition_id):
                port = FakeHtmlRuntimePort([])
                values = iter((10, 13))
                with self.assertRaises(VerifyV7ContratInvalide):
                    verify_acquisition(
                        acquisition_id=acquisition_id,  # type: ignore[arg-type]
                        axis_ids=("pentagone-api",),
                        provider_evidence=_provider_ok(),
                        artifact=ARTIFACT,
                        qualified_budget=_budget(),
                        harness_expectations=EXPECTATIONS,
                        counter=MonotonicCounter(
                            source_id="fixture-counter",
                            unit="fixture-ticks",
                            rule="monotonic-end-minus-start/v1",
                            read=lambda: next(values),
                        ),
                        adapter=HtmlModalityAdapter(
                            identity=IDENTITY,
                            runtime_port=port,
                        ),
                    )
                self.assertEqual(port.requests, [])


class VerifyV7CorrectiveV2PublicBehavior(unittest.TestCase):
    def test_c2_cross_axis_network_attempt_fails_api_only(self):
        port = FakeHtmlRuntimePort([])
        port.execution_mutations["pentagone-determinisme"] = lambda value: replace(
            value,
            network_attempted=True,
        )
        readings = iter((10, 13, 20, 23))
        result = verify_acquisition(
            acquisition_id="acq-c2",
            axis_ids=("pentagone-api", "pentagone-determinisme"),
            provider_evidence=_provider_ok(),
            artifact=ARTIFACT,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=lambda: next(readings),
            ),
            adapter=HtmlModalityAdapter(identity=IDENTITY, runtime_port=port),
        )

        self.assertEqual(
            tuple(
                (unit.measurement_state, unit.causal_class, unit.verdict)
                for unit in result.units
            ),
            (
                ("SCORED", "MEASUREMENT_COMPLETED", "FAIL"),
                ("SCORED", "MEASUREMENT_COMPLETED", "PASS"),
            ),
        )
        validate_acquisition_result(result)

    def test_c3_counter_provenance_binds_context_and_markers(self):
        readings = iter((10, 13))
        result = verify_acquisition(
            acquisition_id="acq-c3",
            axis_ids=("pentagone-api",),
            provider_evidence=_provider_ok(),
            artifact=ARTIFACT,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=lambda: next(readings),
            ),
            adapter=HtmlModalityAdapter(
                identity=IDENTITY,
                runtime_port=FakeHtmlRuntimePort([]),
            ),
        )
        context = result.verification_context
        trace = result.units[0].trace
        self.assertIsNotNone(trace)
        assert trace is not None
        self.assertEqual(
            (
                trace.start_marker.source_id,
                trace.start_marker.unit,
                trace.start_marker.rule,
                trace.end_marker.source_id,
                trace.end_marker.unit,
                trace.end_marker.rule,
                trace.observed_cost,
            ),
            (
                context.counter_source_id,
                context.counter_unit,
                context.counter_rule,
                context.counter_source_id,
                context.counter_unit,
                context.counter_rule,
                3,
            ),
        )

        forged_context = replace(context, counter_source_id="forged-counter")
        canonical = json.dumps(
            asdict(forged_context),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        forged_digest = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
        forged_units = tuple(
            replace(
                unit,
                context_digest=forged_digest,
                trace=replace(unit.trace, context_digest=forged_digest),
            )
            for unit in result.units
        )
        forged = replace(
            result,
            verification_context=forged_context,
            context_digest=forged_digest,
            units=forged_units,
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_acquisition_result(forged)

    def test_c4_observed_cost_above_budget_is_execution_limit(self):
        readings = iter((10, 18))
        result = verify_acquisition(
            acquisition_id="acq-c4-over",
            axis_ids=("pentagone-api",),
            provider_evidence=_provider_ok(),
            artifact=ARTIFACT,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=lambda: next(readings),
            ),
            adapter=HtmlModalityAdapter(
                identity=IDENTITY,
                runtime_port=FakeHtmlRuntimePort([]),
            ),
        )
        self.assertEqual(
            (
                result.units[0].measurement_state,
                result.units[0].causal_class,
                result.units[0].verdict,
            ),
            ("NOT_SCORED", "ARTIFACT_EXECUTION_LIMIT", None),
        )
        self.assertEqual(result.units[0].trace.observed_cost, 8)
        self.assertEqual(result.units[0].incident_id, result.incidents[0].incident_id)
        validate_acquisition_result(result)

        readings = iter((10, 17))
        at_budget = verify_acquisition(
            acquisition_id="acq-c4-equal",
            axis_ids=("pentagone-api",),
            provider_evidence=_provider_ok(),
            artifact=ARTIFACT,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=lambda: next(readings),
            ),
            adapter=HtmlModalityAdapter(
                identity=IDENTITY,
                runtime_port=FakeHtmlRuntimePort([]),
            ),
        )
        self.assertEqual(
            (
                at_budget.units[0].measurement_state,
                at_budget.units[0].causal_class,
                at_budget.units[0].verdict,
            ),
            ("SCORED", "MEASUREMENT_COMPLETED", "PASS"),
        )
        validate_acquisition_result(at_budget)

    def test_c5_validate_incident_rejects_non_allowlisted_diagnostics(self):
        port = FakeHtmlRuntimePort([])
        port.raise_during_candidate.add("pentagone-api")
        readings = iter((10,))
        result = verify_acquisition(
            acquisition_id="acq-c5",
            axis_ids=("pentagone-api",),
            provider_evidence=_provider_ok(),
            artifact=ARTIFACT,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=lambda: next(readings),
            ),
            adapter=HtmlModalityAdapter(identity=IDENTITY, runtime_port=port),
        )
        incident = result.incidents[0]
        validate_incident(incident)
        self.assertNotIn("raw-runtime-secret-url-body-path", repr(result))

        for proof_ref in (
            "https://secret.example/body?token=SECRET",
            '{"body":"raw"}',
            "/private/tmp/runtime.log",
            "../runtime.log",
            "token=SECRET",
            "RuntimeError('raw')",
            "raw object repr runtime/path",
        ):
            with self.subTest(proof_ref=proof_ref):
                with self.assertRaises(VerifyV7ContratInvalide):
                    validate_incident(replace(incident, proof_refs=(proof_ref,)))

        for proof_ref in (
            _digest("diagnostic-proof"),
            "proof:artifact-bound:stage_1",
        ):
            with self.subTest(allowed_proof_ref=proof_ref):
                validate_incident(replace(incident, proof_refs=(proof_ref,)))

    def test_c6_validate_acquisition_result_rejects_incident_unit_incoherence(self):
        readings = iter((10, 13))
        result = verify_acquisition(
            acquisition_id="acq-c6",
            axis_ids=("pentagone-api",),
            provider_evidence=_provider_ok(),
            artifact=ARTIFACT,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=lambda: next(readings),
            ),
            adapter=HtmlModalityAdapter(
                identity=IDENTITY,
                runtime_port=FakeHtmlRuntimePort([]),
            ),
        )
        forged_incident = Incident(
            incident_id="acq-c6:AXIS:HARNESS_ERROR:pentagone-api",
            stage="harness",
            scope="AXIS",
            causal_class="HARNESS_ERROR",
            affected_unit_ids=("pentagone-api",),
            proof_refs=(),
            context_digest=result.context_digest,
            missing_evidence=("structured_observation",),
            diagnostic_code="EVIDENCE_MISSING",
        )
        with self.assertRaises(VerifyV7ContratInvalide):
            validate_acquisition_result(
                replace(result, incidents=(forged_incident,))
            )


class VerifyV7C2SessionIdentityPublicBehavior(unittest.TestCase):
    def test_same_axis_session_object_is_rejected_on_second_use(self):
        port = FakeHtmlRuntimePort([])
        real_adapter = HtmlModalityAdapter(identity=IDENTITY, runtime_port=port)
        active_session: list[AxisSession] = []
        shared_session = SimpleNamespace(
            prepare=lambda: active_session[0].prepare(),
            inspect_and_execute=lambda permit: active_session[0].inspect_and_execute(
                permit
            ),
            teardown=lambda: active_session[0].teardown(),
        )

        def open_axis(request):
            active_session[:] = [real_adapter.open_axis(request)]
            return shared_session

        readings = iter((10, 13))
        result = verify_acquisition(
            acquisition_id="acq-c2-session-reuse",
            axis_ids=("pentagone-api", "pentagone-determinisme"),
            provider_evidence=_provider_ok(),
            artifact=ARTIFACT,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=lambda: next(readings),
            ),
            adapter=SimpleNamespace(identity=IDENTITY, open_axis=open_axis),
        )

        self.assertEqual(
            (
                result.units[1].axis_id,
                result.units[1].measurement_state,
                result.units[1].causal_class,
                result.units[1].verdict,
            ),
            ("pentagone-determinisme", "NOT_SCORED", "HARNESS_ERROR", None),
        )
        self.assertEqual(len(result.incidents), 1)
        self.assertEqual(
            (
                result.incidents[0].causal_class,
                result.incidents[0].diagnostic_code,
                result.incidents[0].missing_evidence,
            ),
            (
                "HARNESS_ERROR",
                "ATTESTATION_BINDING_MISMATCH",
                ("axis_session_unique",),
            ),
        )
        self.assertEqual(result.units[1].incident_id, result.incidents[0].incident_id)
        validate_acquisition_result(result)

    def test_distinct_axis_session_objects_are_order_independent(self):
        for axis_ids in (
            ("pentagone-api", "pentagone-determinisme"),
            ("pentagone-determinisme", "pentagone-api"),
        ):
            with self.subTest(axis_ids=axis_ids):
                port = FakeHtmlRuntimePort([])
                real_adapter = HtmlModalityAdapter(identity=IDENTITY, runtime_port=port)
                opened_sessions: list[AxisSession] = []

                def open_axis(request):
                    session = real_adapter.open_axis(request)
                    opened_sessions.append(session)
                    return session

                readings = iter((10, 13, 20, 23))
                result = verify_acquisition(
                    acquisition_id="acq-c2-distinct-sessions",
                    axis_ids=axis_ids,
                    provider_evidence=_provider_ok(),
                    artifact=ARTIFACT,
                    qualified_budget=_budget(),
                    harness_expectations=EXPECTATIONS,
                    counter=MonotonicCounter(
                        source_id="fixture-counter",
                        unit="fixture-ticks",
                        rule="monotonic-end-minus-start/v1",
                        read=lambda: next(readings),
                    ),
                    adapter=SimpleNamespace(identity=IDENTITY, open_axis=open_axis),
                )

                self.assertEqual(len(opened_sessions), 2)
                self.assertIsNot(opened_sessions[0], opened_sessions[1])
                self.assertEqual(
                    tuple(
                        (
                            unit.axis_id,
                            unit.measurement_state,
                            unit.causal_class,
                            unit.verdict,
                        )
                        for unit in result.units
                    ),
                    tuple(
                        (axis_id, "SCORED", "MEASUREMENT_COMPLETED", "PASS")
                        for axis_id in axis_ids
                    ),
                )
                validate_acquisition_result(result)


if __name__ == "__main__":
    unittest.main()
