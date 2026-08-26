# /// script
# requires-python = ">=3.12,<3.13"
# ///
"""Contrôles XS-06C : préflight Grok Build pour grok-4.6.

Les frontières système simulées sont le client `grok` lui-même — un
exécutable de substitution placé seul sur le PATH qui journalise chaque
invocation — et un HOME isolé qui matérialise uniquement la forme documentée
de `~/.grok/auth.json`. Aucun collaborateur interne n'est simulé. Fidélité au
client réel observée : `grok version --json` rend un JSON machine sur stdout,
`grok --help` porte les options natives `-m, --model` et
`--reasoning-effort`, `grok models` rend le catalogue textuel sur stdout et
des avertissements de configuration ANSI sur stderr.
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
VERSION_SIMULEE = "1.0.5 (5115b46bc909)"
VERSION_JSON_SIMULEE = (
    '{"currentVersion":"1.0.5 (5115b46bc909)","channel":"stable"}'
)
# Aide simulée : la forme reprend l'aide réelle du client (options natives
# -m, --model et --reasoning-effort). Le prompt -p sert de témoin : sa
# présence dans l'aide ne déclenche jamais son invocation
AIDE_SIMULEE = """Grok Build CLI

Usage: grok [OPTIONS] [PROMPT] [COMMAND]

Commands:
  models       List available models and exit

Options:
  -m, --model <MODEL>
          Model ID to use
      --reasoning-effort <EFFORT>
          Reasoning effort for reasoning models
          [aliases: --effort]
  -p, --prompt <PROMPT>
          Run a single prompt (témoin, jamais invoqué)
"""
# Catalogue simulé : la forme reprend la sortie réelle du client (connexion,
# modèle par défaut, section Available models). Les entrées témoins prouvent
# par leur présence à la frontière que le reçu ne conserve jamais le
# catalogue complet, le modèle par défaut ni les autres modèles
CATALOGUE_SIMULE = """You are logged in with grok.com.

Default model: grok-4.6

Available models:
  * grok-4.6 (default)
  - grok-4.5
  - ocx-cursor-grok-4-6
"""
AVERTISSEMENT_SIMULE = (
    "\\033[2m2026-08-25T00:00:00Z\\033[0m \\033[33m WARN\\033[0m "
    "config: TEMOIN-AVERTISSEMENT-CONFIG"
)
# Credential simulé : la forme reprend le document réel documenté de
# ~/.grok/auth.json. Les champs témoins privés prouvent par leur présence à
# la frontière que le reçu ne conserve jamais la clé d'entrée, le jeton, le
# refresh token, l'expiration, l'utilisateur, l'e-mail, les identifiants
# d'organisation ou d'équipe ni le document brut
CREDENTIAL_SIMULE = {
    "https://auth.x.ai::TEMOIN-UUID-PRIVE": {
        "key": "TEMOIN-CLE-PRIVEE",
        "auth_mode": "oidc",
        "create_time": "2026-08-01T00:00:00Z",
        "user_id": "TEMOIN-USER-PRIVE",
        "email": "prive@example.com",
        "first_name": "Temoin",
        "last_name": "Prive",
        "principal_type": "user",
        "principal_id": "TEMOIN-PRINCIPAL-PRIVE",
        "team_id": "TEMOIN-EQUIPE-PRIVEE",
        "coding_data_retention_opt_out": True,
        "refresh_token": "TEMOIN-REFRESH-PRIVE",
        "expires_at": "2026-09-01T00:00:00Z",
        "oidc_issuer": "https://auth.x.ai",
        "oidc_client_id": "TEMOIN-CLIENT-OIDC",
    }
}
TEMOINS_PRIVES = (
    "TEMOIN-UUID-PRIVE",
    "TEMOIN-CLE-PRIVEE",
    "TEMOIN-USER-PRIVE",
    "prive@example.com",
    "TEMOIN-PRINCIPAL-PRIVE",
    "TEMOIN-EQUIPE-PRIVEE",
    "TEMOIN-REFRESH-PRIVE",
    "TEMOIN-CLIENT-OIDC",
    "refresh_token",
    "expires_at",
)


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS06C(unittest.TestCase):
    """Racine isolée : état V1, registre officiel, client grok simulé et
    HOME isolé porteur de la seule forme documentée de ~/.grok/auth.json."""

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
        # Frontière système : seul un client grok simulé vit sur le PATH ;
        # il journalise ses arguments, preuve qu'aucune forme générative
        # (-p, --prompt-file, prompt positionnel, agent, login, logout,
        # session, --model) n'est jamais invoquée
        self.bin = self.racine / "bin-simule"
        self.bin.mkdir()
        self.journal = self.racine / "journal-grok.txt"
        self.aide = self.bin / "aide-simulee.txt"
        self.catalogue = self.bin / "catalogue-simule.txt"
        self._installer_aide(AIDE_SIMULEE)
        self._installer_catalogue(CATALOGUE_SIMULE)
        self._installer_grok(self._script_grok())
        # Frontière HOME : le HOME isolé matérialise uniquement la forme
        # documentée de ~/.grok/auth.json, jamais le compte réel
        self.home = self.racine / "home-isole"
        self.home.mkdir()
        self.auth = self.home / ".grok" / "auth.json"
        self._installer_credential(CREDENTIAL_SIMULE)
        patch = mock.patch.dict(
            os.environ, {"PATH": str(self.bin), "HOME": str(self.home)}
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.recu_grok = (
            self.racine / CHEMIN_PREFLIGHTS / "grok-build-grok-4-6.json"
        )

    def _installer_aide(self, aide: str) -> None:
        self.aide.write_text(aide, encoding="utf-8")

    def _installer_catalogue(self, catalogue: str) -> None:
        self.catalogue.write_text(catalogue, encoding="utf-8")

    def _installer_credential(self, credential: object) -> None:
        self.auth.parent.mkdir(parents=True, exist_ok=True)
        self.auth.write_text(
            json.dumps(credential, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _script_grok(self, version: str = VERSION_JSON_SIMULEE) -> str:
        """Client simulé : une ligne de journal par invocation, args joints"""
        return (
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            'if [ "$*" = "version --json" ]; then\n'
            f"  echo '{version}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "--help" ]; then\n'
            # /bin/cat : le PATH du test ne contient que le client simulé
            f"  /bin/cat '{self.aide}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "models" ]; then\n'
            # Fidélité au client réel : avertissements ANSI sur stderr,
            # catalogue textuel sur stdout
            f"  printf '{AVERTISSEMENT_SIMULE}\\n' >&2\n"
            f"  /bin/cat '{self.catalogue}'\n"
            "  exit 0\n"
            "fi\n"
            "echo 'invocation hors contrat' >&2\n"
            "exit 64\n"
        )

    def _installer_grok(self, script: str) -> None:
        stub = self.bin / "grok"
        stub.write_text(script, encoding="utf-8")
        stub.chmod(0o755)

    def _preflight(self) -> tuple[int, str]:
        return _principal(
            ["preflight", "--configuration", "grok-build-grok-4-6"], self.racine
        )

    def _lire_recu(self) -> dict:
        return json.loads(self.recu_grok.read_text(encoding="utf-8"))


class PreflightGrokDisponibleTests(BaseXS06C):
    def test_grok_disponible_rend_hold_missing_observation_et_ecrit_recu(self):
        code, sortie = self._preflight()
        # HOLD rend 2 : version, credential configuré, sélection explicite et
        # correspondance exacte de catalogue sont observables sans
        # génération ; plan du compte, quota, effort exposé et identité
        # réellement servie restent non prouvés
        self.assertEqual(code, 2, sortie)
        self.assertIn("HOLD", sortie)
        self.assertIn("MISSING_OBSERVATION", sortie)
        self.assertTrue(self.recu_grok.is_file())
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(recu["configuration_id"], "grok-build-grok-4-6")
        self.assertEqual(recu["adaptateur"], "grok")
        self.assertEqual(recu["interface"]["client"], "grok")
        self.assertEqual(recu["interface"]["version_observee"], VERSION_SIMULEE)
        self.assertEqual(
            recu["authentification"]["observee"],
            {
                "credential_present": True,
                "auth_mode": "oidc",
                "issuer": "https://auth.x.ai",
            },
        )
        self.assertEqual(recu["plan"]["declare"], "Grok")
        # Le plan du compte n'est exposé par aucune des trois sondes
        self.assertEqual(recu["plan"]["observe"], "INCONNU")
        self.assertEqual(recu["modele"]["demande"], "grok-4.6")
        # Sélection explicite établie (option native --model et
        # correspondance de catalogue exacte) : le modèle exposé est prouvé,
        # jamais le modèle réellement servi
        self.assertEqual(recu["modele"]["expose"], "grok-4.6")
        self.assertEqual(recu["effort"]["demande"], "high")
        # L'option --reasoning-effort ne prouve pas que 'high' est exposé
        # pour grok-4.6 : sans métadonnée modèle explicite, INCONNU
        self.assertEqual(recu["effort"]["expose"], "INCONNU")
        self.assertEqual(recu["quota"]["observe"], "INCONNU")
        self.assertEqual(recu["quota"]["consommation_preflight"], "INCONNU")

    def test_projections_des_trois_sondes_fermees_et_completes(self):
        self.assertEqual(self._preflight()[0], 2)
        recu = self._lire_recu()
        self.assertEqual(
            [sonde["commande"] for sonde in recu["sondes"]],
            ["grok version --json", "grok --help", "grok models"],
        )
        self.assertEqual(
            recu["sondes"][0]["projection"], {"version": VERSION_SIMULEE}
        )
        self.assertEqual(
            recu["sondes"][1]["projection"],
            {"option_modele_native": True, "option_effort_native": True},
        )
        self.assertEqual(
            recu["sondes"][2]["projection"], {"modele_demande_present": True}
        )
        for sonde in recu["sondes"]:
            self.assertNotIn("stdout_expurge", sonde)
            self.assertNotIn("stderr_expurge", sonde)


class PreflightGrokContratRecuTests(BaseXS06C):
    def test_reference_d_v1_03_exactement_une_fois(self):
        self.assertEqual(self._preflight()[0], 2)
        texte = self.recu_grok.read_text(encoding="utf-8")
        self.assertEqual(texte.count("D-V1-03"), 1)
        recu = json.loads(texte)
        self.assertEqual(recu["autorite_preflight"], "D-V1-03")

    def test_recu_deterministe_sans_score_ni_self_hash(self):
        self.assertEqual(self._preflight()[0], 2)
        texte = self.recu_grok.read_text(encoding="utf-8")
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

    def test_recu_sans_catalogue_complet_ni_credential_prive(self):
        self.assertEqual(self._preflight()[0], 2)
        texte = self.recu_grok.read_text(encoding="utf-8")
        # Le catalogue complet, le modèle par défaut, les avertissements de
        # configuration et les autres modèles ne sont jamais persistés ; le
        # document de credential et ses champs privés non plus
        for interdit in (
            "grok-4.5",
            "ocx-cursor-grok-4-6",
            "Default model",
            "default",
            "grok.com",
            "TEMOIN-AVERTISSEMENT-CONFIG",
            "Available models",
        ) + TEMOINS_PRIVES:
            self.assertNotIn(interdit, texte)

    def test_seules_les_trois_sondes_autorisees_sont_invoquees(self):
        self.assertEqual(self._preflight()[0], 2)
        invocations = self.journal.read_text(encoding="utf-8").splitlines()
        # Exactement les trois sondes de la liste blanche, dans l'ordre,
        # jamais une forme générative, une session ni une commande --model
        self.assertEqual(
            invocations,
            ["version --json", "--help", "models"],
        )
        for interdit in (
            "--model",
            "-m",
            "-p",
            "--prompt-file",
            "agent",
            "login",
            "logout",
        ):
            for invocation in invocations:
                self.assertNotIn(interdit, invocation.split())

    def test_auth_json_jamais_modifie_par_le_preflight(self):
        avant = self.auth.read_bytes()
        self.assertEqual(self._preflight()[0], 2)
        self.assertEqual(self.auth.read_bytes(), avant)

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


class PreflightGrokIndisponibleTests(BaseXS06C):
    def test_client_introuvable_rend_un_unavailable_interface(self):
        (self.bin / "grok").unlink()
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
        self._installer_grok(
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
        # Interface non établie : aide et catalogue jamais sondés
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["version --json"],
        )

    def test_credential_absent_rend_un_unavailable_authentication(self):
        self.auth.unlink()
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("AUTHENTICATION_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "AUTHENTICATION_UNAVAILABLE")
        self.assertEqual(
            recu["authentification"]["observee"],
            {
                "credential_present": False,
                "auth_mode": "INCONNU",
                "issuer": "INCONNU",
            },
        )
        self.assertEqual(recu["plan"]["observe"], "INCONNU")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")
        # Route non authentifiée : aide et catalogue jamais sondés
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["version --json"],
        )

    def test_document_sans_credential_rend_un_unavailable_authentication(self):
        self._installer_credential({})
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "AUTHENTICATION_UNAVAILABLE")
        self.assertEqual(
            recu["authentification"]["observee"]["credential_present"], False
        )

    def test_delai_de_sonde_depasse_rend_deux_hold_harness_error(self):
        # Incident du dispositif, jamais imputé à la configuration : HOLD
        self._installer_grok("#!/bin/sh\n/bin/sleep 30\n")
        with mock.patch.object(M, "DELAI_SONDE_PREFLIGHT", 1):
            code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["interface"]["version_observee"], "INCONNU")


class PreflightGrokFailClosedTests(BaseXS06C):
    def test_version_illisible_reste_fail_closed_sans_sortie_brute(self):
        self._installer_grok(
            self._script_grok(version="TEMOIN-VERSION-ILLISIBLE hors JSON")
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][0]["projection"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-VERSION-ILLISIBLE",
            self.recu_grok.read_text(encoding="utf-8"),
        )

    def test_credential_illisible_reste_fail_closed_sans_document_brut(self):
        self.auth.write_text(
            "TEMOIN-DOCUMENT-ILLISIBLE hors JSON", encoding="utf-8"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["authentification"]["observee"], "INCONNU")
        texte = self.recu_grok.read_text(encoding="utf-8")
        self.assertNotIn("TEMOIN-DOCUMENT-ILLISIBLE", texte)
        # Forme ambiguë : aide et catalogue jamais sondés
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["version --json"],
        )

    def test_credentials_multiples_forme_ambigue_rend_deux_harness_error(self):
        credential = dict(CREDENTIAL_SIMULE)
        credential["https://auth.x.ai::TEMOIN-SECOND-PRIVE"] = dict(
            next(iter(CREDENTIAL_SIMULE.values()))
        )
        self._installer_credential(credential)
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["authentification"]["observee"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-SECOND-PRIVE", self.recu_grok.read_text(encoding="utf-8")
        )

    def test_credential_hors_oidc_rend_un_sans_persister_le_mode(self):
        credential = {
            "https://auth.x.ai::TEMOIN-UUID-PRIVE": {
                **next(iter(CREDENTIAL_SIMULE.values())),
                "auth_mode": "TEMOIN-MODE-PRIVE",
            }
        }
        self._installer_credential(credential)
        code, sortie = self._preflight()
        # Un credential présent hors de la forme OAuth xAI documentée n'est
        # pas un credential OAuth xAI configuré
        self.assertEqual(code, 1, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "AUTHENTICATION_UNAVAILABLE")
        self.assertEqual(
            recu["authentification"]["observee"],
            {
                "credential_present": True,
                "auth_mode": "INCONNU",
                "issuer": "INCONNU",
            },
        )
        self.assertNotIn(
            "TEMOIN-MODE-PRIVE", self.recu_grok.read_text(encoding="utf-8")
        )

    def test_credential_issuer_divergent_rend_un_sans_persister_l_issuer(self):
        credential = {
            "https://auth.x.ai::TEMOIN-UUID-PRIVE": {
                **next(iter(CREDENTIAL_SIMULE.values())),
                "oidc_issuer": "https://TEMOIN-ISSUER-PRIVE.example",
            }
        }
        self._installer_credential(credential)
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "AUTHENTICATION_UNAVAILABLE")
        self.assertEqual(
            recu["authentification"]["observee"]["issuer"], "INCONNU"
        )
        self.assertNotIn(
            "TEMOIN-ISSUER-PRIVE",
            self.recu_grok.read_text(encoding="utf-8"),
        )

    def test_issuer_normalise_barre_finale_reste_conforme(self):
        credential = {
            "https://auth.x.ai::TEMOIN-UUID-PRIVE": {
                **next(iter(CREDENTIAL_SIMULE.values())),
                "oidc_issuer": "https://auth.x.ai/",
            }
        }
        self._installer_credential(credential)
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(
            recu["authentification"]["observee"]["issuer"],
            "https://auth.x.ai",
        )

    def test_aide_sans_option_model_rend_un_model_unavailable(self):
        # Sans option native --model, la sélection explicite est impossible ;
        # le modèle par défaut grok-4.6 ne vaut jamais preuve du pin
        self._installer_aide(
            "Usage: grok [OPTIONS]\n"
            "      --reasoning-effort <EFFORT>  Reasoning effort\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("MODEL_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "MODEL_UNAVAILABLE")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")
        self.assertEqual(
            recu["sondes"][1]["projection"],
            {"option_modele_native": False, "option_effort_native": True},
        )
        # Sélection explicite impossible : le catalogue n'est jamais sondé
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["version --json", "--help"],
        )

    def test_aide_sans_option_effort_reste_hold_et_effort_inconnu(self):
        self._installer_aide(
            "Usage: grok [OPTIONS]\n  -m, --model <MODEL>  Model ID to use\n"
        )
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(
            recu["sondes"][1]["projection"],
            {"option_modele_native": True, "option_effort_native": False},
        )
        self.assertEqual(recu["effort"]["expose"], "INCONNU")

    def test_catalogue_sans_correspondance_exacte_rend_un_model_unavailable(self):
        # Ni alias ni préfixe approximatif : grok-4.6-fast et
        # ocx-cursor-grok-4-6 ne valent jamais pour grok-4.6, même annoncé
        # comme modèle par défaut
        self._installer_catalogue(
            "You are logged in with grok.com.\n\n"
            "Default model: grok-4.6\n\n"
            "Available models:\n"
            "  - grok-4.6-fast\n"
            "  - ocx-cursor-grok-4-6\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("MODEL_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "MODEL_UNAVAILABLE")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")
        self.assertEqual(
            recu["sondes"][2]["projection"], {"modele_demande_present": False}
        )

    def test_catalogue_illisible_reste_fail_closed_sans_sortie_brute(self):
        self._installer_catalogue("TEMOIN-CATALOGUE-ILLISIBLE sans section\n")
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][2]["projection"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-CATALOGUE-ILLISIBLE",
            self.recu_grok.read_text(encoding="utf-8"),
        )

    def test_catalogue_en_echec_reste_fail_closed(self):
        self._installer_grok(
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            'if [ "$*" = "version --json" ]; then\n'
            f"  echo '{VERSION_JSON_SIMULEE}'\n  exit 0\nfi\n"
            'if [ "$*" = "--help" ]; then\n'
            f"  /bin/cat '{self.aide}'\n  exit 0\nfi\n"
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


class RestitutionPreflightGrokTests(BaseXS06C):
    """Section MSW du préflight Grok : verdict, cause et INCONNU sourcés."""

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

    def test_page_affiche_le_preflight_grok_et_le_verificateur_confirme(self):
        self.assertEqual(self._preflight()[0], 2)
        page = self._restituer()
        self.assertIn('<section id="preflights">', page)
        self.assertIn('data-preflight="grok-build-grok-4-6"', page)
        recu = self._lire_recu()
        self.assertIn(recu["date_preflight"], page)
        self.assertIn("MISSING_OBSERVATION", page)
        # Projections grok rendues : credential, options natives, catalogue
        self.assertIn("credential_present", page)
        self.assertIn("option_modele_native", page)
        self.assertIn("modele_demande_present", page)
        for interdit in TEMOINS_PRIVES:
            self.assertNotIn(interdit, page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_preflight_grok_unavailable_apparait_avec_sa_cause(self):
        (self.bin / "grok").unlink()
        self.assertEqual(self._preflight()[0], 1)
        page = self._restituer()
        self.assertIn("UNAVAILABLE", page)
        self.assertIn("INTERFACE_UNAVAILABLE", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_restitutions_successives_byte_identiques_avec_preflight_grok(self):
        self.assertEqual(self._preflight()[0], 2)
        self.assertEqual(self._restituer(), self._restituer())

    def test_verifier_refuse_un_recu_grok_altere_apres_restitution(self):
        self.assertEqual(self._preflight()[0], 2)
        self._restituer()
        self.recu_grok.write_bytes(self.recu_grok.read_bytes() + b" ")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def _muter_recu(self, transformer) -> None:
        recu = self._lire_recu()
        transformer(recu)
        self.recu_grok.write_text(
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_recu_grok_hors_vocabulaire_leve_erreur_restitution(self):
        mutations = {
            # Une forme générative ou une commande --model n'entre jamais
            # dans la liste blanche grok
            "sonde-agent-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "grok agent bonjour",
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
                            "commande": "grok models --model grok-4.6",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            # Une sonde codex ne vaut jamais pour l'adaptateur grok
            "sonde-codex-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "codex login status",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            "adaptateur-hors-vocabulaire": lambda recu: recu.update(
                {"adaptateur": "cursor"}
            ),
            # La forme d'authentification codex ne vaut pas pour grok
            "auth-forme-codex": lambda recu: recu.update(
                {
                    "authentification": {
                        "observee": {"connecte": True, "methode": "ChatGPT"}
                    }
                }
            ),
            "projection-catalogue-polluee": lambda recu: recu["sondes"][
                2
            ].update(
                {
                    "projection": {
                        "modele_demande_present": True,
                        "catalogue_complet": ["grok-4.5"],
                    }
                }
            ),
            # READY exige les cinq observations : plan et quota INCONNU
            # l'interdisent
            "ready-sans-observation-complete": lambda recu: recu.update(
                {"verdict": "READY", "cause": None}
            ),
        }
        for nom, transformer in mutations.items():
            with self.subTest(mutation=nom):
                if self.recu_grok.exists():
                    self.recu_grok.unlink()
                self.assertEqual(self._preflight()[0], 2)
                self._restituer()
                self._muter_recu(transformer)
                with self.assertRaises(M.ErreurRestitution):
                    M.verifier_restitution(self.racine)
                code, _ = _principal(["verifier-restitution"], self.racine)
                self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
