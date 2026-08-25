# /// script
# requires-python = ">=3.12,<3.13"
# ///
"""Contrôles XS-06A : préflight Claude Code pour Fable 5 et Opus 5.

La frontière système simulée est le client `claude` lui-même : un exécutable
de substitution est placé seul sur le PATH et journalise chaque invocation.
Aucun collaborateur interne n'est simulé.
"""

from __future__ import annotations

import contextlib
import hashlib
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
VERSION_SIMULEE = "2.1.245 (Claude Code)"
# Statut simulé : les champs privés email et orgName prouvent par leur
# présence à la frontière que la projection ne les consigne jamais
AUTH_SIMULE = (
    '{"loggedIn": true, "authMethod": "claude.ai", "apiProvider": "firstParty",'
    ' "subscriptionType": "max", "email": "prive@example.com",'
    ' "orgId": "org-prive-123", "orgName": "Org Privee"}'
)


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS06A(unittest.TestCase):
    """Racine isolée : état V1, registre officiel et client claude simulé."""

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
        # Frontière système : seul un client claude simulé vit sur le PATH ;
        # il journalise ses arguments, preuve qu'aucune forme générative
        # (-p, --print, prompt positionnel, session) n'est jamais invoquée
        self.bin = self.racine / "bin-simule"
        self.bin.mkdir()
        self.journal = self.racine / "journal-claude.txt"
        self._installer_claude(self._script_claude())
        patch = mock.patch.dict(os.environ, {"PATH": str(self.bin)})
        patch.start()
        self.addCleanup(patch.stop)
        self.recu_fable = (
            self.racine / CHEMIN_PREFLIGHTS / "claude-code-fable-5.json"
        )
        self.recu_opus = (
            self.racine / CHEMIN_PREFLIGHTS / "claude-code-opus-5.json"
        )

    def _script_claude(self, auth_json: str = AUTH_SIMULE) -> str:
        """Client simulé : une ligne de journal par invocation, args joints"""
        return (
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            'if [ "$*" = "--version" ]; then\n'
            f"  echo '{VERSION_SIMULEE}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "auth status --json" ]; then\n'
            f"  printf '%s\\n' '{auth_json}'\n"
            "  exit 0\n"
            "fi\n"
            "echo 'invocation hors contrat' >&2\n"
            "exit 64\n"
        )

    def _installer_claude(self, script: str) -> None:
        stub = self.bin / "claude"
        stub.write_text(script, encoding="utf-8")
        stub.chmod(0o755)

    def _preflight(self, identifiant: str) -> tuple[int, str]:
        return _principal(
            ["preflight", "--configuration", identifiant], self.racine
        )

    def _lire_recu(self, chemin: Path) -> dict:
        return json.loads(chemin.read_text(encoding="utf-8"))


class PreflightClaudeDisponibleTests(BaseXS06A):
    def test_claude_disponible_rend_hold_missing_observation_et_ecrit_recu(self):
        code, sortie = self._preflight("claude-code-fable-5")
        # HOLD rend 2 : version, authentification et plan sont observables
        # sans génération, l'identité du modèle servi reste non prouvée
        self.assertEqual(code, 2, sortie)
        self.assertIn("HOLD", sortie)
        self.assertIn("MISSING_OBSERVATION", sortie)
        self.assertTrue(self.recu_fable.is_file())
        recu = self._lire_recu(self.recu_fable)
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(recu["configuration_id"], "claude-code-fable-5")
        self.assertEqual(recu["modele"]["demande"], "claude-fable-5")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")
        self.assertEqual(recu["interface"]["version_observee"], VERSION_SIMULEE)
        self.assertEqual(
            recu["authentification"]["observee"],
            {
                "loggedIn": True,
                "authMethod": "claude.ai",
                "apiProvider": "firstParty",
            },
        )
        self.assertEqual(recu["plan"]["declare"], "Claude Code")
        self.assertEqual(recu["plan"]["observe"], "max")
        self.assertEqual(recu["effort"]["demande"], "high")
        self.assertEqual(recu["effort"]["expose"], "INCONNU")
        self.assertEqual(recu["quota"]["observe"], "INCONNU")
        self.assertEqual(recu["quota"]["consommation_preflight"], "INCONNU")
        # Le fait MSW ne prétend plus inobservé ce qui a été observé
        self.assertIn("authentification et plan observés", recu["fait"])
        self.assertNotIn("authentification, plan servi", recu["fait"])
        self.assertIn("modèle", recu["fait"])

    def test_sonde_auth_projetee_sans_sortie_brute_ni_champ_prive(self):
        self.assertEqual(self._preflight("claude-code-fable-5")[0], 2)
        texte = self.recu_fable.read_text(encoding="utf-8")
        # Les champs privés servis par la frontière ne sont jamais consignés
        for prive in ("email", "prive@example.com", "orgId", "org-prive-123",
                      "orgName", "Org Privee"):
            self.assertNotIn(prive, texte)
        recu = self._lire_recu(self.recu_fable)
        sonde_auth = recu["sondes"][1]
        self.assertEqual(sonde_auth["commande"], "claude auth status --json")
        self.assertEqual(sonde_auth["code_sortie"], 0)
        # Projection déterministe des quatre seuls champs, pas de stdout
        self.assertEqual(
            sonde_auth["projection"],
            {
                "loggedIn": True,
                "authMethod": "claude.ai",
                "apiProvider": "firstParty",
                "subscriptionType": "max",
            },
        )
        self.assertNotIn("stdout_expurge", sonde_auth)
        self.assertNotIn("stderr_expurge", sonde_auth)

    def test_deconnecte_rend_un_unavailable_authentication(self):
        self._installer_claude(
            self._script_claude('{"loggedIn": false}')
        )
        code, sortie = self._preflight("claude-code-fable-5")
        self.assertEqual(code, 1, sortie)
        self.assertIn("AUTHENTICATION_UNAVAILABLE", sortie)
        recu = self._lire_recu(self.recu_fable)
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "AUTHENTICATION_UNAVAILABLE")
        self.assertEqual(
            recu["authentification"]["observee"]["loggedIn"], False
        )
        self.assertEqual(recu["plan"]["observe"], "INCONNU")

    def test_json_auth_illisible_reste_fail_closed_sans_sortie_brute(self):
        self._installer_claude(
            self._script_claude("statut illisible hors JSON")
        )
        code, sortie = self._preflight("claude-code-fable-5")
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu(self.recu_fable)
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["authentification"]["observee"], "INCONNU")
        self.assertEqual(recu["plan"]["observe"], "INCONNU")
        self.assertEqual(recu["sondes"][1]["projection"], "INCONNU")
        # La sortie brute inexploitable n'est jamais consignée
        self.assertNotIn(
            "statut illisible hors JSON",
            self.recu_fable.read_text(encoding="utf-8"),
        )

    def test_structure_auth_attendue_absente_reste_fail_closed(self):
        # loggedIn vrai sans subscriptionType : structure attendue absente
        self._installer_claude(
            self._script_claude(
                '{"loggedIn": true, "authMethod": "claude.ai",'
                ' "apiProvider": "firstParty"}'
            )
        )
        code, _ = self._preflight("claude-code-fable-5")
        self.assertEqual(code, 2)
        recu = self._lire_recu(self.recu_fable)
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["authentification"]["observee"], "INCONNU")
        self.assertEqual(recu["plan"]["observe"], "INCONNU")


class PreflightRecuContratTests(BaseXS06A):
    def test_recu_deterministe_date_utc_sans_score_ni_self_hash_ni_racine(self):
        code, _ = self._preflight("claude-code-fable-5")
        self.assertEqual(code, 2)
        texte = self.recu_fable.read_text(encoding="utf-8")
        recu = json.loads(texte)
        self.assertEqual(recu["schema_version"], "campagne-v1-preflight/v1")
        self.assertRegex(
            recu["date_preflight"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        )
        # Sérialisation déterministe et lisible, sans self-hash ni racine
        self.assertEqual(
            texte,
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        for interdit in ("score", "content_address", "proof_root", "self_hash"):
            self.assertNotIn(interdit, recu)
            self.assertNotIn(f'"{interdit}"', texte)

    def test_reference_d_v1_03_exactement_une_fois(self):
        self.assertEqual(self._preflight("claude-code-opus-5")[0], 2)
        texte = self.recu_opus.read_text(encoding="utf-8")
        self.assertEqual(texte.count("D-V1-03"), 1)
        recu = json.loads(texte)
        self.assertEqual(recu["autorite_preflight"], "D-V1-03")

    def test_les_deux_configurations_recoivent_chacune_un_recu_separe(self):
        self.assertEqual(self._preflight("claude-code-fable-5")[0], 2)
        self.assertEqual(self._preflight("claude-code-opus-5")[0], 2)
        fable = self._lire_recu(self.recu_fable)
        opus = self._lire_recu(self.recu_opus)
        self.assertEqual(fable["modele"]["demande"], "claude-fable-5")
        self.assertEqual(opus["modele"]["demande"], "claude-opus-5")
        self.assertEqual(opus["configuration_id"], "claude-code-opus-5")

    def test_sortie_de_sonde_expurgee_du_chemin_personnel(self):
        # La frontière simulée fait fuiter le chemin du compte local : le
        # reçu consigné doit l'expurger
        self._installer_claude(
            "#!/bin/sh\n"
            f"echo '{VERSION_SIMULEE} depuis {Path.home()}/.claude'\n"
            "exit 0\n"
        )
        self.assertEqual(self._preflight("claude-code-fable-5")[0], 2)
        texte = self.recu_fable.read_text(encoding="utf-8")
        self.assertNotIn(str(Path.home()), texte)
        recu = json.loads(texte)
        self.assertIn("~/.claude", recu["sondes"][0]["stdout_expurge"])

    def test_seules_les_deux_sondes_autorisees_sont_invoquees(self):
        self.assertEqual(self._preflight("claude-code-fable-5")[0], 2)
        self.assertEqual(self._preflight("claude-code-opus-5")[0], 2)
        invocations = self.journal.read_text(encoding="utf-8").splitlines()
        # Exactement les deux sondes de la liste blanche, dans l'ordre,
        # jamais une forme générative ni une session
        self.assertEqual(
            invocations,
            ["--version", "auth status --json"] * 2,
        )
        for interdit in ("-p", "--print", "--model", "--continue", "--resume"):
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
        self.assertEqual(self._preflight("claude-code-fable-5")[0], 2)
        apres = sorted(
            (chemin.name, chemin.read_bytes())
            for chemin in repertoire.iterdir()
        )
        self.assertEqual(avant, apres)


class PreflightIndisponibleTests(BaseXS06A):
    def test_client_introuvable_rend_un_unavailable_interface(self):
        (self.bin / "claude").unlink()
        code, sortie = self._preflight("claude-code-fable-5")
        # UNAVAILABLE rend 1 : l'interface est absente
        self.assertEqual(code, 1, sortie)
        self.assertIn("UNAVAILABLE", sortie)
        self.assertIn("INTERFACE_UNAVAILABLE", sortie)
        recu = self._lire_recu(self.recu_fable)
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "INTERFACE_UNAVAILABLE")
        self.assertEqual(recu["interface"]["version_observee"], "INCONNU")
        self.assertEqual(recu["sondes"], [])

    def test_sonde_version_en_echec_rend_un_unavailable_interface(self):
        self._installer_claude(
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            "echo 'client défaillant' >&2\nexit 7\n"
        )
        code, sortie = self._preflight("claude-code-fable-5")
        self.assertEqual(code, 1, sortie)
        recu = self._lire_recu(self.recu_fable)
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "INTERFACE_UNAVAILABLE")
        self.assertEqual(recu["sondes"][0]["code_sortie"], 7)
        self.assertEqual(recu["interface"]["version_observee"], "INCONNU")
        # Interface non établie : la sonde auth n'est jamais lancée
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version"],
        )

    def test_delai_de_sonde_depasse_rend_deux_hold_harness_error(self):
        # Incident du dispositif, jamais imputé à la configuration : HOLD
        self._installer_claude("#!/bin/sh\n/bin/sleep 30\n")
        with mock.patch.object(M, "DELAI_SONDE_PREFLIGHT", 1):
            code, sortie = self._preflight("claude-code-fable-5")
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu(self.recu_fable)
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["interface"]["version_observee"], "INCONNU")


class PreflightRefusTests(BaseXS06A):
    def test_configuration_absente_du_registre_rend_un_sans_recu(self):
        code, sortie = self._preflight("configuration-fantome")
        self.assertEqual(code, 1)
        self.assertIn("ECHEC", sortie)
        self.assertIn("configuration-fantome", sortie)
        self.assertFalse((self.racine / CHEMIN_PREFLIGHTS).exists())

    def test_adaptateur_non_claude_rend_un_sans_recu(self):
        code, sortie = self._preflight("codex-gpt-5-6-sol")
        self.assertEqual(code, 1)
        self.assertIn("ECHEC", sortie)
        self.assertIn("V1-XS-06B", sortie)
        self.assertFalse((self.racine / CHEMIN_PREFLIGHTS).exists())
        self.assertFalse(self.journal.exists())

    def test_preflight_sans_configuration_rend_un_sans_recu(self):
        code, sortie = _principal(["preflight"], self.racine)
        self.assertEqual(code, 1)
        self.assertIn("ECHEC", sortie)
        self.assertFalse((self.racine / CHEMIN_PREFLIGHTS).exists())

    def test_forme_cli_hors_contrat_rend_deux(self):
        for arguments in (
            ["preflight", "--configuration"],
            ["preflight", "--force", "x"],
        ):
            with self.subTest(arguments=arguments):
                code, sortie = _principal(arguments, self.racine)
                self.assertEqual(code, 2)
                self.assertIn("usage", sortie)


_SOURCES_RESTITUTION = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES)


class RestitutionPreflightTests(BaseXS06A):
    """Section MSW des préflights : verdict, cause et INCONNU sourcés."""

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

    def _deux_preflights(self) -> None:
        self.assertEqual(self._preflight("claude-code-fable-5")[0], 2)
        self.assertEqual(self._preflight("claude-code-opus-5")[0], 2)

    def _muter_recu(self, chemin: Path, transformer) -> None:
        recu = self._lire_recu(chemin)
        transformer(recu)
        chemin.write_text(
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_page_affiche_verdict_cause_et_inconnu_pour_chaque_preflight(self):
        self._deux_preflights()
        page = self._restituer()
        self.assertIn('<section id="preflights">', page)
        self.assertEqual(page.count(' data-preflight="'), 2)
        for identifiant, recu_chemin in (
            ("claude-code-fable-5", self.recu_fable),
            ("claude-code-opus-5", self.recu_opus),
        ):
            recu = self._lire_recu(recu_chemin)
            self.assertIn(f'data-preflight="{identifiant}"', page)
            self.assertIn(recu["date_preflight"], page)
            # Fait MSW sourcé par le reçu de préflight versionné
            relatif = f"{CHEMIN_PREFLIGHTS}/{identifiant}.json"
            empreinte = hashlib.sha256(recu_chemin.read_bytes()).hexdigest()
            self.assertIn(
                f'data-chemin="{relatif}" data-sha256="{empreinte}"', page
            )
        self.assertIn("HOLD", page)
        self.assertIn("MISSING_OBSERVATION", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_preflight_unavailable_apparait_avec_sa_cause(self):
        (self.bin / "claude").unlink()
        self.assertEqual(self._preflight("claude-code-fable-5")[0], 1)
        page = self._restituer()
        self.assertIn("UNAVAILABLE", page)
        self.assertIn("INTERFACE_UNAVAILABLE", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_sans_preflight_la_page_reste_conforme_sans_section(self):
        page = self._restituer()
        self.assertNotIn('<section id="preflights">', page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_restitutions_successives_byte_identiques_avec_preflights(self):
        self._deux_preflights()
        self.assertEqual(self._restituer(), self._restituer())

    def test_verifier_refuse_un_recu_altere_apres_restitution(self):
        self._deux_preflights()
        self._restituer()
        self.recu_fable.write_bytes(self.recu_fable.read_bytes() + b" ")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def test_verifier_refuse_un_article_preflight_injecte(self):
        page = self._restituer()
        self.page.write_text(
            page.replace(
                "</body>",
                '<article class="affirmation" data-classe="fait" '
                'data-preflight="claude-code-fable-5"><p>préflight inventé</p>'
                "</article></body>",
            ),
            encoding="utf-8",
        )
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def test_recu_hors_vocabulaire_leve_erreur_restitution(self):
        mutations = {
            "verdict-hors-vocabulaire": lambda recu: recu.update(
                {"verdict": "PASS"}
            ),
            "cause-hors-vocabulaire": lambda recu: recu.update(
                {"cause": "RESEAU_LENT"}
            ),
            "cause-incoherente-avec-verdict": lambda recu: recu.update(
                {"cause": "INTERFACE_UNAVAILABLE"}
            ),
            "autorite-divergente": lambda recu: recu.update(
                {"autorite_preflight": "D-V1-01"}
            ),
            "score-injecte": lambda recu: recu.update({"score": 10}),
            "sonde-generative-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "claude -p bonjour",
                            "code_sortie": 0,
                            "stdout_expurge": "",
                            "stderr_expurge": "",
                        }
                    ]
                }
            ),
            "sonde-continue-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "claude --continue",
                            "code_sortie": 0,
                            "stdout_expurge": "",
                            "stderr_expurge": "",
                        }
                    ]
                }
            ),
            "sonde-skip-permissions-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "claude --dangerously-skip-permissions",
                            "code_sortie": 0,
                            "stdout_expurge": "",
                            "stderr_expurge": "",
                        }
                    ]
                }
            ),
            # READY exige les cinq observations : auth, plan, modèle exposé,
            # effort exposé et quota ne peuvent rester INCONNU
            "ready-sans-observation-complete": lambda recu: recu.update(
                {"verdict": "READY", "cause": None}
            ),
        }
        for nom, transformer in mutations.items():
            with self.subTest(mutation=nom):
                for chemin in (self.recu_fable, self.recu_opus):
                    if chemin.exists():
                        chemin.unlink()
                self._deux_preflights()
                self._restituer()
                self._muter_recu(self.recu_fable, transformer)
                with self.assertRaises(M.ErreurRestitution):
                    M.verifier_restitution(self.racine)
                code, _ = _principal(["verifier-restitution"], self.racine)
                self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
