from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import preuve_u025_p1 as p1
from tools.preuve_u025_p1 import (
    CASES,
    DEFAULT_PROOF,
    PATHS,
    InvalidProof,
    build_files,
    calculate_cost,
    calculate_latency,
    canonical,
    digest,
    load_bundles,
    validate,
    verify_proof,
)
from tests._helpers_v1 import extraire_revision_historique


class PreuveU025P1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.revision = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.revision.cleanup)
        cls.racine_historique = Path(cls.revision.name)
        extraire_revision_historique(cls.racine_historique)

    def test_preuve_commise_est_complete_et_reproductible(self) -> None:
        paquet_historique = (
            self.racine_historique / "tasks/dev/pre-cadrage-entretien-client"
        )
        with (
            patch.object(p1, "ROOT", self.racine_historique),
            patch.object(p1, "PACKAGE", paquet_historique),
        ):
            result = verify_proof(DEFAULT_PROOF)
            self.assertEqual(build_files(), build_files())

        self.assertEqual("PASS", result["verdict"])
        self.assertEqual(16, result["cases"])
        self.assertEqual(3, result["paths"])
        self.assertEqual(48, result["receipts"])
        self.assertEqual(42, result["effort_facts"])
        self.assertEqual(0, result["candidate_calls"])
        self.assertEqual("0", result["supplier_spend"])

    def test_tous_les_temoins_traversent_les_trois_voies(self) -> None:
        files = build_files()
        bundles = load_bundles(files)
        cases = bundles["case_fixtures"]["cases"]
        receipts = bundles["receipts"]["receipts"]

        self.assertEqual(list(CASES), [case["case_id"] for case in cases])
        for path in PATHS:
            selected = [
                receipt for receipt in receipts if receipt["path"] == path
            ]
            self.assertEqual(
                list(CASES), [receipt["case_id"] for receipt in selected]
            )
            self.assertTrue(
                all(receipt["expected"] == receipt["observed"] for receipt in selected)
            )
            self.assertTrue(
                all(receipt["candidate_calls"] == 0 for receipt in selected)
            )
            self.assertTrue(
                all(receipt["supplier_spend"] == "0" for receipt in selected)
            )

        by_id = {case["case_id"]: case for case in cases}
        self.assertEqual("PASS", by_id["WT-ACCEPTABLE"]["automatic"]["status"])
        self.assertEqual("FAIL", by_id["WT-SCHEMA"]["automatic"]["status"])
        self.assertEqual("FAIL", by_id["WT-ANCRE"]["automatic"]["status"])
        self.assertEqual("FAIL", by_id["WT-VOCABULAIRE"]["automatic"]["status"])
        self.assertEqual(
            "HARNESS_ERROR", by_id["WT-HARNESS"]["automatic"]["status"]
        )
        self.assertEqual(
            "UNABLE_TO_JUDGE", by_id["WT-HUMAIN-INDISPONIBLE"]["human"]
        )

    def test_recu_modifie_est_refuse_meme_si_le_lot_est_readresse(self) -> None:
        files = dict(build_files())
        index = json.loads(files["artifact-index.json"])
        entry = next(
            item for item in index["artifacts"] if item["logical_name"] == "receipts"
        )
        old_path = f"artifacts/{entry['sha256']}"
        bundle = json.loads(files.pop(old_path))
        bundle["receipts"][0]["observed"]["result"] = "INCONNU"
        content = canonical(bundle)
        entry["sha256"] = digest(content)
        entry["size_bytes"] = len(content)
        files[f"artifacts/{entry['sha256']}"] = content
        files["artifact-index.json"] = canonical(index)

        with self.assertRaisesRegex(InvalidProof, "reçu altéré"):
            validate(files)

    def test_registre_append_only_modifie_est_refuse(self) -> None:
        files = dict(build_files())
        lines = files["evidence-register.jsonl"].splitlines()
        first = json.loads(lines[0])
        first["record_type"] = "altered"
        lines[0] = canonical(first).rstrip(b"\n")
        files["evidence-register.jsonl"] = b"\n".join(lines) + b"\n"

        with self.assertRaisesRegex(InvalidProof, "append-only"):
            validate(files)

    def test_calculs_figes_couvrent_tentatives_absence_et_latence(self) -> None:
        cost = calculate_cost(
            [
                {"supplier_spend": "0"},
                {"supplier_spend": "0"},
            ],
            1,
        )
        undefined = calculate_cost([{"supplier_spend": "0"}], 0)
        complete = calculate_latency(
            {"request": 0, "automatic": 1, "human": 2}
        )
        missing = calculate_latency(
            {"request": 0, "automatic": 1, "human": None}
        )

        self.assertEqual(2, cost["attempt_count"])
        self.assertEqual("0", cost["supplier_spend_total"])
        self.assertEqual("0", cost["supplier_cost_per_officially_acceptable"])
        self.assertIsNone(
            undefined["supplier_cost_per_officially_acceptable"]
        )
        self.assertEqual(1, complete["configuration_latency_logical_ticks"])
        self.assertEqual(2, complete["official_decision_delay_logical_ticks"])
        self.assertIsNone(
            missing["official_decision_delay_logical_ticks"]
        )

    def test_secret_potentiel_est_refuse(self) -> None:
        files = dict(build_files())
        files["closure.md"] += b"\nTOKEN=" + (b"x" * 22) + b"\n"

        with self.assertRaisesRegex(InvalidProof, "secret potentiel"):
            validate(files)


if __name__ == "__main__":
    unittest.main()
