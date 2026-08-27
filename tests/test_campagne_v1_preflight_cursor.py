# /// script
# requires-python = ">=3.12,<3.13"
# ///
"""Contrôles XS-06D : préflight Cursor CLI pour Kimi K3.

La frontière système simulée est le client `agent` lui-même — un exécutable
de substitution placé seul sur le PATH qui journalise ses arguments exacts et
sert uniquement des sorties expurgées de test. Aucun collaborateur interne
n'est simulé. Fidélité au diagnostic de lancement couvert par D-V1-03 :
`agent --version` rend la version, `agent --help` porte l'option native
`--model` et la syntaxe d'override `effort=high`, `agent status --format
json` et `agent about --format json` rendent des JSON machine, `agent
models` rend des lignes `identifiant - libellé` dont les quatre entrées
Kimi observées.
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

from tests._helpers_v1 import retirer_couverture_publiee  # noqa: E402

CHEMIN_PREFLIGHTS = (
    "tasks/dev/pre-cadrage-entretien-client/campagne-v1/preflights-v1"
)
VERSION_SIMULEE = "2026.08.11-e8db854"
# Aide simulée : la forme reprend les deux seules observations conservées du
# diagnostic (option native --model, syntaxe d'override effort=high). Les
# options -p et --force servent de témoins : leur présence dans l'aide ne
# déclenche jamais leur invocation
AIDE_SIMULEE = """Cursor Agent CLI

Usage: agent [options] [prompt]

Commands:
  models          List available models
  create-chat     Create a chat (témoin, jamais invoqué)

Options:
  -m, --model <model>   Model to use; override reasoning effort with
                        "TEMOIN-MODELE-AIDE?effort=high"
  -p, --print           Print response and exit (témoin, jamais invoqué)
  -f, --force           Force (témoin, jamais invoqué)
"""
# Statut simulé : la forme reprend un document de statut de compte. Les
# champs témoins privés prouvent par leur présence à la frontière que le
# reçu ne conserve jamais userInfo, e-mail, identifiant, prénom, nom, date
# de création, access token ni refresh token
STATUT_SIMULE = {
    "status": "authenticated",
    "isAuthenticated": True,
    "userInfo": {
        "id": "TEMOIN-ID-PRIVE",
        "email": "prive@example.com",
        "firstName": "Temoin",
        "lastName": "Prive",
        "createdAt": "2026-01-01T00:00:00Z",
    },
    "accessToken": "TEMOIN-ACCESS-PRIVE",
    "refreshToken": "TEMOIN-REFRESH-PRIVE",
}
# Compte simulé : les champs témoins prouvent que le reçu ne conserve jamais
# userEmail, lastRequestId, modèle par défaut, système, architecture,
# terminal ni shell
COMPTE_SIMULE = {
    "cliVersion": VERSION_SIMULEE,
    "subscriptionTier": "Ultra",
    "userEmail": "prive@example.com",
    "lastRequestId": "TEMOIN-REQUEST-PRIVE",
    "defaultModel": "TEMOIN-MODELE-DEFAUT",
    "system": "TEMOIN-SYSTEME",
    "architecture": "TEMOIN-ARCH",
    "terminal": "TEMOIN-TERMINAL",
    "shell": "TEMOIN-SHELL",
}
# Catalogue simulé : les quatre lignes Kimi conservées du diagnostic, plus
# une entrée témoin. kimi-k3-low, kimi-k3-max et kimi-k2.7-code prouvent par
# leur présence à la frontière qu'aucune variante interdite ne vaut
# correspondance et que le catalogue complet n'est jamais persisté
CATALOGUE_SIMULE = """kimi-k3-low - Kimi K3 Low
kimi-k3-high - Kimi K3 High
kimi-k3-max - Kimi K3
kimi-k2.7-code - Kimi K2.7 Code
TEMOIN-AUTRE-MODELE - Temoin Autre Modele
"""
TEMOINS_PRIVES = (
    "TEMOIN-ID-PRIVE",
    "prive@example.com",
    "TEMOIN-ACCESS-PRIVE",
    "TEMOIN-REFRESH-PRIVE",
    "TEMOIN-REQUEST-PRIVE",
    "TEMOIN-MODELE-DEFAUT",
    "TEMOIN-SYSTEME",
    "TEMOIN-ARCH",
    "TEMOIN-TERMINAL",
    "TEMOIN-SHELL",
    "userInfo",
    "userEmail",
    "accessToken",
    "refreshToken",
    "lastRequestId",
    "createdAt",
    "firstName",
    "lastName",
)
TEMOINS_CATALOGUE = (
    "kimi-k3-low",
    "kimi-k3-max",
    "kimi-k2.7-code",
    "TEMOIN-AUTRE-MODELE",
    "Kimi K3 Low",
    "Kimi K3 High",
    "TEMOIN-MODELE-AIDE",
)


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS06D(unittest.TestCase):
    """Racine isolée : état V1, registre officiel et client agent simulé."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        etat = M.CHEMIN_ETAT.as_posix()
        destination = self.racine / etat
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / etat, destination)
        retirer_couverture_publiee(destination)
        shutil.copytree(
            RACINE / M.REGISTRE_OFFICIEL, self.racine / M.REGISTRE_OFFICIEL
        )
        # Frontière système : seul un client agent simulé vit sur le PATH ;
        # il journalise ses arguments exacts, preuve qu'aucune forme
        # générative (-p, --print, agent, create-chat, resume, prompt
        # positionnel, session interactive, --model, --force, --yolo,
        # --auto-review, --approve-mcps, --api-key, --endpoint, login,
        # logout, worker) n'est jamais invoquée
        self.bin = self.racine / "bin-simule"
        self.bin.mkdir()
        self.journal = self.racine / "journal-agent.txt"
        self.aide = self.bin / "aide-simulee.txt"
        self.statut = self.bin / "statut-simule.json"
        self.compte = self.bin / "compte-simule.json"
        self.catalogue = self.bin / "catalogue-simule.txt"
        self._installer_aide(AIDE_SIMULEE)
        self._installer_statut(STATUT_SIMULE)
        self._installer_compte(COMPTE_SIMULE)
        self._installer_catalogue(CATALOGUE_SIMULE)
        self._installer_agent(self._script_agent())
        patch = mock.patch.dict(os.environ, {"PATH": str(self.bin)})
        patch.start()
        self.addCleanup(patch.stop)
        self.recu_cursor = (
            self.racine / CHEMIN_PREFLIGHTS / "cursor-kimi-k3.json"
        )

    def _installer_aide(self, aide: str) -> None:
        self.aide.write_text(aide, encoding="utf-8")

    def _installer_statut(self, statut: object) -> None:
        self.statut.write_text(
            json.dumps(statut, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def _installer_compte(self, compte: object) -> None:
        self.compte.write_text(
            json.dumps(compte, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def _installer_catalogue(self, catalogue: str) -> None:
        self.catalogue.write_text(catalogue, encoding="utf-8")

    def _script_agent(self, version: str = VERSION_SIMULEE) -> str:
        """Client simulé : une ligne de journal par invocation, args joints"""
        return (
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            'if [ "$*" = "--version" ]; then\n'
            f"  echo '{version}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "--help" ]; then\n'
            # /bin/cat : le PATH du test ne contient que le client simulé
            f"  /bin/cat '{self.aide}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "status --format json" ]; then\n'
            f"  /bin/cat '{self.statut}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "about --format json" ]; then\n'
            f"  /bin/cat '{self.compte}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "models" ]; then\n'
            f"  /bin/cat '{self.catalogue}'\n"
            "  exit 0\n"
            "fi\n"
            "echo 'invocation hors contrat' >&2\n"
            "exit 64\n"
        )

    def _installer_agent(self, script: str) -> None:
        stub = self.bin / "agent"
        stub.write_text(script, encoding="utf-8")
        stub.chmod(0o755)

    def _preflight(self) -> tuple[int, str]:
        return _principal(
            ["preflight", "--configuration", "cursor-kimi-k3"], self.racine
        )

    def _lire_recu(self) -> dict:
        return json.loads(self.recu_cursor.read_text(encoding="utf-8"))


class PreflightCursorDisponibleTests(BaseXS06D):
    def test_cursor_disponible_rend_hold_missing_observation_et_ecrit_recu(self):
        code, sortie = self._preflight()
        # HOLD rend 2 : version, sélection native, authentification, tier et
        # correspondance exacte de catalogue sont observables sans
        # génération ; quota, consommation de quota et identité réellement
        # servie restent non prouvés
        self.assertEqual(code, 2, sortie)
        self.assertIn("HOLD", sortie)
        self.assertIn("MISSING_OBSERVATION", sortie)
        self.assertTrue(self.recu_cursor.is_file())
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(recu["configuration_id"], "cursor-kimi-k3")
        self.assertEqual(recu["adaptateur"], "agent")
        self.assertEqual(recu["interface"]["client"], "agent")
        self.assertEqual(recu["interface"]["version_observee"], VERSION_SIMULEE)
        self.assertEqual(
            recu["authentification"]["observee"],
            {"status": "authenticated", "isAuthenticated": True},
        )
        self.assertEqual(recu["plan"]["declare"], "Cursor")
        # subscriptionTier non vide sur compte authentifié : tier actif du
        # compte, sans réécrire le libellé déclaré
        self.assertEqual(recu["plan"]["observe"], "Ultra")
        self.assertEqual(recu["modele"]["demande"], "kimi-k3")
        # La présence exacte de kimi-k3-high projette le modèle exposé et
        # l'effort high, jamais l'identité réellement servie
        self.assertEqual(recu["modele"]["expose"], "kimi-k3-high")
        self.assertEqual(recu["effort"]["demande"], "high")
        self.assertEqual(recu["effort"]["expose"], "high")
        self.assertEqual(recu["quota"]["observe"], "INCONNU")
        self.assertEqual(recu["quota"]["consommation_preflight"], "INCONNU")

    def test_projections_des_cinq_sondes_fermees_et_completes(self):
        self.assertEqual(self._preflight()[0], 2)
        recu = self._lire_recu()
        self.assertEqual(
            [sonde["commande"] for sonde in recu["sondes"]],
            [
                "agent --version",
                "agent --help",
                "agent status --format json",
                "agent about --format json",
                "agent models",
            ],
        )
        self.assertEqual(
            recu["sondes"][0]["projection"], {"version": VERSION_SIMULEE}
        )
        self.assertEqual(
            recu["sondes"][1]["projection"],
            {"option_modele_native": True, "syntaxe_effort_high": True},
        )
        self.assertEqual(
            recu["sondes"][2]["projection"],
            {"status": "authenticated", "isAuthenticated": True},
        )
        self.assertEqual(
            recu["sondes"][3]["projection"],
            {"cliVersion": VERSION_SIMULEE, "subscriptionTier": "Ultra"},
        )
        self.assertEqual(
            recu["sondes"][4]["projection"], {"cible_presente": True}
        )
        for sonde in recu["sondes"]:
            self.assertNotIn("stdout_expurge", sonde)
            self.assertNotIn("stderr_expurge", sonde)


class PreflightCursorContratRecuTests(BaseXS06D):
    def test_reference_d_v1_03_exactement_une_fois(self):
        self.assertEqual(self._preflight()[0], 2)
        texte = self.recu_cursor.read_text(encoding="utf-8")
        self.assertEqual(texte.count("D-V1-03"), 1)
        recu = json.loads(texte)
        self.assertEqual(recu["autorite_preflight"], "D-V1-03")

    def test_recu_deterministe_sans_score_ni_self_hash(self):
        self.assertEqual(self._preflight()[0], 2)
        texte = self.recu_cursor.read_text(encoding="utf-8")
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

    def test_recu_sans_catalogue_complet_ni_donnee_privee(self):
        self.assertEqual(self._preflight()[0], 2)
        texte = self.recu_cursor.read_text(encoding="utf-8")
        # Le catalogue complet, les autres modèles, le modèle par défaut et
        # les champs privés de statut et de compte ne sont jamais persistés
        for interdit in TEMOINS_CATALOGUE + TEMOINS_PRIVES:
            self.assertNotIn(interdit, texte)

    def test_seules_les_cinq_sondes_autorisees_sont_invoquees(self):
        self.assertEqual(self._preflight()[0], 2)
        invocations = self.journal.read_text(encoding="utf-8").splitlines()
        # Exactement les cinq probes de la liste blanche, dans l'ordre,
        # jamais une forme générative, une session ni une commande --model
        self.assertEqual(
            invocations,
            [
                "--version",
                "--help",
                "status --format json",
                "about --format json",
                "models",
            ],
        )
        for interdit in (
            "-p",
            "--print",
            "agent",
            "create-chat",
            "resume",
            "--model",
            "-m",
            "--force",
            "--yolo",
            "--auto-review",
            "--approve-mcps",
            "--api-key",
            "--endpoint",
            "login",
            "logout",
            "worker",
        ):
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


class PreflightCursorIndisponibleTests(BaseXS06D):
    def test_client_introuvable_rend_un_unavailable_interface(self):
        (self.bin / "agent").unlink()
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
        self._installer_agent(
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
        self.assertEqual(recu["sondes"][0]["projection"], "INCONNU")
        # Interface non établie : les quatre autres probes jamais lancées
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version"],
        )

    def test_statut_non_authentifie_rend_un_unavailable_authentication(self):
        self._installer_statut(
            {"status": "unauthenticated", "isAuthenticated": False}
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("AUTHENTICATION_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "AUTHENTICATION_UNAVAILABLE")
        self.assertEqual(
            recu["authentification"]["observee"],
            {"status": "unauthenticated", "isAuthenticated": False},
        )
        self.assertEqual(recu["plan"]["observe"], "INCONNU")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")
        # Route non authentifiée : compte et catalogue jamais sondés
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version", "--help", "status --format json"],
        )

    def test_catalogue_sans_cible_exacte_rend_un_model_unavailable(self):
        # kimi-k3-low, kimi-k3-max et kimi-k2.7-code ne valent jamais
        # correspondance : la variante max est interdite par la décision
        # propriétaire et la ligne 'kimi-k3-max - Kimi K3' n'est pas la cible
        self._installer_catalogue(
            "kimi-k3-low - Kimi K3 Low\n"
            "kimi-k3-max - Kimi K3\n"
            "kimi-k2.7-code - Kimi K2.7 Code\n"
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
            recu["sondes"][4]["projection"], {"cible_presente": False}
        )

    def test_delai_de_sonde_depasse_rend_deux_hold_harness_error(self):
        # Incident du dispositif, jamais imputé à la configuration : HOLD
        self._installer_agent("#!/bin/sh\n/bin/sleep 30\n")
        with mock.patch.object(M, "DELAI_SONDE_PREFLIGHT", 1):
            code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["interface"]["version_observee"], "INCONNU")


class PreflightCursorFailClosedTests(BaseXS06D):
    def test_version_vide_reste_fail_closed_sans_invention(self):
        self._installer_agent(self._script_agent(version=""))
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][0]["projection"], "INCONNU")

    def test_aide_sans_option_model_rend_deux_harness_error(self):
        # Le contrat fige : une aide sans sélection native exacte donne
        # HOLD / HARNESS_ERROR ; les probes de compte ne sont pas lancées
        self._installer_aide(
            "Usage: agent [options]\n"
            '  Override reasoning effort with "TEMOIN-MODELE-AIDE?effort=high"\n'
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        self.assertIn("HARNESS_ERROR", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")
        self.assertEqual(
            recu["sondes"][1]["projection"],
            {"option_modele_native": False, "syntaxe_effort_high": True},
        )
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version", "--help"],
        )

    def test_aide_sans_syntaxe_effort_high_rend_deux_harness_error(self):
        self._installer_aide(
            "Usage: agent [options]\n  -m, --model <model>  Model to use\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(
            recu["sondes"][1]["projection"],
            {"option_modele_native": True, "syntaxe_effort_high": False},
        )
        self.assertEqual(recu["effort"]["expose"], "INCONNU")

    def test_statut_illisible_reste_fail_closed_sans_sortie_brute(self):
        self.statut.write_text(
            "TEMOIN-STATUT-ILLISIBLE hors JSON", encoding="utf-8"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][2]["projection"], "INCONNU")
        self.assertEqual(recu["authentification"]["observee"], "INCONNU")
        texte = self.recu_cursor.read_text(encoding="utf-8")
        self.assertNotIn("TEMOIN-STATUT-ILLISIBLE", texte)
        # Statut inobservé : compte et catalogue jamais sondés
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version", "--help", "status --format json"],
        )

    def test_compte_illisible_reste_fail_closed_sans_sortie_brute(self):
        self.compte.write_text(
            "TEMOIN-COMPTE-ILLISIBLE hors JSON", encoding="utf-8"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][3]["projection"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-COMPTE-ILLISIBLE",
            self.recu_cursor.read_text(encoding="utf-8"),
        )

    def test_tier_absent_sur_compte_authentifie_rend_deux_missing_observation(self):
        compte = dict(COMPTE_SIMULE)
        del compte["subscriptionTier"]
        self._installer_compte(compte)
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        self.assertIn("MISSING_OBSERVATION", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(recu["plan"]["observe"], "INCONNU")
        self.assertEqual(
            recu["sondes"][3]["projection"],
            {"cliVersion": VERSION_SIMULEE, "subscriptionTier": "INCONNU"},
        )
        # Tier inobservé : le catalogue n'est pas sondé, aucune valeur de
        # remplacement n'est créée
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version", "--help", "status --format json", "about --format json"],
        )

    def test_tier_vide_rend_deux_missing_observation(self):
        self._installer_compte({**COMPTE_SIMULE, "subscriptionTier": " "})
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(recu["plan"]["observe"], "INCONNU")

    def test_catalogue_illisible_reste_fail_closed_sans_sortie_brute(self):
        self._installer_catalogue("TEMOIN-CATALOGUE-ILLISIBLE sans separateur\n")
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][4]["projection"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-CATALOGUE-ILLISIBLE",
            self.recu_cursor.read_text(encoding="utf-8"),
        )

    def test_catalogue_ambigu_cible_dupliquee_rend_deux_harness_error(self):
        self._installer_catalogue(
            "kimi-k3-high - Kimi K3 High\nkimi-k3-high - Kimi K3 High\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][4]["projection"], "INCONNU")

    def test_catalogue_en_echec_reste_fail_closed(self):
        self._installer_agent(
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            'if [ "$*" = "--version" ]; then\n'
            f"  echo '{VERSION_SIMULEE}'\n  exit 0\nfi\n"
            'if [ "$*" = "--help" ]; then\n'
            f"  /bin/cat '{self.aide}'\n  exit 0\nfi\n"
            'if [ "$*" = "status --format json" ]; then\n'
            f"  /bin/cat '{self.statut}'\n  exit 0\nfi\n"
            'if [ "$*" = "about --format json" ]; then\n'
            f"  /bin/cat '{self.compte}'\n  exit 0\nfi\n"
            "echo 'catalogue indisponible' >&2\nexit 9\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][4]["code_sortie"], 9)
        self.assertEqual(recu["sondes"][4]["projection"], "INCONNU")


_SOURCES_RESTITUTION = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES)


class RestitutionPreflightCursorTests(BaseXS06D):
    """Section MSW du préflight Cursor : verdict, cause et INCONNU sourcés."""

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

    def test_page_affiche_le_preflight_cursor_et_le_verificateur_confirme(self):
        self.assertEqual(self._preflight()[0], 2)
        page = self._restituer()
        self.assertIn('<section id="preflights">', page)
        self.assertIn('data-preflight="cursor-kimi-k3"', page)
        recu = self._lire_recu()
        self.assertIn(recu["date_preflight"], page)
        self.assertIn("MISSING_OBSERVATION", page)
        # Projections cursor rendues : statut, compte, aide et catalogue
        self.assertIn("isAuthenticated", page)
        self.assertIn("subscriptionTier", page)
        self.assertIn("syntaxe_effort_high", page)
        self.assertIn("cible_presente", page)
        self.assertIn("kimi-k3-high", page)
        for interdit in TEMOINS_PRIVES:
            self.assertNotIn(interdit, page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_preflight_cursor_unavailable_apparait_avec_sa_cause(self):
        (self.bin / "agent").unlink()
        self.assertEqual(self._preflight()[0], 1)
        page = self._restituer()
        self.assertIn("UNAVAILABLE", page)
        self.assertIn("INTERFACE_UNAVAILABLE", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_restitutions_successives_byte_identiques_avec_preflight_cursor(self):
        self.assertEqual(self._preflight()[0], 2)
        self.assertEqual(self._restituer(), self._restituer())

    def test_verifier_refuse_un_recu_cursor_altere_apres_restitution(self):
        self.assertEqual(self._preflight()[0], 2)
        self._restituer()
        self.recu_cursor.write_bytes(self.recu_cursor.read_bytes() + b" ")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def _muter_recu(self, transformer) -> None:
        recu = self._lire_recu()
        transformer(recu)
        self.recu_cursor.write_text(
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_recu_cursor_hors_vocabulaire_leve_erreur_restitution(self):
        mutations = {
            # Une forme générative ou une commande --model n'entre jamais
            # dans la liste blanche agent
            "sonde-generative-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "agent -p bonjour",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            "sonde-model-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "agent models --model kimi-k3-high",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            # Une sonde claude ne vaut jamais pour l'adaptateur agent
            "sonde-claude-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "claude --version",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            "adaptateur-hors-vocabulaire": lambda recu: recu.update(
                {"adaptateur": "cursor"}
            ),
            # La forme d'authentification codex ne vaut pas pour agent
            "auth-forme-codex": lambda recu: recu.update(
                {
                    "authentification": {
                        "observee": {"connecte": True, "methode": "ChatGPT"}
                    }
                }
            ),
            "projection-catalogue-polluee": lambda recu: recu["sondes"][
                4
            ].update(
                {
                    "projection": {
                        "cible_presente": True,
                        "catalogue_complet": ["kimi-k3-low"],
                    }
                }
            ),
            # READY exige les cinq observations : quota INCONNU l'interdit
            "ready-sans-observation-complete": lambda recu: recu.update(
                {"verdict": "READY", "cause": None}
            ),
        }
        for nom, transformer in mutations.items():
            with self.subTest(mutation=nom):
                if self.recu_cursor.exists():
                    self.recu_cursor.unlink()
                self.assertEqual(self._preflight()[0], 2)
                self._restituer()
                self._muter_recu(transformer)
                with self.assertRaises(M.ErreurRestitution):
                    M.verifier_restitution(self.racine)
                code, _ = _principal(["verifier-restitution"], self.racine)
                self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
