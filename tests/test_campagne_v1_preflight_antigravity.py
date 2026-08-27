# /// script
# requires-python = ">=3.12,<3.13"
# ///
"""Contrôles XS-06F : préflight Antigravity pour Gemini 3.7 Flash (High).

La frontière système simulée est le client `agy` lui-même — un exécutable
de substitution placé seul sur le PATH qui journalise ses arguments exacts
et sert uniquement des sorties expurgées de test. Aucun collaborateur
interne n'est simulé. Fidélité au diagnostic de lancement couvert par
D-V1-03 : `agy --version` rend la version, `agy models` rend le catalogue
texte avec l'entrée exacte `gemini-3.7-flash-high` libellée
`Gemini 3.7 Flash (High)`, et `agy -p /usage` rend les deux lignes
`Gemini Models` avec leurs fenêtres `Weekly Limit Remaining` et
`Five Hour Limit Remaining` sous la forme réelle expurgée : pourcentage
restant puis reset ISO 8601 en dernier champ de la même ligne, sans mot
reset.
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
# Sortie brute fidèle à l'observation réelle de cette tranche : le reçu
# réel projette '1.1.21' avec la projection première ligne non vide, donc
# la première ligne servie par le vrai client est '1.1.21' ; le libellé
# 'agy 1.1.21' du diagnostic nomme le client plus sa version, il n'est pas
# le verbatim stdout
VERSION_SIMULEE = "1.1.21"
# Catalogue simulé : l'entrée exacte avec son libellé exact, plus une entrée
# témoin qui prouve par sa présence à la frontière que les autres modèles ne
# sont jamais conservés
CATALOGUE_SIMULE = (
    "Available models:\n"
    "  gemini-3.7-flash-high - Gemini 3.7 Flash (High)\n"
    "  temoin-autre-modele - TEMOIN Modèle Privé\n"
)
# /usage simulé conforme à la forme réelle expurgée du diagnostic : les
# deux lignes Gemini Models à 100 % restant avec reset ISO 8601 en dernier
# champ sans mot reset, plus des lignes Claude/GPT témoins jamais
# conservées
USAGE_SIMULE = (
    "Usage snapshot\n"
    "Claude Models Weekly Limit Remaining 63.5% 2026-12-31T23:59:59Z\n"
    "GPT Models Weekly Limit Remaining 41.5% 2026-11-30T23:59:59Z\n"
    "Gemini Models Weekly Limit Remaining 100% 2026-09-02T12:58:23Z\n"
    "Gemini Models Five Hour Limit Remaining 100% 2026-08-26T17:58:23Z\n"
)
SONDES_ATTENDUES = ["--version", "models", "-p /usage"]


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS06F(unittest.TestCase):
    """Racine isolée : état V1, registre officiel et client agy simulé."""

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
        # Frontière système : seul un client agy simulé vit sur le PATH ; il
        # journalise ses arguments exacts, preuve qu'aucune forme TUI,
        # interactive, générative ou de mutation (agy -i,
        # --prompt-interactive, -p hors littéral /usage, update, install,
        # plugin, mcp, /model, /credits, /logout, connexion, --model,
        # --effort, --agent, --continue, --conversation, --project, --mode,
        # --sandbox, --dangerously-skip-permissions) n'est jamais invoquée ;
        # le vrai agy n'existe pas sur ce PATH
        self.bin = self.racine / "bin-simule"
        self.bin.mkdir()
        self.journal = self.racine / "journal-agy.txt"
        self.catalogue = self.bin / "catalogue-simule.txt"
        self.usage = self.bin / "usage-simule.txt"
        self._installer_catalogue(CATALOGUE_SIMULE)
        self._installer_usage(USAGE_SIMULE)
        self._installer_agy(self._script_agy())
        patch = mock.patch.dict(os.environ, {"PATH": str(self.bin)})
        patch.start()
        self.addCleanup(patch.stop)
        self.recu_antigravity = (
            self.racine / CHEMIN_PREFLIGHTS / "antigravity-gemini-3-7-flash.json"
        )

    def _installer_catalogue(self, contenu: str) -> None:
        self.catalogue.write_text(contenu, encoding="utf-8")

    def _installer_usage(self, contenu: str) -> None:
        self.usage.write_text(contenu, encoding="utf-8")

    def _script_agy(self, version: str = VERSION_SIMULEE) -> str:
        """Client simulé : une ligne de journal par invocation, args joints"""
        return (
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            'if [ "$*" = "--version" ]; then\n'
            f"  echo '{version}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "models" ]; then\n'
            # /bin/cat : le PATH du test ne contient que le client simulé
            f"  /bin/cat '{self.catalogue}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "-p /usage" ]; then\n'
            f"  /bin/cat '{self.usage}'\n"
            "  exit 0\n"
            "fi\n"
            "echo 'invocation hors contrat' >&2\n"
            "exit 64\n"
        )

    def _installer_agy(self, script: str) -> None:
        stub = self.bin / "agy"
        stub.write_text(script, encoding="utf-8")
        stub.chmod(0o755)

    def _preflight(self) -> tuple[int, str]:
        return _principal(
            ["preflight", "--configuration", "antigravity-gemini-3-7-flash"],
            self.racine,
        )

    def _lire_recu(self) -> dict:
        return json.loads(self.recu_antigravity.read_text(encoding="utf-8"))


class PreflightAntigravityDisponibleTests(BaseXS06F):
    def test_route_prete_rend_zero_ready_et_ecrit_recu(self):
        code, sortie = self._preflight()
        # READY rend 0 : les cinq contrôles sont observés par les trois
        # probes non génératives ; l'identité réellement servie reste INCONNU
        self.assertEqual(code, 0, sortie)
        self.assertIn("READY", sortie)
        self.assertTrue(self.recu_antigravity.is_file())
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "READY")
        self.assertIsNone(recu["cause"])
        self.assertEqual(
            recu["configuration_id"], "antigravity-gemini-3-7-flash"
        )
        self.assertEqual(recu["adaptateur"], "agy")
        self.assertEqual(recu["interface"]["type"], "cli")
        self.assertEqual(recu["interface"]["client"], "agy")
        self.assertEqual(recu["interface"]["version_observee"], VERSION_SIMULEE)
        # Authentification de métadonnées : accessibilité observée, jamais
        # une identité de compte
        self.assertEqual(
            recu["authentification"]["observee"],
            {
                "metadonnees_catalogue_accessibles": True,
                "metadonnees_quota_accessibles": True,
            },
        )
        self.assertEqual(recu["plan"]["declare"], "Gemini")
        # La catégorie observée prouve une catégorie de quota active, jamais
        # un palier tarifaire, un prix ou une facture
        self.assertEqual(
            recu["plan"]["observe"],
            "catégorie 'Gemini Models' active dans /usage, palier commercial "
            "non observé",
        )
        self.assertEqual(recu["modele"]["demande"], "gemini-3.7-flash-high")
        # L'identifiant exact exposé porte la variante d'effort en suffixe
        self.assertEqual(recu["modele"]["expose"], "gemini-3.7-flash-high")
        self.assertEqual(recu["effort"]["demande"], "high")
        self.assertEqual(recu["effort"]["expose"], "high")
        self.assertEqual(
            recu["quota"]["observe"],
            {
                "source": "agy:/usage",
                "fenetres": {
                    "cinq_heures": {
                        "pourcentage_restant": 100,
                        "reset": "2026-08-26T17:58:23Z",
                    },
                    "hebdomadaire": {
                        "pourcentage_restant": 100,
                        "reset": "2026-09-02T12:58:23Z",
                    },
                },
            },
        )
        self.assertEqual(recu["quota"]["consommation_preflight"], "INCONNU")

    def test_objets_distincts_du_recu(self):
        self.assertEqual(self._preflight()[0], 0)
        recu = self._lire_recu()
        # L'identité réellement servie reste INCONNU sans génération, jamais
        # une conclusion déduite du catalogue, du quota ou du client
        self.assertEqual(recu["identite_reellement_servie"], "INCONNU")
        self.assertEqual(recu["autorite_preflight"], "D-V1-03")
        self.assertEqual(
            recu["commande_publique"],
            "uv run tools/campagne_v1.py preflight --configuration "
            "antigravity-gemini-3-7-flash",
        )

    def test_forme_reelle_du_diagnostic_rend_ready_sans_missing_observation(self):
        # Régression du faux MISSING_OBSERVATION de la première passe : la
        # forme réelle expurgée porte le reset ISO 8601 en dernier champ de
        # la même ligne, sans mot reset ; elle doit rendre READY
        self._installer_usage(
            "Gemini Models Weekly Limit Remaining 100% 2026-09-02T12:58:23Z\n"
            "Gemini Models Five Hour Limit Remaining 100% "
            "2026-08-26T17:58:23Z\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 0, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "READY")
        self.assertNotEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(
            recu["quota"]["observe"]["fenetres"],
            {
                "cinq_heures": {
                    "pourcentage_restant": 100,
                    "reset": "2026-08-26T17:58:23Z",
                },
                "hebdomadaire": {
                    "pourcentage_restant": 100,
                    "reset": "2026-09-02T12:58:23Z",
                },
            },
        )

    def test_version_brute_avec_prefixe_client_reste_projetee_entiere(self):
        # Le diagnostic libelle le client 'agy 1.1.21' ; si le client sert
        # cette forme brute, la projection garde la ligne entière non vide,
        # sans extraction inventée
        self._installer_agy(self._script_agy(version="agy 1.1.21"))
        code, _ = self._preflight()
        self.assertEqual(code, 0)
        recu = self._lire_recu()
        self.assertEqual(recu["interface"]["version_observee"], "agy 1.1.21")
        self.assertEqual(
            recu["sondes"][0]["projection"], {"version": "agy 1.1.21"}
        )

    def test_projections_des_trois_sondes_fermees_et_completes(self):
        self.assertEqual(self._preflight()[0], 0)
        recu = self._lire_recu()
        self.assertEqual(
            [sonde["commande"] for sonde in recu["sondes"]],
            [f"agy {suite}".strip() for suite in SONDES_ATTENDUES],
        )
        self.assertEqual(
            recu["sondes"][0]["projection"], {"version": VERSION_SIMULEE}
        )
        self.assertEqual(
            recu["sondes"][1]["projection"],
            {"entree_exacte_presente": True, "libelle_concordant": True},
        )
        self.assertEqual(
            recu["sondes"][2]["projection"],
            {
                "categorie_gemini_presente": True,
                "fenetres_reconnues": ["cinq_heures", "hebdomadaire"],
            },
        )
        for sonde in recu["sondes"]:
            self.assertNotIn("stdout_expurge", sonde)
            self.assertNotIn("stderr_expurge", sonde)


class PreflightAntigravityIndisponibleTests(BaseXS06F):
    def test_client_introuvable_rend_un_unavailable_interface(self):
        (self.bin / "agy").unlink()
        code, sortie = self._preflight()
        # UNAVAILABLE rend 1 : l'interface est absente
        self.assertEqual(code, 1, sortie)
        self.assertIn("INTERFACE_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "INTERFACE_UNAVAILABLE")
        self.assertEqual(recu["interface"]["version_observee"], "INCONNU")
        self.assertEqual(recu["identite_reellement_servie"], "INCONNU")
        self.assertEqual(recu["sondes"], [])

    def test_version_en_echec_rend_un_sans_autre_probe(self):
        self._installer_agy(
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
        # Interface non établie : catalogue et usage jamais sondés
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version"],
        )

    def test_authentification_requise_rend_un_authentication_unavailable(self):
        self._installer_agy(
            self._script_agy().replace(
                f"  /bin/cat '{self.catalogue}'\n  exit 0",
                "  echo 'Not logged in. Please sign in to continue.' >&2\n"
                "  exit 3",
            )
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("AUTHENTICATION_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "AUTHENTICATION_UNAVAILABLE")
        # Accessibilité observée fausse, jamais une identité de compte ; le
        # message brut n'est pas consigné
        self.assertEqual(
            recu["authentification"]["observee"],
            {
                "metadonnees_catalogue_accessibles": False,
                "metadonnees_quota_accessibles": "INCONNU",
            },
        )
        self.assertNotIn(
            "Please sign in",
            self.recu_antigravity.read_text(encoding="utf-8"),
        )
        # Session absente : la probe d'usage n'est pas lancée
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version", "models"],
        )

    def test_entree_exacte_absente_rend_un_model_unavailable(self):
        self._installer_catalogue(
            "Available models:\n"
            "  gemini-3.7-flash - Gemini 3.7 Flash\n"
            "  temoin-autre-modele - TEMOIN Modèle Privé\n"
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
            recu["sondes"][1]["projection"],
            {"entree_exacte_presente": False, "libelle_concordant": "INCONNU"},
        )
        # Modèle non exposé : la probe d'usage n'est pas lancée
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version", "models"],
        )

    def test_categorie_gemini_absente_rend_un_plan_unavailable(self):
        # Les fenêtres Claude/GPT ne compensent jamais la catégorie Gemini
        self._installer_usage(
            "Usage snapshot\n"
            "Claude Models Weekly Limit Remaining 63.5% 2026-12-31T23:59:59Z\n"
            "GPT Models Weekly Limit Remaining 41.5% 2026-11-30T23:59:59Z\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("PLAN_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "PLAN_UNAVAILABLE")
        self.assertEqual(recu["plan"]["observe"], "INCONNU")
        self.assertEqual(recu["quota"]["observe"], "INCONNU")
        self.assertEqual(
            recu["sondes"][2]["projection"],
            {"categorie_gemini_presente": False, "fenetres_reconnues": []},
        )

    def test_fenetre_gemini_a_zero_rend_un_quota_exhausted(self):
        self._installer_usage(
            USAGE_SIMULE.replace(
                "Five Hour Limit Remaining 100% 2026-08-26T17:58:23Z",
                "Five Hour Limit Remaining 0% 2026-08-26T17:58:23Z",
            )
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("QUOTA_EXHAUSTED", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "QUOTA_EXHAUSTED")
        # Le quota observé et le plan observé restent consignés : la fenêtre
        # bloquante est nommée sans valeur inventée
        self.assertEqual(
            recu["quota"]["observe"]["fenetres"]["cinq_heures"][
                "pourcentage_restant"
            ],
            0,
        )
        self.assertEqual(
            recu["plan"]["observe"],
            "catégorie 'Gemini Models' active dans /usage, palier commercial "
            "non observé",
        )

    def test_delai_de_sonde_depasse_rend_deux_hold_harness_error(self):
        # Incident du dispositif, jamais imputé à la configuration : HOLD
        self._installer_agy("#!/bin/sh\n/bin/sleep 30\n")
        with mock.patch.object(M, "DELAI_SONDE_PREFLIGHT", 1):
            code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["interface"]["version_observee"], "INCONNU")


class PreflightAntigravityIdentiteTests(BaseXS06F):
    def test_libelle_contradictoire_rend_deux_identity_mismatch(self):
        self._installer_catalogue(
            "Available models:\n"
            "  gemini-3.7-flash-high - Gemini 3.7 Flash (Low)\n"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        self.assertIn("IDENTITY_MISMATCH", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "IDENTITY_MISMATCH")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")
        self.assertEqual(
            recu["sondes"][1]["projection"],
            {"entree_exacte_presente": True, "libelle_concordant": False},
        )
        # Identité non établie : la probe d'usage n'est pas lancée
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version", "models"],
        )

    def test_variante_differente_jamais_substituee(self):
        # Seule la variante low est exposée : aucune substitution n'obtient
        # un verdict plus favorable que MODEL_UNAVAILABLE
        self._installer_catalogue(
            "Available models:\n"
            "  gemini-3.7-flash-low - Gemini 3.7 Flash (Low)\n"
            "  gemini-3.7-flash-max - Gemini 3.7 Flash (Max)\n"
        )
        code, _ = self._preflight()
        self.assertEqual(code, 1)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "MODEL_UNAVAILABLE")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")


class PreflightAntigravityFailClosedTests(BaseXS06F):
    def test_version_vide_reste_fail_closed_sans_invention(self):
        self._installer_agy(self._script_agy(version=""))
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][0]["projection"], "INCONNU")

    def test_catalogue_vide_reste_fail_closed_sans_sortie_brute(self):
        self._installer_catalogue("")
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][1]["projection"], "INCONNU")

    def test_entree_sans_libelle_reste_fail_closed(self):
        # Identifiant présent sans libellé lisible : la concordance reste
        # inobservée, jamais inventée
        self._installer_catalogue("gemini-3.7-flash-high\n")
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][1]["projection"], "INCONNU")

    def test_usage_sans_forme_reconnaissable_rend_deux_harness_error(self):
        self._installer_usage("TEMOIN-USAGE-ILLISIBLE hors forme\n")
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][2]["projection"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-USAGE-ILLISIBLE",
            self.recu_antigravity.read_text(encoding="utf-8"),
        )

    def test_fenetre_gemini_dupliquee_rend_deux_harness_error(self):
        self._installer_usage(
            USAGE_SIMULE
            + "Gemini Models Five Hour Limit Remaining 90% 2026-08-26T18:58:23Z\n"
        )
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][2]["projection"], "INCONNU")

    def test_reset_absent_rend_deux_missing_observation(self):
        self._installer_usage(
            USAGE_SIMULE.replace(
                "Five Hour Limit Remaining 100% 2026-08-26T17:58:23Z",
                "Five Hour Limit Remaining 100%",
            )
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        self.assertIn("MISSING_OBSERVATION", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        # La valeur absente reste INCONNU dans le détail observé, jamais
        # reconstruite
        self.assertEqual(
            recu["quota"]["observe"]["fenetres"]["cinq_heures"]["reset"],
            "INCONNU",
        )

    def test_pourcentage_absent_rend_deux_missing_observation(self):
        self._installer_usage(
            USAGE_SIMULE.replace(
                "Gemini Models Weekly Limit Remaining 100% 2026-09-02T12:58:23Z",
                "Gemini Models Weekly Limit Remaining 2026-09-02T12:58:23Z",
            )
        )
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(
            recu["quota"]["observe"]["fenetres"]["hebdomadaire"][
                "pourcentage_restant"
            ],
            "INCONNU",
        )


class PreflightAntigravityContratRecuTests(BaseXS06F):
    def test_reference_d_v1_03_exactement_une_fois(self):
        self.assertEqual(self._preflight()[0], 0)
        texte = self.recu_antigravity.read_text(encoding="utf-8")
        self.assertEqual(texte.count("D-V1-03"), 1)
        recu = json.loads(texte)
        self.assertEqual(recu["autorite_preflight"], "D-V1-03")

    def test_recu_deterministe_sans_score_ni_self_hash(self):
        self.assertEqual(self._preflight()[0], 0)
        texte = self.recu_antigravity.read_text(encoding="utf-8")
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

    def test_recu_sans_autre_modele_ni_ligne_claude_gpt_ni_sortie_brute(self):
        code, sortie = self._preflight()
        self.assertEqual(code, 0)
        texte = self.recu_antigravity.read_text(encoding="utf-8")
        # Les autres modèles du catalogue, les lignes Claude/GPT de /usage
        # et la sortie brute ne sont jamais persistés — ni dans le reçu, ni
        # dans les messages de commande
        for interdit in (
            "temoin-autre-modele",
            "TEMOIN Modèle Privé",
            "Claude Models",
            "GPT Models",
            "2026-12-31T23:59:59Z",
            "2026-11-30T23:59:59Z",
            "63.5",
            "41.5",
            "Available models",
            "Usage snapshot",
        ):
            self.assertNotIn(interdit, texte)
            self.assertNotIn(interdit, sortie)

    def test_seules_les_trois_probes_autorisees_sont_invoquees_dans_l_ordre(self):
        self.assertEqual(self._preflight()[0], 0)
        invocations = self.journal.read_text(encoding="utf-8").splitlines()
        # Exactement les trois probes de la liste blanche, une fois chacune,
        # dans l'ordre du contrat ; jamais agy en TUI, -i,
        # --prompt-interactive, -p hors littéral /usage, update, install,
        # plugin, mcp, /model, /credits, /logout, une connexion, un prompt,
        # --model, --effort, --agent, --continue, --conversation,
        # --project, --mode, --sandbox ni --dangerously-skip-permissions
        self.assertEqual(invocations, SONDES_ATTENDUES)
        for interdit in (
            "-i",
            "--prompt-interactive",
            "update",
            "install",
            "plugin",
            "mcp",
            "/model",
            "/credits",
            "/logout",
            "login",
            "--model",
            "--effort",
            "--agent",
            "--continue",
            "--conversation",
            "--project",
            "--mode",
            "--sandbox",
            "--dangerously-skip-permissions",
        ):
            for invocation in invocations:
                self.assertNotIn(interdit, invocation.split())
        # Le seul -p invoqué porte le littéral /usage
        self.assertEqual(
            [inv for inv in invocations if "-p" in inv.split()],
            ["-p /usage"],
        )

    def test_aucun_recu_d_acquisition_ecrit_repertoire_intact(self):
        repertoire = self.racine / M._RACINE_CAMPAGNE_V1 / "recus-v1"
        repertoire.mkdir(parents=True)
        temoin = repertoire / "temoin.json"
        temoin.write_text("{}\n", encoding="utf-8")
        avant = sorted(
            (chemin.name, chemin.read_bytes())
            for chemin in repertoire.iterdir()
        )
        self.assertEqual(self._preflight()[0], 0)
        apres = sorted(
            (chemin.name, chemin.read_bytes())
            for chemin in repertoire.iterdir()
        )
        self.assertEqual(avant, apres)


_SOURCES_RESTITUTION = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES)


class RestitutionPreflightAntigravityTests(BaseXS06F):
    """Section MSW du préflight Antigravity : objets distincts rendus."""

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

    def test_page_affiche_les_objets_distincts_et_le_verificateur_confirme(self):
        self.assertEqual(self._preflight()[0], 0)
        page = self._restituer()
        self.assertIn('<section id="preflights">', page)
        self.assertIn('data-preflight="antigravity-gemini-3-7-flash"', page)
        recu = self._lire_recu()
        self.assertIn(recu["date_preflight"], page)
        self.assertIn("READY", page)
        # Les objets distincts sont rendus séparément : l'authentification
        # de métadonnées, le plan observé sans palier promu, le modèle
        # exact, le quota Gemini et l'identité réellement servie
        self.assertIn("authentification observée", page)
        self.assertIn("metadonnees_catalogue_accessibles", page)
        self.assertIn("palier commercial non observé", page)
        self.assertIn("gemini-3.7-flash-high", page)
        self.assertIn("agy:/usage", page)
        self.assertIn("pourcentage_restant", page)
        self.assertIn("identité réellement servie", page)
        for interdit in (
            "temoin-autre-modele",
            "2026-12-31T23:59:59Z",
            "2026-11-30T23:59:59Z",
            "63.5",
            "41.5",
        ):
            self.assertNotIn(interdit, page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_preflight_antigravity_unavailable_apparait_avec_sa_cause(self):
        (self.bin / "agy").unlink()
        self.assertEqual(self._preflight()[0], 1)
        page = self._restituer()
        self.assertIn("UNAVAILABLE", page)
        self.assertIn("INTERFACE_UNAVAILABLE", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_restitutions_successives_byte_identiques(self):
        self.assertEqual(self._preflight()[0], 0)
        self.assertEqual(self._restituer(), self._restituer())

    def test_verifier_refuse_un_recu_antigravity_altere_apres_restitution(self):
        self.assertEqual(self._preflight()[0], 0)
        self._restituer()
        self.recu_antigravity.write_bytes(
            self.recu_antigravity.read_bytes() + b" "
        )
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def _muter_recu(self, transformer) -> None:
        recu = self._lire_recu()
        transformer(recu)
        self.recu_antigravity.write_text(
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_recu_antigravity_hors_vocabulaire_leve_erreur_restitution(self):
        mutations = {
            # Un prompt candidat n'entre jamais dans la liste blanche agy :
            # -p ne porte que le littéral /usage
            "sonde-prompt-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "agy -p bonjour",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            "sonde-update-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "agy update",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            "sonde-modele-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "agy -p /usage --model gemini-3.7-flash-high",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            # Une sonde claude ne vaut jamais pour l'adaptateur agy
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
            # L'identité réellement servie ne devient jamais une conclusion
            "identite-promue": lambda recu: recu.update(
                {"identite_reellement_servie": "gemini-3.7-flash-high"}
            ),
            "objet-identite-absent": lambda recu: recu.pop(
                "identite_reellement_servie"
            ),
            # La forme d'authentification cursor ne vaut pas pour agy
            "auth-forme-cursor": lambda recu: recu.update(
                {
                    "authentification": {
                        "observee": {
                            "status": "authenticated",
                            "isAuthenticated": True,
                        }
                    }
                }
            ),
            # La projection d'usage reste fermée : jamais de sortie brute
            "projection-usage-polluee": lambda recu: recu["sondes"][2].update(
                {
                    "projection": {
                        "categorie_gemini_presente": True,
                        "fenetres_reconnues": ["cinq_heures", "hebdomadaire"],
                        "sortie_brute": "TEMOIN",
                    }
                }
            ),
            # READY exige chaque fenêtre Gemini pleinement observée : un
            # reset ou un pourcentage INCONNU ou NON_DEFINI est refusé
            "ready-reset-inconnu": lambda recu: recu["quota"]["observe"][
                "fenetres"
            ]["cinq_heures"].update({"reset": "INCONNU"}),
            "ready-pourcentage-non-defini": lambda recu: recu["quota"][
                "observe"
            ]["fenetres"]["hebdomadaire"].update(
                {"pourcentage_restant": "NON_DEFINI"}
            ),
            "ready-quota-inconnu": lambda recu: recu["quota"].update(
                {"observe": "INCONNU"}
            ),
            # Une fenêtre hors vocabulaire n'entre jamais dans le quota
            "fenetre-hors-vocabulaire": lambda recu: recu["quota"].update(
                {
                    "observe": {
                        "source": "agy:/usage",
                        "fenetres": {
                            "mensuelle": {
                                "pourcentage_restant": 100,
                                "reset": "TEMOIN",
                            }
                        },
                    }
                }
            ),
        }
        for nom, transformer in mutations.items():
            with self.subTest(mutation=nom):
                if self.recu_antigravity.exists():
                    self.recu_antigravity.unlink()
                self.assertEqual(self._preflight()[0], 0)
                self._restituer()
                self._muter_recu(transformer)
                with self.assertRaises(M.ErreurRestitution):
                    M.verifier_restitution(self.racine)
                code, _ = _principal(["verifier-restitution"], self.racine)
                self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
