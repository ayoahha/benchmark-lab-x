# /// script
# requires-python = ">=3.12"
# ///
"""Contrôles XS-05 : qualification du harnais V1 sur les témoins approuvés."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import unittest
import tempfile
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

_PAQUET = (
    "tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json",
    "tasks/dev/pre-cadrage-entretien-client/brief-proprietaire.md",
    "tasks/dev/pre-cadrage-entretien-client/registre-verite.md",
    "tasks/dev/pre-cadrage-entretien-client/stimulus.md",
    "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md",
)

CHEMIN_RECU = (
    "tasks/dev/pre-cadrage-entretien-client/campagne-v1/"
    "qualification-harnais-v1/recu-qualification.json"
)


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS05(unittest.TestCase):
    """Racine isolée : paquet approuvé complet et état V1."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        for relatif in (*_PAQUET, M.CHEMIN_ETAT.as_posix()):
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        self.recu = self.racine / CHEMIN_RECU

    def _qualifier(self) -> tuple[int, str]:
        return _principal(["qualifier"], self.racine)

    def _lire_recu(self) -> dict:
        return json.loads(self.recu.read_text(encoding="utf-8"))


class QualifierTests(BaseXS05):
    def test_qualifier_rend_zero_imprime_pass_et_ecrit_le_recu(self):
        code, sortie = self._qualifier()
        self.assertEqual(code, 0, sortie)
        self.assertIn("PASS", sortie)
        self.assertTrue(self.recu.is_file())
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "PASS")

    def test_recu_porte_les_champs_requis_du_contrat(self):
        import hashlib
        import platform

        code, sortie = self._qualifier()
        self.assertEqual(code, 0, sortie)
        recu = self._lire_recu()
        self.assertEqual(
            recu["schema_version"], "campagne-v1-qualification-harnais/v1"
        )
        # Date ISO 8601 UTC, lisible par la restitution
        self.assertRegex(
            recu["date_qualification"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        )
        self.assertEqual(
            recu["commande_publique"], "uv run tools/campagne_v1.py qualifier"
        )
        self.assertEqual(
            recu["commande_suite"],
            "uv run pytest tests/test_campagne_v1_qualification.py -q",
        )
        # Pin déclaré compatible uv run, et identité exacte observée
        self.assertEqual(recu["interpreteur"]["pin"], ">=3.12")
        self.assertEqual(
            recu["interpreteur"]["observe"],
            f"{platform.python_implementation()} {platform.python_version()}",
        )
        # Chemin et SHA-256 du validateur réellement exécuté
        self.assertEqual(
            recu["validateur"]["chemin"], "tools/validateur_pre_cadrage_v0.py"
        )
        self.assertEqual(
            recu["validateur"]["sha256"],
            hashlib.sha256(
                (RACINE / "tools/validateur_pre_cadrage_v0.py").read_bytes()
            ).hexdigest(),
        )
        # Source et cardinalité des seize témoins approuvés
        temoins = recu["temoins"]
        self.assertEqual(
            temoins["source"],
            "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md",
        )
        self.assertEqual(
            temoins["sha256"],
            hashlib.sha256(
                (self.racine / temoins["source"]).read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(temoins["cardinalite"], 16)
        self.assertEqual(len(temoins["noms"]), 16)
        self.assertEqual(len(set(temoins["noms"])), 16)
        self.assertIn("WT-ACCEPTABLE", temoins["noms"])
        self.assertIn("WT-HARNESS", temoins["noms"])
        # Les deux décisions figées restent des entrées, jamais rejouées
        self.assertEqual(
            recu["decisions_figees"],
            {
                "route_evaluation_v0": "USE_MANUAL",
                "plateforme_specifique": "STOP_SPECIFIC_PLATFORM",
            },
        )

    def test_recu_json_deterministe_sans_adresse_de_contenu(self):
        code, _ = self._qualifier()
        self.assertEqual(code, 0)
        texte = self.recu.read_text(encoding="utf-8")
        recu = json.loads(texte)
        # Sérialisation déterministe et lisible, sans self-hash ni racine de preuve
        self.assertEqual(
            texte,
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        for interdit in ("content_address", "proof_root", "self_hash"):
            self.assertNotIn(interdit, recu)

    def test_temoin_altere_rend_non_zero_et_nomme_le_temoin(self):
        # Altère le matériau du témoin WT-VOCABULAIRE dans la sortie canonique :
        # son delta exact ne s'applique plus, le témoin altéré est nommé
        chemin_temoins = (
            self.racine
            / "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md"
        )
        texte = chemin_temoins.read_text(encoding="utf-8")
        bloc = texte.split("```markdown\n", 1)[1].split("\n```", 1)[0]
        bloc_altere = bloc.replace(
            "qualification: QUALIFIABLE", "qualification: QUALIFIE", 1
        )
        self.assertNotEqual(bloc, bloc_altere)
        chemin_temoins.write_text(
            texte.replace(bloc, bloc_altere, 1), encoding="utf-8"
        )
        code, sortie = self._qualifier()
        self.assertNotEqual(code, 0)
        self.assertIn("WT-VOCABULAIRE", sortie)
        self.assertNotIn("verdict : PASS", sortie)
        self.assertFalse(self.recu.exists())

    def test_temoin_divergent_rend_non_zero_sans_ecrire_de_recu(self):
        # Un paquet dont un fichier diverge des empreintes approuvées rend le
        # dispositif incapable d'établir PASS : le premier témoin divergent est
        # nommé et le reçu existant reste inchangé
        self.assertEqual(self._qualifier()[0], 0)
        octets_avant = self.recu.read_bytes()
        brief = (
            self.racine
            / "tasks/dev/pre-cadrage-entretien-client/brief-proprietaire.md"
        )
        brief.write_bytes(brief.read_bytes() + b"\n")
        code, sortie = self._qualifier()
        self.assertNotEqual(code, 0)
        self.assertIn("WT-ACCEPTABLE", sortie)
        self.assertIn("HARNESS_ERROR", sortie)
        self.assertNotIn("verdict : PASS", sortie)
        self.assertEqual(self.recu.read_bytes(), octets_avant)

    def test_incompatibilite_interpreteur_produit_harness_error_jamais_fail(self):
        from unittest import mock

        # Frontière système simulée : interpréteur observé sous le pin >=3.12
        with (
            mock.patch.object(
                M.platform, "python_version_tuple", return_value=("3", "11", "9")
            ),
            mock.patch.object(
                M.platform, "python_version", return_value="3.11.9"
            ),
        ):
            code, sortie = self._qualifier()
        self.assertNotEqual(code, 0)
        self.assertIn("HARNESS_ERROR", sortie)
        # F-08 : jamais pris pour un échec candidat
        self.assertNotIn("FAIL", sortie)
        self.assertIn(">=3.12", sortie)
        self.assertIn("3.11.9", sortie)
        self.assertFalse(self.recu.exists())

    def test_forme_cli_hors_contrat_rend_deux(self):
        for arguments in (["qualifier", "extra"], ["qualifier", "--force"]):
            with self.subTest(arguments=arguments):
                code, sortie = _principal(arguments, self.racine)
                self.assertEqual(code, 2)
                self.assertIn("usage", sortie)


_SOURCES_RESTITUTION = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES)


class RestitutionQualificationTests(BaseXS05):
    """Section MSW de qualification : date, verdict et commande exacte sourcés."""

    def setUp(self):
        super().setUp()
        for relatif in _SOURCES_RESTITUTION:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        shutil.copytree(
            RACINE / M.REGISTRE_OFFICIEL, self.racine / M.REGISTRE_OFFICIEL
        )
        self.page = self.racine / M.CHEMIN_PAGE

    def _restituer(self) -> str:
        code, sortie = _principal(["restituer"], self.racine)
        self.assertEqual(code, 0, sortie)
        return self.page.read_text(encoding="utf-8")

    def test_page_affiche_date_verdict_et_commande_exacte_sources(self):
        import hashlib

        self.assertEqual(self._qualifier()[0], 0)
        recu = self._lire_recu()
        page = self._restituer()
        self.assertIn('<section id="qualification-harnais">', page)
        self.assertIn(recu["date_qualification"], page)
        self.assertIn("PASS", page)
        self.assertIn("uv run tools/campagne_v1.py qualifier", page)
        # Fait MSW sourcé par le reçu de qualification versionné
        relatif = CHEMIN_RECU
        empreinte = hashlib.sha256(self.recu.read_bytes()).hexdigest()
        self.assertIn(
            f'data-chemin="{relatif}" data-sha256="{empreinte}"', page
        )
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_sans_recu_la_page_reste_conforme_sans_section(self):
        page = self._restituer()
        self.assertNotIn('<section id="qualification-harnais">', page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_restitutions_successives_byte_identiques_avec_recu(self):
        self.assertEqual(self._qualifier()[0], 0)
        self.assertEqual(self._restituer(), self._restituer())

    def test_verifier_refuse_une_date_divergente_puis_accepte_restauree(self):
        self.assertEqual(self._qualifier()[0], 0)
        recu = self._lire_recu()
        page = self._restituer()
        alteree = page.replace(
            recu["date_qualification"], "1970-01-01T00:00:00Z"
        )
        self.assertNotEqual(alteree, page)
        self.page.write_text(alteree, encoding="utf-8")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)
        self.page.write_text(page, encoding="utf-8")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_verifier_refuse_un_recu_altere_apres_restitution(self):
        self.assertEqual(self._qualifier()[0], 0)
        self._restituer()
        self.recu.write_bytes(self.recu.read_bytes() + b" ")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def test_verifier_refuse_une_section_qualification_injectee(self):
        page = self._restituer()
        self.page.write_text(
            page.replace(
                "</body>",
                '<article class="affirmation" data-classe="fait" '
                'data-qualification-harnais="PASS"><p>qualification inventée</p>'
                "</article></body>",
            ),
            encoding="utf-8",
        )
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)


if __name__ == "__main__":
    unittest.main()
