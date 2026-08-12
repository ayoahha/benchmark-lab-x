"""Régressions publiques du noyau verify-v7 après migration open_axis."""

from __future__ import annotations

import inspect
import sys
import unittest
from dataclasses import replace
from pathlib import Path


RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

from verify_v7 import (  # noqa: E402
    AcquisitionResult,
    AxisSession,
    HarnessReadyAttestation,
    ModalityAdapter,
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


if __name__ == "__main__":
    unittest.main()
