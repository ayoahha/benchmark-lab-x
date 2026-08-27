# /// script
# requires-python = ">=3.12,<3.13"
# ///
"""Contrôles XS-05 : qualification du harnais V1 sur les témoins approuvés."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import sys
import unittest
import tempfile
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

from tests._helpers_v1 import retirer_couverture_publiee  # noqa: E402

_PAQUET = (
    "tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json",
    "tasks/dev/pre-cadrage-entretien-client/brief-proprietaire.md",
    "tasks/dev/pre-cadrage-entretien-client/registre-verite.md",
    "tasks/dev/pre-cadrage-entretien-client/stimulus.md",
    "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md",
)

# Instrument et suite immuables, rejoués depuis la racine fournie
_INSTRUMENT = (
    "tools/validateur_pre_cadrage_v0.py",
    "tests/test_validateur_pre_cadrage_v0.py",
)

CHEMIN_RECU = (
    "tasks/dev/pre-cadrage-entretien-client/campagne-v1/"
    "qualification-harnais-v1/recu-qualification.json"
)

# Empreinte approuvée de la source des seize témoins, entrée figée du contrat
EMPREINTE_TEMOINS = (
    "8a419c5950127c8187119545237f32b0ecb9b0062116afc3421e0c96a00bd011"
)

# Identité CPython 3.12 concrète simulée pour la frontière système des tests
VERSION_SIMULEE = "3.12.13"


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS05(unittest.TestCase):
    """Racine isolée : paquet approuvé, état V1, validateur et suite immuables."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        for relatif in (*_PAQUET, *_INSTRUMENT, M.CHEMIN_ETAT.as_posix()):
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        self.recu = self.racine / CHEMIN_RECU
        self.temoins = (
            self.racine
            / "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md"
        )
        self.validateur = self.racine / "tools/validateur_pre_cadrage_v0.py"
        self.suite = self.racine / "tests/test_validateur_pre_cadrage_v0.py"

    def _qualifier(self) -> tuple[int, str]:
        # La suite tourne par la commande figée de l'Issue sous l'interpréteur
        # hôte : la frontière système est simulée à un CPython 3.12 concret ;
        # les tests dédiés d'incompatibilité posent leurs propres valeurs.
        # La validation runtime de production reste intacte et le
        # sous-processus de suite s'exécute réellement sous CPython 3.12
        with (
            mock.patch.object(
                M.platform, "python_implementation", return_value="CPython"
            ),
            mock.patch.object(
                M.platform, "python_version", return_value=VERSION_SIMULEE
            ),
            mock.patch.object(
                M.platform,
                "python_version_tuple",
                return_value=tuple(VERSION_SIMULEE.split(".")),
            ),
        ):
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
        # Commande de suite portable exactement égale à l'exécution réelle
        self.assertEqual(
            recu["commande_suite"],
            "uv run --python 3.12 python -m unittest "
            "tests.test_validateur_pre_cadrage_v0",
        )
        # Pin exact CPython 3.12 et identité exacte observée
        self.assertEqual(recu["interpreteur"]["pin"], "CPython 3.12")
        self.assertEqual(
            recu["interpreteur"]["observe"], f"CPython {VERSION_SIMULEE}"
        )
        # Chemin et SHA-256 du validateur résolu depuis la racine fournie
        self.assertEqual(
            recu["validateur"]["chemin"], "tools/validateur_pre_cadrage_v0.py"
        )
        self.assertEqual(
            recu["validateur"]["sha256"],
            hashlib.sha256(self.validateur.read_bytes()).hexdigest(),
        )
        # Source et cardinalité des seize témoins approuvés
        temoins = recu["temoins"]
        self.assertEqual(
            temoins["source"],
            "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md",
        )
        self.assertEqual(temoins["sha256"], EMPREINTE_TEMOINS)
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

    def test_hash_du_validateur_vient_de_la_racine_fournie(self):
        # Le validateur de la racine diverge de l'immuable qualifié : la
        # qualification refuse HARNESS_ERROR au lieu de hacher le dépôt
        self.validateur.write_text(
            self.validateur.read_text(encoding="utf-8") + "\n# mutation\n",
            encoding="utf-8",
        )
        code, sortie = self._qualifier()
        self.assertNotEqual(code, 0)
        self.assertIn("verdict : HARNESS_ERROR", sortie)
        self.assertIn("tools/validateur_pre_cadrage_v0.py", sortie)
        self.assertNotIn("verdict : FAIL", sortie)
        self.assertFalse(self.recu.exists())

    def test_validateur_absent_de_la_racine_est_harness_error(self):
        self.validateur.unlink()
        code, sortie = self._qualifier()
        self.assertNotEqual(code, 0)
        self.assertIn("verdict : HARNESS_ERROR", sortie)
        self.assertIn("tools/validateur_pre_cadrage_v0.py", sortie)
        self.assertNotIn("verdict : FAIL", sortie)
        self.assertFalse(self.recu.exists())

    def test_suite_indisponible_est_harness_error_jamais_fail(self):
        self.suite.unlink()
        code, sortie = self._qualifier()
        self.assertNotEqual(code, 0)
        self.assertIn("verdict : HARNESS_ERROR", sortie)
        self.assertIn("tests/test_validateur_pre_cadrage_v0.py", sortie)
        self.assertNotIn("verdict : FAIL", sortie)
        self.assertFalse(self.recu.exists())

    def test_suite_en_echec_est_harness_error_jamais_fail(self):
        # Une suite de validation divergente ou en échec est un défaut du
        # dispositif : HARNESS_ERROR, jamais un FAIL candidat
        self.suite.write_text(
            "import unittest\n\n\n"
            "class EchecSimule(unittest.TestCase):\n"
            "    def test_echec(self):\n"
            "        self.fail('échec simulé de la suite')\n",
            encoding="utf-8",
        )
        code, sortie = self._qualifier()
        self.assertNotEqual(code, 0)
        self.assertIn("verdict : HARNESS_ERROR", sortie)
        self.assertNotIn("verdict : FAIL", sortie)
        self.assertFalse(self.recu.exists())

    def test_temoin_altere_rend_non_zero_et_nomme_le_temoin(self):
        # Altère le matériau du témoin WT-VOCABULAIRE dans la sortie canonique :
        # divergence de corpus nommant le témoin affecté, jamais un FAIL candidat
        texte = self.temoins.read_text(encoding="utf-8")
        bloc = texte.split("```markdown\n", 1)[1].split("\n```", 1)[0]
        bloc_altere = bloc.replace(
            "qualification: QUALIFIABLE", "qualification: QUALIFIE", 1
        )
        self.assertNotEqual(bloc, bloc_altere)
        self.temoins.write_text(
            texte.replace(bloc, bloc_altere, 1), encoding="utf-8"
        )
        code, sortie = self._qualifier()
        self.assertNotEqual(code, 0)
        self.assertIn("WT-VOCABULAIRE", sortie)
        self.assertIn("verdict : HARNESS_ERROR", sortie)
        self.assertNotIn("verdict : FAIL", sortie)
        self.assertFalse(self.recu.exists())

    def test_source_temoins_alteree_hors_delta_est_harness_error(self):
        # Altération qui ne casse aucun delta canonique : la source approuvée
        # elle-même est nommée, le verdict reste HARNESS_ERROR, jamais FAIL
        self.temoins.write_bytes(self.temoins.read_bytes() + b"\nnote ajoutee\n")
        code, sortie = self._qualifier()
        self.assertNotEqual(code, 0)
        self.assertIn("temoins-qualification.md", sortie)
        self.assertIn("verdict : HARNESS_ERROR", sortie)
        self.assertNotIn("verdict : FAIL", sortie)
        self.assertFalse(self.recu.exists())

    def test_fichier_du_paquet_divergent_est_harness_error(self):
        # Un fichier du paquet approuvé diverge : divergence de corpus nommée,
        # HARNESS_ERROR sans écrire ni réécrire de reçu
        self.assertEqual(self._qualifier()[0], 0)
        octets_avant = self.recu.read_bytes()
        brief = (
            self.racine
            / "tasks/dev/pre-cadrage-entretien-client/brief-proprietaire.md"
        )
        brief.write_bytes(brief.read_bytes() + b"\n")
        code, sortie = self._qualifier()
        self.assertNotEqual(code, 0)
        self.assertIn("brief-proprietaire.md", sortie)
        self.assertIn("verdict : HARNESS_ERROR", sortie)
        self.assertNotIn("verdict : FAIL", sortie)
        self.assertEqual(self.recu.read_bytes(), octets_avant)

    def test_incompatibilite_interpreteur_produit_harness_error_jamais_fail(self):
        # Frontière système posée par ce test seul, sans la fixture 3.12 :
        # interpréteur observé hors du pin exact CPython 3.12
        for version, version_tuple in (
            ("3.11.9", ("3", "11", "9")),
            ("3.14.2", ("3", "14", "2")),
        ):
            with self.subTest(version=version):
                with (
                    mock.patch.object(
                        M.platform,
                        "python_implementation",
                        return_value="CPython",
                    ),
                    mock.patch.object(
                        M.platform,
                        "python_version_tuple",
                        return_value=version_tuple,
                    ),
                    mock.patch.object(
                        M.platform, "python_version", return_value=version
                    ),
                ):
                    code, sortie = _principal(["qualifier"], self.racine)
                self.assertNotEqual(code, 0)
                self.assertIn("HARNESS_ERROR", sortie)
                # F-08 : jamais pris pour un échec candidat
                self.assertNotIn("FAIL", sortie)
                self.assertIn("CPython 3.12", sortie)
                self.assertIn(version, sortie)
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

    def _muter_recu(self, transformer) -> None:
        recu = self._lire_recu()
        transformer(recu)
        self.recu.write_text(
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_page_affiche_date_verdict_et_commande_exacte_sources(self):
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

    def test_decisions_figees_mutees_levent_erreur_restitution(self):
        self.assertEqual(self._qualifier()[0], 0)
        self._restituer()
        self._muter_recu(
            lambda recu: recu["decisions_figees"].update(
                {"route_evaluation_v0": "USE_AUTO"}
            )
        )
        with self.assertRaises(M.ErreurRestitution):
            M.verifier_restitution(self.racine)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)
        self.assertIn("decisions_figees", sortie)

    def test_champs_imbriques_invalides_levent_erreur_restitution(self):
        mutations = {
            "interpreteur-observe-vide": lambda recu: recu["interpreteur"].update(
                {"observe": ""}
            ),
            "interpreteur-pin-affaibli": lambda recu: recu["interpreteur"].update(
                {"pin": ">=3.10"}
            ),
            "validateur-hash-divergent": lambda recu: recu["validateur"].update(
                {"sha256": "0" * 64}
            ),
            "validateur-chemin-deplace": lambda recu: recu["validateur"].update(
                {"chemin": "tools/autre_validateur.py"}
            ),
            "temoins-hash-divergent": lambda recu: recu["temoins"].update(
                {"sha256": "f" * 64}
            ),
            "temoins-cardinalite-fausse": lambda recu: recu["temoins"].update(
                {"cardinalite": 15}
            ),
            "temoins-noms-tronques": lambda recu: recu["temoins"].update(
                {"noms": recu["temoins"]["noms"][:-1]}
            ),
            "temoins-table-vide": lambda recu: recu.update({"temoins": {}}),
            "interpreteur-non-table": lambda recu: recu.update(
                {"interpreteur": "CPython"}
            ),
        }
        for nom, transformer in mutations.items():
            with self.subTest(mutation=nom):
                if self.recu.exists():
                    self.recu.unlink()
                self.assertEqual(self._qualifier()[0], 0)
                self._restituer()
                self._muter_recu(transformer)
                with self.assertRaises(M.ErreurRestitution):
                    M.verifier_restitution(self.racine)
                code, _ = _principal(["verifier-restitution"], self.racine)
                self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
