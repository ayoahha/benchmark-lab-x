from __future__ import annotations

import json
import sys
import tempfile
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
import serie_incrementale  # noqa: E402
from empreintes import empreinte  # noqa: E402
from protocole_v2 import (  # noqa: E402
    PROTOCOLE_VERSION,
    SCHEMA_ATTEMPT,
    ContratV2Invalide,
)


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
    def test_ledger_reconcilie_un_429_openrouter_sans_artefact(self):
        cible = cellule()
        cible["execution_manifest_hash"] = empreinte(cible["execution_manifest"])
        cible["payload_hash"] = "2" * 64
        cible["max_cost_microdollars"] = 830
        lock_hash = "3" * 64
        reservation_id = f"{cible['collection_id']}__a1"
        tentative = {
            "schema_version": SCHEMA_ATTEMPT,
            "protocol_version": PROTOCOLE_VERSION,
            "campaign_lock_hash": lock_hash,
            "collection_id": cible["collection_id"],
            "attempt": 1,
            "result": "FAILED_RETRYABLE",
            "cause_code": "HTTP_429",
            "execution_manifest_hash": cible["execution_manifest_hash"],
            "payload_hash": cible["payload_hash"],
            "http_response_received": True,
            "candidate_artifact_accepted": False,
            "cost_accounting": {
                "status": "upper_bound",
                "cost_microdollars": 830,
                "reservation_id": reservation_id,
            },
            "retry_after": "60",
        }
        ledger = {
            "schema_version": "benchmark-lab-x/budget-ledger/v2",
            "campaign_lock_hash": lock_hash,
            "currency": "USD",
            "cap_microdollars": 1000,
            "engaged_microdollars": 830,
            "reservations": {
                reservation_id: {
                    "status": "finalized",
                    "max_microdollars": 830,
                    "cost_microdollars": 830,
                    "created_at": "2026-08-10T00:00:00Z",
                    "finalized_at": "2026-08-10T00:00:01Z",
                }
            },
            "hold": False,
            "hold_reasons": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            campagne = Path(tmp)
            tentative_path = (
                campagne / "collections" / cible["collection_id"]
                / "attempt-1" / "attempt-receipt.json"
            )
            tentative_path.parent.mkdir(parents=True)
            tentative_path.write_text(
                json.dumps(tentative, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (campagne / "budget-ledger.json").write_text(
                json.dumps(ledger, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            resultat = serie_incrementale._comptabilite_ledger_v2(
                campagne, {"collections": [cible]}, lock_hash
            )
        self.assertEqual(resultat["recorded_microdollars"], 830)
        self.assertEqual(resultat["engaged_microdollars"], 0)
        self.assertEqual(resultat["reconciled_microdollars"], 830)
        self.assertEqual(len(resultat["adjustments"]), 1)

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
            _projection_microdollars(
                budget, {alias: 6 for alias in valeurs}
            ),
            6_525_060,
        )
        self.assertEqual(
            _projection_microdollars(budget, {
                "mimo-v2-5": 1,
                "hy3": 5,
                "kimi-k3-max": 6,
                "muse-spark-1-2-max": 6,
            }),
            5_945_652,
        )
        self.assertEqual(_projection_microdollars(budget, {}), 0)


if __name__ == "__main__":
    unittest.main()
