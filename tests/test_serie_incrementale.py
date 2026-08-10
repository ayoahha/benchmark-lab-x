from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

from serie_incrementale import (  # noqa: E402
    _projection_microdollars,
    approuver_continuation,
    contrat_compatibilite,
    identite_modele,
    identite_route,
    selectionner_fallback,
)
from protocole_v2 import ContratV2Invalide  # noqa: E402


def cellule(provider: str = "deepseek", quantization: str = "fp8") -> dict:
    route_identity = {
        "kind": "publisher_managed",
        "canonical_publisher": "deepseek",
        "provider_slug": provider,
        "provider_name": provider.title(),
        "endpoint_tag": f"{provider}/{quantization}",
    }
    return {
        "collection_id": "deepseek-v4-flash__r1",
        "alias": "deepseek-v4-flash",
        "run": 1,
        "task_version": "task-v4",
        "prompt_sha256": "a" * 64,
        "route": {
            "ownership": route_identity,
            "metadata_evidence": {
                "url": "https://example.invalid/endpoints",
                "observed_at": "2026-08-08T00:00:00Z",
                "response_sha256": "b" * 64,
            },
        },
        "execution_manifest": {
            "mode": "direct",
            "model_requested": "deepseek/deepseek-v4-flash-0731",
            "backend": "openrouter",
            "provider_pinned": provider,
            "provider_expected": provider.title(),
            "endpoint_tag": f"{provider}/{quantization}",
            "quantization": {"status": "declared", "value": quantization},
            "revision": {
                "status": "declared",
                "kind": "endpoint_model_id",
                "value": "deepseek/deepseek-v4-flash-0731",
            },
            "reasoning_effort": None,
            "request_parameters": {
                "temperature": 0,
                "provider": {
                    "only": [provider],
                    "allow_fallbacks": False,
                    "require_parameters": True,
                    "data_collection": "allow",
                },
                "usage": {"include": True},
            },
            "max_tokens": 384000,
            "data_policy_requested": "allow",
            "request_adapter_version": "openrouter-chat-completions/v1",
            "tools": [],
            "agent": None,
            "local_environment": None,
        },
    }


class SerieIncrementaleTests(unittest.TestCase):
    def test_approbation_lie_exactement_les_fallbacks_et_b0_09(self):
        continuation = {
            "series_id": "pentagone-v0",
            "routes": {
                "deepseek-v4-flash": {
                    "fallback": {
                        "route_identity": {
                            "provider_pinned": "gmicloud",
                            "endpoint_tag": "gmicloud/fp8",
                        }
                    }
                }
            },
            "budget": {
                "primary_routes_estimate_microdollars": 6_525_060,
                "global_cap_microdollars": 100_000_000,
            },
        }
        approuver_continuation(
            continuation,
            "a" * 40,
            {"deepseek-v4-flash": "gmicloud"},
            6_525_060,
            "2026-08-10T00:00:00Z",
        )
        self.assertEqual(continuation["gates"]["b0_10"], "HOLD")
        self.assertEqual(
            continuation["approvals"]["fallback_routes"][0]["endpoint_tag"],
            "gmicloud/fp8",
        )
        with self.assertRaisesRegex(ContratV2Invalide, "fallbacks"):
            approuver_continuation(
                continuation,
                "a" * 40,
                {},
                6_525_060,
                "2026-08-10T00:00:00Z",
            )

    def test_identite_modele_reste_stable_quand_la_route_change(self):
        primaire = cellule()
        secondaire = cellule("cloudflare")
        self.assertEqual(identite_modele(primaire), identite_modele(secondaire))
        self.assertNotEqual(identite_route(primaire), identite_route(secondaire))
        self.assertEqual(
            contrat_compatibilite(primaire)["sha256"],
            contrat_compatibilite(secondaire)["sha256"],
        )

    def test_fallback_exige_revision_quantification_parametres_et_capacite(self):
        cible = cellule()
        endpoints = [
            {
                "tag": "a-degraded/fp8",
                "provider_name": "Degraded",
                "model_id": "deepseek/deepseek-v4-flash-0731",
                "quantization": "fp8",
                "max_completion_tokens": 500000,
                "context_length": 500000,
                "supported_parameters": ["max_tokens", "temperature"],
                "pricing": {"prompt": "0.0000001", "completion": "0.0000002"},
                "status": -2,
            },
            {
                "tag": "b-wrong-revision/fp8",
                "provider_name": "Wrong Revision",
                "model_id": "deepseek/autre",
                "quantization": "fp8",
                "max_completion_tokens": 500000,
                "context_length": 500000,
                "supported_parameters": ["max_tokens", "temperature"],
                "pricing": {"prompt": "0.0000001", "completion": "0.0000002"},
            },
            {
                "tag": "c-wrong-quant/fp4",
                "provider_name": "Wrong Quant",
                "model_id": "deepseek/deepseek-v4-flash-0731",
                "quantization": "fp4",
                "max_completion_tokens": 500000,
                "context_length": 500000,
                "supported_parameters": ["max_tokens", "temperature"],
                "pricing": {"prompt": "0.0000001", "completion": "0.0000002"},
            },
            {
                "tag": "d-too-small/fp8",
                "provider_name": "Too Small",
                "model_id": "deepseek/deepseek-v4-flash-0731",
                "quantization": "fp8",
                "max_completion_tokens": 1000,
                "context_length": 1000,
                "supported_parameters": ["max_tokens", "temperature"],
                "pricing": {"prompt": "0.0000001", "completion": "0.0000002"},
            },
            {
                "tag": "cloudflare/fp8",
                "provider_name": "Cloudflare",
                "model_id": "deepseek/deepseek-v4-flash-0731",
                "quantization": "fp8",
                "max_completion_tokens": 384000,
                "context_length": 500000,
                "supported_parameters": ["max_tokens", "temperature"],
                "pricing": {"prompt": "0.00000014", "completion": "0.00000028"},
            },
        ]
        body = json.dumps({"data": {"endpoints": endpoints}}, separators=(",", ":"))
        snapshot = {
            "models": {
                "deepseek/deepseek-v4-flash-0731": {
                    "metadata_evidence": {
                        "url": "https://example.invalid/endpoints",
                        "observed_at": "2026-08-08T00:00:00Z",
                        "response_sha256": __import__("hashlib").sha256(body.encode()).hexdigest(),
                        "response_body": body,
                    }
                }
            }
        }
        fallback, absence = selectionner_fallback(cible, snapshot)
        self.assertIsNone(absence)
        self.assertEqual(
            fallback["route_identity"]["provider_pinned"], "cloudflare"
        )
        self.assertEqual(
            fallback["equivalence"]["compatibility_contract_sha256"],
            contrat_compatibilite(cible)["sha256"],
        )

    def test_projection_b0_09_des_42_slots(self):
        valeurs = {
            "deepseek-v4-flash": 70133,
            "deepseek-v4-pro": 85783,
            "mimo-v2-5": 41603,
            "minimax-m3": 150843,
            "hy3": 73600,
            "kimi-k3-max": 3114075,
            "muse-spark-1-2-max": 447132,
        }
        budget = {
            "historical_runs": 76,
            "historical_provider_prompts": 83,
            "by_alias": {
                alias: {"runs": 4, "repriced_microdollars": valeur}
                for alias, valeur in valeurs.items()
            },
        }
        self.assertEqual(
            _projection_microdollars(budget, set(valeurs), 6), 6_525_060
        )
        self.assertEqual(_projection_microdollars(budget, set(), 6), 0)


if __name__ == "__main__":
    unittest.main()
