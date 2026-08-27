# /// script
# requires-python = ">=3.12"
# ///
"""Contrôles XS-03 : aperçu des autorisations avant toute action distante."""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

from tests._helpers_v1 import retirer_couverture_publiee  # noqa: E402

IDS_OFFICIELS = (
    "antigravity-gemini-3-7-flash",
    "claude-code-fable-5",
    "claude-code-opus-5",
    "codex-gpt-5-6-sol",
    "cursor-kimi-k3",
    "grok-build-grok-4-6",
    "zai-glm-5-3",
)


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS03(unittest.TestCase):
    """Racine isolée portant une copie byte-identique du registre officiel."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        shutil.copytree(
            RACINE / M.REGISTRE_OFFICIEL, self.racine / M.REGISTRE_OFFICIEL
        )


class ApercuAutorisationsTests(BaseXS03):
    def test_panel_complet_sept_configurations_et_six_categories(self):
        code, sortie = _principal(["autorisations"], self.racine)
        self.assertEqual(code, 0, sortie)
        for identifiant in IDS_OFFICIELS:
            self.assertIn(f"configuration : {identifiant}", sortie)
        for categorie in (
            "compte concerné :",
            "plan :",
            "authentification interactive exigée :",
            "quota engagé",
            "dépense engagée :",
        ):
            with self.subTest(categorie=categorie):
                self.assertEqual(sortie.count(categorie), 7, sortie)

    def test_filtre_identifiant_exact_ne_rend_que_cette_configuration(self):
        code, sortie = _principal(
            ["autorisations", "--configuration", "claude-code-fable-5"], self.racine
        )
        self.assertEqual(code, 0, sortie)
        self.assertIn("configuration : claude-code-fable-5", sortie)
        self.assertEqual(sortie.count("configuration : "), 1)
        for autre in IDS_OFFICIELS:
            if autre != "claude-code-fable-5":
                self.assertNotIn(autre, sortie)

    def test_identifiant_absent_rend_un_et_nomme_la_configuration_fautive(self):
        code, sortie = _principal(
            ["autorisations", "--configuration", "configuration-fantome"], self.racine
        )
        self.assertEqual(code, 1)
        self.assertIn("configuration-fantome", sortie)

    def test_forme_cli_hors_contrat_rend_deux_et_affiche_l_usage(self):
        for arguments in (
            ["autorisations", "--configuration"],
            ["autorisations", "--autre", "x"],
            ["autorisations", "claude-code-fable-5"],
        ):
            with self.subTest(arguments=arguments):
                code, sortie = _principal(arguments, self.racine)
                self.assertEqual(code, 2)
                self.assertIn("usage", sortie)


class SemantiqueMswTests(BaseXS03):
    def test_compte_concerne_reste_inconnu_sans_substitution(self):
        code, sortie = _principal(["autorisations"], self.racine)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.count("compte concerné : INCONNU"), 7, sortie)
        # Ni le produit, ni le plan, ni configuration_id ne deviennent un compte
        for substitution in (
            "compte concerné : Claude Code",
            "compte concerné : claude-code-fable-5",
            "compte concerné : Z.AI",
        ):
            self.assertNotIn(substitution, sortie)

    def test_plan_reprend_plan_nom_declare(self):
        code, sortie = _principal(
            ["autorisations", "--configuration", "zai-glm-5-3"], self.racine
        )
        self.assertEqual(code, 0, sortie)
        self.assertIn("plan : Z.AI Coding Plan", sortie)

    def test_conservation_champ_par_champ_de_inconnu(self):
        code, sortie = _principal(["autorisations"], self.racine)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(
            sortie.count("authentification interactive exigée : INCONNU"), 7, sortie
        )
        for champ_quota in (
            "unite=INCONNU",
            "valeur=INCONNU",
            "portee=INCONNU",
            "reset_fenetre=INCONNU",
            "reset_ancrage=INCONNU",
            "reset_au_depassement=INCONNU",
        ):
            with self.subTest(champ=champ_quota):
                self.assertEqual(sortie.count(champ_quota), 7, sortie)
        self.assertEqual(
            sortie.count(
                "dépense engagée : prix_montant=INCONNU | prix_devise=INCONNU "
                "| periode=INCONNU"
            ),
            7,
            sortie,
        )
        # L'absence d'achat nouveau ne devient jamais zéro ni gratuité
        for interdit in ("prix_montant=0", "gratuit", "0 INCONNU"):
            self.assertNotIn(interdit, sortie)


class FrontiereReseauTests(BaseXS03):
    """Le réseau est une frontière système : le chemin public n'en appelle aucune."""

    def test_chemin_public_sans_primitive_de_connexion(self):
        import socket
        from unittest import mock

        def primitive_interdite(*args, **kwargs):
            raise AssertionError(
                "primitive de connexion appelée sur le chemin public autorisations"
            )

        with (
            mock.patch.object(socket, "socket", primitive_interdite),
            mock.patch.object(socket, "create_connection", primitive_interdite),
            mock.patch.object(socket, "getaddrinfo", primitive_interdite),
        ):
            code, sortie = _principal(["autorisations"], self.racine)
            self.assertEqual(code, 0, sortie)
            code, sortie = _principal(
                ["autorisations", "--configuration", "claude-code-fable-5"],
                self.racine,
            )
            self.assertEqual(code, 0, sortie)


_ENTREES_RESTITUTION = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES) + (
    M.CHEMIN_ETAT.as_posix(),
)


class RestitutionAutorisationsTests(BaseXS03):
    """Section HTML autorisations fidèle aux mêmes entrées du registre officiel."""

    def setUp(self):
        super().setUp()
        for relatif in _ENTREES_RESTITUTION:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        self.page = self.racine / M.CHEMIN_PAGE

    def _restituer(self) -> str:
        code, sortie = _principal(["restituer"], self.racine)
        self.assertEqual(code, 0, sortie)
        return self.page.read_text(encoding="utf-8")

    def test_section_html_porte_les_sept_entrees_d_autorisations(self):
        page = self._restituer()
        self.assertIn('<section id="autorisations">', page)
        self.assertEqual(page.count(' data-autorisation="'), 7)
        for identifiant in IDS_OFFICIELS:
            self.assertIn(f'data-autorisation="{identifiant}"', page)

    def test_section_html_fidele_aux_valeurs_declarees(self):
        page = self._restituer()
        self.assertEqual(page.count("compte concerné : <code>INCONNU</code>"), 7)
        self.assertIn("plan : <code>Z.AI Coding Plan</code>", page)
        self.assertIn(
            "authentification interactive exigée : <code>INCONNU</code>", page
        )
        self.assertIn("prix_montant <code>INCONNU</code>", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_verifier_refuse_une_divergence_injectee_dans_la_section(self):
        page = self._restituer()
        divergente = page.replace(
            "compte concerné : <code>INCONNU</code>",
            "compte concerné : <code>compte-actif</code>",
            1,
        )
        self.assertNotEqual(divergente, page)
        self.page.write_text(divergente, encoding="utf-8")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)
        self.page.write_text(page, encoding="utf-8")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_verifier_refuse_une_huitieme_autorisation_injectee(self):
        page = self._restituer()
        self.page.write_text(
            page.replace(
                "</body>",
                '<article class="affirmation" data-classe="fait" '
                'data-autorisation="huitieme"><p>entrée injectée</p></article></body>',
            ),
            encoding="utf-8",
        )
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)


if __name__ == "__main__":
    unittest.main()
