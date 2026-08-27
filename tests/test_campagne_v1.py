# /// script
# requires-python = ">=3.12"
# ///
"""Contrôles de la restitution humaine V1 vide et de son vérificateur."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

from tests._helpers_v1 import retirer_couverture_publiee  # noqa: E402

_ENTREES = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES) + (
    M.CHEMIN_ETAT.as_posix(),
)


class CampagneV1Tests(unittest.TestCase):
    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        for relatif in _ENTREES:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        self.page = self.racine / M.CHEMIN_PAGE

    def _restituer(self) -> bytes:
        self.assertEqual(M.restituer(self.racine), 0)
        return self.page.read_bytes()

    def _verifier_apres_injection(self, originale: str, modifiee: str) -> None:
        self.page.write_text(modifiee, encoding="utf-8")
        self.assertNotEqual(M.verifier_restitution(self.racine), 0)
        self.page.write_text(originale, encoding="utf-8")
        self.assertEqual(M.verifier_restitution(self.racine), 0)

    def test_restitutions_successives_byte_identiques(self):
        premiere = self._restituer()
        seconde = self._restituer()
        self.assertEqual(premiere, seconde)

    def test_repertoire_recus_present_et_vide_apres_restituer(self):
        self._restituer()
        repertoire = (
            self.racine
            / "tasks/dev/pre-cadrage-entretien-client/campagne-v1/recus-v1"
        )
        self.assertTrue(repertoire.is_dir())
        self.assertEqual(list(repertoire.iterdir()), [])

    def test_jetons_exacts_presents(self):
        page = self._restituer().decode("utf-8")
        for jeton in (
            "panel: vide",
            "acquisitions: 0",
            "conclusion: ABSTENTION",
            "INCONNU",
            "NON_DEFINI",
            "HARNESS_ERROR",
            "ABSTENTION",
        ):
            self.assertIn(jeton, page)

    def test_six_etapes_futures_marquees_a_venir(self):
        page = self._restituer().decode("utf-8")
        self.assertEqual(page.count('data-marqueur="a-venir"'), 6)
        self.assertEqual(len(M.ETAPES_FUTURES), 6)

    def test_verifier_rend_zero_sur_page_produite(self):
        self._restituer()
        self.assertEqual(M.verifier_restitution(self.racine), 0)

    def test_verifier_rend_non_zero_apres_divergence_puis_restauration(self):
        page = self._restituer().decode("utf-8")
        self._verifier_apres_injection(
            page, page.replace("acquisitions: 0", "acquisitions: 1")
        )

    def test_refuse_affirmation_sans_classe_msw(self):
        page = self._restituer().decode("utf-8")
        self._verifier_apres_injection(
            page,
            page.replace(
                "</body>",
                '<article class="affirmation"><p>affirmation libre</p></article></body>',
            ),
        )

    def test_refuse_valeur_factuelle_sans_chemin_ni_empreinte(self):
        page = self._restituer().decode("utf-8")
        self._verifier_apres_injection(
            page,
            page.replace(
                "</body>",
                '<article class="affirmation" data-classe="fait">'
                "<p>valeur factuelle 42</p></article></body>",
            ),
        )

    def test_refuse_empreinte_citee_divergente(self):
        page = self._restituer().decode("utf-8")
        empreinte = M._sha256_fichier(self.racine / "docs/RULES.md")
        self._verifier_apres_injection(
            page, page.replace(empreinte, "0" * 64)
        )

    def test_refuse_source_modifiee_apres_restitution(self):
        self._restituer()
        rules = self.racine / "docs/RULES.md"
        rules.write_bytes(rules.read_bytes() + b"\n")
        self.assertNotEqual(M.verifier_restitution(self.racine), 0)

    def test_refuse_etape_sans_marqueur_a_venir(self):
        page = self._restituer().decode("utf-8")
        self._verifier_apres_injection(
            page, page.replace(' data-marqueur="a-venir"', "", 1)
        )

    def test_refuse_toute_ressource_distante(self):
        page = self._restituer().decode("utf-8")
        for injection in (
            "<script>alert(1)</script>",
            '<link rel="stylesheet">',
            '<img alt="">',
            'src="x.js"',
            "https://example.org",
            "http://example.org",
            '@import "x.css"',
            "url(x.png)",
        ):
            with self.subTest(injection=injection):
                self._verifier_apres_injection(
                    page, page.replace("</body>", injection + "</body>")
                )

    def test_recus_presents_bloquent_la_conclusion_xs01(self):
        self._restituer()
        recu = (
            self.racine
            / "tasks/dev/pre-cadrage-entretien-client/campagne-v1/recus-v1/recu.json"
        )
        recu.write_text("{}", encoding="utf-8")
        with self.assertRaises(M.ErreurRestitution):
            M.verifier_restitution(self.racine)

    def test_usage_invalide_rend_deux(self):
        self.assertEqual(M.principal([]), 2)
        self.assertEqual(M.principal(["autre"]), 2)


if __name__ == "__main__":
    unittest.main()
