"""Preuves publiques de la modalité HTML verify-v7, sans runtime réel."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Callable


RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

from verify_v7 import (  # noqa: E402
    MARKER_ADMISSION,
    MARKER_AUTOTEST,
    MARKER_EVAL,
    MARKER_HARNESS_READY,
    MARKER_INIT,
    MARKER_LOAD,
    MARKER_PREPARE,
    MARKER_TEARDOWN,
    AdapterIdentity,
    Artifact,
    EnvironmentManifest,
    HarnessExpectations,
    HarnessPreparation,
    MonotonicCounter,
    ProviderEvidence,
    QualifiedBudget,
    RuntimeIdentity,
    TeardownObservation,
    VerifyV7ContratInvalide,
    validate_acquisition_result,
    validate_incident,
    validate_unit_result,
    verify_acquisition,
)
from verify_v7_html import (  # noqa: E402
    CandidateExecutionObservation,
    HtmlModalityAdapter,
)


def _digest(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


IDENTITY = AdapterIdentity(
    adapter_id="html-task-v5",
    adapter_version="test-version",
    adapter_hash=_digest("adapter"),
)
ENVIRONMENT = EnvironmentManifest(
    schema_version="verify-v7-environment/v1",
    python_runtime=RuntimeIdentity("cpython", "3.13", _digest("python")),
    operating_system=RuntimeIdentity("macos", "15", _digest("os")),
    modality_runtime=RuntimeIdentity("fake-html", "1", _digest("runtime")),
    dependencies=(RuntimeIdentity("stdlib", "3.13", _digest("stdlib")),),
    influential_configuration=(("network-policy", _digest("deny")),),
)
EXPECTATIONS = HarnessExpectations(
    adapter_identity=IDENTITY,
    environment_manifest=ENVIRONMENT,
    core_digest=_digest("verify-v7-core"),
)
CANDIDATE_BYTES = b"<html><canvas></canvas><script>function simulate(t){return [0,0]}</script></html>"
ARTIFACT = Artifact(
    content=CANDIDATE_BYTES,
    digest=_digest(CANDIDATE_BYTES),
    proof_ref="proof:artifact-bound",
)


def _budget() -> QualifiedBudget:
    return QualifiedBudget(
        value=7,
        unit="fixture-ticks",
        budget_hash=_digest("budget-lock"),
        scope="artifact",
        measurement_rule="monotonic-end-minus-start/v1",
    )


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


class FakeAxisRuntime:
    def __init__(self, request, events: list[str], port: "FakeHtmlRuntimePort") -> None:
        self.request = request
        self.events = events
        self.port = port
        self.session_id = f"session:{request.axis_id}"

    def prepare(self) -> HarnessPreparation:
        self.events.extend((MARKER_PREPARE, MARKER_AUTOTEST))
        preparation = HarnessPreparation(
            session_id=self.session_id,
            axis_id=self.request.axis_id,
            adapter_identity=self.request.adapter_identity,
            environment_digest=self.request.environment_digest,
            budget_digest=self.request.budget_digest,
            core_digest=self.request.core_digest,
            artifact_digest=self.request.artifact_digest,
            artifact_proof_ref=self.request.artifact_proof_ref,
            bootstrap_success=True,
            autotest_success=True,
            stage_proofs=(
                (MARKER_PREPARE, f"proof:{self.request.axis_id}:prepare"),
                (MARKER_AUTOTEST, f"proof:{self.request.axis_id}:autotest"),
            ),
            watchdog_healthy=True,
            ambiguous=False,
        )
        mutation = self.port.preparation_mutations.get(self.request.axis_id)
        return mutation(preparation) if mutation is not None else preparation

    def execute_candidate(self, permit) -> CandidateExecutionObservation:
        self.events.append("CANDIDATE_BYTES")
        self.asserted_candidate = permit.candidate_bytes
        if self.request.axis_id in self.port.raise_during_candidate:
            raise RuntimeError("raw-runtime-secret-url-body-path")
        self.events.extend((MARKER_LOAD, MARKER_INIT, MARKER_EVAL))
        observation = CandidateExecutionObservation(
            session_id=self.session_id,
            axis_id=self.request.axis_id,
            ready_receipt_ref=permit.ready_attestation.receipt_ref,
            artifact_digest=self.request.artifact_digest,
            artifact_proof_ref=self.request.artifact_proof_ref,
            budget_digest=self.request.budget_digest,
            environment_digest=self.request.environment_digest,
            stage_proofs=(
                (MARKER_LOAD, f"proof:{self.request.axis_id}:load"),
                (MARKER_INIT, f"proof:{self.request.axis_id}:init"),
                (MARKER_EVAL, f"proof:{self.request.axis_id}:eval"),
            ),
            evaluation_completed=True,
            verdict="PASS",
            budget_expired=False,
            watchdog_healthy=True,
            ambiguous=False,
            network_attempted=False,
            confinement_healthy=True,
            confinement_ambiguous=False,
        )
        mutation = self.port.execution_mutations.get(self.request.axis_id)
        return mutation(observation) if mutation is not None else observation

    def teardown(self) -> TeardownObservation:
        self.events.append(MARKER_TEARDOWN)
        if self.request.axis_id in self.port.raise_during_teardown:
            raise RuntimeError("raw-teardown-secret-url-body-path")
        observation = TeardownObservation(
            session_id=self.session_id,
            axis_id=self.request.axis_id,
            proof_ref=f"proof:{self.request.axis_id}:teardown",
            complete=True,
            watchdog_healthy=True,
            ambiguous=False,
        )
        mutation = self.port.teardown_mutations.get(self.request.axis_id)
        return mutation(observation) if mutation is not None else observation


class FakeHtmlRuntimePort:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.requests = []
        self.runtimes: list[FakeAxisRuntime] = []
        self.preparation_mutations: dict[
            str, Callable[[HarnessPreparation], HarnessPreparation | object]
        ] = {}
        self.execution_mutations: dict[
            str,
            Callable[
                [CandidateExecutionObservation],
                CandidateExecutionObservation | object,
            ],
        ] = {}
        self.teardown_mutations: dict[
            str, Callable[[TeardownObservation], TeardownObservation | object]
        ] = {}
        self.raise_during_candidate: set[str] = set()
        self.raise_during_teardown: set[str] = set()
        self.reused_runtime: FakeAxisRuntime | None = None
        self.reuse_first_runtime = False

    def open_axis(self, request) -> FakeAxisRuntime:
        self.events.append("OPEN_AXIS")
        self.requests.append(request)
        self.assert_no_candidate(request)
        if self.reused_runtime is not None:
            return self.reused_runtime
        if self.reuse_first_runtime and self.runtimes:
            return self.runtimes[0]
        runtime = FakeAxisRuntime(request, self.events, self)
        self.runtimes.append(runtime)
        return runtime

    @staticmethod
    def assert_no_candidate(request) -> None:
        if hasattr(request, "candidate_bytes") or hasattr(request, "content"):
            raise AssertionError("octets candidats exposés avant READY")


class HtmlAdapterPublicBehavior(unittest.TestCase):
    def _execute(
        self,
        *,
        port: FakeHtmlRuntimePort,
        readings: tuple[object, ...],
        provider_evidence: ProviderEvidence | None = None,
        artifact: Artifact = ARTIFACT,
        budget: QualifiedBudget | None = None,
        expectations: HarnessExpectations = EXPECTATIONS,
        counter_overrides: dict[str, object] | None = None,
        axis_ids: tuple[str, ...] = ("pentagone-api",),
    ):
        values = iter(readings)
        counter_values: dict[str, object] = {
            "source_id": "fixture-counter",
            "unit": "fixture-ticks",
            "rule": "monotonic-end-minus-start/v1",
            "read": lambda: next(values),
        }
        counter_values.update(counter_overrides or {})
        return verify_acquisition(
            acquisition_id="acq-html",
            axis_ids=axis_ids,
            provider_evidence=(
                provider_evidence if provider_evidence is not None else _provider_ok()
            ),
            artifact=artifact,
            qualified_budget=budget if budget is not None else _budget(),
            harness_expectations=expectations,
            counter=MonotonicCounter(**counter_values),  # type: ignore[arg-type]
            adapter=HtmlModalityAdapter(identity=IDENTITY, runtime_port=port),
        )

    def _run_candidate(
        self,
        candidate_bytes: bytes,
        *,
        readings: tuple[int, ...] = (10,),
        axis_ids: tuple[str, ...] = ("pentagone-api", "pentagone-determinisme"),
    ):
        events: list[str] = []
        values = iter(readings)

        def read() -> int:
            value = next(values)
            events.append(f"COUNTER:{value}")
            return value

        port = FakeHtmlRuntimePort(events)
        artifact = Artifact(
            content=candidate_bytes,
            digest=_digest(candidate_bytes),
            proof_ref="proof:artifact-bound",
        )
        result = verify_acquisition(
            acquisition_id="acq-html",
            axis_ids=axis_ids,
            provider_evidence=_provider_ok(),
            artifact=artifact,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=read,
            ),
            adapter=HtmlModalityAdapter(identity=IDENTITY, runtime_port=port),
        )
        return result, port, events

    def test_admissible_html_is_scored_after_bound_ready_and_start_marker(self):
        events: list[str] = []
        readings = iter((10, 13))

        def read() -> int:
            value = next(readings)
            events.append(f"COUNTER:{value}")
            return value

        port = FakeHtmlRuntimePort(events)
        adapter = HtmlModalityAdapter(identity=IDENTITY, runtime_port=port)

        result = verify_acquisition(
            acquisition_id="acq-html",
            axis_ids=("pentagone-api",),
            provider_evidence=_provider_ok(),
            artifact=ARTIFACT,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=read,
            ),
            adapter=adapter,
        )

        self.assertEqual(adapter.identity, IDENTITY)
        self.assertEqual(result.adapter_call_count, 1)
        self.assertEqual(result.incidents, ())
        self.assertEqual(result.units[0].measurement_state, "SCORED")
        self.assertEqual(result.units[0].causal_class, "MEASUREMENT_COMPLETED")
        self.assertEqual(result.units[0].verdict, "PASS")
        self.assertEqual(
            result.units[0].trace.markers,
            (
                MARKER_PREPARE,
                MARKER_AUTOTEST,
                MARKER_HARNESS_READY,
                MARKER_ADMISSION,
                MARKER_LOAD,
                MARKER_INIT,
                MARKER_EVAL,
                MARKER_TEARDOWN,
            ),
        )
        self.assertEqual(
            events,
            [
                "OPEN_AXIS",
                MARKER_PREPARE,
                MARKER_AUTOTEST,
                "COUNTER:10",
                "CANDIDATE_BYTES",
                MARKER_LOAD,
                MARKER_INIT,
                MARKER_EVAL,
                "COUNTER:13",
                MARKER_TEARDOWN,
            ],
        )
        self.assertEqual(port.runtimes[0].asserted_candidate, CANDIDATE_BYTES)
        self.assertFalse(hasattr(adapter, "candidate_bytes"))

    def test_html_envelope_and_static_autonomy_table(self):
        valid = (
            b"<html><script>const x='<html></html>'; const u='https://example.test'</script></html>",
            b"<html><style>/* <html></html> */ .x{fill:url(#gradient)}</style><!-- <html></html> --></html>",
            b"<html><a href=' #section '>ok</a><object data='#payload'></object></html>",
            b"<html><div style='background:URL( \"#shape\" )'></div></html>",
        )
        invalid = (
            b"\xff<html></html>",
            b"\xef\xbb\xbf<html></html>",
            b" <html></html>",
            b"<!doctype html><html></html>",
            b"<HTML></HTML>",
            b"<html lang='fr'></html>",
            b"<html ></html>",
            b"<html\n></html>",
            b"<html><html></html></html>",
            b"<html></html><html></html>",
            b"<html></html> ",
            b"<html><base href='#ok'></html>",
            b"<html><iframe srcdoc='<p>x</p>'></iframe></html>",
            b"<html><meta http-equiv=' ReFrEsH ' content='0'></html>",
            b"<html><div style='background:u/**/rl(https://example.test/x)'></div></html>",
            b"<html><style>background:u\\72l(data:image/png,x)</style></html>",
            b"<html><style>@\\69mport '#theme'</style></html>",
            b"<html><style>background:image-set(url(#a) 1x)</style></html>",
            b"<html><style>background:url(</style></html>",
        )
        attributes = (
            ("form", "action"),
            ("applet", "archive"),
            ("body", "background"),
            ("q", "cite"),
            ("object", "classid"),
            ("object", "codebase"),
            ("object", "data"),
            ("button", "formaction"),
            ("a", "href"),
            ("link", "icon"),
            ("img", "longdesc"),
            ("html", "manifest"),
            ("a", "ping"),
            ("video", "poster"),
            ("head", "profile"),
            ("img", "src"),
            ("img", "srcset"),
            ("img", "usemap"),
            ("use", "xlink:href"),
        )
        forbidden_values = (
            "asset.png",
            "../asset.png",
            "//example.test/x",
            "https://example.test/x",
            " data:text/plain,x ",
            "BLOB:opaque",
            " JaVaScRiPt:alert(1) ",
        )
        for candidate in valid:
            with self.subTest(kind="valid", candidate=candidate):
                result, port, _ = self._run_candidate(
                    candidate,
                    readings=(10, 13, 20, 23),
                )
                self.assertTrue(
                    all(unit.measurement_state == "SCORED" for unit in result.units)
                )
                self.assertEqual(result.incidents, ())
                self.assertEqual(len(port.runtimes), 2)
                self.assertEqual(result.static_admission_count, 1)
                self.assertTrue(
                    all(
                        not trace.admission_attestation.dynamic_confinement_claimed
                        for trace in (unit.trace for unit in result.units)
                        if trace is not None
                    )
                )
        for candidate in invalid:
            with self.subTest(kind="invalid", candidate=candidate):
                result, port, events = self._run_candidate(candidate)
                self.assertEqual(result.adapter_call_count, 1)
                self.assertEqual(result.static_admission_count, 1)
                self.assertEqual(len(result.incidents), 1)
                self.assertEqual(result.incidents[0].scope, "ACQUISITION")
                self.assertEqual(result.incidents[0].causal_class, "ARTIFACT_INVALID")
                self.assertTrue(
                    all(unit.causal_class == "ARTIFACT_INVALID" for unit in result.units)
                )
                self.assertNotIn("CANDIDATE_BYTES", events)
                self.assertEqual(len(port.runtimes), 1)
        for tag, attribute in attributes:
            for value in forbidden_values:
                with self.subTest(attribute=attribute, value=value):
                    if tag == "html":
                        candidate = f"<html {attribute}='{value}'></html>".encode()
                    else:
                        candidate = (
                            f"<html><{tag} {attribute}='{value}'></{tag}></html>"
                        ).encode()
                    result, port, events = self._run_candidate(candidate)
                    self.assertEqual(result.incidents[0].causal_class, "ARTIFACT_INVALID")
                    self.assertNotIn("CANDIDATE_BYTES", events)
                    self.assertEqual(len(port.runtimes), 1)

    def test_ready_fields_and_axis_isolation_fail_closed_before_candidate_access(self):
        axis_id = "pentagone-api"
        mutations: tuple[
            Callable[[HarnessPreparation], HarnessPreparation | object], ...
        ] = (
            lambda preparation: object(),
            lambda preparation: replace(preparation, session_id=""),
            lambda preparation: replace(preparation, axis_id="other-axis"),
            lambda preparation: replace(
                preparation,
                adapter_identity=replace(IDENTITY, adapter_version="other"),
            ),
            lambda preparation: replace(
                preparation,
                environment_digest=_digest("other-environment"),
            ),
            lambda preparation: replace(
                preparation,
                budget_digest=_digest("other-budget"),
            ),
            lambda preparation: replace(
                preparation,
                core_digest=_digest("other-core"),
            ),
            lambda preparation: replace(
                preparation,
                artifact_digest=_digest("other-artifact"),
            ),
            lambda preparation: replace(
                preparation,
                artifact_proof_ref="proof:other-artifact",
            ),
            lambda preparation: replace(preparation, bootstrap_success=False),
            lambda preparation: replace(preparation, autotest_success=False),
            lambda preparation: replace(preparation, bootstrap_success=1),
            lambda preparation: replace(preparation, autotest_success=1),
            lambda preparation: replace(preparation, watchdog_healthy=False),
            lambda preparation: replace(preparation, ambiguous=True),
            lambda preparation: replace(
                preparation,
                stage_proofs=preparation.stage_proofs[:1],
            ),
            lambda preparation: replace(
                preparation,
                stage_proofs=(
                    preparation.stage_proofs[0],
                    (
                        MARKER_AUTOTEST,
                        preparation.stage_proofs[0][1],
                    ),
                ),
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                events: list[str] = []
                readings = iter((10,))
                port = FakeHtmlRuntimePort(events)
                port.preparation_mutations[axis_id] = mutation
                result = verify_acquisition(
                    acquisition_id="acq-html",
                    axis_ids=(axis_id,),
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
                self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
                self.assertEqual(result.units[0].measurement_state, "NOT_SCORED")
                self.assertEqual(result.static_admission_count, 0)
                self.assertNotIn("CANDIDATE_BYTES", events)
                self.assertEqual(events[-1], MARKER_TEARDOWN)
                self.assertNotIn("raw-", repr(result))

        events = []
        readings = iter((10, 13, 20))
        port = FakeHtmlRuntimePort(events)
        port.reuse_first_runtime = True
        result = verify_acquisition(
            acquisition_id="acq-html",
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
        self.assertEqual(result.units[1].causal_class, "HARNESS_ERROR")
        self.assertEqual(result.adapter_call_count, 2)
        self.assertEqual(result.static_admission_count, 1)

        events = []
        port = FakeHtmlRuntimePort(events)
        second_axis = "pentagone-determinisme"
        port.preparation_mutations[second_axis] = lambda preparation: replace(
            preparation,
            stage_proofs=(
                (MARKER_PREPARE, "proof:pentagone-api:prepare"),
                (MARKER_AUTOTEST, "proof:pentagone-api:autotest"),
            ),
        )
        result = self._execute(
            port=port,
            readings=(10, 13, 20, 23),
            axis_ids=("pentagone-api", second_axis),
        )
        self.assertEqual(result.units[0].measurement_state, "SCORED")
        self.assertEqual(result.units[1].causal_class, "HARNESS_ERROR")
        self.assertNotIn("CANDIDATE_BYTES", events[events.index("OPEN_AXIS", 1) :])

        for reused_stage in (MARKER_LOAD, MARKER_INIT, MARKER_EVAL, MARKER_TEARDOWN):
            with self.subTest(reused_stage=reused_stage):
                events = []
                port = FakeHtmlRuntimePort(events)
                if reused_stage == MARKER_TEARDOWN:
                    port.teardown_mutations[second_axis] = lambda observation: replace(
                        observation,
                        proof_ref="proof:pentagone-api:teardown",
                    )
                else:
                    port.execution_mutations[second_axis] = (
                        lambda observation, reused_stage=reused_stage: replace(
                            observation,
                            stage_proofs=tuple(
                                (
                                    stage,
                                    (
                                        f"proof:pentagone-api:{stage.lower()}"
                                        if stage == reused_stage
                                        else proof_ref
                                    ),
                                )
                                for stage, proof_ref in observation.stage_proofs
                            ),
                        )
                    )
                result = self._execute(
                    port=port,
                    readings=(10, 13, 20, 23),
                    axis_ids=("pentagone-api", second_axis),
                )
                self.assertEqual(result.units[0].measurement_state, "SCORED")
                self.assertEqual(result.units[1].causal_class, "HARNESS_ERROR")
                self.assertEqual(
                    result.incidents[0].diagnostic_code,
                    "ATTESTATION_BINDING_MISMATCH",
                )

    def test_counter_configuration_and_teardown_bindings_fail_closed(self):
        for counter_overrides in (
            {"rule": "other-rule"},
            {"unit": "other-unit"},
        ):
            with self.subTest(counter_overrides=counter_overrides):
                port = FakeHtmlRuntimePort([])
                result = self._execute(
                    port=port,
                    readings=(),
                    counter_overrides=counter_overrides,
                )
                self.assertEqual(result.adapter_call_count, 0)
                self.assertEqual(port.requests, [])
                self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
                self.assertEqual(
                    result.incidents[0].diagnostic_code,
                    "ATTESTATION_BINDING_MISMATCH",
                )
                validate_acquisition_result(result)

        port = FakeHtmlRuntimePort([])
        result = self._execute(
            port=port,
            readings=(),
            budget=replace(_budget(), measurement_rule="other-rule"),
        )
        self.assertEqual(result.adapter_call_count, 0)
        self.assertEqual(port.requests, [])
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
        validate_acquisition_result(result)

        for mutation in (
            lambda value: replace(value, session_id="other-session"),
            lambda value: replace(value, axis_id="other-axis"),
        ):
            with self.subTest(teardown_binding=mutation):
                port = FakeHtmlRuntimePort([])
                port.teardown_mutations["pentagone-api"] = mutation
                result = self._execute(port=port, readings=(10, 13))
                self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
                self.assertEqual(result.units[0].measurement_state, "NOT_SCORED")

        reads: list[object] = []
        readings = iter((10, True, 13))

        def read_once_per_boundary():
            value = next(readings)
            reads.append(value)
            return value

        port = FakeHtmlRuntimePort([])
        result = verify_acquisition(
            acquisition_id="acq-html",
            axis_ids=("pentagone-api",),
            provider_evidence=_provider_ok(),
            artifact=ARTIFACT,
            qualified_budget=_budget(),
            harness_expectations=EXPECTATIONS,
            counter=MonotonicCounter(
                source_id="fixture-counter",
                unit="fixture-ticks",
                rule="monotonic-end-minus-start/v1",
                read=read_once_per_boundary,
            ),
            adapter=HtmlModalityAdapter(identity=IDENTITY, runtime_port=port),
        )
        self.assertEqual(reads, [10, True])
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
        self.assertEqual(port.events[-1], MARKER_TEARDOWN)

    def test_strict_types_state_contradictions_and_counter_boundaries(self):
        caller_cases = (
            replace(_provider_ok(), lock_bound=1),
            replace(_provider_ok(), artifact_admissible=0),
        )
        for provider in caller_cases:
            with self.subTest(caller_provider=provider):
                port = FakeHtmlRuntimePort([])
                with self.assertRaises(VerifyV7ContratInvalide):
                    self._execute(port=port, readings=(10, 13), provider_evidence=provider)
                self.assertEqual(port.requests, [])
        for value in (True, 0, -1):
            with self.subTest(caller_budget=value):
                port = FakeHtmlRuntimePort([])
                with self.assertRaises(VerifyV7ContratInvalide):
                    self._execute(
                        port=port,
                        readings=(10, 13),
                        budget=replace(_budget(), value=value),
                    )
                self.assertEqual(port.requests, [])

        axis_id = "pentagone-api"
        observation_mutations = (
            lambda value: replace(value, evaluation_completed=1),
            lambda value: replace(value, budget_expired=0),
            lambda value: replace(value, network_attempted=1),
            lambda value: replace(value, evaluation_completed=True, budget_expired=True),
            lambda value: replace(value, evaluation_completed=True, verdict=None),
            lambda value: replace(value, evaluation_completed=False, verdict="PASS"),
            lambda value: replace(
                value,
                budget_expired=True,
                evaluation_completed=False,
                verdict=None,
            ),
            lambda value: replace(
                value,
                stage_proofs=(
                    *value.stage_proofs,
                    ("BUDGET_EXPIRED", f"proof:{axis_id}:expired"),
                ),
            ),
            lambda value: replace(value, ready_receipt_ref=_digest("wrong-ready")),
            lambda value: replace(value, artifact_digest=_digest("wrong-artifact")),
            lambda value: replace(value, budget_digest=_digest("wrong-budget")),
            lambda value: replace(value, environment_digest=_digest("wrong-environment")),
            lambda value: replace(value, axis_id="wrong-axis"),
            lambda value: replace(value, session_id="wrong-session"),
        )
        for mutation in observation_mutations:
            with self.subTest(observation_mutation=mutation):
                port = FakeHtmlRuntimePort([])
                port.execution_mutations[axis_id] = mutation
                result = self._execute(port=port, readings=(10, 13))
                self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
                self.assertEqual(result.units[0].measurement_state, "NOT_SCORED")
                self.assertNotIn("raw-runtime", repr(result))
                self.assertEqual(port.events[-1], MARKER_TEARDOWN)

        for readings in ((True, 13), (10, True), (13, 10)):
            with self.subTest(counter_readings=readings):
                port = FakeHtmlRuntimePort([])
                result = self._execute(port=port, readings=readings)
                self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
                self.assertEqual(port.events[-1], MARKER_TEARDOWN)
        for counter_overrides in ({"source_id": ""},):
            with self.subTest(counter_overrides=counter_overrides):
                port = FakeHtmlRuntimePort([])
                with self.assertRaises(VerifyV7ContratInvalide):
                    self._execute(
                        port=port,
                        readings=(10, 13),
                        counter_overrides=counter_overrides,
                    )
                self.assertEqual(port.requests, [])

        for end, expected in ((16, "HARNESS_ERROR"), (17, "ARTIFACT_EXECUTION_LIMIT")):
            with self.subTest(counter_end=end):
                port = FakeHtmlRuntimePort([])
                port.execution_mutations[axis_id] = lambda value: replace(
                    value,
                    stage_proofs=(
                        (MARKER_LOAD, f"proof:{axis_id}:load"),
                        ("BUDGET_EXPIRED", f"proof:{axis_id}:expired"),
                    ),
                    evaluation_completed=False,
                    verdict=None,
                    budget_expired=True,
                )
                result = self._execute(port=port, readings=(10, end))
                self.assertEqual(result.units[0].causal_class, expected)
                self.assertEqual(result.units[0].trace.observed_cost, end - 10)

    def test_result_recomputes_every_embedded_binding_and_rejects_isolated_mutations(self):
        port = FakeHtmlRuntimePort([])
        result = self._execute(port=port, readings=(10, 13))

        self.assertEqual(
            result.verification_context.budget_digest,
            "sha256:55b3ef56ba7452d56594d127d50540340fc7749d8f7b0238f10164a0bb14bcc8",
        )
        self.assertEqual(
            result.verification_context.environment_digest,
            "sha256:f800d639f42e9238d397e694a094e0430bb0c5ec6de022ae680b94b59aef4c01",
        )
        validate_acquisition_result(result)
        validate_unit_result(result.units[0])

        trace = result.units[0].trace
        self.assertIsNotNone(trace)
        assert trace is not None
        ready = trace.ready_attestation
        context = result.verification_context
        self.assertEqual(trace.teardown_observation.axis_id, trace.axis_id)
        self.assertEqual(trace.teardown_observation.session_id, trace.session_id)
        mutated_environment = replace(
            context.environment_manifest,
            influential_configuration=(("network-policy", _digest("other")),),
        )
        mutations = (
            replace(result, context_digest=_digest("wrong-context")),
            replace(
                result,
                verification_context=replace(
                    context,
                    budget_digest=_digest("wrong-budget"),
                ),
            ),
            replace(
                result,
                verification_context=replace(
                    context,
                    environment_digest=_digest("wrong-environment"),
                ),
            ),
            replace(
                result,
                verification_context=replace(
                    context,
                    environment_manifest=mutated_environment,
                ),
            ),
            replace(
                result,
                verification_context=replace(
                    context,
                    artifact_digest=_digest("wrong-artifact"),
                ),
            ),
            replace(
                result,
                verification_context=replace(
                    context,
                    artifact_proof_ref="proof:wrong-artifact",
                ),
            ),
            replace(
                result,
                verification_context=replace(
                    context,
                    core_digest=_digest("wrong-core"),
                ),
            ),
            replace(
                result,
                ready_attestations=(
                    replace(ready, receipt_ref=_digest("wrong-receipt")),
                ),
            ),
            replace(
                result,
                ready_attestations=(
                    replace(
                        ready,
                        start_marker=replace(
                            ready.start_marker,
                            value=ready.start_marker.value + 1,
                        ),
                    ),
                ),
            ),
            replace(
                result,
                admission_attestation=replace(
                    result.admission_attestation,
                    proof_ref=_digest("wrong-admission"),
                ),
            ),
            replace(
                result,
                units=(
                    replace(
                        result.units[0],
                        trace=replace(
                            trace,
                            end_marker=replace(
                                trace.end_marker,
                                value=trace.end_marker.value + 1,
                            ),
                        ),
                    ),
                ),
            ),
            replace(
                result,
                units=(
                    replace(
                        result.units[0],
                        trace=replace(
                            trace,
                            qualified_budget=replace(trace.qualified_budget, value=8),
                        ),
                    ),
                ),
            ),
            replace(
                result,
                units=(
                    replace(
                        result.units[0],
                        trace=replace(
                            trace,
                            observation=replace(
                                trace.observation,
                                stage_proofs=(
                                    (MARKER_LOAD, "proof:mutated:load"),
                                    *trace.observation.stage_proofs[1:],
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            replace(
                result,
                units=(
                    replace(
                        result.units[0],
                        trace=replace(
                            trace,
                            teardown_observation=replace(
                                trace.teardown_observation,
                                proof_ref="proof:mutated:teardown",
                            ),
                        ),
                    ),
                ),
            ),
            replace(
                result,
                units=(replace(result.units[0], context_digest=_digest("wrong-unit")),),
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(VerifyV7ContratInvalide):
                    validate_acquisition_result(mutation)

        malformed_manifests = (
            replace(
                ENVIRONMENT,
                dependencies=(
                    replace(ENVIRONMENT.dependencies[0], version="2"),
                    ENVIRONMENT.dependencies[0],
                ),
            ),
            replace(
                ENVIRONMENT,
                dependencies=(
                    ENVIRONMENT.dependencies[0],
                    replace(ENVIRONMENT.dependencies[0], version="14"),
                ),
            ),
            replace(
                ENVIRONMENT,
                influential_configuration=(
                    ("z-key", _digest("z")),
                    ("a-key", _digest("a")),
                ),
            ),
        )
        for manifest in malformed_manifests:
            with self.subTest(manifest=manifest):
                port = FakeHtmlRuntimePort([])
                with self.assertRaises(VerifyV7ContratInvalide):
                    self._execute(
                        port=port,
                        readings=(10, 13),
                        expectations=replace(
                            EXPECTATIONS,
                            environment_manifest=manifest,
                        ),
                    )
                self.assertEqual(port.requests, [])

    def test_regression_states_dynamic_network_and_redacted_runtime_failures(self):
        axis_id = "pentagone-api"
        for verdict in ("PASS", "FAIL"):
            with self.subTest(verdict=verdict):
                port = FakeHtmlRuntimePort([])
                port.execution_mutations[axis_id] = lambda value, verdict=verdict: replace(
                    value,
                    verdict=verdict,
                )
                result = self._execute(port=port, readings=(10, 13))
                self.assertEqual(result.units[0].measurement_state, "SCORED")
                self.assertEqual(result.units[0].causal_class, "MEASUREMENT_COMPLETED")
                self.assertEqual(result.units[0].verdict, verdict)
                self.assertEqual(result.incidents, ())

        for stages in (
            (MARKER_LOAD,),
            (MARKER_LOAD, MARKER_INIT),
            (MARKER_LOAD, MARKER_INIT, MARKER_EVAL),
        ):
            with self.subTest(limit_stages=stages):
                port = FakeHtmlRuntimePort([])
                port.execution_mutations[axis_id] = lambda value, stages=stages: replace(
                    value,
                    stage_proofs=tuple(
                        (stage, f"proof:{axis_id}:{stage.lower()}")
                        for stage in (*stages, "BUDGET_EXPIRED")
                    ),
                    evaluation_completed=False,
                    verdict=None,
                    budget_expired=True,
                )
                result = self._execute(port=port, readings=(10, 17))
                self.assertEqual(
                    result.units[0].causal_class,
                    "ARTIFACT_EXECUTION_LIMIT",
                )
                self.assertEqual(result.units[0].measurement_state, "NOT_SCORED")

        port = FakeHtmlRuntimePort([])
        port.execution_mutations[axis_id] = lambda value: replace(
            value,
            network_attempted=True,
        )
        result = self._execute(
            port=port,
            readings=(10, 13, 20, 23),
            axis_ids=("pentagone-api", "pentagone-determinisme"),
        )
        self.assertEqual(result.units[0].verdict, "FAIL")
        self.assertEqual(result.units[1].verdict, "PASS")
        self.assertTrue(
            all(unit.measurement_state == "SCORED" for unit in result.units)
        )

        port = FakeHtmlRuntimePort([])
        port.execution_mutations[axis_id] = lambda value: replace(
            value,
            stage_proofs=((MARKER_LOAD, f"proof:{axis_id}:load"),),
            evaluation_completed=False,
            verdict=None,
            network_attempted=True,
        )
        result = self._execute(port=port, readings=(10, 13))
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
        self.assertEqual(result.incidents[0].diagnostic_code, "EVIDENCE_MISSING")

        port = FakeHtmlRuntimePort([])
        port.execution_mutations[axis_id] = lambda value: replace(
            value,
            stage_proofs=(
                (MARKER_LOAD, f"proof:{axis_id}:load"),
                ("BUDGET_EXPIRED", f"proof:{axis_id}:expired"),
            ),
            evaluation_completed=False,
            verdict=None,
            budget_expired=True,
            network_attempted=True,
        )
        result = self._execute(port=port, readings=(10, 17))
        self.assertEqual(
            result.units[0].causal_class,
            "ARTIFACT_EXECUTION_LIMIT",
        )

        for mutation in (
            lambda value: replace(value, confinement_healthy=False),
            lambda value: replace(value, confinement_ambiguous=True),
        ):
            with self.subTest(confinement_mutation=mutation):
                port = FakeHtmlRuntimePort([])
                port.execution_mutations[axis_id] = mutation
                result = self._execute(port=port, readings=(10, 13))
                self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
                self.assertEqual(
                    result.incidents[0].diagnostic_code,
                    "CONFINEMENT_UNHEALTHY",
                )

        for failure_kind in ("candidate", "teardown"):
            with self.subTest(failure_kind=failure_kind):
                port = FakeHtmlRuntimePort([])
                if failure_kind == "candidate":
                    port.raise_during_candidate.add(axis_id)
                else:
                    port.raise_during_teardown.add(axis_id)
                result = self._execute(port=port, readings=(10, 13))
                self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
                self.assertEqual(result.units[0].measurement_state, "NOT_SCORED")
                self.assertEqual(result.incidents[0].diagnostic_code, "ADAPTER_EXCEPTION")
                self.assertNotIn("secret", repr(result))
                self.assertEqual(port.events[-1], MARKER_TEARDOWN)

        for teardown_mutation in (
            lambda value: replace(value, complete=False),
            lambda value: replace(value, watchdog_healthy=False),
            lambda value: replace(value, ambiguous=True),
            lambda value: replace(value, complete=1),
        ):
            with self.subTest(teardown_mutation=teardown_mutation):
                port = FakeHtmlRuntimePort([])
                port.teardown_mutations[axis_id] = teardown_mutation
                result = self._execute(port=port, readings=(10, 13))
                self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")

        incomplete = replace(_provider_ok(), payload_bound=False)
        port = FakeHtmlRuntimePort([])
        result = self._execute(
            port=port,
            readings=(),
            provider_evidence=incomplete,
        )
        self.assertEqual(result.units[0].causal_class, "HARNESS_ERROR")
        self.assertEqual(result.adapter_call_count, 0)
        self.assertEqual(port.requests, [])


class VerifyV7CorrectiveV2HtmlPublicBehavior(unittest.TestCase):
    def test_c1_admission_rejects_mixed_srcset_and_crlf_escaped_import(self):
        candidates = (
            b'<html><img srcset="#safe,https://evil.test/x"></html>',
            b"<html><style>@\\69\r\nmport 'https://evil.test/x'</style></html>",
        )
        for candidate_bytes in candidates:
            with self.subTest(candidate_bytes=candidate_bytes):
                events: list[str] = []
                port = FakeHtmlRuntimePort(events)
                readings = iter((10, 13, 20, 23))
                artifact = Artifact(
                    content=candidate_bytes,
                    digest=_digest(candidate_bytes),
                    proof_ref="proof:artifact-bound",
                )
                result = verify_acquisition(
                    acquisition_id="acq-c1",
                    axis_ids=("pentagone-api", "pentagone-determinisme"),
                    provider_evidence=_provider_ok(),
                    artifact=artifact,
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

                self.assertEqual(len(result.incidents), 1)
                self.assertEqual(result.incidents[0].scope, "ACQUISITION")
                self.assertEqual(result.incidents[0].causal_class, "ARTIFACT_INVALID")
                self.assertEqual(result.static_admission_count, 1)
                self.assertEqual(result.adapter_call_count, 1)
                self.assertEqual(len(port.requests), 1)
                self.assertEqual(events.count("CANDIDATE_BYTES"), 0)
                self.assertTrue(
                    all(
                        unit.measurement_state == "NOT_SCORED"
                        and unit.causal_class == "ARTIFACT_INVALID"
                        and unit.incident_id == result.incidents[0].incident_id
                        for unit in result.units
                    )
                )
                validate_acquisition_result(result)

    def test_c7_teardown_error_survives_invalid_admission(self):
        candidate_bytes = b"<html><img src='https://evil.test/x'></html>"
        events: list[str] = []
        port = FakeHtmlRuntimePort(events)
        port.raise_during_teardown.add("pentagone-api")
        readings = iter((10, 20))
        artifact = Artifact(
            content=candidate_bytes,
            digest=_digest(candidate_bytes),
            proof_ref="proof:artifact-bound",
        )
        result = verify_acquisition(
            acquisition_id="acq-c7",
            axis_ids=("pentagone-api", "pentagone-determinisme"),
            provider_evidence=_provider_ok(),
            artifact=artifact,
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

        self.assertEqual(len(result.units), 2)
        self.assertEqual(len(result.incidents), 1)
        self.assertEqual(result.incidents[0].scope, "ACQUISITION")
        self.assertEqual(result.incidents[0].stage, "teardown")
        self.assertEqual(result.incidents[0].causal_class, "HARNESS_ERROR")
        self.assertEqual(
            result.incidents[0].affected_unit_ids,
            ("pentagone-api", "pentagone-determinisme"),
        )
        self.assertTrue(
            all(
                unit.measurement_state == "NOT_SCORED"
                and unit.causal_class == "HARNESS_ERROR"
                and unit.verdict is None
                and unit.incident_id == result.incidents[0].incident_id
                for unit in result.units
            )
        )
        self.assertNotIn("ARTIFACT_INVALID", repr(result))
        self.assertEqual(result.adapter_call_count, 1)
        self.assertEqual(result.static_admission_count, 1)
        self.assertEqual(len(port.requests), 1)
        self.assertEqual(events.count("CANDIDATE_BYTES"), 0)
        validate_acquisition_result(result)


if __name__ == "__main__":
    unittest.main()
