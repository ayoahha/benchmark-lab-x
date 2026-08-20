from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from tools.valider_autorites_campagne_v0 import (
    EMPREINTE_FRAGMENT_ATTENDUE,
    ErreurAutorites,
    valider_autorites_campagne_v0,
)


RACINE = Path(__file__).resolve().parents[1]
FRAGMENT = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/autorites-v1/autorites.json"
)


class AutoritesCampagneV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(FRAGMENT.read_bytes())

    def _valider_mutation(self, document: dict[str, object]) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            fragment = Path(dossier) / "autorites.json"
            fragment.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ErreurAutorites):
                valider_autorites_campagne_v0(fragment)

    def test_fragment_canonique_est_valide(self) -> None:
        recu = valider_autorites_campagne_v0()

        self.assertEqual("AUTORITES_CAMPAGNE_V0_OK", recu["status"])
        self.assertEqual(EMPREINTE_FRAGMENT_ATTENDUE, recu["fragment_sha256"])

    def test_rejette_route_contraire_a_use_manual(self) -> None:
        document = deepcopy(self.document)
        document["authorities"]["evaluation_route"]["value"] = "USE_PROMPTFOO"

        self._valider_mutation(document)

    def test_rejette_plateforme_contraire_a_stop_specific_platform(self) -> None:
        document = deepcopy(self.document)
        document["authorities"]["specific_platform"]["value"] = (
            "CONTINUE_SPECIFIC_PLATFORM"
        )

        self._valider_mutation(document)

    def test_rejette_auto_router_contraire_a_excluded(self) -> None:
        document = deepcopy(self.document)
        document["authorities"]["auto_router"]["value"] = "INCLUDED"

        self._valider_mutation(document)

    def test_rejette_les_autres_constantes_contraires(self) -> None:
        mutations = {
            "profil": ("measurement_profile", "value", "subscription"),
            "formule": ("official_acceptability", "operator", "OR"),
            "pareto": ("pareto", "coverage", "FOURTH_AXIS"),
            "abstention": (
                "abstention",
                "unique_winner_without_sufficient_explicit_preference",
                "ALLOWED",
            ),
        }
        for nom, (autorite, champ, valeur) in mutations.items():
            with self.subTest(autorite=nom):
                document = deepcopy(self.document)
                document["authorities"][autorite][champ] = valeur
                self._valider_mutation(document)

    def test_rejette_reference_ou_hash_divergent(self) -> None:
        document = deepcopy(self.document)
        document["authorities"]["evaluation_route"]["decision"]["body_sha256"
        ] = "0" * 64

        self._valider_mutation(document)

    def test_rejette_champ_m6_2_ou_inconnu(self) -> None:
        document = deepcopy(self.document)
        document["authorities"]["panel"] = []

        self._valider_mutation(document)


if __name__ == "__main__":
    unittest.main()
