"""Preuves locales sans réseau ni Chromium du protocole v2"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import shutil
import sys
import tempfile
import tomllib
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

from empreintes import empreinte  # noqa: E402
from protocole_v2 import (  # noqa: E402
    CARDS_V4,
    PANEL_B0,
    PREDICATS_V4,
    PROTOCOLE_VERSION,
    SCHEMA_ATTEMPT,
    SCHEMA_COLLECTION,
    SCHEMA_CONTEXT,
    SCHEMA_COVERAGE,
    SCHEMA_ENVIRONMENT,
    SCHEMA_LOCK,
    SCHEMA_SCORE,
    ContratV2Invalide,
    PlafondDepasse,
    RegistreBudget,
    agreger_scores,
    assembler_prompt_verrouille,
    chemin_relatif_sur,
    decision_reprise,
    ecrire_json_immuable,
    empreinte_lock,
    resultat_acquis_v2,
    valider_autorisation_payante,
    valider_environnement_observe,
    valider_lock,
    valider_recu_couverture,
    valider_recu_score,
)
import rapport_campagne  # noqa: E402
from integrer_temoins_r016 import (  # noqa: E402
    IntegrationR016Invalide,
    verifier_destination,
)
from preparer_campagne import (  # noqa: E402
    _arbre_tache,
    _charger_snapshot_routes,
    construire_lock,
    cout_max_microdollars,
)
from qualifier_temoins import charger_qualification_set  # noqa: E402


def environnement_fixture(browser: dict | None) -> dict:
    runtimes = [{"name": "python", "version": "3.14.6"}]
    if browser is not None:
        runtimes.append({"name": "playwright", "version": "1.62.0"})
    return {
        "schema_version": SCHEMA_ENVIRONMENT,
        "os": {"name": "FixtureOS", "version": "1", "kernel": "fixture-kernel"},
        "architecture": "fixture-arch",
        "locale": "fr_FR.UTF-8",
        "timezone": "Europe/Paris",
        "runtimes": sorted(runtimes, key=lambda x: x["name"]),
        "browser": browser,
        "sandbox_image_digest": None,
    }


def lock_minimal() -> dict:
    kinds = {cid: "binary" if cid in CARDS_V4[:2] else "levels" for cid in CARDS_V4}
    cards = []
    for cid in CARDS_V4:
        manifeste_verify = {
            "schema_version": "benchmark-lab-x/verifier-manifest/v2",
            "card_id": cid,
            "verify_version": "verify-v5",
            "predicates": list(PREDICATS_V4[cid]),
            "assets": [{
                "path": "tools/verifier_pentagone_v5.py",
                "sha256": "f" * 64,
                "bytes": 1,
            }],
        }
        cards.append({
            "id": cid,
            "kind": kinds[cid],
            "verify_version": "verify-v5",
            "verify_hash": empreinte(manifeste_verify),
            "verifier_path": "tools/verifier_pentagone_v5.py",
            "verify_manifest": manifeste_verify,
            "watchdog_s": 180,
            "predicates": list(PREDICATS_V4[cid]),
            "aggregation": {"runs": 6, "order_statistic": 4},
        })
    collections = []
    for alias in PANEL_B0:
        route_execution = {
            "backend": "openrouter",
            "provider": "example",
            "expect_provider": "Example",
            "quantization": "fixture",
            "revision": "fixture",
            "criterion_version": "fixture/v1",
            "price_source": "fixture locale",
            "price_observed_at": "2026-08-08T00:00:00+02:00",
            "input_usd_per_million_tokens": "0.1",
            "output_usd_per_million_tokens": "0.2",
            "request_usd": "0",
            "prompt_token_upper_bound": 100,
        }
        parameters = {"temperature": 0, "top_p": 1, "seed": 42}
        manifeste = {
            "schema_version": "benchmark-lab-x/execution-manifest/v2",
            "protocol_version": PROTOCOLE_VERSION,
            "task_version": "task-v3",
            "prompt_sha256": "1" * 64,
            "model": f"example/{alias}",
            "route": route_execution,
            "parameters": parameters,
            "max_tokens": 65_536,
            "data_policy": "allow",
            "runner_version": "collect.py/v3",
        }
        for run in range(1, 7):
            collections.append({
                "collection_id": f"{alias}__r{run}",
                "alias": alias,
                "run": run,
                "task_version": "task-v3",
                "prompt_sha256": "1" * 64,
                "model": f"example/{alias}",
                "route": {**route_execution, "metadata_status": "resolved"},
                "parameters": parameters,
                "max_tokens": 65_536,
                "max_cost_microdollars": 13_118,
                "execution_manifest": manifeste,
                "execution_manifest_hash": empreinte(manifeste),
            })
    environnement_runner = environnement_fixture(None)
    environnement_mesure = environnement_fixture(
        {"name": "chromium", "version": "151.0.7922.34"}
    )
    return {
        "schema_version": SCHEMA_LOCK,
        "protocol_version": PROTOCOLE_VERSION,
        "campaign_id": "fixture-v2",
        "paid_authorization_required": True,
        "repository_source": {"commit": "d" * 40},
        "environments": {
            "runner": {
                "descriptor": environnement_runner,
                "sha256": empreinte(environnement_runner),
            },
            "measurement": {
                "descriptor": environnement_mesure,
                "sha256": empreinte(environnement_mesure),
            },
        },
        "panel": list(PANEL_B0),
        "runs": 6,
        "attempts_max": 3,
        "runner": {"concurrency": 2, "transport_timeout_s": 600},
        "budget": {"currency": "USD", "cap_microdollars": 55_000_000,
                   "estimate_microdollars": 31_812_500},
        "registry_source": {"path": "models.toml", "sha256": "a" * 64},
        "route_snapshot_source": {
            "path": "runs/fixture/routes-preflight.json",
            "sha256": "b" * 64,
            "schema_version": "benchmark-lab-x/route-preflight-snapshot/v1",
            "observed_at": "2026-08-08T00:00:00+02:00",
            "criterion_version": "benchmark-lab-x/selection-route/v2",
            "budget_status": "B0_09_UNCHANGED",
            "repriced_estimate_microdollars": 31_812_500,
            "b0_09_approval_hash": "c" * 64,
        },
        "task": {"task_version": "task-v3", "task_dir": "tasks/dev/pentagone-rotatif",
                 "task_file": "task-v3.md", "task_tree": [{"path": "task-v3.md"}],
                 "prompt_sha256": "1" * 64},
        "score_cards": cards,
        "collections": collections,
    }


def _cause_negative(card_id: str) -> str:
    return {
        "pentagone-api": "OUTPUT_NO_PAGE",
        "pentagone-determinisme": "NON_DETERMINISTIC",
        "pentagone-confinement-court": "INITIAL_STATE_INVALID",
        "pentagone-precision-24s": "PRECISION_THRESHOLD_FAILED",
        "pentagone-horizons-longs": "OUT_OF_BOUNDS",
    }[card_id]


def _resultat_carte(card: dict, valeur: bool) -> dict:
    predicats = {p: valeur for p in card["predicates"]}
    resultat = {
        "etat": "SCORED",
        "cause_code": None if valeur else _cause_negative(card["id"]),
        "verdict": "PASS" if valeur else "FAIL",
        "niveau": None,
        "frontiere": None,
        "predicates": predicats,
        "measurements": {},
    }
    if card["kind"] == "levels":
        resultat["niveau"] = len(predicats) if valeur else 0
        resultat["frontiere"] = None if valeur else card["predicates"][0]
    return resultat


def couverture_complete(racine: Path) -> tuple[dict, str, dict]:
    task_dir = racine / "task"
    (task_dir / "temoins").mkdir(parents=True)
    contenus = {"positif.md": "cas positif\n", "negatif.md": "cas négatif\n"}
    for nom, contenu in contenus.items():
        (task_dir / nom).write_text(contenu, encoding="utf-8")

    lock = lock_minimal()
    provenance = {"temoins": {}}
    for nom, valeur in (("positif.md", True), ("negatif.md", False)):
        provenance["temoins"][nom] = {
            "producteur": f"producteur-{nom}",
            "acces_au_verificateur": False,
            "consignes": f"produire {nom}",
            "resultat_attendu": {
                card["id"]: {p: valeur for p in card["predicates"]}
                for card in lock["score_cards"]
            },
        }
    provenance_data = (
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    provenance_path = task_dir / "temoins" / "provenance.json"
    provenance_path.write_bytes(provenance_data)

    lock["task"]["task_dir"] = "task"
    lock["task"]["task_tree"] = []
    for nom, contenu in contenus.items():
        data = contenu.encode("utf-8")
        lock["task"]["task_tree"].append({
            "path": nom,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "role": "judge",
        })
    lock["task"]["task_tree"].append({
        "path": "temoins/provenance.json",
        "sha256": hashlib.sha256(provenance_data).hexdigest(),
        "bytes": len(provenance_data),
        "role": "judge",
    })
    lock_hash = empreinte_lock(lock)
    environnement = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
    environnement_hash = empreinte(environnement)

    witnesses = {}
    observations = {}
    cards = {}
    for nom, valeur in (("positif.md", True), ("negatif.md", False)):
        temoin_hash = hashlib.sha256(contenus[nom].encode("utf-8")).hexdigest()
        source = provenance["temoins"][nom]
        witnesses[nom] = {
            "producer": source["producteur"],
            "access_to_verifier": source["acces_au_verificateur"],
            "instructions": source["consignes"],
            "expected_result": source["resultat_attendu"],
            "sha256": temoin_hash,
        }
        observations[nom] = {}
        for card in lock["score_cards"]:
            observations[nom][card["id"]] = {
                "score_card_id": card["id"],
                "witness_sha256": temoin_hash,
                "verify_hash": card["verify_hash"],
                "measurement_environment_hash": environnement_hash,
                **_resultat_carte(card, valeur),
            }
    for card in lock["score_cards"]:
        cards[card["id"]] = {
            "verify_hash": card["verify_hash"],
            "predicates": {
                p: {"positive": ["positif.md"], "negative": ["negatif.md"]}
                for p in card["predicates"]
            },
        }
    receipt = {
        "schema_version": SCHEMA_COVERAGE,
        "campaign_lock_hash": lock_hash,
        "task_version": "task-v3",
        "prompt_sha256": "1" * 64,
        "measurement_environment": environnement,
        "measurement_environment_hash": environnement_hash,
        "provenance_path": "temoins/provenance.json",
        "provenance_sha256": hashlib.sha256(provenance_data).hexdigest(),
        "witnesses": witnesses,
        "observations": observations,
        "cards": cards,
        "qualified": True,
    }
    return lock, lock_hash, receipt


def score_complet(lock: dict, card: dict, cellule: dict) -> tuple[dict, dict, str]:
    lock_hash = empreinte_lock(lock)
    collection = {
        "schema_version": SCHEMA_COLLECTION,
        "protocol_version": PROTOCOLE_VERSION,
        "campaign_lock_hash": lock_hash,
        "collection_id": cellule["collection_id"],
        "result": "COMPLETE",
        "task_version": lock["task"]["task_version"],
        "prompt_sha256": lock["task"]["prompt_sha256"],
        "execution_manifest_hash": cellule["execution_manifest_hash"],
        "response_sha256": hashlib.sha256(b"response\n").hexdigest(),
    }
    collection_hash = empreinte(collection)
    environnement = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
    contexte = {
        "schema_version": SCHEMA_CONTEXT,
        "protocol_version": PROTOCOLE_VERSION,
        "task_version": lock["task"]["task_version"],
        "prompt_sha256": lock["task"]["prompt_sha256"],
        "score_card_id": card["id"],
        "verify_version": card["verify_version"],
        "verify_hash": card["verify_hash"],
        "measurement_environment_hash": empreinte(environnement),
        "regime_confidentialite": "expose",
    }
    resultat = _resultat_carte(card, True)
    score = {
        "schema_version": SCHEMA_SCORE,
        "protocol_version": PROTOCOLE_VERSION,
        "campaign_lock_hash": lock_hash,
        "collection_id": cellule["collection_id"],
        "collection_receipt_hash": collection_hash,
        "response_sha256": collection["response_sha256"],
        "alias": cellule["alias"],
        "run": cellule["run"],
        "score_card_id": card["id"],
        "verify_version": card["verify_version"],
        "verify_hash": card["verify_hash"],
        "measurement_context": contexte,
        "measurement_context_hash": empreinte(contexte),
        "measurement_environment": environnement,
        "etat": resultat["etat"],
        "cause_code": resultat["cause_code"],
        "verdict": resultat["verdict"],
        "niveau": resultat["niveau"],
        "frontiere": resultat["frontiere"],
        "predicats": resultat["predicates"],
        "mesures": resultat["measurements"],
    }
    return collection, score, collection_hash


class ProtocolV2Tests(unittest.TestCase):
    def test_prompt_verrouille_inclut_donnees(self):
        task_dir = RACINE / "tasks/dev/pentagone-rotatif"
        task = {
            "task_dir": "tasks/dev/pentagone-rotatif",
            "task_file": "task-v3.md",
            "task_tree": _arbre_tache(task_dir, "task-v3.md", ["donnees.md"]),
            "prompt_sha256": "0" * 64,
        }
        prompt, inputs = assembler_prompt_verrouille(
            RACINE, task, verifier_arbre=True, verifier_prompt=False
        )
        self.assertEqual(set(inputs), {"donnees.md"})
        self.assertEqual(
            hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "9e64405f9fac5dec58a576e7cdbf81aed5b1b6d4c2be8bca74ef1f73fbe4a613",
        )

    def test_collecteur_direct_refuse_apres_complete_ou_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            cid = "reference-gpt-5-6__r1"
            tentative = racine / "collections" / cid / "attempt-1"
            tentative.mkdir(parents=True)
            (tentative / "COMPLETE").write_text("ok\n", encoding="utf-8")
            self.assertIn("COMPLETE", resultat_acquis_v2(racine, cid) or "")

            (tentative / "COMPLETE").unlink()
            score = racine / "scores" / ("a" * 64) / "pentagone-api" / "score.json"
            score.parent.mkdir(parents=True)
            score.write_text(
                json.dumps({"collection_id": cid, "etat": "SCORED"}), encoding="utf-8"
            )
            self.assertIn("SCORED", resultat_acquis_v2(racine, cid) or "")

    def test_qualification_set_est_fermee_et_exclut_les_temoins_historique(self):
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp)
            (dossier / "temoins").mkdir()
            qualifiant = dossier / "temoins/positif.md"
            qualifiant.write_text("positif\n", encoding="utf-8")
            (dossier / "temoins/historique.md").write_text("ancien\n", encoding="utf-8")
            (dossier / "anchor-historique.md").write_text("ancien\n", encoding="utf-8")
            objet = {
                "qualification_set": ["temoins/positif.md"],
                "temoins": {
                    "temoins/positif.md": {"producteur": "fixture"},
                    "temoins/historique.md": {"producteur": "historique"},
                },
            }
            provenance, chemins = charger_qualification_set(dossier, objet)
            self.assertEqual(
                set(provenance), {"temoins/positif.md", "temoins/historique.md"}
            )
            self.assertEqual(chemins, [qualifiant.resolve()])

            incoherent = copy.deepcopy(objet)
            incoherent["qualification_set"].append("temoins/inconnu.md")
            with self.assertRaises(ContratV2Invalide):
                charger_qualification_set(dossier, incoherent)

    def test_lock_contient_114_collectes_et_cinq_cartes(self):
        lock = valider_lock(lock_minimal())
        self.assertEqual(len(lock["collections"]), 114)
        self.assertEqual([c["id"] for c in lock["score_cards"]], list(CARDS_V4))
        altere = copy.deepcopy(lock)
        altere["collections"].pop()
        with self.assertRaises(ContratV2Invalide):
            valider_lock(altere)

    def test_lock_refuse_source_ou_environnement_non_fige(self):
        sans_source = lock_minimal()
        del sans_source["repository_source"]
        with self.assertRaisesRegex(ContratV2Invalide, "commit source"):
            valider_lock(sans_source)

        environnement_altere = lock_minimal()
        environnement_altere["environments"]["runner"]["descriptor"]["timezone"] = "UTC"
        with self.assertRaisesRegex(ContratV2Invalide, "empreinte"):
            valider_lock(environnement_altere)

        lock = lock_minimal()
        observe = copy.deepcopy(lock["environments"]["runner"]["descriptor"])
        valider_environnement_observe(lock, "runner", observe)
        observe["architecture"] = "autre"
        with self.assertRaisesRegex(ContratV2Invalide, "différent du lock"):
            valider_environnement_observe(lock, "runner", observe)

    def test_lock_refuse_une_identite_ou_un_budget_auto_declare(self):
        lock = lock_minimal()
        variantes = []
        modele = copy.deepcopy(lock)
        modele["collections"][0]["model"] = "example/autre"
        variantes.append(modele)
        cout = copy.deepcopy(lock)
        cout["collections"][0]["max_cost_microdollars"] -= 1
        variantes.append(cout)
        agregation = copy.deepcopy(lock)
        agregation["score_cards"][0]["aggregation"]["order_statistic"] = 3
        variantes.append(agregation)
        verify_hash = copy.deepcopy(lock)
        verify_hash["score_cards"][0]["verify_hash"] = "0" * 64
        variantes.append(verify_hash)
        for variante in variantes:
            with self.subTest(variante=variante):
                with self.assertRaises(ContratV2Invalide):
                    valider_lock(variante)

    def test_preparateur_local_construit_le_panel_reel_sans_reseau(self):
        registry = tomllib.loads((RACINE / "models.toml").read_text(encoding="utf-8"))
        resolved = {}
        for alias in PANEL_B0:
            resolved[alias] = {
                "metadata_status": "resolved",
                "provider": registry[alias]["provider"],
                "quantization": "fixture",
                "revision": "fixture",
                "criterion_version": "fixture/v1",
                "price_source": "fixture locale",
                "price_observed_at": "2026-08-08T00:00:00+02:00",
                "input_usd_per_million_tokens": "0.1",
                "output_usd_per_million_tokens": "0.2",
                "request_usd": "0",
                "max_tokens": 65_536,
            }
        draft = {
            "schema_version": "benchmark-lab-x/campaign-draft/v2",
            "protocol_version": PROTOCOLE_VERSION,
            "campaign_id": "fixture-preparer-v2",
            "question": "fixture locale",
            "created_at": "2026-08-08T00:00:00+02:00",
            "source_commit": "a" * 40,
            "task_dir": "tasks/dev/pentagone-rotatif",
            "task_file": "task-v3.md",
            "visible_inputs": ["donnees.md"],
            "models_file": "models.toml",
            "candidates": list(PANEL_B0),
            "runs": 6,
            "attempts_max": 3,
            "concurrence": 2,
            "timeout": 600,
            "cap_microdollars": 55_000_000,
            "estimate_microdollars": 31_812_500,
            "resolved": resolved,
        }
        snapshot = {
            "schema_version": "benchmark-lab-x/route-preflight-snapshot/v1",
            "panel": list(PANEL_B0),
            "observed_at": "2026-08-08T00:00:00+02:00",
            "criterion_version": "benchmark-lab-x/selection-route/v2",
            "models_file": "models.toml",
            "models_file_sha256": hashlib.sha256(
                (RACINE / "models.toml").read_bytes()
            ).hexdigest(),
            "resolved": resolved,
            "budget_reestimate": {
                "status": "B0_09_UNCHANGED",
                "approved_estimate_microdollars": 31_812_500,
                "repriced_estimate_microdollars": 31_812_500,
                "approved_cap_microdollars": 55_000_000,
            },
            "b0_09_approval": {
                "schema_version": "benchmark-lab-x/b0-09-approval/v1",
                "decision": "B0_09_REVISED_ESTIMATE_APPROVED",
                "approved_by": "Ayo",
                "approved_at": "2026-08-08T18:30:15+02:00",
                "estimate_microdollars": 31_812_500,
                "cap_microdollars": 55_000_000,
                "source_snapshot_path": "runs/fixture/source.json",
                "source_snapshot_sha256": "a" * 64,
                "scope": "fixture",
            },
        }
        with tempfile.TemporaryDirectory(dir=RACINE / "runs") as tmp:
            snapshot_path = Path(tmp) / "routes-preflight.json"
            snapshot_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            draft["route_snapshot_file"] = snapshot_path.relative_to(RACINE).as_posix()
            draft["route_snapshot_sha256"] = hashlib.sha256(
                snapshot_path.read_bytes()
            ).hexdigest()
            with patch("protocole_v2._verifier_source_depot"):
                lock = construire_lock(draft)
        self.assertEqual(len(lock["collections"]), 114)
        self.assertEqual(lock["budget"]["cap_microdollars"], 55_000_000)
        self.assertEqual(lock["repository_source"], {"commit": "a" * 40})
        self.assertEqual(set(lock["environments"]), {"runner", "measurement"})
        lignes_actifs = lock["score_cards"][0]["verify_manifest"]["assets"]
        self.assertEqual(
            [a["path"] for a in lignes_actifs],
            sorted(a["path"] for a in lignes_actifs),
        )
        actifs = {a["path"] for a in lignes_actifs}
        self.assertIn("tools/qualifier_temoins.py", actifs)
        self.assertIn("tasks/dev/pentagone-rotatif/temoins/provenance.json", actifs)
        self.assertEqual(
            len([p for p in actifs if "/temoins/" in p and p.endswith(".md")]),
            13,
        )

    def test_preparateur_refuse_le_snapshot_b0_09_en_hold(self):
        snapshot = RACINE / "runs/2026-08-08-pentagone-v3-preflight/routes-preflight.json"
        draft = {
            "route_snapshot_file": snapshot.relative_to(RACINE).as_posix(),
            "route_snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            "estimate_microdollars": 31_812_500,
            "cap_microdollars": 55_000_000,
        }
        with self.assertRaisesRegex(ContratV2Invalide, "B0-09"):
            _charger_snapshot_routes(
                draft,
                list(PANEL_B0),
                RACINE / "models.toml",
            )

    def test_controle_r016_refuse_une_provenance_qualifiante_modifiee(self):
        source = RACINE / "tasks/dev/pentagone-rotatif/temoins"
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task"
            shutil.copytree(source, task_dir / "temoins")
            provenance_path = task_dir / "temoins/provenance.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            nom = provenance["qualification_set"][0]
            provenance["temoins"][nom]["producteur"] = "producteur altéré"
            provenance_path.write_text(
                json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(IntegrationR016Invalide):
                verifier_destination(task_dir)

    def test_agregation_quatrieme_meilleur_sur_six(self):
        niveaux = [9, 3, 8, 7, 1, 6]
        scores = [{"run": i, "etat": "SCORED", "niveau": n}
                  for i, n in enumerate(niveaux, start=1)]
        agrege = agreger_scores("levels", scores)
        self.assertEqual(agrege["niveau_retenu"], 6)
        verdicts = ["PASS", "FAIL", "PASS", "PASS", "FAIL", "PASS"]
        binaire = agreger_scores("binary", [
            {"run": i, "etat": "SCORED", "verdict": v}
            for i, v in enumerate(verdicts, start=1)
        ])
        self.assertEqual(binaire["verdict_retenu"], "PASS")
        self.assertEqual(binaire["pass_count"], 4)

    def test_unknown_bloque_seulement_l_agregat_concerne(self):
        scores = [{"run": i, "etat": "SCORED", "niveau": i} for i in range(1, 7)]
        scores[2] = {"run": 3, "etat": "UNKNOWN", "cause_code": "VERIFY_TIMEOUT"}
        bloque = agreger_scores("levels", scores)
        self.assertFalse(bloque["classement_valide"])
        autres = agreger_scores("levels", [
            {"run": i, "etat": "SCORED", "niveau": i} for i in range(1, 7)
        ])
        self.assertTrue(autres["classement_valide"])

    def test_reprise_fermee(self):
        cellule = lock_minimal()["collections"][0]
        base = {"schema_version": SCHEMA_ATTEMPT, "collection_id": cellule["collection_id"],
                "attempt": 1, "result": "FAILED", "cause_code": "HTTP_429",
                "candidate_content_received": False,
                "route_hash": cellule["execution_manifest_hash"],
                "cost_accounting": {"status": "known", "cost_microdollars": 0}}
        self.assertEqual(decision_reprise(base, cellule)["action"], "retry")
        inconnu = copy.deepcopy(base)
        inconnu["cost_accounting"]["status"] = "unknown"
        self.assertEqual(decision_reprise(inconnu, cellule)["action"], "hold")
        contenu = copy.deepcopy(base)
        contenu["candidate_content_received"] = True
        self.assertEqual(decision_reprise(contenu, cellule)["action"], "hold")
        autre = copy.deepcopy(base)
        autre["cause_code"] = "HTTP_500"
        self.assertEqual(decision_reprise(autre, cellule)["action"], "hold")

    def test_registre_budget_atomique_ne_depasse_pas_le_plafond(self):
        with tempfile.TemporaryDirectory() as tmp:
            registre = RegistreBudget(Path(tmp) / "ledger.json", 100, "c" * 64)
            def reserver(i):
                try:
                    registre.reserver(f"r{i}", 60)
                    return "ok"
                except PlafondDepasse:
                    return "refuse"
            with ThreadPoolExecutor(max_workers=2) as pool:
                resultats = list(pool.map(reserver, (1, 2)))
            self.assertEqual(sorted(resultats), ["ok", "refuse"])
            state = registre.etat()
            self.assertEqual(RegistreBudget._reserve_total(state), 60)

    def test_registre_budget_refuse_un_etat_valide_json_mais_corrompu(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            registre = RegistreBudget(path, 100, "a" * 64)
            registre.reserver("r1", 60)
            original = json.loads(path.read_text(encoding="utf-8"))
            variantes = []
            negatif = copy.deepcopy(original)
            negatif["engaged_microdollars"] = -1
            variantes.append(negatif)
            statut = copy.deepcopy(original)
            statut["reservations"]["r1"]["status"] = "opaque"
            variantes.append(statut)
            depasse = copy.deepcopy(original)
            depasse["reservations"]["r1"]["max_microdollars"] = 101
            variantes.append(depasse)
            for variante in variantes:
                with self.subTest(variante=variante):
                    path.write_text(json.dumps(variante), encoding="utf-8")
                    with self.assertRaises(ContratV2Invalide):
                        registre.etat()

    def test_ecriture_immuable_concurrente_necrase_jamais(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            def ecrire(valeur):
                try:
                    ecrire_json_immuable(path, {"valeur": valeur})
                    return "ok"
                except ContratV2Invalide:
                    return "refuse"
            with ThreadPoolExecutor(max_workers=2) as pool:
                resultats = list(pool.map(ecrire, (1, 2)))
            self.assertEqual(sorted(resultats), ["ok", "refuse"])
            self.assertIn(json.loads(path.read_text(encoding="utf-8"))["valeur"], {1, 2})

    def test_cout_maximal_est_calcule_depuis_les_prix_figes(self):
        route = {"input_usd_per_million_tokens": "1.25",
                 "output_usd_per_million_tokens": "10", "request_usd": "0.001"}
        self.assertEqual(cout_max_microdollars(route, 100, 1_000), 11_125)

    def test_cout_absent_conserve_le_maximum_et_place_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            registre = RegistreBudget(Path(tmp) / "ledger.json", 100, "d" * 64)
            registre.reserver("r1", 60)
            registre.finaliser("r1", None)
            state = registre.etat()
            self.assertTrue(state["hold"])
            self.assertEqual(RegistreBudget._reserve_total(state), 60)

    def test_autorisation_payante_liee_au_lock_et_au_plafond(self):
        auth = {"schema_version": "benchmark-lab-x/paid-authorization/v1",
                "decision": "GO_PAID_COLLECTION", "campaign_lock_hash": "e" * 64,
                "cap_microdollars": 55_000_000, "approved_by": "Ayo",
                "approved_at": "2026-08-08T00:00:00+02:00"}
        valider_autorisation_payante(auth, "e" * 64, 55_000_000)
        auth["cap_microdollars"] += 1
        with self.assertRaises(ContratV2Invalide):
            valider_autorisation_payante(auth, "e" * 64, 55_000_000)

    def test_recu_r016_complet_et_peremption(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock, lock_hash, receipt = couverture_complete(racine)
            self.assertEqual(
                valider_recu_couverture(receipt, lock, lock_hash, racine),
                (True, []),
            )
            stale = copy.deepcopy(receipt)
            stale["campaign_lock_hash"] = "f" * 64
            ok, motifs = valider_recu_couverture(stale, lock, lock_hash, racine)
            self.assertFalse(ok)
            self.assertIn("reçu R-016 lié à un autre lock", motifs)
            non_aveugle = copy.deepcopy(receipt)
            non_aveugle["witnesses"]["positif.md"]["access_to_verifier"] = True
            non_aveugle["qualified"] = False
            ok, motifs = valider_recu_couverture(non_aveugle, lock, lock_hash, racine)
            self.assertFalse(ok)
            self.assertTrue(any("provenance verrouillée" in motif for motif in motifs))

    def test_recu_r016_recalcule_la_couverture_depuis_les_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock, lock_hash, receipt = couverture_complete(racine)
            card = lock["score_cards"][0]
            predicat = card["predicates"][0]
            receipt["cards"][card["id"]]["predicates"][predicat]["positive"] = [
                "negatif.md"
            ]
            ok, motifs = valider_recu_couverture(receipt, lock, lock_hash, racine)
            self.assertFalse(ok)
            self.assertTrue(any("différente des observations" in motif for motif in motifs))

    def test_recu_score_recalcule_niveau_et_contexte(self):
        lock = lock_minimal()
        cellule = lock["collections"][0]
        card = lock["score_cards"][2]
        collection, score, collection_hash = score_complet(lock, card, cellule)
        lock_hash = empreinte_lock(lock)
        self.assertIs(
            valider_recu_score(
                score, lock, lock_hash, card, cellule, collection, collection_hash
            ),
            score,
        )
        niveau_faux = copy.deepcopy(score)
        niveau_faux["niveau"] -= 1
        with self.assertRaises(ContratV2Invalide):
            valider_recu_score(
                niveau_faux, lock, lock_hash, card, cellule, collection, collection_hash
            )
        contexte_faux = copy.deepcopy(score)
        contexte_faux["measurement_context"]["prompt_sha256"] = "f" * 64
        contexte_faux["measurement_context_hash"] = empreinte(
            contexte_faux["measurement_context"]
        )
        with self.assertRaises(ContratV2Invalide):
            valider_recu_score(
                contexte_faux, lock, lock_hash, card, cellule, collection, collection_hash
            )

    def test_rapport_v2_refuse_un_score_semantiquement_altere(self):
        lock = lock_minimal()
        cellule = lock["collections"][0]
        card = lock["score_cards"][2]
        collection, score, collection_hash = score_complet(lock, card, cellule)
        score["niveau"] -= 1
        with tempfile.TemporaryDirectory() as tmp:
            campagne = Path(tmp)
            tentative = campagne / "collections" / cellule["collection_id"] / "attempt-1"
            tentative.mkdir(parents=True)
            (tentative / "response.md").write_text("response\n", encoding="utf-8")
            (tentative / "collection-receipt.json").write_text(
                json.dumps(collection), encoding="utf-8"
            )
            (tentative / "COMPLETE").write_text("ok\n", encoding="utf-8")
            score_path = (
                campagne / "scores" / collection_hash / card["id"]
                / f"{card['verify_hash']}.json"
            )
            score_path.parent.mkdir(parents=True)
            score_path.write_text(json.dumps(score), encoding="utf-8")
            with self.assertRaises(ContratV2Invalide):
                rapport_campagne._score_v2(
                    campagne, lock, empreinte_lock(lock), card,
                    cellule["alias"], cellule["run"],
                )

    def test_traversee_refusee(self):
        for chemin in ("../secret", "/tmp/secret", "a/./b"):
            with self.assertRaises(ContratV2Invalide):
                chemin_relatif_sur(chemin, "fixture")

    def test_rapport_v2_ne_lance_ni_processus_ni_chromium(self):
        lock = lock_minimal()
        with tempfile.TemporaryDirectory() as tmp:
            campagne = Path(tmp)
            (campagne / "campaign.lock.json").write_text("{}\n", encoding="utf-8")
            conf = {"protocol_version": PROTOCOLE_VERSION,
                    "campaign_lock": "campaign.lock.json"}
            with patch.object(rapport_campagne, "valider_lock", return_value=lock), \
                 patch.object(rapport_campagne, "empreinte_lock", return_value="9" * 64), \
                 patch.object(rapport_campagne.subprocess, "Popen",
                              side_effect=AssertionError("processus interdit")), \
                 contextlib.redirect_stdout(io.StringIO()) as sortie:
                code = rapport_campagne.rapport_v2(campagne, conf)
            self.assertEqual(code, 0)
            resultat = json.loads(sortie.getvalue())
            self.assertFalse(resultat["conformite"]["page_validee"])
            self.assertEqual(len(resultat["cartes"]), 5)


if __name__ == "__main__":
    unittest.main()
