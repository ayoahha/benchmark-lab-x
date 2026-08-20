from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.campaign_v0_manual_harness import (
    ManualHarness,
    ManualHarnessError,
    prepare_command_descriptor,
)
from tools.campaign_v0_shared_core_adapter import (
    INCONNU,
    PreparationContractError,
    build_blind_decision_view,
    canonical_sha256,
    classify_incident,
    normalise_observations,
    validate_receipt,
)
from tools.valider_preparation_campagne_v0 import (
    ADAPTER_PAR_DEFAUT,
    CONTRATS_PAR_DEFAUT,
    HARNESS_PAR_DEFAUT,
    MANIFESTE_PAR_DEFAUT,
    PREPARATION_ROOT,
    RACINE,
    RECU_PAR_DEFAUT,
    ErreurPreparationCampagne,
    _canonical,
    assert_offline_module,
    main,
    valider_preparation_campagne_v0,
)


class PreparationCampagneV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.contracts = json.loads(CONTRATS_PAR_DEFAUT.read_bytes())
        self.manifest = json.loads(MANIFESTE_PAR_DEFAUT.read_bytes())
        self.receipt = json.loads(RECU_PAR_DEFAUT.read_bytes())

    def _temporary_file(self, content: bytes) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "artifact"
        path.write_bytes(content)
        return path

    def _mutated_json(self, document: dict[str, object]) -> Path:
        return self._temporary_file(_canonical(document))

    def _validate(
        self,
        contracts: Path = CONTRATS_PAR_DEFAUT,
        manifest: Path = MANIFESTE_PAR_DEFAUT,
        receipt: Path = RECU_PAR_DEFAUT,
        adapter: Path = ADAPTER_PAR_DEFAUT,
        harness: Path = HARNESS_PAR_DEFAUT,
    ) -> dict[str, object]:
        return valider_preparation_campagne_v0(
            contracts,
            manifest,
            receipt,
            adapter,
            harness,
            RACINE,
        )

    def test_paquet_valide_et_racine_unique(self) -> None:
        result = self._validate()

        self.assertEqual("PREPARATION_CAMPAGNE_V0_OK", result["status"])
        self.assertEqual(PREPARATION_ROOT, result["preparation_root"])
        self.assertEqual(5, len(result["output_identities"]))

    def test_rejette_derives_de_racine_autorite_schema_et_canonicalite(self) -> None:
        mutations = []
        extra = deepcopy(self.contracts)
        extra["unexpected"] = True
        mutations.append(extra)
        missing = deepcopy(self.contracts)
        missing.pop("lock_binding")
        mutations.append(missing)
        authority = deepcopy(self.contracts)
        authority["authority_bindings"]["phase_1"]["comment_id"] = 0
        mutations.append(authority)
        for document in mutations:
            with self.subTest(keys=sorted(document)):
                with self.assertRaises(ErreurPreparationCampagne):
                    self._validate(contracts=self._mutated_json(document))

        noncanonical = self._temporary_file(
            json.dumps(self.contracts, ensure_ascii=False, indent=2).encode("utf-8")
        )
        with self.assertRaises(ErreurPreparationCampagne):
            self._validate(contracts=noncanonical)

        manifest = deepcopy(self.manifest)
        manifest["metadata"]["locked_root"] = "0" * 64
        with self.assertRaises(ErreurPreparationCampagne):
            self._validate(manifest=self._mutated_json(manifest))

    def test_rejette_configuration_slot_output_et_promotion_observed(self) -> None:
        documents = []
        extra_configuration = deepcopy(self.contracts)
        extra_configuration["contracts"]["measurement_protocol"]["panel"].append(
            deepcopy(extra_configuration["contracts"]["measurement_protocol"]["panel"][0])
        )
        documents.append(extra_configuration)
        extra_slot = deepcopy(self.contracts)
        extra_slot["contracts"]["measurement_protocol"]["panel"][0]["slot"] = "ACQ-EXTRA"
        documents.append(extra_slot)
        extra_output = deepcopy(self.contracts)
        extra_output["output_identities"].append("campaign-v0-extra/v1")
        documents.append(extra_output)
        promoted = deepcopy(self.contracts)
        promoted["contracts"]["measurement_protocol"]["panel"][0]["model"]["state"] = "OBSERVED"
        documents.append(promoted)
        for document in documents:
            with self.subTest(output_count=len(document["output_identities"])):
                with self.assertRaises(ErreurPreparationCampagne):
                    self._validate(contracts=self._mutated_json(document))

    def test_rejette_retry_fallback_spend_quota_et_campaign_enablement(self) -> None:
        for field in (
            "retry",
            "fallback",
            "spend",
            "quota_consumption",
            "campaign_execution",
        ):
            document = deepcopy(self.contracts)
            document["authorizations"][field] = "AUTHORIZED"
            with self.subTest(field=field), self.assertRaises(ErreurPreparationCampagne):
                self._validate(contracts=self._mutated_json(document))

    def test_modules_runtime_sont_statiquement_offline(self) -> None:
        assert_offline_module(ADAPTER_PAR_DEFAUT, "adapter")
        assert_offline_module(HARNESS_PAR_DEFAUT, "harness")

        source = HARNESS_PAR_DEFAUT.read_bytes() + b"\nimport subprocess\nsubprocess.run([])\n"
        executable = self._temporary_file(source)
        with self.assertRaises(ErreurPreparationCampagne):
            assert_offline_module(executable, "harness")

    def test_descripteurs_commandes_sont_exacts_et_non_executants(self) -> None:
        grok = prepare_command_descriptor("grok46_xai_build_oauth")
        kimi = prepare_command_descriptor("kimi_k3_cursor_cli")

        self.assertEqual("REQUESTED", grok["state"])
        self.assertEqual("__PROMPT_FILE__", grok["argv"][-1])
        self.assertIn("--disable-web-search", grok["argv"])
        self.assertIn("--no-subagents", grok["argv"])
        self.assertEqual(["agent", "--print"], kimi["argv"][:2])
        self.assertEqual("__PROMPT__", kimi["argv"][-1])

    def test_incidents_sont_classes_selon_m6_4(self) -> None:
        facts = {
            "identity_mismatch": False,
            "local_or_unattributable_failure": False,
            "missing_required_observation": False,
            "provider_attribution_proven": False,
            "provider_operation_failed": False,
        }
        cases = (
            ({"provider_operation_failed": True}, "HARNESS_ERROR"),
            (
                {"provider_operation_failed": True, "provider_attribution_proven": True},
                "PROVIDER_FAILURE",
            ),
            ({"local_or_unattributable_failure": True}, "HARNESS_ERROR"),
            ({"identity_mismatch": True}, "IDENTITY_MISMATCH"),
            ({"missing_required_observation": True}, "MISSING_OBSERVATION"),
        )
        for changes, expected in cases:
            current = {**facts, **changes}
            with self.subTest(expected=expected):
                self.assertEqual(expected, classify_incident(current))

    def test_cout_absent_reste_inconnu_et_aucune_imputation_n_est_acceptee(self) -> None:
        observations = normalise_observations({})
        self.assertEqual(INCONNU, observations["provider_cost"]["value_minor"])
        self.assertEqual(INCONNU, observations["provider_cost"]["currency"])

        with self.assertRaises(PreparationContractError):
            normalise_observations(
                {
                    "provider_cost": {
                        "attributable_evidence_sha256": INCONNU,
                        "currency": "USD",
                        "value_minor": 0,
                    }
                }
            )

    def test_recu_est_immutable_et_chaine_par_predecesseur(self) -> None:
        harness = ManualHarness()
        first_bytes = harness.record_observation("grok46_xai_build_oauth", {})
        first = json.loads(first_bytes)
        second_bytes = harness.record_observation("kimi_k3_cursor_cli", {})
        second = json.loads(second_bytes)

        self.assertEqual(first["content_address"]["sha256"], second["payload"]["predecessor_content_sha256"])
        self.assertEqual((first_bytes, second_bytes), harness.receipts)
        with self.assertRaises(ManualHarnessError):
            harness.record_observation("grok46_xai_build_oauth", {})

    def test_validation_recu_rejette_hash_candidate_recalcule_incorrect(self) -> None:
        harness = ManualHarness()
        receipt = json.loads(
            harness.record_observation(
                "grok46_xai_build_oauth",
                {"candidate_content": "synthetic candidate"},
            )
        )
        receipt["payload"]["observations"]["candidate"]["sha256"] = "0" * 64
        receipt["content_address"]["sha256"] = canonical_sha256(receipt["payload"])

        with self.assertRaises(PreparationContractError):
            validate_receipt(receipt)

    def test_vue_aveugle_n_expose_ni_identite_ni_cout(self) -> None:
        harness = ManualHarness()
        receipt = json.loads(harness.record_observation("grok46_xai_build_oauth", {}))
        controls = {f"G-{index:03d}": INCONNU for index in range(1, 6)}
        view = build_blind_decision_view(receipt, "ITEM-001", {"criterion": "SYNTHETIC"}, controls)
        forbidden = {
            "acquisition_id",
            "configuration_id",
            "cost",
            "latency",
            "model",
            "provider",
            "route",
            "usage",
        }
        self.assertFalse(set(view).intersection(forbidden))
        with self.assertRaises(PreparationContractError):
            build_blind_decision_view(receipt, "ITEM-001", {"provider": "LEAK"}, controls)

    def test_rejette_derive_manifeste_et_recu_non_deterministe(self) -> None:
        manifest = deepcopy(self.manifest)
        manifest["approved_sources"].reverse()
        with self.assertRaises(ErreurPreparationCampagne):
            self._validate(manifest=self._mutated_json(manifest))

        receipt = deepcopy(self.receipt)
        receipt["created_at"] = "2026-08-20T00:00:00Z"
        with self.assertRaises(ErreurPreparationCampagne):
            self._validate(receipt=self._mutated_json(receipt))

    def test_cli_prefixes_succes_et_echec(self) -> None:
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = main([])
        self.assertEqual(0, code)
        self.assertTrue(output.getvalue().startswith("PREPARATION_CAMPAGNE_V0_OK"))
        self.assertEqual("", error.getvalue())

        invalid = self._temporary_file(b'{"schema_version":"invalid"}\n')
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = main(["--contracts", str(invalid)])
        self.assertNotEqual(0, code)
        self.assertEqual("", output.getvalue())
        self.assertTrue(error.getvalue().startswith("HOLD_M7_1_PREPARATION:"))


if __name__ == "__main__":
    unittest.main()
