# /// script
# requires-python = ">=3.12,<3.13"
# ///
"""Contrôles XS-06B : préflight Codex pour GPT-5.6 Sol.

La frontière système simulée est le client `codex` lui-même : un exécutable
de substitution est placé seul sur le PATH et journalise chaque invocation.
Aucun collaborateur interne n'est simulé. Fidélité au client réel observée :
`codex login status` écrit son statut sur stderr, `codex debug models` rend
le catalogue de modèles brut en JSON sur stdout.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import unittest
import tempfile
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

CHEMIN_PREFLIGHTS = (
    "tasks/dev/pre-cadrage-entretien-client/campagne-v1/preflights-v1"
)
VERSION_SIMULEE = "codex-cli 0.149.1"
LOGIN_SIMULE = "Logged in using ChatGPT"
# Catalogue simulé : la forme reprend le catalogue réel du client (models,
# slug, supported_reasoning_levels). Les champs témoins prouvent par leur
# présence à la frontière que le reçu ne conserve jamais le catalogue
# complet ni un contenu hors projection
CATALOGUE_SIMULE = {
    "models": [
        {
            "slug": "gpt-5.6-sol",
            "display_name": "GPT-5.6-Sol",
            "default_reasoning_level": "low",
            "supported_reasoning_levels": [
                {"effort": "low", "description": "témoin bas"},
                {"effort": "medium", "description": "témoin moyen"},
                {"effort": "high", "description": "témoin haut"},
                {"effort": "xhigh", "description": "témoin très haut"},
                {"effort": "max", "description": "témoin max"},
                {"effort": "ultra", "description": "témoin ultra"},
            ],
            "available_in_plans": ["plus", "pro", "team"],
            "model_messages": {
                "instructions_template": "TEMOIN-INSTRUCTIONS-PRIVEES"
            },
            "context_window": 272000,
        },
        {
            "slug": "gpt-5.4",
            "display_name": "GPT-5.4",
            "supported_reasoning_levels": [
                {"effort": "low", "description": "témoin bas"},
                {"effort": "medium", "description": "témoin moyen"},
            ],
            "available_in_plans": ["plus"],
        },
    ]
}


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS06B(unittest.TestCase):
    """Racine isolée : état V1, registre officiel et client codex simulé."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        etat = M.CHEMIN_ETAT.as_posix()
        destination = self.racine / etat
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / etat, destination)
        shutil.copytree(
            RACINE / M.REGISTRE_OFFICIEL, self.racine / M.REGISTRE_OFFICIEL
        )
        # Frontière système : seul un client codex simulé vit sur le PATH ;
        # il journalise ses arguments, preuve qu'aucune forme générative
        # (exec, apply, review, resume, prompt positionnel) n'est jamais
        # invoquée
        self.bin = self.racine / "bin-simule"
        self.bin.mkdir()
        self.journal = self.racine / "journal-codex.txt"
        self.catalogue = self.bin / "catalogue-simule.json"
        self._installer_catalogue(CATALOGUE_SIMULE)
        self._installer_codex(self._script_codex())
        patch = mock.patch.dict(os.environ, {"PATH": str(self.bin)})
        patch.start()
        self.addCleanup(patch.stop)
        self.recu_codex = (
            self.racine / CHEMIN_PREFLIGHTS / "codex-gpt-5-6-sol.json"
        )

    def _installer_catalogue(self, catalogue: object) -> None:
        self.catalogue.write_text(
            json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _script_codex(self, login: str = LOGIN_SIMULE) -> str:
        """Client simulé : une ligne de journal par invocation, args joints"""
        return (
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            'if [ "$*" = "--version" ]; then\n'
            f"  echo '{VERSION_SIMULEE}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "login status" ]; then\n'
            # Fidélité au client réel : le statut de connexion sort sur stderr
            f"  echo '{login}' >&2\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "debug models" ]; then\n'
            # /bin/cat : le PATH du test ne contient que le client simulé
            f"  /bin/cat '{self.catalogue}'\n"
            "  exit 0\n"
            "fi\n"
            "echo 'invocation hors contrat' >&2\n"
            "exit 64\n"
        )

    def _installer_codex(self, script: str) -> None:
        stub = self.bin / "codex"
        stub.write_text(script, encoding="utf-8")
        stub.chmod(0o755)

    def _preflight(self) -> tuple[int, str]:
        return _principal(
            ["preflight", "--configuration", "codex-gpt-5-6-sol"], self.racine
        )

    def _lire_recu(self) -> dict:
        return json.loads(self.recu_codex.read_text(encoding="utf-8"))


class PreflightCodexDisponibleTests(BaseXS06B):
    def test_codex_disponible_rend_hold_missing_observation_et_ecrit_recu(self):
        code, sortie = self._preflight()
        # HOLD rend 2 : version, authentification et catalogue sont
        # observables sans génération ; plan du compte, quota et identité
        # réellement servie restent non prouvés
        self.assertEqual(code, 2, sortie)
        self.assertIn("HOLD", sortie)
        self.assertIn("MISSING_OBSERVATION", sortie)
        self.assertTrue(self.recu_codex.is_file())
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(recu["configuration_id"], "codex-gpt-5-6-sol")
        self.assertEqual(recu["adaptateur"], "codex")
        self.assertEqual(recu["interface"]["client"], "codex")
        self.assertEqual(recu["interface"]["version_observee"], VERSION_SIMULEE)
        self.assertEqual(
            recu["authentification"]["observee"],
            {"connecte": True, "methode": "ChatGPT"},
        )
        self.assertEqual(recu["plan"]["declare"], "Codex")
        # Le plan du compte n'est exposé par aucune des trois sondes
        self.assertEqual(recu["plan"]["observe"], "INCONNU")
        self.assertEqual(recu["modele"]["demande"], "gpt-5.6-sol")
        # Correspondance de catalogue exacte : le modèle exposé est prouvé,
        # jamais le modèle réellement servi
        self.assertEqual(recu["modele"]["expose"], "gpt-5.6-sol")
        self.assertEqual(recu["effort"]["demande"], "high")
        self.assertEqual(recu["effort"]["expose"], "high")
        self.assertEqual(recu["quota"]["observe"], "INCONNU")
        self.assertEqual(recu["quota"]["consommation_preflight"], "INCONNU")


class PreflightCodexContratRecuTests(BaseXS06B):
    def test_reference_d_v1_03_exactement_une_fois(self):
        self.assertEqual(self._preflight()[0], 2)
        texte = self.recu_codex.read_text(encoding="utf-8")
        self.assertEqual(texte.count("D-V1-03"), 1)
        recu = json.loads(texte)
        self.assertEqual(recu["autorite_preflight"], "D-V1-03")

    def test_recu_deterministe_sans_score_ni_self_hash(self):
        self.assertEqual(self._preflight()[0], 2)
        texte = self.recu_codex.read_text(encoding="utf-8")
        recu = json.loads(texte)
        self.assertEqual(recu["schema_version"], "campagne-v1-preflight/v1")
        self.assertRegex(
            recu["date_preflight"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        )
        self.assertEqual(
            texte,
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        for interdit in ("score", "content_address", "proof_root", "self_hash"):
            self.assertNotIn(interdit, recu)
            self.assertNotIn(f'"{interdit}"', texte)

    def test_reçu_sans_catalogue_complet_ni_contenu_prive(self):
        self.assertEqual(self._preflight()[0], 2)
        texte = self.recu_codex.read_text(encoding="utf-8")
        # Le catalogue complet servi à la frontière n'est jamais conservé :
        # ni autre modèle, ni plans, ni instructions, ni sortie brute
        for interdit in (
            "gpt-5.4",
            "available_in_plans",
            "TEMOIN-INSTRUCTIONS-PRIVEES",
            "context_window",
            "supported_reasoning_levels",
            LOGIN_SIMULE,
        ):
            self.assertNotIn(interdit, texte)
        recu = self._lire_recu()
        sonde_login = recu["sondes"][1]
        self.assertEqual(sonde_login["commande"], "codex login status")
        self.assertNotIn("stdout_expurge", sonde_login)
        self.assertNotIn("stderr_expurge", sonde_login)
        sonde_catalogue = recu["sondes"][2]
        self.assertEqual(sonde_catalogue["commande"], "codex debug models")
        self.assertEqual(
            sonde_catalogue["projection"],
            {
                "modele_demande_present": True,
                "efforts_annonces": [
                    "low", "medium", "high", "xhigh", "max", "ultra"
                ],
            },
        )
        self.assertNotIn("stdout_expurge", sonde_catalogue)

    def test_sortie_de_sonde_version_expurgee_du_chemin_personnel(self):
        self._installer_codex(
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            f"echo '{VERSION_SIMULEE} depuis {Path.home()}/.codex'\n"
            "exit 0\n"
        )
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        texte = self.recu_codex.read_text(encoding="utf-8")
        self.assertNotIn(str(Path.home()), texte)
        recu = self._lire_recu()
        self.assertIn("~/.codex", recu["sondes"][0]["stdout_expurge"])

    def test_seules_les_trois_sondes_autorisees_sont_invoquees(self):
        self.assertEqual(self._preflight()[0], 2)
        invocations = self.journal.read_text(encoding="utf-8").splitlines()
        # Exactement les trois sondes de la liste blanche, dans l'ordre,
        # jamais une forme générative ni une session
        self.assertEqual(
            invocations,
            ["--version", "login status", "debug models"],
        )
        for interdit in ("exec", "review", "apply", "resume", "fork", "-p"):
            for invocation in invocations:
                self.assertNotIn(interdit, invocation.split())

    def test_aucun_recu_d_acquisition_ecrit_repertoire_intact(self):
        repertoire = self.racine / M._RACINE_CAMPAGNE_V1 / "recus-v1"
        repertoire.mkdir(parents=True)
        temoin = repertoire / "temoin.json"
        temoin.write_text("{}\n", encoding="utf-8")
        avant = sorted(
            (chemin.name, chemin.read_bytes())
            for chemin in repertoire.iterdir()
        )
        self.assertEqual(self._preflight()[0], 2)
        apres = sorted(
            (chemin.name, chemin.read_bytes())
            for chemin in repertoire.iterdir()
        )
        self.assertEqual(avant, apres)


class PreflightCodexIndisponibleTests(BaseXS06B):
    def test_client_introuvable_rend_un_unavailable_interface(self):
        (self.bin / "codex").unlink()
        code, sortie = self._preflight()
        # UNAVAILABLE rend 1 : l'interface est absente
        self.assertEqual(code, 1, sortie)
        self.assertIn("INTERFACE_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "INTERFACE_UNAVAILABLE")
        self.assertEqual(recu["interface"]["version_observee"], "INCONNU")
        self.assertEqual(recu["sondes"], [])

    def test_sonde_version_en_echec_rend_un_sans_autre_sonde(self):
        self._installer_codex(
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            "echo 'client défaillant' >&2\nexit 7\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "INTERFACE_UNAVAILABLE")
        self.assertEqual(recu["sondes"][0]["code_sortie"], 7)
        # Interface non établie : connexion et catalogue jamais sondés
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version"],
        )

    def test_deconnecte_rend_un_unavailable_authentication(self):
        # Fidélité au client réel : 'Not logged in' sur stderr, code 1
        self._installer_codex(
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            'if [ "$*" = "--version" ]; then\n'
            f"  echo '{VERSION_SIMULEE}'\n  exit 0\nfi\n"
            'if [ "$*" = "login status" ]; then\n'
            "  echo 'Not logged in' >&2\n  exit 1\nfi\n"
            "exit 64\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("AUTHENTICATION_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "AUTHENTICATION_UNAVAILABLE")
        self.assertEqual(
            recu["authentification"]["observee"],
            {"connecte": False, "methode": "INCONNU"},
        )
        self.assertEqual(recu["plan"]["observe"], "INCONNU")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")
        # Route non authentifiée : le catalogue n'est jamais sondé
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version", "login status"],
        )

    def test_delai_de_sonde_depasse_rend_deux_hold_harness_error(self):
        # Incident du dispositif, jamais imputé à la configuration : HOLD
        self._installer_codex("#!/bin/sh\n/bin/sleep 30\n")
        with mock.patch.object(M, "DELAI_SONDE_PREFLIGHT", 1):
            code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["interface"]["version_observee"], "INCONNU")


class PreflightCodexFailClosedTests(BaseXS06B):
    def test_login_hors_liste_fermee_reste_fail_closed_sans_sortie_brute(self):
        self._installer_codex(
            self._script_codex(login="Logged in as prive@example.com")
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["authentification"]["observee"], "INCONNU")
        self.assertEqual(recu["sondes"][1]["projection"], "INCONNU")
        # La sortie brute non reconnue n'est jamais consignée : aucune
        # identité de compte ne peut fuir dans le reçu
        texte = self.recu_codex.read_text(encoding="utf-8")
        self.assertNotIn("prive@example.com", texte)
        # Statut de connexion inobservé : le catalogue n'est jamais sondé
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version", "login status"],
        )

    def test_catalogue_sans_le_modele_rend_un_model_unavailable(self):
        self._installer_catalogue(
            {"models": [{"slug": "gpt-5.4", "supported_reasoning_levels": []}]}
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("MODEL_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "MODEL_UNAVAILABLE")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")
        self.assertEqual(recu["effort"]["expose"], "INCONNU")
        self.assertEqual(
            recu["sondes"][2]["projection"],
            {"modele_demande_present": False, "efforts_annonces": []},
        )

    def test_effort_high_absent_des_efforts_annonces_rend_un(self):
        self._installer_catalogue(
            {
                "models": [
                    {
                        "slug": "gpt-5.6-sol",
                        "supported_reasoning_levels": [
                            {"effort": "low", "description": "témoin"},
                            {"effort": "medium", "description": "témoin"},
                        ],
                    }
                ]
            }
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("MODEL_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "MODEL_UNAVAILABLE")
        # Le modèle est exposé ; l'effort demandé ne l'est pas et aucune
        # substitution n'est admise
        self.assertEqual(recu["modele"]["expose"], "gpt-5.6-sol")
        self.assertEqual(recu["effort"]["expose"], "INCONNU")

    def test_catalogue_sans_annonce_d_effort_reste_hold_missing_observation(self):
        self._installer_catalogue({"models": [{"slug": "gpt-5.6-sol"}]})
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(recu["modele"]["expose"], "gpt-5.6-sol")
        self.assertEqual(recu["effort"]["expose"], "INCONNU")

    def test_catalogue_illisible_reste_fail_closed_sans_sortie_brute(self):
        self.catalogue.write_text(
            "catalogue illisible hors JSON", encoding="utf-8"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][2]["projection"], "INCONNU")
        self.assertNotIn(
            "catalogue illisible hors JSON",
            self.recu_codex.read_text(encoding="utf-8"),
        )

    def test_catalogue_en_echec_reste_fail_closed(self):
        self._installer_codex(
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            'if [ "$*" = "--version" ]; then\n'
            f"  echo '{VERSION_SIMULEE}'\n  exit 0\nfi\n"
            'if [ "$*" = "login status" ]; then\n'
            f"  echo '{LOGIN_SIMULE}' >&2\n  exit 0\nfi\n"
            "echo 'catalogue indisponible' >&2\nexit 9\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][2]["code_sortie"], 9)
        self.assertEqual(recu["sondes"][2]["projection"], "INCONNU")


_SOURCES_RESTITUTION = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES)


class RestitutionPreflightCodexTests(BaseXS06B):
    """Section MSW du préflight Codex : verdict, cause et INCONNU sourcés."""

    def setUp(self):
        super().setUp()
        for relatif in _SOURCES_RESTITUTION:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        self.page = self.racine / M.CHEMIN_PAGE

    def _restituer(self) -> str:
        code, sortie = _principal(["restituer"], self.racine)
        self.assertEqual(code, 0, sortie)
        return self.page.read_text(encoding="utf-8")

    def test_page_affiche_le_preflight_codex_et_le_verificateur_confirme(self):
        self.assertEqual(self._preflight()[0], 2)
        page = self._restituer()
        self.assertIn('<section id="preflights">', page)
        self.assertIn('data-preflight="codex-gpt-5-6-sol"', page)
        recu = self._lire_recu()
        self.assertIn(recu["date_preflight"], page)
        self.assertIn("MISSING_OBSERVATION", page)
        # Projections codex rendues : connexion, catalogue et efforts
        self.assertIn("connecte", page)
        self.assertIn("modele_demande_present", page)
        self.assertIn("efforts_annonces", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_preflight_codex_unavailable_apparait_avec_sa_cause(self):
        (self.bin / "codex").unlink()
        self.assertEqual(self._preflight()[0], 1)
        page = self._restituer()
        self.assertIn("UNAVAILABLE", page)
        self.assertIn("INTERFACE_UNAVAILABLE", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_restitutions_successives_byte_identiques_avec_preflight_codex(self):
        self.assertEqual(self._preflight()[0], 2)
        self.assertEqual(self._restituer(), self._restituer())

    def test_verifier_refuse_un_recu_codex_altere_apres_restitution(self):
        self.assertEqual(self._preflight()[0], 2)
        self._restituer()
        self.recu_codex.write_bytes(self.recu_codex.read_bytes() + b" ")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def _muter_recu(self, transformer) -> None:
        recu = self._lire_recu()
        transformer(recu)
        self.recu_codex.write_text(
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_recu_codex_hors_vocabulaire_leve_erreur_restitution(self):
        mutations = {
            # Une forme générative n'entre jamais dans la liste blanche codex
            "sonde-exec-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "codex exec bonjour",
                            "code_sortie": 0,
                            "stdout_expurge": "",
                            "stderr_expurge": "",
                        }
                    ]
                }
            ),
            "sonde-apply-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "codex apply",
                            "code_sortie": 0,
                            "stdout_expurge": "",
                            "stderr_expurge": "",
                        }
                    ]
                }
            ),
            # Une sonde claude ne vaut jamais pour l'adaptateur codex
            "sonde-claude-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "claude auth status --json",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            "adaptateur-hors-vocabulaire": lambda recu: recu.update(
                {"adaptateur": "grok"}
            ),
            # La forme d'authentification claude ne vaut pas pour codex
            "auth-forme-claude": lambda recu: recu.update(
                {
                    "authentification": {
                        "observee": {
                            "loggedIn": True,
                            "authMethod": "claude.ai",
                            "apiProvider": "firstParty",
                        }
                    }
                }
            ),
            "projection-catalogue-polluee": lambda recu: recu["sondes"][
                2
            ].update({"projection": {"modele_demande_present": True,
                                     "efforts_annonces": [7]}}),
            # READY exige les cinq observations : plan et quota INCONNU
            # l'interdisent
            "ready-sans-observation-complete": lambda recu: recu.update(
                {"verdict": "READY", "cause": None}
            ),
        }
        for nom, transformer in mutations.items():
            with self.subTest(mutation=nom):
                if self.recu_codex.exists():
                    self.recu_codex.unlink()
                self.assertEqual(self._preflight()[0], 2)
                self._restituer()
                self._muter_recu(transformer)
                with self.assertRaises(M.ErreurRestitution):
                    M.verifier_restitution(self.racine)
                code, _ = _principal(["verifier-restitution"], self.racine)
                self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
