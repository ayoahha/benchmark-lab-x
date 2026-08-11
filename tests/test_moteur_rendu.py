# /// script
# requires-python = ">=3.12"
# ///
"""Contrôle du lancement Chromium sous le sandbox macOS de Codex"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import moteur_rendu as M  # noqa: E402


class NavigateurFaux:
    version = M.CHROMIUM_EPINGLE


class ChromiumFaux:
    def __init__(self):
        self.appels = []

    def launch(self, **options):
        self.appels.append(options)
        return NavigateurFaux()


class PlaywrightFaux:
    def __init__(self):
        self.chromium = ChromiumFaux()


class MoteurRenduTests(unittest.TestCase):
    def test_codex_seatbelt_utilise_le_mode_mono_processus(self):
        playwright = PlaywrightFaux()
        with patch.dict("os.environ", {"CODEX_SANDBOX": "seatbelt"}, clear=False):
            M.lancer_chromium(playwright)
        self.assertEqual(playwright.chromium.appels, [{"args": ["--single-process"]}])

    def test_hors_codex_conserve_le_lancement_standard(self):
        playwright = PlaywrightFaux()
        with patch.dict("os.environ", {}, clear=True):
            M.lancer_chromium(playwright)
        self.assertEqual(playwright.chromium.appels, [{}])


if __name__ == "__main__":
    unittest.main()
