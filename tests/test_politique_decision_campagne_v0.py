from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.valider_politique_decision_campagne_v0 import (
    EMPREINTE_POLITIQUE_ATTENDUE,
    main,
    valider_politique_decision_campagne_v0,
)


RACINE = Path(__file__).resolve().parents[1]
POLITIQUE = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "politique-decision-v1/politique-decision.json"
)


class PolitiqueDecisionCampagneV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(POLITIQUE.read_bytes())

    def _rejete(self, document: dict[str, object]) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "politique.json"
            chemin.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertNotEqual(0, main([str(chemin)]))

    def test_politique_canonique_est_valide(self) -> None:
        recu = valider_politique_decision_campagne_v0()

        self.assertEqual("POLITIQUE_DECISION_CAMPAGNE_V0_OK", recu["status"])
        self.assertEqual(EMPREINTE_POLITIQUE_ATTENDUE, recu["policy_sha256"])
        self.assertEqual(3, recu["pareto_axis_count"])
        self.assertEqual(6, recu["abstention_case_count"])
        self.assertEqual("ABSENT_VOLUNTARILY", recu["owner_preference"])

    def test_rejette_budget_implicite_ou_autorisation_de_depense(self) -> None:
        for cle, valeur in (
            ("effect", "FILTER_ABOVE_ZERO"),
            ("authorizes_execution_or_spend", "YES"),
        ):
            document = deepcopy(self.document)
            document["decision_budget"][cle] = valeur
            with self.subTest(cle=cle):
                self._rejete(document)

    def test_rejette_ttl_ou_comparaison_trans_evenement(self) -> None:
        mutations = []
        ttl = deepcopy(self.document)
        ttl["freshness"]["day_threshold"] = 30
        mutations.append(ttl)
        trans_evenement = deepcopy(self.document)
        trans_evenement["freshness"]["material_change_effect"] = "CONTINUE"
        mutations.append(trans_evenement)

        for document in mutations:
            self._rejete(document)

    def test_rejette_agregat_ou_generalisation_de_latence_n1(self) -> None:
        mutations = []
        mediane = deepcopy(self.document)
        mediane["latency"]["report"] = "MEDIAN"
        mutations.append(mediane)
        generalisation = deepcopy(self.document)
        generalisation["latency"]["n1_interpretation"] = "GENERALIZABLE"
        mutations.append(generalisation)

        for document in mutations:
            self._rejete(document)

    def test_rejette_axes_desordonnes_couverture_ou_score_global(self) -> None:
        mutations = []
        axes = deepcopy(self.document)
        axes["pareto"]["axes"][0], axes["pareto"]["axes"][1] = (
            axes["pareto"]["axes"][1],
            axes["pareto"]["axes"][0],
        )
        mutations.append(axes)
        couverture = deepcopy(self.document)
        couverture["pareto"]["coverage_is_axis"] = "YES"
        mutations.append(couverture)
        score = deepcopy(self.document)
        score["pareto"]["global_score"] = "ALLOWED"
        mutations.append(score)

        for document in mutations:
            self._rejete(document)

    def test_rejette_preference_inventee_ou_gagnant_sans_preference(self) -> None:
        mutations = []
        preference = deepcopy(self.document)
        preference["pareto"]["preference"] = "LOWEST_COST"
        mutations.append(preference)
        gagnant = deepcopy(self.document)
        gagnant["pareto"]["unique_winner_without_explicit_sufficient_preference"] = "ALLOWED"
        mutations.append(gagnant)

        for document in mutations:
            self._rejete(document)

    def test_rejette_imputation_inconnu_ou_non_defini(self) -> None:
        mutations = []
        cout = deepcopy(self.document)
        cout["missing_value_rules"]["missing_attributable_provider_cost"] = 0
        mutations.append(cout)
        ratio = deepcopy(self.document)
        ratio["missing_value_rules"]["zero_acceptable_outputs_cost_metric"] = 0
        mutations.append(ratio)

        for document in mutations:
            self._rejete(document)

    def test_rejette_promotion_attendu_ou_decide_en_observation(self) -> None:
        document = deepcopy(self.document)
        document["evidence_states"]["promotion_expected_or_decided_to_observed"] = "ALLOWED"

        self._rejete(document)

    def test_rejette_cas_abstention_manquant_ou_effet_divergent(self) -> None:
        manquant = deepcopy(self.document)
        manquant["abstention_cases"].pop()
        effet = deepcopy(self.document)
        effet["abstention_cases"][4]["effect"] = "RECOMMEND"

        self._rejete(manquant)
        self._rejete(effet)

    def test_rejette_autorisation_execution_quota_acquisition_ou_m6_6(self) -> None:
        for cle in ("execution", "spend_or_quota", "acquisition", "provider_operation", "m6_6"):
            document = deepcopy(self.document)
            document["authorizations"][cle] = "GRANTED"
            with self.subTest(cle=cle):
                self._rejete(document)

    def test_rejette_autorite_predecesseur_ou_champ_supplementaire(self) -> None:
        autorite = deepcopy(self.document)
        autorite["owner_authorities"]["owner_acceptance"]["author"] = "other"
        predecesseur = deepcopy(self.document)
        predecesseur["predecessor_artifacts"]["m6_4_acquisition_plan"]["sha256"] = "0" * 64
        champ = deepcopy(self.document)
        champ["unexpected"] = True

        self._rejete(autorite)
        self._rejete(predecesseur)
        self._rejete(champ)


if __name__ == "__main__":
    unittest.main()
