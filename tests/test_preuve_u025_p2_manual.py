from __future__ import annotations

from copy import deepcopy
import unittest

from tools import preuve_u025_p2_manual as p2


class PreuveU025P2ManualTests(unittest.TestCase):
    def test_lock_exige_les_deux_roles_ayo(self) -> None:
        lock = p2.lock_value(
            p2.GIT_BASE,
            "2026-08-16T00:00:00+00:00",
            "case-index-sha256",
        )
        p2.validate_lock(lock)

        for field in ("manual_reviewer", "manual_method_owner"):
            with self.subTest(field=field):
                divergent = deepcopy(lock)
                divergent[field] = "CURRENT_CODEX_SESSION"
                with self.assertRaises(p2.InvalidProof):
                    p2.validate_lock(divergent)

    def test_inventaire_et_ordre_des_seize_cas_sont_geles(self) -> None:
        fixtures, _, _ = p2.load_p1()
        index = p2.case_index_value(fixtures)

        self.assertEqual(16, len(index["cases"]))
        self.assertEqual(
            p2.CASE_ORDER,
            tuple(value["case_id"] for value in index["cases"]),
        )

    def test_dossier_aveugle_ne_contient_que_les_trois_objets(self) -> None:
        dossier = p2.blind_dossier("stimulus", "sortie", "rubrique")

        p2.assert_blind_dossier(dossier)
        self.assertEqual(
            {"stimulus", "SORTIE-A", "rubrique HR-001"},
            set(dossier),
        )

    def test_dossier_aveugle_refuse_un_case_id(self) -> None:
        dossier = p2.blind_dossier(
            "stimulus", "sortie WT-ACCEPTABLE", "rubrique"
        )

        with self.assertRaises(p2.InvalidProof):
            p2.assert_blind_dossier(dossier)

    def test_combinaison_finale_est_strictement_mecanique(self) -> None:
        observations = {
            ("PASS", "ACCEPTABLE"): "OFFICIALLY_ACCEPTABLE",
            ("FAIL", None): "CANDIDATE_NOT_ACCEPTABLE",
            ("PASS", "NOT_ACCEPTABLE"): "CANDIDATE_NOT_ACCEPTABLE",
            ("HARNESS_ERROR", None): "HARNESS_ERROR",
            ("PASS", "UNABLE_TO_JUDGE"): "UNABLE_TO_JUDGE",
        }

        for inputs, expected in observations.items():
            with self.subTest(inputs=inputs):
                self.assertEqual(expected, p2.combine(*inputs))

        with self.assertRaises(p2.InvalidProof):
            p2.combine("PASS", None)

    def test_lock_refuse_toute_autorisation_externe(self) -> None:
        lock = p2.lock_value(
            p2.GIT_BASE,
            "2026-08-16T00:00:00+00:00",
            "case-index-sha256",
        )
        lock["authorizations"]["candidate_call"] = True

        with self.assertRaises(p2.InvalidProof):
            p2.validate_lock(lock)


if __name__ == "__main__":
    unittest.main()
