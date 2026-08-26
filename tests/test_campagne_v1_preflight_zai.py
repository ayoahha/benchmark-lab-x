# /// script
# requires-python = ">=3.12,<3.13"
# ///
"""Contrôles XS-06E : préflight OpenCodex et Z.AI Coding Plan pour GLM 5.3.

La frontière système simulée est le client `opencodex` lui-même — un
exécutable de substitution placé seul sur le PATH qui journalise ses
arguments exacts et sert uniquement des sorties expurgées de test. Aucun
collaborateur interne n'est simulé. Fidélité au diagnostic de lancement
couvert par D-V1-03 : `opencodex --version` rend la version, `opencodex
ready --json` rend un JSON {ready, status, pid, port}, `opencodex provider
show zai --json` rend la configuration expurgée du fournisseur, `opencodex
models live --provider zai --json` rend un tableau de lignes de catalogue,
`opencodex account current zai --json` rend l'état de clé actif et
`opencodex provider quota --json` rend les rapports de quota dont la source
`zai:quota-limit`.
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
VERSION_SIMULEE = "opencodex 2.31.0"
ENDPOINT_DECLARE = "https://api.z.ai/api/coding/paas/v4"
# Readiness simulée : pid et port sont des témoins privés, jamais conservés
READY_SIMULE = {"ready": True, "status": "ready", "pid": 65001, "port": 10100}
# Fournisseur simulé : la clé masquée, le pool de clés, les en-têtes et les
# notes prouvent par leur présence à la frontière que le reçu ne conserve
# jamais apiKey, apiKeyPool, en-têtes, notes ni le document brut
FOURNISSEUR_SIMULE = {
    "name": "zai",
    "isDefault": True,
    "adapter": "openai-chat",
    "baseUrl": ENDPOINT_DECLARE,
    "defaultModel": "glm-5.3",
    "models": ["glm-5.3"],
    "apiKey": "sk-TEMOIN***CLE-PRIVEE",
    "apiKeyPool": [
        {"id": "TEMOIN-ID-CLE", "key": "sk-TEMOIN-POOL", "label": "TEMOIN-LABEL-POOL"}
    ],
    "headers": {"X-Temoin": "TEMOIN-EN-TETE-PRIVE"},
    "notes": "TEMOIN-NOTES-PRIVEES",
}
# Catalogue simulé : l'entrée exacte zai/glm-5.3 non désactivée annonçant
# l'effort high, plus une entrée témoin. L'effort par défaut, les autres
# efforts et l'autre modèle prouvent qu'ils ne sont jamais persistés
CATALOGUE_SIMULE = [
    {
        "provider": "zai",
        "id": "glm-5.3",
        "namespaced": "zai/glm-5.3",
        "disabled": False,
        "reasoningEfforts": ["medium", "high"],
        "defaultReasoningEffort": "medium",
    },
    {
        "provider": "zai",
        "id": "TEMOIN-AUTRE-MODELE",
        "namespaced": "zai/TEMOIN-AUTRE-MODELE",
        "disabled": False,
        "reasoningEfforts": ["TEMOIN-EFFORT-AUTRE"],
    },
]
# Compte simulé : activeId, id, masked, label et priorité prouvent par leur
# présence à la frontière que le reçu ne conserve jamais un identifiant ni
# un fragment de clé
COMPTE_SIMULE = {
    "provider": "zai",
    "type": "api-key",
    "activeId": "TEMOIN-ID-ACTIF",
    "autoSwitchThreshold": 80,
    "account": {
        "id": "TEMOIN-ID-ACTIF",
        "masked": "sk-TEM***VEE",
        "label": "TEMOIN-LABEL-CLE",
        "active": True,
        "priority": 1,
    },
}
# Quota simulé : un rapport zai:quota-limit à deux fenêtres reconnues et un
# rapport témoin d'un autre fournisseur, jamais conservé
QUOTA_SIMULE = {
    "generatedAt": 1756200000000,
    "reports": [
        {
            "provider": "TEMOIN-AUTRE-FOURNISSEUR",
            "label": "TEMOIN-AUTRE-RAPPORT",
            "source": "temoin:quota",
            "quota": {"fiveHourPercent": 99.9, "updatedAt": 1756200000000},
            "updatedAt": 1756200000000,
        },
        {
            "provider": "zai",
            "label": "Z.AI — GLM Coding Plan",
            "source": "zai:quota-limit",
            "quota": {
                "fiveHourPercent": 12.5,
                "fiveHourResetAt": 1756207200000,
                "weeklyPercent": 40.0,
                "weeklyResetAt": 1756600000000,
                "updatedAt": 1756200000000,
            },
            "updatedAt": 1756200000000,
        },
    ],
}
TEMOINS_PRIVES = (
    "sk-TEMOIN",
    "TEMOIN-ID-CLE",
    "TEMOIN-LABEL-POOL",
    "TEMOIN-EN-TETE-PRIVE",
    "TEMOIN-NOTES-PRIVEES",
    "TEMOIN-ID-ACTIF",
    "sk-TEM***VEE",
    "TEMOIN-LABEL-CLE",
    "apiKey",
    "apiKeyPool",
    "activeId",
    "masked",
    "65001",
    "10100",
)
TEMOINS_CATALOGUE = (
    "TEMOIN-AUTRE-MODELE",
    "TEMOIN-EFFORT-AUTRE",
    "defaultReasoningEffort",
    "medium",
)
TEMOINS_QUOTA = (
    "TEMOIN-AUTRE-FOURNISSEUR",
    "TEMOIN-AUTRE-RAPPORT",
    "temoin:quota",
    "99.9",
)
SONDES_ATTENDUES = [
    "--version",
    "ready --json",
    "provider show zai --json",
    "models live --provider zai --json",
    "account current zai --json",
    "provider quota --json",
]


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS06E(unittest.TestCase):
    """Racine isolée : état V1, registre officiel et client opencodex simulé."""

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
        # Frontière système : seul un client opencodex simulé vit sur le
        # PATH ; il journalise ses arguments exacts, preuve qu'aucune forme
        # générative ni mutation (codex exec, provider test, --refresh,
        # sync, start, stop, login, logout, account use, account refresh,
        # config set, config unset, models add, models edit) n'est jamais
        # invoquée ; le vrai codex n'existe pas sur ce PATH
        self.bin = self.racine / "bin-simule"
        self.bin.mkdir()
        self.journal = self.racine / "journal-opencodex.txt"
        self.ready = self.bin / "ready-simule.json"
        self.fournisseur = self.bin / "fournisseur-simule.json"
        self.catalogue = self.bin / "catalogue-simule.json"
        self.compte = self.bin / "compte-simule.json"
        self.quota = self.bin / "quota-simule.json"
        self._installer_ready(READY_SIMULE)
        self._installer_fournisseur(FOURNISSEUR_SIMULE)
        self._installer_catalogue(CATALOGUE_SIMULE)
        self._installer_compte(COMPTE_SIMULE)
        self._installer_quota(QUOTA_SIMULE)
        self._installer_opencodex(self._script_opencodex())
        patch = mock.patch.dict(os.environ, {"PATH": str(self.bin)})
        patch.start()
        self.addCleanup(patch.stop)
        self.recu_zai = self.racine / CHEMIN_PREFLIGHTS / "zai-glm-5-3.json"

    def _installer_json(self, chemin: Path, contenu: object) -> None:
        chemin.write_text(
            json.dumps(contenu, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def _installer_ready(self, ready: object) -> None:
        self._installer_json(self.ready, ready)

    def _installer_fournisseur(self, fournisseur: object) -> None:
        self._installer_json(self.fournisseur, fournisseur)

    def _installer_catalogue(self, catalogue: object) -> None:
        self._installer_json(self.catalogue, catalogue)

    def _installer_compte(self, compte: object) -> None:
        self._installer_json(self.compte, compte)

    def _installer_quota(self, quota: object) -> None:
        self._installer_json(self.quota, quota)

    def _script_opencodex(self, version: str = VERSION_SIMULEE) -> str:
        """Client simulé : une ligne de journal par invocation, args joints"""
        return (
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{self.journal}'\n"
            'if [ "$*" = "--version" ]; then\n'
            f"  echo '{version}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "ready --json" ]; then\n'
            # /bin/cat : le PATH du test ne contient que le client simulé
            f"  /bin/cat '{self.ready}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "provider show zai --json" ]; then\n'
            f"  /bin/cat '{self.fournisseur}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "models live --provider zai --json" ]; then\n'
            f"  /bin/cat '{self.catalogue}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "account current zai --json" ]; then\n'
            f"  /bin/cat '{self.compte}'\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$*" = "provider quota --json" ]; then\n'
            f"  /bin/cat '{self.quota}'\n"
            "  exit 0\n"
            "fi\n"
            "echo 'invocation hors contrat' >&2\n"
            "exit 64\n"
        )

    def _installer_opencodex(self, script: str) -> None:
        stub = self.bin / "opencodex"
        stub.write_text(script, encoding="utf-8")
        stub.chmod(0o755)

    def _preflight(self) -> tuple[int, str]:
        return _principal(
            ["preflight", "--configuration", "zai-glm-5-3"], self.racine
        )

    def _lire_recu(self) -> dict:
        return json.loads(self.recu_zai.read_text(encoding="utf-8"))


class PreflightZaiDisponibleTests(BaseXS06E):
    def test_route_prete_rend_zero_ready_et_ecrit_recu(self):
        code, sortie = self._preflight()
        # READY rend 0 : les cinq contrôles sont observés par les six probes
        # non génératives ; l'identité réellement servie reste INCONNU
        self.assertEqual(code, 0, sortie)
        self.assertIn("READY", sortie)
        self.assertTrue(self.recu_zai.is_file())
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "READY")
        self.assertIsNone(recu["cause"])
        self.assertEqual(recu["configuration_id"], "zai-glm-5-3")
        self.assertEqual(recu["adaptateur"], "opencodex")
        self.assertEqual(recu["interface"]["client"], "opencodex")
        self.assertEqual(recu["interface"]["version_observee"], VERSION_SIMULEE)
        self.assertEqual(
            recu["authentification"]["observee"],
            {"fournisseur": "zai", "type": "api-key", "cle_active": True},
        )
        self.assertEqual(recu["plan"]["declare"], "Z.AI Coding Plan")
        # Le libellé déclaré reste distinct du fait observé : seul l'endpoint
        # de quota du Coding Plan qui a répondu est consigné comme observé
        self.assertEqual(
            recu["plan"]["observe"],
            "endpoint de quota du Coding Plan a répondu (source zai:quota-limit)",
        )
        self.assertEqual(recu["modele"]["demande"], "glm-5.3")
        # La présence exacte de zai/glm-5.3 projette le modèle exposé et
        # l'effort high, jamais l'identité réellement servie
        self.assertEqual(recu["modele"]["expose"], "zai/glm-5.3")
        self.assertEqual(recu["effort"]["demande"], "high")
        self.assertEqual(recu["effort"]["expose"], "high")
        self.assertEqual(
            recu["quota"]["observe"],
            {
                "source": "zai:quota-limit",
                "fenetres": {
                    "cinq_heures": {
                        "pourcentage": 12.5,
                        "reset": 1756207200000,
                    },
                    "hebdomadaire": {
                        "pourcentage": 40.0,
                        "reset": 1756600000000,
                    },
                    "mensuelle": {
                        "pourcentage": "INCONNU",
                        "reset": "INCONNU",
                    },
                },
            },
        )
        self.assertEqual(recu["quota"]["consommation_preflight"], "INCONNU")

    def test_quatre_objets_distincts_du_recu(self):
        self.assertEqual(self._preflight()[0], 0)
        recu = self._lire_recu()
        # 1. catalogue déclaré : jamais une preuve d'accès ni d'identité
        self.assertEqual(
            recu["catalogue_declare"],
            {
                "fournisseur": "zai",
                "adaptateur": "openai-chat",
                "endpoint": ENDPOINT_DECLARE,
                "entree_exacte_presente": True,
                "effort_high_present": True,
            },
        )
        # 2. proxy OpenCodex : version et readiness, sans pid ni port
        self.assertEqual(
            recu["proxy_opencodex"],
            {"version": VERSION_SIMULEE, "ready": True, "status": "ready"},
        )
        # 3. authentification : présence active projetée sans identifiant
        self.assertEqual(
            recu["authentification"]["observee"],
            {"fournisseur": "zai", "type": "api-key", "cle_active": True},
        )
        # 4. identité réellement servie : INCONNU sans génération, jamais
        # une conclusion déduite du catalogue, de la clé ou du quota
        self.assertEqual(recu["identite_reellement_servie"], "INCONNU")

    def test_projections_des_six_sondes_fermees_et_completes(self):
        self.assertEqual(self._preflight()[0], 0)
        recu = self._lire_recu()
        self.assertEqual(
            [sonde["commande"] for sonde in recu["sondes"]],
            [f"opencodex {suite}".strip() for suite in SONDES_ATTENDUES],
        )
        self.assertEqual(
            recu["sondes"][0]["projection"], {"version": VERSION_SIMULEE}
        )
        self.assertEqual(
            recu["sondes"][1]["projection"], {"ready": True, "status": "ready"}
        )
        self.assertEqual(
            recu["sondes"][2]["projection"],
            {
                "nom": "zai",
                "adaptateur": "openai-chat",
                "endpoint": ENDPOINT_DECLARE,
                "modele_defaut": "glm-5.3",
                "desactive": False,
                "modele_demande_present": True,
            },
        )
        self.assertEqual(
            recu["sondes"][3]["projection"],
            {
                "entree_presente": True,
                "desactivee": False,
                "effort_high_present": True,
            },
        )
        self.assertEqual(
            recu["sondes"][4]["projection"],
            {"fournisseur": "zai", "type": "api-key", "cle_active": True},
        )
        self.assertEqual(
            recu["sondes"][5]["projection"],
            {
                "rapport_zai_present": True,
                "source": "zai:quota-limit",
                "fenetres_reconnues": ["cinq_heures", "hebdomadaire"],
            },
        )
        for sonde in recu["sondes"]:
            self.assertNotIn("stdout_expurge", sonde)
            self.assertNotIn("stderr_expurge", sonde)


class PreflightZaiContratRecuTests(BaseXS06E):
    def test_reference_d_v1_03_exactement_une_fois(self):
        self.assertEqual(self._preflight()[0], 0)
        texte = self.recu_zai.read_text(encoding="utf-8")
        self.assertEqual(texte.count("D-V1-03"), 1)
        recu = json.loads(texte)
        self.assertEqual(recu["autorite_preflight"], "D-V1-03")

    def test_recu_deterministe_sans_score_ni_self_hash(self):
        self.assertEqual(self._preflight()[0], 0)
        texte = self.recu_zai.read_text(encoding="utf-8")
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

    def test_recu_sans_secret_ni_catalogue_complet_ni_rapport_etranger(self):
        code, sortie = self._preflight()
        self.assertEqual(code, 0)
        texte = self.recu_zai.read_text(encoding="utf-8")
        # Clés, pool, en-têtes, notes, identifiants, pid, port, catalogue
        # complet, effort par défaut, autres efforts, autres modèles et
        # rapports des autres fournisseurs ne sont jamais persistés — ni
        # dans le reçu, ni dans les messages de commande
        for interdit in TEMOINS_PRIVES + TEMOINS_CATALOGUE + TEMOINS_QUOTA:
            self.assertNotIn(interdit, texte)
            self.assertNotIn(interdit, sortie)
        # Le libellé du rapport de quota n'est pas projeté : seul le fait
        # que l'endpoint du Coding Plan a répondu est conservé
        self.assertNotIn("GLM Coding Plan", texte)

    def test_seules_les_six_sondes_autorisees_sont_invoquees_dans_l_ordre(self):
        self.assertEqual(self._preflight()[0], 0)
        invocations = self.journal.read_text(encoding="utf-8").splitlines()
        # Exactement les six probes de la liste blanche, une fois chacune,
        # dans l'ordre du contrat ; jamais codex exec, provider test,
        # --refresh, sync, start, stop, login, logout, account use,
        # account refresh, config set, config unset, models add, models
        # edit, un prompt ou une commande générative
        self.assertEqual(invocations, SONDES_ATTENDUES)
        for interdit in (
            "exec",
            "test",
            "--refresh",
            "sync",
            "start",
            "stop",
            "login",
            "logout",
            "use",
            "refresh",
            "set",
            "unset",
            "add",
            "edit",
            "--model",
            "-p",
            "--print",
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
        self.assertEqual(self._preflight()[0], 0)
        apres = sorted(
            (chemin.name, chemin.read_bytes())
            for chemin in repertoire.iterdir()
        )
        self.assertEqual(avant, apres)


class PreflightZaiIndisponibleTests(BaseXS06E):
    def test_client_introuvable_rend_un_unavailable_interface(self):
        (self.bin / "opencodex").unlink()
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

    def test_version_en_echec_rend_un_sans_autre_sonde(self):
        self._installer_opencodex(
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
        # Interface non établie : les cinq autres probes jamais lancées
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version"],
        )

    def test_proxy_non_pret_rend_un_provider_failure(self):
        # Le vrai client rend 1 avec un JSON bien formé quand le proxy n'est
        # pas prêt : la probe est bien formée, la route n'est pas utilisable
        self._installer_ready(
            {"ready": False, "status": "unreachable", "pid": None, "port": None}
        )
        self._installer_opencodex(
            self._script_opencodex().replace(
                f"/bin/cat '{self.ready}'\n  exit 0",
                f"/bin/cat '{self.ready}'\n  exit 1",
            )
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("PROVIDER_FAILURE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "PROVIDER_FAILURE")
        self.assertEqual(
            recu["proxy_opencodex"],
            {"version": VERSION_SIMULEE, "ready": False, "status": "unreachable"},
        )
        # Proxy non prêt : fournisseur, catalogue, compte et quota jamais
        # sondés
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            ["--version", "ready --json"],
        )

    def test_aucune_cle_active_rend_un_authentication_unavailable(self):
        self._installer_compte({**COMPTE_SIMULE, "activeId": None, "account": None})
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("AUTHENTICATION_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "AUTHENTICATION_UNAVAILABLE")
        self.assertEqual(
            recu["authentification"]["observee"],
            {"fournisseur": "zai", "type": "api-key", "cle_active": False},
        )
        self.assertEqual(recu["plan"]["observe"], "INCONNU")
        # Route non authentifiée : le quota n'est pas sondé
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            SONDES_ATTENDUES[:5],
        )

    def test_entree_exacte_absente_rend_un_model_unavailable(self):
        self._installer_catalogue([CATALOGUE_SIMULE[1]])
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("MODEL_UNAVAILABLE", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "MODEL_UNAVAILABLE")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")
        self.assertEqual(recu["effort"]["expose"], "INCONNU")
        self.assertEqual(
            recu["sondes"][3]["projection"],
            {
                "entree_presente": False,
                "desactivee": "INCONNU",
                "effort_high_present": "INCONNU",
            },
        )
        # Modèle non exposé : compte et quota jamais sondés
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            SONDES_ATTENDUES[:4],
        )

    def test_entree_desactivee_rend_un_model_unavailable(self):
        catalogue = [dict(CATALOGUE_SIMULE[0], disabled=True), CATALOGUE_SIMULE[1]]
        self._installer_catalogue(catalogue)
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "MODEL_UNAVAILABLE")
        self.assertEqual(recu["modele"]["expose"], "INCONNU")

    def test_effort_high_absent_rend_un_model_unavailable(self):
        catalogue = [
            dict(CATALOGUE_SIMULE[0], reasoningEfforts=["medium"]),
            CATALOGUE_SIMULE[1],
        ]
        self._installer_catalogue(catalogue)
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "MODEL_UNAVAILABLE")
        self.assertEqual(recu["effort"]["expose"], "INCONNU")
        self.assertEqual(
            recu["sondes"][3]["projection"],
            {
                "entree_presente": True,
                "desactivee": False,
                "effort_high_present": False,
            },
        )

    def test_quota_epuise_rend_un_quota_exhausted(self):
        quota = json.loads(json.dumps(QUOTA_SIMULE))
        quota["reports"][1]["quota"]["fiveHourPercent"] = 100.0
        self._installer_quota(quota)
        code, sortie = self._preflight()
        self.assertEqual(code, 1, sortie)
        self.assertIn("QUOTA_EXHAUSTED", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "UNAVAILABLE")
        self.assertEqual(recu["cause"], "QUOTA_EXHAUSTED")
        # Le quota observé et le plan observé restent consignés : l'endpoint
        # a répondu, la fenêtre bloquante est nommée sans valeur inventée
        self.assertEqual(
            recu["quota"]["observe"]["fenetres"]["cinq_heures"]["pourcentage"],
            100.0,
        )
        self.assertEqual(
            recu["plan"]["observe"],
            "endpoint de quota du Coding Plan a répondu (source zai:quota-limit)",
        )

    def test_delai_de_sonde_depasse_rend_deux_hold_harness_error(self):
        # Incident du dispositif, jamais imputé à la configuration : HOLD
        self._installer_opencodex("#!/bin/sh\n/bin/sleep 30\n")
        with mock.patch.object(M, "DELAI_SONDE_PREFLIGHT", 1):
            code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["interface"]["version_observee"], "INCONNU")


class PreflightZaiIdentiteTests(BaseXS06E):
    def test_adaptateur_divergent_rend_deux_identity_mismatch(self):
        self._installer_fournisseur(
            {**FOURNISSEUR_SIMULE, "adapter": "anthropic-messages"}
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        self.assertIn("IDENTITY_MISMATCH", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "IDENTITY_MISMATCH")
        # Identité divergente : catalogue, compte et quota jamais sondés
        self.assertEqual(
            self.journal.read_text(encoding="utf-8").splitlines(),
            SONDES_ATTENDUES[:3],
        )

    def test_endpoint_divergent_rend_deux_identity_mismatch(self):
        self._installer_fournisseur(
            {**FOURNISSEUR_SIMULE, "baseUrl": "https://open.bigmodel.cn/api/paas/v4"}
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "IDENTITY_MISMATCH")
        # L'endpoint divergent observé reste projeté, jamais promu déclaré
        self.assertEqual(
            recu["sondes"][2]["projection"]["endpoint"],
            "https://open.bigmodel.cn/api/paas/v4",
        )

    def test_fournisseur_divergent_rend_deux_identity_mismatch(self):
        self._installer_fournisseur({**FOURNISSEUR_SIMULE, "name": "temoin"})
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "IDENTITY_MISMATCH")


class PreflightZaiFailClosedTests(BaseXS06E):
    def test_version_vide_reste_fail_closed_sans_invention(self):
        self._installer_opencodex(self._script_opencodex(version=""))
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][0]["projection"], "INCONNU")

    def test_ready_illisible_reste_fail_closed_sans_sortie_brute(self):
        self.ready.write_text(
            "TEMOIN-READY-ILLISIBLE hors JSON", encoding="utf-8"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][1]["projection"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-READY-ILLISIBLE",
            self.recu_zai.read_text(encoding="utf-8"),
        )

    def test_statut_ready_hors_vocabulaire_reste_fail_closed(self):
        self._installer_ready({**READY_SIMULE, "status": "TEMOIN-STATUT"})
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][1]["projection"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-STATUT", self.recu_zai.read_text(encoding="utf-8")
        )

    def test_fournisseur_illisible_reste_fail_closed_sans_sortie_brute(self):
        self.fournisseur.write_text(
            "TEMOIN-FOURNISSEUR-ILLISIBLE hors JSON", encoding="utf-8"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][2]["projection"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-FOURNISSEUR-ILLISIBLE",
            self.recu_zai.read_text(encoding="utf-8"),
        )

    def test_catalogue_ambigu_entree_dupliquee_rend_deux_harness_error(self):
        self._installer_catalogue([CATALOGUE_SIMULE[0], CATALOGUE_SIMULE[0]])
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][3]["projection"], "INCONNU")

    def test_compte_illisible_reste_fail_closed_sans_sortie_brute(self):
        self.compte.write_text(
            "TEMOIN-COMPTE-ILLISIBLE hors JSON", encoding="utf-8"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][4]["projection"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-COMPTE-ILLISIBLE",
            self.recu_zai.read_text(encoding="utf-8"),
        )

    def test_rapport_zai_absent_rend_deux_missing_observation(self):
        self._installer_quota(
            {"generatedAt": 1756200000000, "reports": [QUOTA_SIMULE["reports"][0]]}
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        self.assertIn("MISSING_OBSERVATION", sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        # plan.observe ne devient jamais observé sans réponse zai:quota-limit
        self.assertEqual(recu["plan"]["observe"], "INCONNU")
        self.assertEqual(recu["quota"]["observe"], "INCONNU")
        self.assertEqual(
            recu["sondes"][5]["projection"],
            {
                "rapport_zai_present": False,
                "source": "INCONNU",
                "fenetres_reconnues": [],
            },
        )

    def test_source_divergente_rend_deux_missing_observation(self):
        quota = json.loads(json.dumps(QUOTA_SIMULE))
        quota["reports"][1]["source"] = "temoin:autre-source"
        self._installer_quota(quota)
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(recu["plan"]["observe"], "INCONNU")

    def test_rapport_sans_fenetre_reconnue_rend_deux_missing_observation(self):
        quota = json.loads(json.dumps(QUOTA_SIMULE))
        quota["reports"][1]["quota"] = {"updatedAt": 1756200000000}
        self._installer_quota(quota)
        code, _ = self._preflight()
        self.assertEqual(code, 2)
        recu = self._lire_recu()
        self.assertEqual(recu["cause"], "MISSING_OBSERVATION")
        self.assertEqual(recu["quota"]["observe"], "INCONNU")

    def test_quota_illisible_reste_fail_closed_sans_sortie_brute(self):
        self.quota.write_text(
            "TEMOIN-QUOTA-ILLISIBLE hors JSON", encoding="utf-8"
        )
        code, sortie = self._preflight()
        self.assertEqual(code, 2, sortie)
        recu = self._lire_recu()
        self.assertEqual(recu["verdict"], "HOLD")
        self.assertEqual(recu["cause"], "HARNESS_ERROR")
        self.assertEqual(recu["sondes"][5]["projection"], "INCONNU")
        self.assertNotIn(
            "TEMOIN-QUOTA-ILLISIBLE",
            self.recu_zai.read_text(encoding="utf-8"),
        )


_SOURCES_RESTITUTION = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES)


class RestitutionPreflightZaiTests(BaseXS06E):
    """Section MSW du préflight Z.AI : quatre objets rendus séparément."""

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

    def test_page_affiche_les_quatre_objets_et_le_verificateur_confirme(self):
        self.assertEqual(self._preflight()[0], 0)
        page = self._restituer()
        self.assertIn('<section id="preflights">', page)
        self.assertIn('data-preflight="zai-glm-5-3"', page)
        recu = self._lire_recu()
        self.assertIn(recu["date_preflight"], page)
        self.assertIn("READY", page)
        # Les quatre objets sont rendus séparément
        self.assertIn("catalogue déclaré", page)
        self.assertIn("proxy OpenCodex", page)
        self.assertIn("authentification observée", page)
        self.assertIn("identité réellement servie", page)
        # Projections zai rendues : readiness, fournisseur, catalogue,
        # compte et quota
        self.assertIn("cle_active", page)
        self.assertIn("entree_presente", page)
        self.assertIn("zai:quota-limit", page)
        # La page autonome ne porte aucune séquence de schéma distant :
        # l'endpoint projeté est neutralisé, jamais omis
        self.assertIn("https&#58;//api.z.ai/api/coding/paas/v4", page)
        for interdit in TEMOINS_PRIVES:
            self.assertNotIn(interdit, page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_preflight_zai_unavailable_apparait_avec_sa_cause(self):
        (self.bin / "opencodex").unlink()
        self.assertEqual(self._preflight()[0], 1)
        page = self._restituer()
        self.assertIn("UNAVAILABLE", page)
        self.assertIn("INTERFACE_UNAVAILABLE", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_restitutions_successives_byte_identiques_avec_preflight_zai(self):
        self.assertEqual(self._preflight()[0], 0)
        self.assertEqual(self._restituer(), self._restituer())

    def test_verifier_refuse_un_recu_zai_altere_apres_restitution(self):
        self.assertEqual(self._preflight()[0], 0)
        self._restituer()
        self.recu_zai.write_bytes(self.recu_zai.read_bytes() + b" ")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def _muter_recu(self, transformer) -> None:
        recu = self._lire_recu()
        transformer(recu)
        self.recu_zai.write_text(
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_recu_zai_hors_vocabulaire_leve_erreur_restitution(self):
        mutations = {
            # Une forme générative ou de mutation n'entre jamais dans la
            # liste blanche opencodex
            "sonde-generative-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "codex exec --model zai/glm-5.3",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            "sonde-refresh-injectee": lambda recu: recu.update(
                {
                    "sondes": [
                        {
                            "commande": "opencodex provider quota --refresh --json",
                            "code_sortie": 0,
                            "projection": "INCONNU",
                        }
                    ]
                }
            ),
            # Une sonde claude ne vaut jamais pour l'adaptateur opencodex
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
                {"adaptateur": "zai"}
            ),
            # La forme d'authentification cursor ne vaut pas pour opencodex
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
            # L'identité réellement servie ne devient jamais une conclusion
            "identite-promue": lambda recu: recu.update(
                {"identite_reellement_servie": "glm-5.3"}
            ),
            # Les quatre objets distincts ne sont pas amputables
            "objet-proxy-absent": lambda recu: recu.pop("proxy_opencodex"),
            "objet-catalogue-absent": lambda recu: recu.pop("catalogue_declare"),
            "projection-quota-polluee": lambda recu: recu["sondes"][5].update(
                {
                    "projection": {
                        "rapport_zai_present": True,
                        "source": "zai:quota-limit",
                        "fenetres_reconnues": ["cinq_heures", "hebdomadaire"],
                        "rapports_bruts": ["TEMOIN"],
                    }
                }
            ),
        }
        for nom, transformer in mutations.items():
            with self.subTest(mutation=nom):
                if self.recu_zai.exists():
                    self.recu_zai.unlink()
                self.assertEqual(self._preflight()[0], 0)
                self._restituer()
                self._muter_recu(transformer)
                with self.assertRaises(M.ErreurRestitution):
                    M.verifier_restitution(self.racine)
                code, _ = _principal(["verifier-restitution"], self.racine)
                self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
