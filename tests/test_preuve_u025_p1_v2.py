from __future__ import annotations

import json
import unittest

from tools.preuve_u025_p1_v2 import (
    CASES,
    HUMAN_FAILURES,
    ORACLE,
    ORACLE_SHA256,
    PATHS,
    InvalidProof,
    build_files,
    canonical,
    digest,
    load_bundles,
    validate,
)


def readdress_bundle(
    files: dict[str, bytes], logical_name: str, bundle: object
) -> None:
    index = json.loads(files["artifact-index.json"])
    entry = next(
        item
        for item in index["artifacts"]
        if item["logical_name"] == logical_name
    )
    del files[f"artifacts/{entry['sha256']}"]
    content = canonical(bundle)
    entry["sha256"] = digest(content)
    entry["size_bytes"] = len(content)
    files[f"artifacts/{entry['sha256']}"] = content
    files["artifact-index.json"] = canonical(index)


class PreuveU025P1V2RegressionTests(unittest.TestCase):
    def test_chaque_voie_execute_son_adaptateur_avec_sa_trace(self) -> None:
        files = build_files()
        bundles = load_bundles(files)
        receipts = bundles["receipts"]["receipts"]
        traces = bundles["execution_traces"]["traces"]

        self.assertEqual(len(CASES) * len(PATHS), len(traces))
        for case_id in CASES:
            selected = [
                receipt
                for receipt in receipts
                if receipt["case_id"] == case_id
            ]
            trace_hashes = {
                receipt["observed_identity"]["execution_trace_sha256"]
                for receipt in selected
            }
            execution_ids = {
                receipt["observed_identity"]["execution_id"]
                for receipt in selected
            }
            adapter_kinds = {
                receipt["observed_identity"]["adapter_kind"]
                for receipt in selected
            }
            self.assertEqual(len(PATHS), len(trace_hashes))
            self.assertEqual(len(PATHS), len(execution_ids))
            self.assertEqual(set(PATHS), adapter_kinds)

    def test_expected_vient_de_l_oracle_independant_pour_les_16_cas(self) -> None:
        files = build_files()
        receipts = load_bundles(files)["receipts"]["receipts"]

        self.assertEqual(set(CASES), set(ORACLE))
        self.assertEqual(10, len(HUMAN_FAILURES))
        for case_id in HUMAN_FAILURES:
            self.assertEqual("NOT_ACCEPTABLE", ORACLE[case_id]["human"])
        for receipt in receipts:
            self.assertEqual(ORACLE[receipt["case_id"]], receipt["expected"])
            self.assertEqual(ORACLE_SHA256, receipt["expected_source_sha256"])
            before = dict(receipt["expected"])
            receipt["observed"]["result"] = "TAMPERED"
            self.assertEqual(before, receipt["expected"])

    def test_graphe_est_racine_et_readressage_partiel_echoue(self) -> None:
        files = build_files()
        self.assertIn("evidence-manifest.json", files)
        self.assertIn("proof-root.json", files)
        validate(files)

        bundles = load_bundles(files)
        receipts = bundles["receipts"]
        last = receipts["receipts"][-1]
        last["unknowns"] = [*last["unknowns"], "PARTIAL_READDRESS"]
        unhashed = {
            key: value
            for key, value in last.items()
            if key != "receipt_sha256"
        }
        last["receipt_sha256"] = digest(canonical(unhashed))
        readdress_bundle(files, "receipts", receipts)

        with self.assertRaisesRegex(InvalidProof, "graphe|racine|registre"):
            validate(files)

    def test_effort_observe_exige_une_preuve_distincte(self) -> None:
        facts = load_bundles(build_files())["effort_register"]["facts"]

        self.assertEqual(len(PATHS) * 7 * 2, len(facts))
        observed_proofs = set()
        for fact in facts:
            if fact["state"] == "OBSERVE":
                proof = (fact["action_sha256"], fact["artifact_sha256"])
                self.assertNotIn(None, proof)
                self.assertNotIn(proof, observed_proofs)
                observed_proofs.add(proof)
            else:
                self.assertEqual("INCONNU", fact["state"])
                self.assertIsNone(fact["action_sha256"])
                self.assertIsNone(fact["artifact_sha256"])

    def test_rapport_99_1_est_recalcule_et_refuse(self) -> None:
        files = build_files()
        reports = load_bundles(files)["reports"]
        report = reports["reports"][0]
        report["counts"]["OFFICIALLY_ACCEPTABLE"] = 99
        report["counts"]["CANDIDATE_NOT_ACCEPTABLE"] = 1
        report["decidable_denominator"] = 100
        report["official_acceptance_rate"] = "99/100"
        report["coverage"] = "100/16"
        unhashed = {
            key: value
            for key, value in report.items()
            if key != "report_sha256"
        }
        report["report_sha256"] = digest(canonical(unhashed))
        readdress_bundle(files, "reports", reports)

        with self.assertRaisesRegex(InvalidProof, "rapport|racine|graphe"):
            validate(files)


if __name__ == "__main__":
    unittest.main()
