# /// script
# requires-python = ">=3.12"
# dependencies = ["mpmath==1.3.0"]
# ///
"""Contrôle pur de la séparation des contextes du vérificateur v5"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import verifier_pentagone_v5 as V  # noqa: E402
import verifier_pentagone_v6 as V6  # noqa: E402


class PageFausse:
    def __init__(self):
        self.cache = {}
        self.historique = []
        self.fermee = False

    def close(self):
        self.fermee = True


def evaluer_dependant_ordre(page: PageFausse, instants):
    resultats = []
    for instant in instants:
        t = float(instant)
        if t not in page.cache:
            rang = len(page.historique) + 1
            page.historique.append(t)
            page.cache[t] = [t + rang * 1e-6, -t + rang * 2e-6]
        resultats.append(list(page.cache[t]))
    return resultats


class VerifierPentagoneV5Tests(unittest.TestCase):
    def test_ordre_inverse_utilise_un_contexte_neuf(self):
        initiale = PageFausse()
        nouvelles = []

        def nouvelle_page(_nav, _html):
            page = PageFausse()
            nouvelles.append(page)
            return page

        ordre = [0, 1, 2, 3]
        with patch.object(V, "_evaluer", side_effect=evaluer_dependant_ordre), \
             patch.object(V, "_page", side_effect=nouvelle_page):
            a1, a2, inverse, a3 = V._mesurer_determinisme(
                object(), initiale, "<html></html>", ordre
            )

        self.assertTrue(initiale.fermee)
        self.assertEqual(len(nouvelles), 2)
        self.assertTrue(all(page.fermee for page in nouvelles))
        self.assertEqual(a1, a2)
        self.assertEqual(a1, a3)
        self.assertNotEqual(a1, list(reversed(inverse)))
        self.assertEqual(V.VERIFY_VERSION, "verify-v5")

    def test_v6_horizon_long_s_arrete_au_confinement_75(self):
        card_id = "pentagone-horizons-longs"
        predicates = {name: True for name in V6.PREDICATS_V5[card_id]}
        result = V6._score_niveaux(card_id, predicates, None, {})
        self.assertEqual(V6.VERIFY_VERSION, "verify-v6")
        self.assertNotIn("E75_PRECISION", result["predicates"])
        self.assertEqual(result["niveau"], 5)
        self.assertEqual(result["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
