from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.valider_panel_identites_campagne_v0 import (
    EMPREINTE_PANEL_ATTENDUE,
    main,
    valider_panel_identites_campagne_v0,
)


RACINE = Path(__file__).resolve().parents[1]
PANEL = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/panel-identites-v1/panel-identites.json"
)


def _configuration(document: dict[str, object], identifiant: str) -> dict[str, object]:
    for configuration in document["panel"]["configurations"]:
        if configuration["configuration_id"] == identifiant:
            return configuration
    raise AssertionError(f"configuration absente: {identifiant}")


class PanelIdentitesCampagneV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(PANEL.read_bytes())

    def _verifier_echec_non_nul(self, document: dict[str, object]) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            panel = Path(dossier) / "panel-identites.json"
            panel.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertNotEqual(0, main([str(panel)]))

    def test_panel_canonique_est_valide(self) -> None:
        recu = valider_panel_identites_campagne_v0()

        self.assertEqual("PANEL_IDENTITES_CAMPAGNE_V0_OK", recu["status"])
        self.assertEqual(EMPREINTE_PANEL_ATTENDUE, recu["panel_sha256"])
        self.assertEqual(2, recu["configuration_count"])
        self.assertEqual("USE_MANUAL", recu["harness_family"])

    def test_rejette_configuration_supplementaire(self) -> None:
        document = deepcopy(self.document)
        tierce = deepcopy(document["panel"]["configurations"][0])
        tierce["configuration_id"] = "grok46_xai_build_oauth_bis"
        document["panel"]["configurations"].append(tierce)

        self._verifier_echec_non_nul(document)

    def test_rejette_configuration_manquante(self) -> None:
        document = deepcopy(self.document)
        document["panel"]["configurations"] = [
            configuration
            for configuration in document["panel"]["configurations"]
            if configuration["configuration_id"] != "kimi_k3_cursor_cli"
        ]

        self._verifier_echec_non_nul(document)

    def test_rejette_auto_router(self) -> None:
        document = deepcopy(self.document)
        auto = deepcopy(document["panel"]["configurations"][0])
        auto["configuration_id"] = "auto_router"
        auto["provider"] = {"state": "DECIDED", "value": "AUTO_ROUTER"}
        document["panel"]["configurations"].append(auto)

        self._verifier_echec_non_nul(document)

    def test_rejette_openrouter(self) -> None:
        mutations = []
        fournisseur = deepcopy(self.document)
        _configuration(fournisseur, "grok46_xai_build_oauth")["provider"] = {
            "state": "DECIDED",
            "value": "OPENROUTER",
        }
        mutations.append(fournisseur)
        canari = deepcopy(self.document)
        canari["exclusions"]["openrouter_canary"] = "REQUIRED"
        mutations.append(canari)

        for document in mutations:
            with self.subTest(document=document):
                self._verifier_echec_non_nul(document)

    def test_rejette_opencode_zen_pour_kimi(self) -> None:
        document = deepcopy(self.document)
        kimi = _configuration(document, "kimi_k3_cursor_cli")
        kimi["provider"] = {"state": "DECIDED", "value": "OPENCODE_ZEN"}
        kimi["endpoint"] = {
            "state": "EXPECTED",
            "value": "https://opencode.ai/zen/v1/chat/completions",
        }

        self._verifier_echec_non_nul(document)

    def test_rejette_slug_cursor_divergent(self) -> None:
        for slug in ("cursor-kimi-k3", "kimi-k3-low"):
            document = deepcopy(self.document)
            _configuration(document, "kimi_k3_cursor_cli")["executable_slug"] = {
                "state": "DECIDED",
                "value": slug,
            }

            with self.subTest(slug=slug):
                self._verifier_echec_non_nul(document)

    def test_rejette_route_endpoint_ou_parametre_divergent(self) -> None:
        mutations = []
        route = deepcopy(self.document)
        _configuration(route, "kimi_k3_cursor_cli")["route"] = {
            "state": "DECIDED",
            "value": "OPENAI_COMPATIBLE_CHAT_COMPLETIONS",
        }
        mutations.append(route)
        endpoint = deepcopy(self.document)
        _configuration(endpoint, "grok46_xai_build_oauth")["endpoint"] = {
            "state": "EXPECTED",
            "value": "https://api.x.ai/v1/responses",
        }
        mutations.append(endpoint)
        parametre = deepcopy(self.document)
        _configuration(parametre, "grok46_xai_build_oauth")["parameters"][
            "reasoning"
        ] = {"state": "DECIDED", "value": "high"}
        mutations.append(parametre)

        for document in mutations:
            with self.subTest(document=document):
                self._verifier_echec_non_nul(document)

    def test_rejette_heritage_silencieux_des_limites_zen(self) -> None:
        document = deepcopy(self.document)
        _configuration(document, "kimi_k3_cursor_cli")["parameters"][
            "context_tokens"
        ] = {"state": "DECIDED", "value": 1048576}

        self._verifier_echec_non_nul(document)

    def test_rejette_heritage_p3_silencieux(self) -> None:
        mutations = []
        promotion = deepcopy(self.document)
        promotion["shared_identity"]["reviewed_source_basis"][
            "promotion_to_m6_implementation_or_authority"
        ] = "ALLOWED"
        mutations.append(promotion)
        implementation = deepcopy(self.document)
        implementation["shared_identity"]["shared_core_adapter"][
            "implementation_state"
        ] = (
            "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p3-v1/"
            "adapters/shared_acquisition.py"
        )
        mutations.append(implementation)

        for document in mutations:
            with self.subTest(document=document):
                self._verifier_echec_non_nul(document)

    def test_rejette_reference_autorite_manquante(self) -> None:
        document = deepcopy(self.document)
        del document["owner_authorities"]["corrected_owner_decision"]

        self._verifier_echec_non_nul(document)

    def test_rejette_valeur_demandee_promue_en_observee(self) -> None:
        document = deepcopy(self.document)
        _configuration(document, "grok46_xai_build_oauth")["observed"][
            "served_model"
        ] = {"state": "OBSERVED", "value": "grok-4.6"}

        self._verifier_echec_non_nul(document)


if __name__ == "__main__":
    unittest.main()
