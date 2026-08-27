# /// script
# requires-python = ">=3.12"
# ///
"""Contrôles verticaux de la récupération V1-R1 (préparation) et V1-R2
(exécution autorisée D-V1-05) au seam public.

Chaque test passe par `principal` avec une racine de dépôt temporaire copiée
du dépôt réel (doubles locaux). Aucun fournisseur, harnais ou exécutable
réel n'est résolu ni lancé : `subprocess.Popen` et `shutil.which` sont
doublés en échec explicite par défaut ; les tests d'exécution R2 les
remplacent par des doubles contrôlés qui comptent chaque processus.
"""

from __future__ import annotations

import builtins
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

_CAMPAGNE = Path("tasks/dev/pre-cadrage-entretien-client/campagne-v1")
_PRE_CADRAGE = Path("tasks/dev/pre-cadrage-entretien-client")

ARGV_ANTIGRAVITY = (
    "agy",
    "--model",
    "gemini-3.7-flash-high",
    "--effort",
    "high",
    "--sandbox",
    "--disable-slash-commands",
    "--print=__STIMULUS_UTF8__",
)
ARGV_ZAI = (
    "codex",
    "exec",
    "--skip-git-repo-check",
    "--sandbox",
    "read-only",
    "--model",
    "zai/glm-5.3",
    "--cd",
    "__ISOLATED_WORKSPACE__",
    "--config",
    'model_reasoning_effort="high"',
    "-",
)

SOURCES_HISTORIQUES = (
    _CAMPAGNE / "autorisation-acquisition-v1.json",
    _CAMPAGNE / "verrou-campagne-v1" / "verrou.json",
    _PRE_CADRAGE / "stimulus.md",
    _CAMPAGNE / "registre-panel-v1" / "antigravity-gemini-3-7-flash.toml",
    _CAMPAGNE / "registre-panel-v1" / "zai-glm-5-3.toml",
    _CAMPAGNE
    / "recus-v1"
    / "80046afee6e56ab9dcbdbbda4d5a4190d0d77cad2449b900ae16861e14cad839.json",
    _CAMPAGNE
    / "recus-v1"
    / "0964422c4970ed527846e5dce3f7f9fcc9640897424044aad3f7cbc146695f40.json",
)

_FICHIERS_ENTREE = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES) + (
    M.CHEMIN_CARTE,
    M.CHEMIN_STIMULUS,
    M.CHEMIN_ETAT.as_posix(),
    M.CHEMIN_SOURCES_PLANS.as_posix(),
    M.CHEMIN_VERROU.as_posix(),
    M.CHEMIN_AUTORISATION_ACQUISITION.as_posix(),
    M.CHEMIN_REGISTRE_VALIDATION.as_posix(),
    M.CHEMIN_RECU_QUALIFICATION.as_posix(),
)
_REPERTOIRES_ENTREE = (
    _CAMPAGNE / "registre-panel-v1",
    _CAMPAGNE / "preflights-v1",
)
# Reçus de référence copiés un à un : le répertoire vivant recus-v1 n'est
# jamais copié en bloc, un reçu -002 réel du dépôt ne doit pas entrer dans
# les bacs temporaires des tests
_RECUS_REFERENCE = (
    _CAMPAGNE
    / "recus-v1"
    / "80046afee6e56ab9dcbdbbda4d5a4190d0d77cad2449b900ae16861e14cad839.json",
    _CAMPAGNE
    / "recus-v1"
    / "0964422c4970ed527846e5dce3f7f9fcc9640897424044aad3f7cbc146695f40.json",
    _CAMPAGNE
    / "recus-v1"
    / "955c15c1d635386c7a25b9b0f3013e519883326236fcc2810cb05683d859a7f9.json",
)


def _refus_executable(*arguments: object, **cles: object) -> None:
    raise AssertionError("aucun exécutable ne doit être résolu ni lancé")


class _BaseRecuperation(unittest.TestCase):
    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        for relatif in _FICHIERS_ENTREE:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        for repertoire in _REPERTOIRES_ENTREE:
            shutil.copytree(RACINE / repertoire, self.racine / repertoire)
        repertoire_recus = self.racine / _CAMPAGNE / "recus-v1"
        repertoire_recus.mkdir(parents=True, exist_ok=True)
        for relatif in _RECUS_REFERENCE:
            shutil.copyfile(RACINE / relatif, self.racine / relatif)
        self._aligner_registre_validation_sur_le_bac()
        self.chemin_verrou_recuperation = self.racine / M.CHEMIN_VERROU_RECUPERATION
        self._popen_d_origine = subprocess.Popen
        self._which_d_origine = shutil.which
        subprocess.Popen = _refus_executable
        shutil.which = _refus_executable
        self.addCleanup(setattr, subprocess, "Popen", self._popen_d_origine)
        self.addCleanup(setattr, shutil, "which", self._which_d_origine)

    def _aligner_registre_validation_sur_le_bac(self) -> None:
        """Restreint le registre de validation copié aux seuls reçus isolés
        du bac : les entrées couvrant des reçus officiels du dépôt réel
        (les -002 vivants) sont retirées et la couverture recomptée, sans
        jamais copier ces reçus dans le bac."""
        chemin_registre = self.racine / M.CHEMIN_REGISTRE_VALIDATION
        registre = json.loads(chemin_registre.read_text(encoding="utf-8"))
        registre["entrees"] = [
            entree
            for entree in registre["entrees"]
            if (self.racine / entree["recu"]).is_file()
        ]
        recompte = {verdict: 0 for verdict in M.VERDICTS_CANDIDATS}
        for entree in registre["entrees"]:
            if entree["verdict"] is not None:
                recompte[entree["verdict"]["statut"]] += 1
        registre["couverture"] = {
            "acquisitions_officielles": len(registre["entrees"]),
            "sorties_candidates": sum(recompte.values()),
            "verdicts": recompte,
        }
        chemin_registre.write_bytes(M.octets_canoniques(registre))

    def _appeler(self, arguments: list[str]) -> tuple[int, str]:
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            code = M.principal(arguments, racine=self.racine)
        return code, tampon.getvalue()

    def _instantane(self) -> dict[str, str]:
        instantanes: dict[str, str] = {}
        for chemin in sorted(self.racine.rglob("*")):
            relatif = chemin.relative_to(self.racine).as_posix()
            if chemin.is_dir():
                instantanes[relatif] = "repertoire"
            else:
                instantanes[relatif] = hashlib.sha256(
                    chemin.read_bytes()
                ).hexdigest()
        return instantanes

    def _verrou_recuperation(self) -> dict:
        return json.loads(
            self.chemin_verrou_recuperation.read_text(encoding="utf-8")
        )


class RecuperationHarnaisTests(_BaseRecuperation):
    def test_preparer_recuperation_materialise_le_verrou_exact(self):
        code, sortie = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        verrou = self._verrou_recuperation()
        self.assertEqual(
            self.chemin_verrou_recuperation.read_bytes(),
            M.octets_canoniques(verrou),
        )
        self.assertEqual(
            verrou["schema_version"], "campagne-v1-verrou-recuperation/v1"
        )
        self.assertEqual(
            verrou["portee"],
            {
                "issue": "https://github.com/ayoahha/benchmark-lab-x/issues/131",
                "product_version": "V1",
                "tranche": "V1-R1",
            },
        )
        self.assertEqual(
            verrou["configurations"],
            [
                {
                    "configuration_id": "antigravity-gemini-3-7-flash",
                    "acquisition_id": (
                        "ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002"
                    ),
                    "descripteur": {
                        "argv": list(ARGV_ANTIGRAVITY),
                        "stimulus_utf8": "argument",
                    },
                },
                {
                    "configuration_id": "zai-glm-5-3",
                    "acquisition_id": "ACQ-V1-ZAI-GLM-5-3-002",
                    "descripteur": {
                        "argv": list(ARGV_ZAI),
                        "stimulus_utf8": "stdin",
                    },
                },
            ],
        )
        self.assertEqual(verrou["autorite_execution"], "NOT_GRANTED")
        self.assertEqual(verrou["creneaux_executes"], 0)
        self.assertEqual(verrou["reprises_executees"], 0)
        self.assertEqual(verrou["fallback"], "NONE")
        self.assertEqual(
            verrou["variantes_interdites"],
            ["fallback", "retry", "fast", "priority", "max", "ultra"],
        )
        self.assertEqual(
            verrou["preuves_identite_futures"],
            [
                {
                    "configuration_id": "zai-glm-5-3",
                    "observe_uniquement_par": (
                        "trace OpenCodex attribuable à la tentative : "
                        "fournisseur zai, modèle glm-5.3, effort effectif "
                        "high, une tentative, aucun fallback"
                    ),
                    "sinon": "provenance servie INCONNU et HOLD",
                },
                {
                    "configuration_id": "antigravity-gemini-3-7-flash",
                    "observe_uniquement_par": (
                        "métadonnée attribuable à la tentative portant "
                        "gemini-3.7-flash-high"
                    ),
                    "sinon": "provenance servie INCONNU et HOLD",
                },
            ],
        )
        self.assertEqual(
            verrou["jamais_preuve"], ["argv demandé", "code de sortie 0"]
        )
        self.assertEqual(
            verrou["sentinelles"],
            [
                {
                    "configuration_id": "antigravity-gemini-3-7-flash",
                    "lien": (
                        "https://github.com/ayoahha/benchmark-lab-x/issues/109"
                    ),
                    "marqueur": "DIAGNOSTIC_NON_CANDIDAT",
                    "exclusion_fermee": ["recus-v1", "verdicts-v1"],
                },
                {
                    "configuration_id": "zai-glm-5-3",
                    "lien": (
                        "https://github.com/ayoahha/benchmark-lab-x/issues/109"
                    ),
                    "marqueur": "DIAGNOSTIC_NON_CANDIDAT",
                    "exclusion_fermee": ["recus-v1", "verdicts-v1"],
                },
            ],
        )
        attendus = [
            {
                "chemin": relatif.as_posix(),
                "sha256": hashlib.sha256(
                    (RACINE / relatif).read_bytes()
                ).hexdigest(),
            }
            for relatif in SOURCES_HISTORIQUES
        ]
        self.assertEqual(verrou["sources_historiques"], attendus)
        self.assertEqual(
            [
                {"chemin": chemin, "sha256": M.EMPREINTES_SOURCES_HISTORIQUES_RECUPERATION[chemin]}
                for chemin in M.CHEMINS_SOURCES_HISTORIQUES_RECUPERATION
            ],
            attendus,
        )
        empreinte = hashlib.sha256(
            self.chemin_verrou_recuperation.read_bytes()
        ).hexdigest()
        self.assertIn(empreinte, sortie)
        self.assertIn("verrou de récupération vérifié", sortie)
        self.assertIn("AUTORITE_EXECUTION : D-V1-05", sortie)
        chemin_autorisation = (
            self.racine / M.CHEMIN_AUTORISATION_RECUPERATION
        )
        autorisation = json.loads(
            chemin_autorisation.read_text(encoding="utf-8")
        )
        self.assertEqual(
            chemin_autorisation.read_bytes(),
            M.octets_canoniques(autorisation),
        )
        self.assertEqual(autorisation["autorite"], "D-V1-05")
        self.assertEqual(
            autorisation["jeton"],
            "D_V1_05 = AUTHORIZE:CANDIDATES_HIGH_COMMON; AGENTS_MEDIUM",
        )
        self.assertEqual(
            autorisation["verrou_recuperation"]["sha256"], empreinte
        )
        portee = autorisation["portee"]
        self.assertEqual(portee["tranche"], "V1-R2")
        self.assertEqual(portee["appels_fournisseur_max"], 2)
        self.assertEqual(portee["appels_par_creneau"], 1)
        self.assertEqual(portee["reprises_automatiques"], 0)
        self.assertEqual(portee["reprises_manuelles"], 0)
        self.assertEqual(portee["fallback"], "NONE")
        self.assertEqual(portee["depense_incrementale"], 0)
        self.assertEqual(portee["effort_candidat"], "high")
        self.assertEqual(
            [creneau["acquisition_id"] for creneau in portee["acquisitions"]],
            [
                "ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002",
                "ACQ-V1-ZAI-GLM-5-3-002",
            ],
        )

    def test_reexecution_verifie_les_octets_sans_reecriture(self):
        premier, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(premier, 0)
        octets_premier = self.chemin_verrou_recuperation.read_bytes()
        infos_premier = os.lstat(self.chemin_verrou_recuperation)
        second, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(second, 0)
        self.assertEqual(
            self.chemin_verrou_recuperation.read_bytes(), octets_premier
        )
        infos_second = os.lstat(self.chemin_verrou_recuperation)
        self.assertEqual(infos_second.st_ino, infos_premier.st_ino)
        self.assertEqual(infos_second.st_mtime_ns, infos_premier.st_mtime_ns)

    def test_divergence_du_verrou_rend_deux_et_nomme_le_champ_fautif(self):
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        verrou = self._verrou_recuperation()
        verrou["autorite_execution"] = "GRANTED"
        self.chemin_verrou_recuperation.write_bytes(
            M.octets_canoniques(verrou)
        )
        octets_divergents = self.chemin_verrou_recuperation.read_bytes()
        code, sortie = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 2)
        self.assertIn("autorite_execution", sortie)
        self.assertIn("aucune réécriture", sortie)
        self.assertEqual(
            self.chemin_verrou_recuperation.read_bytes(), octets_divergents
        )

    def test_divergence_d_un_descripteur_nomme_le_champ_exact(self):
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        verrou = self._verrou_recuperation()
        verrou["configurations"][1]["descripteur"]["argv"][6] = "zai/glm-4"
        self.chemin_verrou_recuperation.write_bytes(
            M.octets_canoniques(verrou)
        )
        code, sortie = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 2)
        self.assertIn(
            "configurations[zai-glm-5-3].descripteur.argv", sortie
        )

    def test_source_historique_modifiee_rend_deux_sans_reecriture(self):
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        octets_premier = self.chemin_verrou_recuperation.read_bytes()
        stimulus = self.racine / M.CHEMIN_STIMULUS
        stimulus.write_bytes(stimulus.read_bytes() + b"\nalteration")
        code, sortie = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 2)
        self.assertIn("stimulus", sortie)
        self.assertEqual(
            self.chemin_verrou_recuperation.read_bytes(), octets_premier
        )

    def test_verrou_recuperation_symbolique_rend_deux(self):
        cible = self.racine / M.CHEMIN_ETAT
        self.chemin_verrou_recuperation.parent.mkdir(parents=True, exist_ok=True)
        self.chemin_verrou_recuperation.symlink_to(cible)
        code, sortie = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 2)
        self.assertIn("fichier régulier non symbolique attendu", sortie)

    def test_acquerir_recuperation_rend_deux_autorite_absente_sans_effet(self):
        for identifiant in ("antigravity-gemini-3-7-flash", "zai-glm-5-3"):
            avant = self._instantane()
            code, sortie = self._appeler(
                ["acquerir", "--recuperation", "--configuration", identifiant]
            )
            self.assertEqual(code, 2, sortie)
            self.assertIn("AUTORITE_ABSENTE", sortie)
            self.assertIn("aucun processus", sortie)
            self.assertIn("aucun espace de tentative", sortie)
            self.assertIn("aucun journal", sortie)
            self.assertIn("aucun reçu", sortie)
            self.assertEqual(self._instantane(), avant)

    def test_acquerir_recuperation_refuse_un_slug_invalide(self):
        avant = self._instantane()
        code, sortie = self._appeler(
            ["acquerir", "--recuperation", "--configuration", "Majus-cule"]
        )
        self.assertEqual(code, 2)
        self.assertIn("slug stable", sortie)
        self.assertEqual(self._instantane(), avant)

    def test_restitution_porte_l_etat_minimal_de_recuperation(self):
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        code, _ = self._appeler(["restituer"])
        self.assertEqual(code, 0)
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertEqual(page.count(' data-recuperation-harnais="'), 3)
        self.assertIn("ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002", page)
        self.assertIn("ACQ-V1-ZAI-GLM-5-3-002", page)
        self.assertIn("NOT_GRANTED", page)
        self.assertIn("INCONNU et HOLD", page)
        self.assertIn("D-V1-05", page)
        self.assertIn(
            "D_V1_05 = AUTHORIZE:CANDIDATES_HIGH_COMMON; AGENTS_MEDIUM", page
        )
        code, _ = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 0)

    def test_restitution_sans_verrou_de_recuperation_reste_conforme(self):
        code, _ = self._appeler(["restituer"])
        self.assertEqual(code, 0)
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertEqual(page.count(' data-recuperation-harnais="'), 0)
        code, _ = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 0)

    def test_tentative_antigravity_substitue_le_stimulus_sans_stdin(self):
        stimulus = "éventail UTF-8 : voilà".encode("utf-8")
        tentative = M.construire_tentative_recuperation(
            "antigravity-gemini-3-7-flash", stimulus, "/espace/isole"
        )
        self.assertEqual(
            tentative["argv"],
            [
                "agy",
                "--model",
                "gemini-3.7-flash-high",
                "--effort",
                "high",
                "--sandbox",
                "--disable-slash-commands",
                "--print=éventail UTF-8 : voilà",
            ],
        )
        self.assertIsNone(tentative["stdin"])
        self.assertEqual(tentative["cwd"], "/espace/isole")

    def test_tentative_zai_porte_le_stimulus_sur_stdin_et_cd_isole(self):
        tentative = M.construire_tentative_recuperation(
            "zai-glm-5-3", b"octets du stimulus", "/espace/isole"
        )
        self.assertEqual(
            tentative["argv"],
            [
                "codex",
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--model",
                "zai/glm-5.3",
                "--cd",
                "/espace/isole",
                "--config",
                'model_reasoning_effort="high"',
                "-",
            ],
        )
        self.assertEqual(tentative["stdin"], b"octets du stimulus")
        self.assertEqual(tentative["cwd"], "/espace/isole")

    def test_tentative_refuse_tout_identifiant_hors_creneaux(self):
        for identifiant in ("claude-code-fable-5", "zai-glm-5-3-002"):
            with self.assertRaises(M.ErreurRecuperation):
                M.construire_tentative_recuperation(
                    identifiant, b"x", "/espace/isole"
                )

    def test_identite_zai_observee_seulement_par_trace_exacte(self):
        exacte = {
            "tentative_id": "ACQ-V1-ZAI-GLM-5-3-002",
            "fournisseur": "zai",
            "modele": "glm-5.3",
            "effort_effectif": "high",
            "tentatives": 1,
            "fallback": "NONE",
        }
        verdict = M.evaluer_identite_servie_recuperation("zai-glm-5-3", exacte)
        self.assertEqual(
            verdict,
            {
                "statut": "OBSERVED",
                "disposition": "OBSERVED",
                "incident": None,
                "champs_divergents": [],
                "cause": None,
            },
        )
        for trace, cause_attendue in (
            (None, "absence de trace attribuable"),
            (
                {**exacte, "tentative_id": "ACQ-V1-AUTRE"},
                "trace non attribuable à la tentative",
            ),
            (
                {
                    "tentative_id": "ACQ-V1-ZAI-GLM-5-3-002",
                    "modele": "REQUESTED",
                    "code_sortie": 0,
                },
                None,
            ),
        ):
            verdict = M.evaluer_identite_servie_recuperation("zai-glm-5-3", trace)
            self.assertEqual(verdict["statut"], "INCONNU")
            self.assertEqual(verdict["disposition"], "HOLD")
            self.assertIsNone(verdict["incident"])
            if cause_attendue is not None:
                self.assertIn(cause_attendue, verdict["cause"])
        divergente = {
            **exacte,
            "fournisseur": "openai",
            "effort_effectif": "low",
        }
        verdict = M.evaluer_identite_servie_recuperation("zai-glm-5-3", divergente)
        self.assertEqual(verdict["statut"], "INCONNU")
        self.assertEqual(verdict["disposition"], "HOLD")
        self.assertEqual(verdict["incident"], "IDENTITY_MISMATCH")
        self.assertEqual(
            verdict["champs_divergents"], ["effort_effectif", "fournisseur"]
        )
        self.assertNotIn("verdict", verdict)

    def test_identite_antigravity_observee_seulement_par_trace_exacte(self):
        exacte = {
            "tentative_id": "ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002",
            "modele": "gemini-3.7-flash-high",
        }
        verdict = M.evaluer_identite_servie_recuperation(
            "antigravity-gemini-3-7-flash", exacte
        )
        self.assertEqual(verdict["statut"], "OBSERVED")
        for trace in (
            None,
            {**exacte, "tentative_id": "ACQ-V1-AUTRE"},
            {
                "tentative_id": "ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002",
                "modele": "REQUESTED",
                "code_sortie": 0,
            },
        ):
            verdict = M.evaluer_identite_servie_recuperation(
                "antigravity-gemini-3-7-flash", trace
            )
            self.assertEqual(verdict["statut"], "INCONNU")
            self.assertEqual(verdict["disposition"], "HOLD")
            self.assertIsNone(verdict["incident"])
        divergente = {**exacte, "modele": "gemini-2.0-flash"}
        verdict = M.evaluer_identite_servie_recuperation(
            "antigravity-gemini-3-7-flash", divergente
        )
        self.assertEqual(verdict["statut"], "INCONNU")
        self.assertEqual(verdict["disposition"], "HOLD")
        self.assertEqual(verdict["incident"], "IDENTITY_MISMATCH")
        self.assertEqual(verdict["champs_divergents"], ["modele"])
        self.assertNotIn("verdict", verdict)

    def test_sentinelles_diagnostic_non_candidat_sans_recu_ni_verdict(self):
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        verrou = self._verrou_recuperation()
        self.assertEqual(len(verrou["sentinelles"]), 2)
        for sentinelle in verrou["sentinelles"]:
            self.assertEqual(
                sentinelle["marqueur"], "DIAGNOSTIC_NON_CANDIDAT"
            )
            self.assertEqual(
                set(sentinelle),
                {"configuration_id", "lien", "marqueur", "exclusion_fermee"},
            )
            for cle in sentinelle:
                self.assertNotIn("recu", cle)
                self.assertNotIn("verdict", cle)
                self.assertNotIn("sortie", cle)
        recus = sorted(
            chemin.name
            for chemin in (self.racine / _CAMPAGNE / "recus-v1").iterdir()
        )
        self.assertEqual(
            recus,
            sorted(
                [
                    "80046afee6e56ab9dcbdbbda4d5a4190d0d77cad2449b900ae16861e14cad839.json",
                    "0964422c4970ed527846e5dce3f7f9fcc9640897424044aad3f7cbc146695f40.json",
                    "955c15c1d635386c7a25b9b0f3013e519883326236fcc2810cb05683d859a7f9.json",
                ]
            ),
        )

    def test_alteration_de_configuration_rend_deux_champ_nomme(self):
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        configuration = (
            self.racine
            / _CAMPAGNE
            / "registre-panel-v1"
            / "zai-glm-5-3.toml"
        )
        configuration.write_bytes(configuration.read_bytes() + b"\n")
        octets_premier = self.chemin_verrou_recuperation.read_bytes()
        code, sortie = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 2)
        self.assertIn("zai-glm-5-3.toml", sortie)
        self.assertEqual(
            self.chemin_verrou_recuperation.read_bytes(), octets_premier
        )

    def test_alteration_de_recu_rend_deux_champ_nomme(self):
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        recu = (
            self.racine
            / _CAMPAGNE
            / "recus-v1"
            / "80046afee6e56ab9dcbdbbda4d5a4190d0d77cad2449b900ae16861e14cad839.json"
        )
        recu.write_bytes(recu.read_bytes() + b"\n")
        code, sortie = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 2)
        self.assertIn("80046afe", sortie)

    def test_seconde_preparation_ne_touche_rien_hors_verrou_ni_le_verrou(self):
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        avant = self._instantane()
        infos_premier = os.lstat(self.chemin_verrou_recuperation)
        code, sortie = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        self.assertIn("AUTORITE_EXECUTION : D-V1-05", sortie)
        self.assertEqual(self._instantane(), avant)
        infos_second = os.lstat(self.chemin_verrou_recuperation)
        self.assertEqual(infos_second.st_ino, infos_premier.st_ino)
        self.assertEqual(infos_second.st_mtime_ns, infos_premier.st_mtime_ns)

    def test_preparation_ne_lit_ni_necrit_hors_de_la_racine(self):
        open_origine = builtins.open
        os_open_origine = os.open
        racine_resolue = self.racine.resolve()

        def _gardien(chemin):
            if isinstance(chemin, int):
                return
            resolu = Path(chemin).resolve()
            if racine_resolue != resolu and racine_resolue not in resolu.parents:
                raise AssertionError(
                    f"lecture/écriture hors de la racine de dépôt : {resolu}"
                )

        def _open_garde(chemin, *args, **cles):
            _gardien(chemin)
            return open_origine(chemin, *args, **cles)

        def _os_open_garde(chemin, *args, **cles):
            _gardien(chemin)
            return os_open_origine(chemin, *args, **cles)

        builtins.open = _open_garde
        os.open = _os_open_garde
        try:
            code, _ = self._appeler(["preparer-recuperation"])
        finally:
            builtins.open = open_origine
            os.open = os_open_origine
        self.assertEqual(code, 0)
        self.assertTrue(self.chemin_verrou_recuperation.is_file())

    def test_erreur_os_de_construction_rend_deux_nomme(self):
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        stimulus = self.racine / M.CHEMIN_STIMULUS
        stimulus.chmod(0o000)
        self.addCleanup(stimulus.chmod, 0o644)
        code, sortie = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 2)
        self.assertIn("ECHEC", sortie)

    def test_course_de_creation_fileexistserror_rend_deux_distinct(self):
        open_origine = os.open

        def _os_open_gardien(chemin, *args, **cles):
            if Path(chemin).name == M.CHEMIN_VERROU_RECUPERATION.name:
                raise FileExistsError(
                    17, "File exists (course simulée)", str(chemin)
                )
            return open_origine(chemin, *args, **cles)

        os.open = _os_open_gardien
        try:
            code, sortie = self._appeler(["preparer-recuperation"])
        finally:
            os.open = open_origine
        self.assertEqual(code, 2)
        self.assertIn("création concurrente détectée", sortie)
        self.assertFalse(self.chemin_verrou_recuperation.exists())


class _ProcessusFactice:
    """Double local d'un processus candidat ou de sonde : aucune exécution."""

    def __init__(self, stdout: bytes, stderr: bytes = b"", code: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self._code = code
        self.pid = 424242
        self.returncode: int | None = None
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO()
        self.stderr = io.BytesIO()
        self.entree: bytes | None = None

    def communicate(self, entree: bytes | None = None, timeout=None):
        self.entree = entree
        self.returncode = self._code
        return self._stdout, self._stderr

    def poll(self):
        return self.returncode

    def wait(self):
        return self.returncode


class ExecutionRecuperationTests(_BaseRecuperation):
    """Exécution V1-R2 sous D-V1-05, prouvée avec des doubles locaux."""

    def setUp(self):
        super().setUp()
        self._privee = tempfile.TemporaryDirectory()
        self.addCleanup(self._privee.cleanup)
        self.racine_privee = Path(self._privee.name)
        self.appels: list[dict] = []
        self._sorties_sonde_usage: list[bytes] = []
        killpg_origine = os.killpg

        def _killpg_factice(groupe: int, signal_envoye: int) -> None:
            raise ProcessLookupError

        os.killpg = _killpg_factice
        self.addCleanup(setattr, os, "killpg", killpg_origine)

    def _appeler_prive(self, arguments: list[str]) -> tuple[int, str]:
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            code = M.principal(
                arguments,
                racine=self.racine,
                racine_privee=self.racine_privee,
            )
        return code, tampon.getvalue()

    def _preparer(self) -> None:
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)

    def _observer_ready(self) -> None:
        observation = {
            "verdict": "READY",
            "cause": None,
            "fait": "double local READY",
        }
        for nom in ("_observer_route_antigravity", "_observer_route_zai"):
            origine = getattr(M, nom)
            setattr(M, nom, lambda *args, **cles: dict(observation))
            self.addCleanup(setattr, M, nom, origine)

    def _installer_popen(
        self, sorties_candidat: dict[str, tuple[bytes, bytes, int]]
    ) -> None:
        def _popen_factice(argv, **cles):
            self.appels.append({"argv": list(argv), "cles": cles})
            if argv[0] == "opencodex":
                sortie = self._sorties_sonde_usage.pop(0)
                return _ProcessusFactice(sortie)
            stdout, stderr, code = sorties_candidat[argv[0]]
            processus = _ProcessusFactice(stdout, stderr, code)
            self.dernier_candidat = processus
            return processus

        subprocess.Popen = _popen_factice

    def _journal(self) -> dict | None:
        chemin = (
            self.racine_privee
            / M.RELATIF_EXECUTION_R2
            / M.NOM_JOURNAL_EXECUTION
        )
        if not chemin.exists():
            return None
        return json.loads(chemin.read_text(encoding="utf-8"))

    def _recus_002(self) -> list[dict]:
        repertoire = self.racine / _CAMPAGNE / "recus-v1"
        recus = []
        for chemin in sorted(repertoire.iterdir()):
            enveloppe = json.loads(chemin.read_text(encoding="utf-8"))
            if "recuperation" in enveloppe["payload"]:
                recus.append(enveloppe)
        return recus

    def test_autorite_divergente_rend_deux_sans_processus(self):
        self._preparer()
        chemin = self.racine / M.CHEMIN_AUTORISATION_RECUPERATION
        autorisation = json.loads(chemin.read_text(encoding="utf-8"))
        autorisation["jeton"] = "D_V1_05 = AUTHORIZE:AUTRE"
        chemin.write_bytes(M.octets_canoniques(autorisation))
        avant = self._instantane()
        code, sortie = self._appeler_prive(
            ["acquerir", "--recuperation", "--configuration", "zai-glm-5-3"]
        )
        self.assertEqual(code, 2, sortie)
        self.assertIn("jeton", sortie)
        self.assertIn("aucun processus fournisseur", sortie)
        self.assertEqual(self._instantane(), avant)
        self.assertIsNone(self._journal())

    def test_preflight_non_ready_bloque_sans_processus_candidat(self):
        self._preparer()
        observation = {
            "verdict": "UNAVAILABLE",
            "cause": "INTERFACE_UNAVAILABLE",
            "fait": "double local : client introuvable",
        }
        origine = M._observer_route_antigravity
        M._observer_route_antigravity = lambda: dict(observation)
        self.addCleanup(setattr, M, "_observer_route_antigravity", origine)
        avant = self._instantane()
        code, sortie = self._appeler_prive(
            [
                "acquerir",
                "--recuperation",
                "--configuration",
                "antigravity-gemini-3-7-flash",
            ]
        )
        self.assertEqual(code, 2, sortie)
        self.assertIn("PREFLIGHT_NON_READY", sortie)
        self.assertIn("UNAVAILABLE", sortie)
        self.assertEqual(self.appels, [])
        self.assertEqual(self._instantane(), avant)
        self.assertIsNone(self._journal())
        self.assertFalse(
            (self.racine_privee / M.RELATIF_EXECUTION_R2).exists()
        )

    def test_antigravity_ready_execute_une_fois_le_descripteur_exact(self):
        self._preparer()
        self._observer_ready()
        stimulus = (self.racine / M.CHEMIN_STIMULUS).read_bytes()
        self._installer_popen(
            {
                "agy": (
                    "sortie candidate de récupération\n"
                    "model: gemini-3.7-flash-high\n".encode("utf-8"),
                    b"",
                    0,
                )
            }
        )
        code, sortie = self._appeler_prive(
            [
                "acquerir",
                "--recuperation",
                "--configuration",
                "antigravity-gemini-3-7-flash",
            ]
        )
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.appels), 1)
        appel = self.appels[0]
        espace = (
            self.racine_privee
            / M.RELATIF_EXECUTION_R2
            / "runtime"
            / "ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002"
            / "espace"
        )
        self.assertEqual(
            appel["argv"],
            [
                "agy",
                "--model",
                "gemini-3.7-flash-high",
                "--effort",
                "high",
                "--sandbox",
                "--disable-slash-commands",
                "--print=" + stimulus.decode("utf-8"),
            ],
        )
        self.assertEqual(appel["cles"]["cwd"], espace)
        self.assertTrue(appel["cles"]["start_new_session"])
        self.assertEqual(self.dernier_candidat.entree, b"")
        self.assertTrue((espace.parent / "sortie-stdout.txt").is_file())
        recus = self._recus_002()
        self.assertEqual(len(recus), 1)
        charge = recus[0]["payload"]
        self.assertEqual(
            charge["recuperation"]["acquisition_id"],
            "ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002",
        )
        self.assertEqual(charge["recuperation"]["autorite"], "D-V1-05")
        self.assertEqual(
            charge["recuperation"]["identite_servie"]["statut"], "OBSERVED"
        )
        self.assertEqual(
            charge["provenance_servie"]["valeur"],
            {"modele": "gemini-3.7-flash-high"},
        )
        self.assertEqual(
            charge["requete"]["argv_resolu"], list(ARGV_ANTIGRAVITY)
        )
        self.assertEqual(charge["execution"]["etat"], "OBSERVED")
        self.assertEqual(
            charge["creneau"].split(":")[2],
            "ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002",
        )
        journal = self._journal()
        self.assertEqual(len(journal["entrees"]), 1)
        self.assertEqual(journal["entrees"][0]["etat_terminal"], "OBSERVED")
        self.assertEqual(journal["entrees"][0]["retry"], 0)
        self.assertEqual(journal["entrees"][0]["descendants"], 0)
        # Seconde invocation : refusée sans aucun processus supplémentaire
        code, sortie = self._appeler_prive(
            [
                "acquerir",
                "--recuperation",
                "--configuration",
                "antigravity-gemini-3-7-flash",
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn("déjà occupé", sortie)
        self.assertEqual(len(self.appels), 1)

    def test_zai_ready_trace_delta_et_stimulus_stdin(self):
        self._preparer()
        self._observer_ready()
        stimulus = (self.racine / M.CHEMIN_STIMULUS).read_bytes()
        self._sorties_sonde_usage = [
            b'{"requests": []}',
            (
                b'{"requests": [{"provider": "zai", "model": "zai/glm-5.3",'
                b' "reasoning_effort": "high"}]}'
            ),
        ]
        self._installer_popen(
            {"codex": (b"sortie candidate zai\n", b"", 0)}
        )
        code, sortie = self._appeler_prive(
            ["acquerir", "--recuperation", "--configuration", "zai-glm-5-3"]
        )
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.appels), 3)
        self.assertEqual(self.appels[0]["argv"][0], "opencodex")
        self.assertEqual(self.appels[2]["argv"][0], "opencodex")
        espace = (
            self.racine_privee
            / M.RELATIF_EXECUTION_R2
            / "runtime"
            / "ACQ-V1-ZAI-GLM-5-3-002"
            / "espace"
        )
        attendu = [
            element if element != "__ISOLATED_WORKSPACE__" else str(espace)
            for element in ARGV_ZAI
        ]
        self.assertEqual(self.appels[1]["argv"], attendu)
        self.assertEqual(self.dernier_candidat.entree, stimulus)
        recus = self._recus_002()
        self.assertEqual(len(recus), 1)
        charge = recus[0]["payload"]
        self.assertEqual(
            charge["recuperation"]["identite_servie"]["statut"], "OBSERVED"
        )
        self.assertEqual(
            charge["provenance_servie"]["valeur"],
            {
                "fournisseur": "zai",
                "modele": "glm-5.3",
                "effort_effectif": "high",
                "tentatives": 1,
                "fallback": "NONE",
            },
        )
        self.assertIn("délta d'usage OpenCodex", charge["provenance_servie"]["preuve"])

    def test_preflight_zai_recoit_la_demande_canonique_non_prefixee(self):
        # Rejoue le défaut V1-R2 : extraire '--model' du descripteur scellé
        # transmettait 'zai/glm-5.3' à _observer_route_zai qui préfixe
        # lui-même 'zai/', d'où la cible fausse 'zai/zai/glm-5.3'
        self._preparer()
        demandes_observees: list[str] = []
        origine = M._observer_route_zai

        def _observer_capture(modele_demande: str) -> dict:
            demandes_observees.append(modele_demande)
            return {
                "verdict": "READY",
                "cause": None,
                "fait": "double local READY",
            }

        M._observer_route_zai = _observer_capture
        self.addCleanup(setattr, M, "_observer_route_zai", origine)
        self._sorties_sonde_usage = [
            b'{"requests": []}',
            (
                b'{"requests": [{"provider": "zai", "model": "zai/glm-5.3",'
                b' "reasoning_effort": "high"}]}'
            ),
        ]
        self._installer_popen(
            {"codex": (b"sortie candidate zai\n", b"", 0)}
        )
        code, sortie = self._appeler_prive(
            ["acquerir", "--recuperation", "--configuration", "zai-glm-5-3"]
        )
        self.assertEqual(code, 0, sortie)
        self.assertEqual(demandes_observees, ["glm-5.3"])
        # Le descripteur candidat exécuté reste exactement celui scellé :
        # '--model zai/glm-5.3', seul l'espace isolé est substitué
        espace = (
            self.racine_privee
            / M.RELATIF_EXECUTION_R2
            / "runtime"
            / "ACQ-V1-ZAI-GLM-5-3-002"
            / "espace"
        )
        attendu = [
            element if element != "__ISOLATED_WORKSPACE__" else str(espace)
            for element in ARGV_ZAI
        ]
        self.assertEqual(self.appels[1]["argv"], attendu)

    def test_identite_absente_reste_inconnu_hold_avec_recu(self):
        self._preparer()
        self._observer_ready()
        self._installer_popen(
            {"agy": (b"sortie candidate sans metadonnee\n", b"", 0)}
        )
        code, sortie = self._appeler_prive(
            [
                "acquerir",
                "--recuperation",
                "--configuration",
                "antigravity-gemini-3-7-flash",
            ]
        )
        self.assertEqual(code, 0, sortie)
        self.assertIn("identité servie : INCONNU · disposition HOLD", sortie)
        self.assertIn("HOLD : provenance servie non attribuable", sortie)
        recus = self._recus_002()
        self.assertEqual(len(recus), 1)
        charge = recus[0]["payload"]
        self.assertEqual(charge["provenance_servie"], "INCONNU")
        identite = charge["recuperation"]["identite_servie"]
        self.assertEqual(identite["statut"], "INCONNU")
        self.assertEqual(identite["disposition"], "HOLD")
        self.assertIsNone(identite["incident"])
        self.assertEqual(charge["execution"]["etat"], "OBSERVED")

    def test_validation_et_restitution_couvrent_le_recu_002(self):
        self._preparer()
        self._observer_ready()
        for relatif in (M.CHEMIN_VALIDATEUR,):
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        self._installer_popen(
            {
                "agy": (
                    "sortie candidate\nmodel: gemini-3.7-flash-high\n".encode(
                        "utf-8"
                    ),
                    b"",
                    0,
                )
            }
        )
        code, _ = self._appeler_prive(
            [
                "acquerir",
                "--recuperation",
                "--configuration",
                "antigravity-gemini-3-7-flash",
            ]
        )
        self.assertEqual(code, 0)
        # Frontière système simulée à un CPython 3.12 concret, à l'identique
        # de la fixture de qualification : le pin de production reste intact
        with (
            mock.patch.object(
                M.platform, "python_implementation", return_value="CPython"
            ),
            mock.patch.object(
                M.platform, "python_version", return_value="3.12.13"
            ),
            mock.patch.object(
                M.platform,
                "python_version_tuple",
                return_value=("3", "12", "13"),
            ),
        ):
            code, sortie = self._appeler(["valider"])
        self.assertEqual(code, 0, sortie)
        registre = json.loads(
            (self.racine / M.CHEMIN_REGISTRE_VALIDATION).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(registre["entrees"]), 3)
        creneaux = [entree["creneau"] for entree in registre["entrees"]]
        self.assertEqual(
            sum(
                1
                for creneau in creneaux
                if creneau.endswith("ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002")
            ),
            1,
        )
        # Le verrou R1 reste reconstructible : les épingles -001 ne sont
        # jamais réécrites par les entrées -002 du registre régénéré
        code, _ = self._appeler(["preparer-recuperation"])
        self.assertEqual(code, 0)
        code, sortie = self._appeler(["restituer"])
        self.assertEqual(code, 0, sortie)
        code, sortie = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 0, sortie)

    def test_trace_zai_sans_delta_ou_avec_fallback(self):
        trace, preuve = M._trace_zai_recuperation("ACQ-V1-ZAI-GLM-5-3-002", [], [])
        self.assertIsNone(trace)
        self.assertIsNone(preuve)
        enregistrement = {
            "provider": "zai",
            "model": "zai/glm-5.3",
            "reasoning_effort": "high",
        }
        autre = {"provider": "openai", "model": "gpt-5.6"}
        trace, _ = M._trace_zai_recuperation(
            "ACQ-V1-ZAI-GLM-5-3-002", [], [enregistrement, autre]
        )
        self.assertEqual(trace["tentatives"], 2)
        self.assertEqual(trace["fallback"], "OBSERVE")
        verdict = M.evaluer_identite_servie_recuperation("zai-glm-5-3", trace)
        self.assertEqual(verdict["statut"], "INCONNU")
        self.assertEqual(verdict["incident"], "IDENTITY_MISMATCH")
        trace, _ = M._trace_zai_recuperation(
            "ACQ-V1-ZAI-GLM-5-3-002",
            [enregistrement],
            [enregistrement, dict(enregistrement)],
        )
        verdict = M.evaluer_identite_servie_recuperation("zai-glm-5-3", trace)
        self.assertEqual(verdict["statut"], "OBSERVED")


if __name__ == "__main__":
    unittest.main()
