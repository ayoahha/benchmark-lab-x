# /// script
# requires-python = ">=3.12"
# ///
"""Contrôles verticaux de la préparation de récupération V1-R1 au seam public.

Chaque test passe par `principal` avec une racine de dépôt temporaire copiée
du dépôt réel (doubles locaux). Aucun fournisseur, harnais ou exécutable
n'est résolu ni lancé : `subprocess.Popen` et `shutil.which` sont doublés
en échec explicite pendant toute la durée de chaque test.
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
    _CAMPAGNE / "recus-v1",
)


def _refus_executable(*arguments: object, **cles: object) -> None:
    raise AssertionError("aucun exécutable ne doit être résolu ni lancé")


class RecuperationHarnaisTests(unittest.TestCase):
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
        self.chemin_verrou_recuperation = self.racine / M.CHEMIN_VERROU_RECUPERATION
        self._popen_d_origine = subprocess.Popen
        self._which_d_origine = shutil.which
        subprocess.Popen = _refus_executable
        shutil.which = _refus_executable
        self.addCleanup(setattr, subprocess, "Popen", self._popen_d_origine)
        self.addCleanup(setattr, shutil, "which", self._which_d_origine)

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
        self.assertIn("AUTORITE_ABSENTE", sortie)

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
        self.assertEqual(page.count(' data-recuperation-harnais="'), 2)
        self.assertIn("ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002", page)
        self.assertIn("ACQ-V1-ZAI-GLM-5-3-002", page)
        self.assertIn("NOT_GRANTED", page)
        self.assertIn("INCONNU et HOLD", page)
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
        self.assertIn("AUTORITE_ABSENTE", sortie)
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


if __name__ == "__main__":
    unittest.main()
