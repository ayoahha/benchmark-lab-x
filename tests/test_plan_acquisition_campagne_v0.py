from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.valider_plan_acquisition_campagne_v0 import (
    EMPREINTE_PLAN_ATTENDUE,
    main,
    valider_plan_acquisition_campagne_v0,
)


RACINE = Path(__file__).resolve().parents[1]
PLAN = RACINE / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/plan-acquisition-v1/plan-acquisition.json"


class PlanAcquisitionCampagneV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(PLAN.read_bytes())

    def _rejete(self, document: dict[str, object]) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "plan.json"
            chemin.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertNotEqual(0, main([str(chemin)]))

    def test_plan_canonique_est_valide(self) -> None:
        recu = valider_plan_acquisition_campagne_v0()
        self.assertEqual("PLAN_ACQUISITION_CAMPAGNE_V0_OK", recu["status"])
        self.assertEqual(EMPREINTE_PLAN_ATTENDUE, recu["plan_sha256"])
        self.assertEqual(2, recu["planned_acquisitions"])
        self.assertEqual(0, recu["automatic_retries"])

    def test_rejette_cardinalite_retry_replication_ou_fallback(self) -> None:
        for cle, valeur in (("planned_acquisitions", 3), ("replications", 1), ("automatic_retries", 1), ("manual_retries", 1), ("fallbacks", "AUTO")):
            document = deepcopy(self.document)
            document["acquisition_plan"][cle] = valeur
            with self.subTest(cle=cle):
                self._rejete(document)

    def test_rejette_slot_ou_stimulus_divergent(self) -> None:
        slot = deepcopy(self.document)
        slot["acquisition_plan"]["slots"][0]["count"] = 2
        stimulus = deepcopy(self.document)
        stimulus["acquisition_plan"]["stimulus"]["sha256"] = "0" * 64
        self._rejete(slot)
        self._rejete(stimulus)

    def test_rejette_effet_incident_divergent(self) -> None:
        document = deepcopy(self.document)
        document["incident_policy"]["harness_error"]["effect"] = "CONTINUE_CAMPAIGN"
        self._rejete(document)

    def test_rejette_promotion_observation(self) -> None:
        document = deepcopy(self.document)
        document["evidence_states"]["future_observations"]["provider_cost"]["value"] = 0
        self._rejete(document)

    def test_rejette_prix_route_invente_ou_prix_direct_applicable(self) -> None:
        prix = deepcopy(self.document)
        prix["pricing"]["grok_build"]["route_unit_price"] = "1.00_USD"
        direct = deepcopy(self.document)
        direct["pricing"]["kimi_cursor"]["moonshot_direct_api_price"] = "APPLICABLE"
        self._rejete(prix)
        self._rejete(direct)

    def test_rejette_sel_ordre_ou_engagement_anticipe(self) -> None:
        for cle, valeur in (("salt_material_present", True), ("order_mapping_present", True), ("salt", "secret")):
            document = deepcopy(self.document)
            document["blind_order"][cle] = valeur
            with self.subTest(cle=cle):
                self._rejete(document)

    def test_rejette_dimension_m6_5_manquante(self) -> None:
        document = deepcopy(self.document)
        document["exclusions"]["m6_5_dimensions"].remove("LATENCY")
        self._rejete(document)

    def test_rejette_autorite_ou_predecesseur_divergent(self) -> None:
        autorite = deepcopy(self.document)
        autorite["owner_authorities"]["owner_acceptance"]["author"] = "other"
        predecesseur = deepcopy(self.document)
        predecesseur["predecessor_artifacts"]["m6_3_panel_identities"]["sha256"] = "0" * 64
        self._rejete(autorite)
        self._rejete(predecesseur)

    def test_rejette_champ_supplementaire(self) -> None:
        document = deepcopy(self.document)
        document["unexpected"] = True
        self._rejete(document)


if __name__ == "__main__":
    unittest.main()
