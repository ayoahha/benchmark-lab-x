# /// script
# requires-python = ">=3.12"
# ///
"""Contrôles publics de la préparation Cursor/Kimi V1-R6-P (#148)."""

from __future__ import annotations

import io
import hashlib
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
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402


RELATIF_PREPARATION = Path(
    "tasks/dev/pre-cadrage-entretien-client/campagne-v1/"
    "completion-panel-v1/preparation-recuperation-cursor-v1.json"
)
RELATIF_RECU_002 = Path(
    "tasks/dev/pre-cadrage-entretien-client/campagne-v1/recus-v1/"
    "4339e558eaba56918f9c8e08e92450e3238fd26c453c3b250926cff4dc3fd82f.json"
)
RELATIF_AUTORISATION_R5 = Path(
    "tasks/dev/pre-cadrage-entretien-client/campagne-v1/completion-panel-v1/"
    "autorisation-recuperation-headless-v1.json"
)
RELATIF_RECUS = Path(
    "tasks/dev/pre-cadrage-entretien-client/campagne-v1/recus-v1"
)
RELATIF_PREFLIGHTS = Path(
    "tasks/dev/pre-cadrage-entretien-client/campagne-v1/preflights-v1"
)
RELATIF_ETAT = Path(
    "tasks/dev/pre-cadrage-entretien-client/campagne-v1/etat-v1.json"
)
DESCRIPTEUR = (
    "agent --trust --print --output-format stream-json --mode ask "
    "--sandbox enabled --workspace __ISOLATED_WORKSPACE__ "
    "--model kimi-k3-high"
)
PREPARATION_ATTENDUE = {
    "schema": "campagne-v1-preparation-recuperation-cursor/v1",
    "authority": "V1_R6 = PREPARE_WITHOUT_CANDIDATE_CALL",
    "tranche": "V1-R6-P",
    "configuration_id": "cursor-kimi-k3",
    "reserved_slot": "ACQ-V1-CURSOR-KIMI-K3-003",
    "state": "WAITING_CURSOR_QUOTA_RESET_CONFIRMATION",
    "execution_authority": "NOT_GRANTED",
    "future_candidate_calls_max": 1,
    "retry": 0,
    "fallback": "NONE",
    "overage": "INTERDIT",
    "incremental_spend_eur": 0,
    "input_mode": "stdin",
    "descriptor": DESCRIPTEUR,
}
PREUVES_SCELLEES = {
    RELATIF_RECU_002: "f32fa8475875fc9379249a13939f0d51345ffa34d991ff3131b2e68ea979ed15",
    RELATIF_AUTORISATION_R5: "f253be65a95d019c077c04c360705772ad686ce37241095d4a57a0010989a639",
    RELATIF_RECUS: "397b868cafe2a56facc95ac8df8b772cc802fc1b89b9d94b3b2d8910da1f90ac",
    RELATIF_PREFLIGHTS: "1aeaf3102effb3bec57de722868f4067353e680db96c78687e8c4a2c0b4a6e8b",
    RELATIF_ETAT: "f1f34418a4eb5f564d83d07cffccfa55d3f2c1a9db48947d4665f3688ba9866b",
}


def _sha256_fichier(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _sha256_manifeste(repertoire: Path) -> str:
    lignes = []
    for chemin in sorted(c for c in repertoire.rglob("*") if c.is_file()):
        relatif = chemin.relative_to(RACINE).as_posix()
        lignes.append(f"{_sha256_fichier(chemin)}  {relatif}\n")
    return hashlib.sha256("".join(lignes).encode("utf-8")).hexdigest()


def _empreintes_historiques() -> dict[Path, str]:
    return {
        relatif: (
            _sha256_manifeste(RACINE / relatif)
            if (RACINE / relatif).is_dir()
            else _sha256_fichier(RACINE / relatif)
        )
        for relatif in PREUVES_SCELLEES
    }


class PreparationRecuperationCursorTests(unittest.TestCase):
    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)

    def _appeler(self, arguments: list[str]) -> tuple[int, str]:
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            code = M.principal(arguments, racine=self.racine)
        return code, tampon.getvalue()

    def test_preparer_materialise_le_contrat_canonique_exact(self):
        code, sortie = self._appeler(["preparer-recuperation-cursor"])

        self.assertEqual(code, 0, sortie)
        chemin = self.racine / RELATIF_PREPARATION
        self.assertEqual(
            chemin.read_bytes(), M.octets_canoniques(PREPARATION_ATTENDUE)
        )
        self.assertEqual(
            json.loads(chemin.read_text(encoding="utf-8")),
            PREPARATION_ATTENDUE,
        )

    def test_preparer_est_idempotent_et_octet_identique(self):
        premier, sortie = self._appeler(["preparer-recuperation-cursor"])
        self.assertEqual(premier, 0, sortie)
        chemin = self.racine / RELATIF_PREPARATION
        octets = chemin.read_bytes()
        infos = os.lstat(chemin)

        second, sortie = self._appeler(["preparer-recuperation-cursor"])

        self.assertEqual(second, 0, sortie)
        self.assertEqual(chemin.read_bytes(), octets)
        apres = os.lstat(chemin)
        self.assertEqual(apres.st_ino, infos.st_ino)
        self.assertEqual(apres.st_mtime_ns, infos.st_mtime_ns)

    def test_garde_publique_refuse_avant_toute_frontiere(self):
        code, sortie = self._appeler(["preparer-recuperation-cursor"])
        self.assertEqual(code, 0, sortie)
        privee = self.racine / "racine-privee-interdite"
        avant = {
            chemin.relative_to(self.racine).as_posix(): _sha256_fichier(chemin)
            for chemin in self.racine.rglob("*")
            if chemin.is_file()
        }
        with (
            mock.patch.object(shutil, "which", side_effect=AssertionError),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError),
            redirect_stdout(tampon := io.StringIO()),
        ):
            code = M.principal(
                [
                    "acquerir",
                    "--recuperation-cursor",
                    "--configuration",
                    "cursor-kimi-k3",
                ],
                racine=self.racine,
                racine_privee=privee,
            )
        apres = {
            chemin.relative_to(self.racine).as_posix(): _sha256_fichier(chemin)
            for chemin in self.racine.rglob("*")
            if chemin.is_file()
        }

        self.assertEqual(code, 2, tampon.getvalue())
        self.assertIn("AUTORITE_EXECUTION_ABSENTE", tampon.getvalue())
        self.assertEqual(apres, avant)
        self.assertFalse(privee.exists())

    def test_garde_autorite_absente_meme_sans_preparation(self):
        with (
            mock.patch.object(shutil, "which", side_effect=AssertionError),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError),
        ):
            code, sortie = self._appeler(
                [
                    "acquerir",
                    "--recuperation-cursor",
                    "--configuration",
                    "cursor-kimi-k3",
                ]
            )

        self.assertEqual(code, 2, sortie)
        self.assertIn("AUTORITE_EXECUTION_ABSENTE", sortie)
        self.assertFalse((self.racine / RELATIF_PREPARATION).exists())

    def test_garde_refuse_configuration_hors_portee(self):
        avant = list(self.racine.rglob("*"))
        code, sortie = self._appeler(
            [
                "acquerir",
                "--recuperation-cursor",
                "--configuration",
                "codex-gpt-5-6-sol",
            ]
        )

        self.assertEqual(code, 2, sortie)
        self.assertIn("configuration_id", sortie)
        self.assertEqual(list(self.racine.rglob("*")), avant)

    def test_garde_refuse_autre_creneau_et_derive_du_descripteur(self):
        for champ, valeur in (
            ("reserved_slot", "ACQ-V1-CURSOR-KIMI-K3-004"),
            ("descriptor", DESCRIPTEUR.replace("--trust ", "")),
        ):
            with self.subTest(champ=champ):
                code, sortie = self._appeler(
                    ["preparer-recuperation-cursor"]
                )
                self.assertEqual(code, 0, sortie)
                chemin = self.racine / RELATIF_PREPARATION
                derivee = dict(PREPARATION_ATTENDUE)
                derivee[champ] = valeur
                chemin.write_bytes(M.octets_canoniques(derivee))
                octets_derives = chemin.read_bytes()

                code, sortie = self._appeler(
                    [
                        "acquerir",
                        "--recuperation-cursor",
                        "--configuration",
                        "cursor-kimi-k3",
                    ]
                )

                self.assertEqual(code, 2, sortie)
                self.assertIn(champ, sortie)
                self.assertEqual(chemin.read_bytes(), octets_derives)
                chemin.write_bytes(M.octets_canoniques(PREPARATION_ATTENDUE))

    def test_preparation_preserve_les_cinq_preuves_historiques(self):
        avant = _empreintes_historiques()
        self.assertEqual(avant, PREUVES_SCELLEES)

        code, sortie = self._appeler(["preparer-recuperation-cursor"])

        self.assertEqual(code, 0, sortie)
        self.assertEqual(_empreintes_historiques(), avant)


if __name__ == "__main__":
    unittest.main()
