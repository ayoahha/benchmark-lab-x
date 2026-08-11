"""Tests des cinq améliorations MSW du workflow de notation"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(Path(__file__).parent))

import noter_campagne  # noqa: E402
import rapport_campagne  # noqa: E402
from empreintes import empreinte  # noqa: E402
from protocole_v2 import (  # noqa: E402
    SCHEMA_SCORE_CHILD,
    SCHEMA_STATUS_HANDOFF,
    ContratV2Invalide,
    chemin_recu_score_enfant,
    construire_process_diagnostic,
    ecrire_json_immuable,
    empreinte_lock,
    expurger_diagnostic_processus,
    valider_recu_score_enfant,
)
from test_protocol_v2 import (  # noqa: E402
    lock_minimal,
    score_complet,
    tentative_complete,
)


def _preparer_collecte(tmp: Path, lock: dict, collection_id: str | None = None):
    cellule = lock["collections"][0]
    if collection_id is not None:
        cellule = next(
            c for c in lock["collections"] if c["collection_id"] == collection_id
        )
    collection_id = cellule["collection_id"]
    card0 = lock["axes"][0]
    collection, score, collection_hash = score_complet(lock, card0, cellule)
    campaign = tmp / "campaign"
    attempt = campaign / "collections" / collection_id / "attempt-1"
    attempt.mkdir(parents=True)
    (attempt / "COMPLETE").write_text("", encoding="utf-8")
    response = b"response\n"
    raw = b"{}\n"
    (attempt / "response.md").write_bytes(response)
    (attempt / "raw.json").write_bytes(raw)
    ecrire_json_immuable(attempt / "collection-receipt.json", collection)
    ecrire_json_immuable(
        attempt / "attempt-receipt.json",
        tentative_complete(lock, cellule, collection),
    )
    return {
        "campaign": campaign,
        "lock": lock,
        "cellule": cellule,
        "collection": collection,
        "collection_hash": collection_hash,
        "collection_id": collection_id,
        "response": attempt / "response.md",
        "score_modele": score,
    }


def _score_pour_axe(base: dict, lock: dict, card: dict, etat: str, cause=None):
    score = copy.deepcopy(base)
    score["axis_id"] = card["id"]
    score["verify_version"] = card["verify_version"]
    score["verify_hash"] = card["verify_hash"]
    contexte = score["measurement_context"]
    contexte["axis_id"] = card["id"]
    contexte["verify_version"] = card["verify_version"]
    contexte["verify_hash"] = card["verify_hash"]
    score["measurement_context_hash"] = empreinte(contexte)
    score["etat"] = etat
    score["cause_code"] = cause
    if etat == "SCORED":
        predicats = {p: True for p in card["predicates"]}
        score["predicats"] = predicats
        score["verdict"] = "PASS"
        score["niveau"] = len(predicats) if card["kind"] == "levels" else None
        score["frontiere"] = None
        score["mesures"] = {}
    else:
        score["predicats"] = {}
        score["mesures"] = {}
        score["verdict"] = None
        score["niveau"] = None
        score["frontiere"] = None
    return score


def _chemin_parent(ctx, card):
    lock_hash = empreinte_lock(ctx["lock"])
    return (
        ctx["campaign"]
        / "scores"
        / ctx["collection_hash"]
        / card["id"]
        / f"{card['verify_hash']}.json"
    )


def _resultat_scored(card: dict) -> dict:
    predicats = {p: True for p in card["predicates"]}
    return {
        "etat": "SCORED",
        "cause_code": None,
        "verdict": "PASS",
        "niveau": len(predicats) if card["kind"] == "levels" else None,
        "frontiere": None,
        "predicates": predicats,
        "measurements": {},
        "card_id": card["id"],
    }


def _preparer_instrument(racine: Path, lock: dict) -> Path:
    instrument = racine / "instrument"
    digest = hashlib.sha256(b"x").hexdigest()
    for card in lock["axes"]:
        verifier = instrument / card["verifier_path"]
        verifier.parent.mkdir(parents=True, exist_ok=True)
        verifier.write_bytes(b"x")
        for asset in card["verify_manifest"]["assets"]:
            path = instrument / asset["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")
            asset["sha256"] = digest
            asset["bytes"] = 1
        card["verify_hash"] = empreinte(card["verify_manifest"])
    return instrument


def _unknown_parent(lock: dict, card: dict, cellule: dict, cause: str) -> dict:
    collection, score, _ = score_complet(lock, card, cellule)
    del collection
    score["etat"] = "UNKNOWN"
    score["cause_code"] = cause
    score["verdict"] = None
    score["niveau"] = None
    score["frontiere"] = None
    score["predicats"] = {}
    score["mesures"] = {}
    return score


def _enfant_pour(parent: dict, code: int = -9, stderr: str = "") -> dict:
    return {
        "schema_version": SCHEMA_SCORE_CHILD,
        "protocol_version": parent["protocol_version"],
        "parent_score_receipt_hash": empreinte(parent),
        "campaign_lock_hash": parent["campaign_lock_hash"],
        "collection_id": parent["collection_id"],
        "collection_receipt_hash": parent["collection_receipt_hash"],
        "axis_id": parent["axis_id"],
        "verify_hash": parent["verify_hash"],
        "etat": "UNKNOWN",
        "cause_code": parent["cause_code"],
        "process_diagnostic": {
            "failure_stage": "timeout" if parent["cause_code"] == "VERIFY_TIMEOUT" else "exit",
            "verifier_exit_code": code,
            "stderr_redacted": expurger_diagnostic_processus(stderr),
        },
    }


def _resultat_serie_fixture(axes_ids, scores_par_run):
    cartes = []
    for axis_id in axes_ids:
        cartes.append({
            "id": axis_id,
            "kind": "binary",
            "verify_version": "verify-v1",
            "verify_hash": "3" * 64,
            "measurement_context_hash": "6" * 64,
            "statut": "provisoire",
            "classement_valide": False,
            "blocages": [],
            "audit_receipt": None,
            "candidats": [{
                "alias": "modele",
                "panel_state": None,
                "providers_served": ["p"],
                "provider_route_order": ["p"],
                "scores": scores_par_run,
                "agregat": {"classement_valide": False},
                "rang_provisoire": None,
            }],
        })
    return {
        "schema_version": "benchmark-lab-x/series-results/v1",
        "protocol_version": "benchmark-lab-x/protocol/v2",
        "campaign_id": "serie-fixture",
        "campaign_lock_hash": "5" * 64,
        "conformite": {
            "instrument_qualifie": True,
            "page_validee": False,
            "blocages": {},
        },
        "campaign_status": "complete",
        "operator_status": None,
        "axes": cartes,
    }


class WorkflowNotationTests(unittest.TestCase):
    def test_missing_only_reutilise_parent_sans_environnement_ni_verificateur(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            ctx = _preparer_collecte(racine, lock)
            parents = []
            for card in lock["axes"]:
                path = _chemin_parent(ctx, card)
                score = _score_pour_axe(ctx["score_modele"], lock, card, "SCORED")
                ecrire_json_immuable(path, score)
                parents.append(path)

            def interdit_descripteur():
                raise AssertionError("descripteur ne doit pas être appelé")

            def interdit_noter(*_a, **_k):
                raise AssertionError("_noter_une_carte ne doit pas être appelé")

            with (
                patch.object(noter_campagne, "descripteur", side_effect=interdit_descripteur),
                patch.object(noter_campagne, "_noter_une_carte", side_effect=interdit_noter),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"], lock, ctx["collection_id"]
                )
            self.assertEqual(produits, parents)
            for path in parents:
                self.assertFalse(Path(f"{path.with_suffix('')}.d").exists())

    def test_reutilise_parent_unknown_sans_nouvel_enfant(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            ctx = _preparer_collecte(racine, lock)
            parents = []
            for i, card in enumerate(lock["axes"]):
                path = _chemin_parent(ctx, card)
                if i == 0:
                    score = _score_pour_axe(
                        ctx["score_modele"], lock, card, "UNKNOWN", "VERIFY_TIMEOUT"
                    )
                else:
                    score = _score_pour_axe(ctx["score_modele"], lock, card, "SCORED")
                ecrire_json_immuable(path, score)
                parents.append(path)

            def interdit_descripteur():
                raise AssertionError("descripteur ne doit pas être appelé")

            def interdit_noter(*_a, **_k):
                raise AssertionError("_noter_une_carte ne doit pas être appelé")

            with (
                patch.object(noter_campagne, "descripteur", side_effect=interdit_descripteur),
                patch.object(noter_campagne, "_noter_une_carte", side_effect=interdit_noter),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"], lock, ctx["collection_id"]
                )
            self.assertEqual(produits, parents)
            for path in parents:
                self.assertFalse(Path(f"{path.with_suffix('')}.d").exists())

    def test_parent_symlink_hold_avant_descripteur(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            ctx = _preparer_collecte(racine, lock)
            card = lock["axes"][0]
            path = _chemin_parent(ctx, card)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Lien cassé : is_symlink True, exists False
            path.symlink_to(racine / "cible-absente.json")

            def interdit_descripteur():
                raise AssertionError("descripteur ne doit pas être appelé")

            with patch.object(
                noter_campagne, "descripteur", side_effect=interdit_descripteur
            ):
                with self.assertRaisesRegex(ContratV2Invalide, "lié symboliquement"):
                    noter_campagne.noter_collection(
                        ctx["campaign"], lock, ctx["collection_id"]
                    )

    def test_unknown_local_ecrit_parent_enfant_puis_continue(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            ctx = _preparer_collecte(racine, lock)
            card_a = lock["axes"][0]
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            appels = []

            def faux_noter(card, *_a, **_k):
                appels.append(card["id"])
                if card["id"] == card_a["id"]:
                    return {
                        "etat": "UNKNOWN",
                        "cause_code": "VERIFY_TIMEOUT",
                        "predicates": {},
                        "measurements": {},
                        "process_diagnostic": {
                            "failure_stage": "timeout",
                            "verifier_exit_code": -9,
                            "stderr_redacted": expurger_diagnostic_processus("délai"),
                        },
                    }
                return _resultat_scored(card)

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne, "_noter_une_carte", side_effect=faux_noter),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"], lock, ctx["collection_id"]
                )
            self.assertEqual(len(produits), 5)
            self.assertEqual(appels, [c["id"] for c in lock["axes"]])
            parent_a = produits[0]
            score_a = json.loads(parent_a.read_text(encoding="utf-8"))
            self.assertEqual(score_a["etat"], "UNKNOWN")
            self.assertNotIn("process_diagnostic", score_a)
            for path in produits[1:]:
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))["etat"], "SCORED"
                )
                self.assertFalse(Path(f"{path.with_suffix('')}.d").exists())
            enfant = json.loads(
                chemin_recu_score_enfant(parent_a, empreinte(score_a)).read_text(
                    encoding="utf-8"
                )
            )
            valider_recu_score_enfant(enfant, score_a)

    def test_enfant_diagnostic_est_expurge_lie_et_write_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            ctx = _preparer_collecte(racine, lock)
            card = lock["axes"][0]
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            secret = (
                "password=hunter2\n"
                "client_secret=verysecret\n"
                "Cookie: session=abc123\n"
                "https://user:pass@example.invalid/path\n"
            )

            def faux_noter(card_arg, *_a, **_k):
                if card_arg["id"] != card["id"]:
                    return _resultat_scored(card_arg)
                return {
                    "etat": "UNKNOWN",
                    "cause_code": "VERIFY_PROCESS_ERROR",
                    "predicates": {},
                    "measurements": {},
                    "process_diagnostic": noter_campagne.construire_process_diagnostic(
                        "exit", 7, secret
                    ),
                }

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne, "_noter_une_carte", side_effect=faux_noter),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"], lock, ctx["collection_id"]
                )
            parent = json.loads(produits[0].read_text(encoding="utf-8"))
            enfant_path = chemin_recu_score_enfant(produits[0], empreinte(parent))
            enfant = json.loads(enfant_path.read_text(encoding="utf-8"))
            redacted = enfant["process_diagnostic"]["stderr_redacted"]
            self.assertEqual(redacted, expurger_diagnostic_processus(secret))
            for fragment in (
                "password=hunter2", "hunter2", "client_secret=verysecret", "verysecret",
                "Cookie: session=abc123", "abc123", "user:pass", "example.invalid",
            ):
                self.assertNotIn(fragment, redacted)
            valider_recu_score_enfant(enfant, parent)
            ecrire_json_immuable(enfant_path, enfant)
            autre = copy.deepcopy(enfant)
            autre["process_diagnostic"] = {
                **enfant["process_diagnostic"],
                "stderr_redacted": expurger_diagnostic_processus("autre"),
            }
            with self.assertRaises(ContratV2Invalide):
                ecrire_json_immuable(enfant_path, autre)

    def test_enfant_diagnostic_accepte_environment_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            ctx = _preparer_collecte(racine, lock)
            cible = lock["axes"][0]["id"]
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])

            def faux_noter(card, *_a, **_k):
                if card["id"] != cible:
                    return _resultat_scored(card)
                return {
                    "etat": "UNKNOWN",
                    "cause_code": "ENVIRONMENT_MISMATCH",
                    "predicates": {},
                    "measurements": {},
                    "process_diagnostic": {
                        "failure_stage": "exit",
                        "verifier_exit_code": 1,
                        "stderr_redacted": expurger_diagnostic_processus(
                            "MoteurNonConforme"
                        ),
                    },
                }

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne, "_noter_une_carte", side_effect=faux_noter),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"], lock, ctx["collection_id"]
                )
            parent = json.loads(produits[0].read_text(encoding="utf-8"))
            enfant = json.loads(
                chemin_recu_score_enfant(produits[0], empreinte(parent)).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(enfant["cause_code"], "ENVIRONMENT_MISMATCH")
            self.assertEqual(enfant["process_diagnostic"]["failure_stage"], "exit")
            valider_recu_score_enfant(enfant, parent)

    def test_expurger_fail_closed_ne_conserve_aucune_portion_brute(self):
        self.assertEqual(expurger_diagnostic_processus(""), "")
        brut = (
            "password=hunter2\n"
            "client_secret=verysecret\n"
            "Cookie: session=abc123\n"
            "https://user:pass@example.invalid/path\n"
        )
        expurge = expurger_diagnostic_processus(brut)
        digest = hashlib.sha256(brut.encode("utf-8")).hexdigest()
        self.assertEqual(expurge, f"[EXPURGÉ stderr_sha256={digest}]")
        for fragment in (
            "password", "hunter2", "client_secret", "verysecret",
            "Cookie", "session", "abc123", "user", "pass",
            "example.invalid", "https://",
        ):
            self.assertNotIn(fragment, expurge)

    def test_valider_enfant_rejette_stderr_brut_et_accepte_format_natif(self):
        lock = lock_minimal()
        cellule = lock["collections"][0]
        parent = _unknown_parent(lock, lock["axes"][0], cellule, "VERIFY_PROCESS_ERROR")
        enfant = _enfant_pour(parent, code=7, stderr="password=hunter2")
        valider_recu_score_enfant(enfant, parent)
        self.assertEqual(
            enfant["process_diagnostic"]["stderr_redacted"],
            expurger_diagnostic_processus("password=hunter2"),
        )
        enfant_brut = copy.deepcopy(enfant)
        enfant_brut["process_diagnostic"]["stderr_redacted"] = "password=hunter2"
        with self.assertRaises(ContratV2Invalide):
            valider_recu_score_enfant(enfant_brut, parent)

    def test_timeout_simule_propage_returncode_vers_enfant(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            stderr_brut = "password=hunter2\nCookie: session=abc123\n"
            # Préparer les autres axes pour n'exercer que le premier
            for card in lock["axes"][1:]:
                ecrire_json_immuable(
                    _chemin_parent(ctx, card),
                    _score_pour_axe(ctx["score_modele"], lock, card, "SCORED"),
                )

            class Processus:
                pid = 4242

                def __init__(self):
                    self.returncode = None

                def communicate(self, timeout=None):
                    if timeout is not None:
                        raise subprocess.TimeoutExpired(["uv"], timeout)
                    self.returncode = -9
                    return "", stderr_brut

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(
                    noter_campagne.subprocess,
                    "Popen",
                    side_effect=lambda *a, **k: Processus(),
                ),
                patch.object(noter_campagne.os, "killpg"),
                patch.object(noter_campagne.os, "getpgid", return_value=4242),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"],
                    lock,
                    ctx["collection_id"],
                    instrument_root=instrument,
                )
            parent = json.loads(produits[0].read_text(encoding="utf-8"))
            self.assertEqual(parent["cause_code"], "VERIFY_TIMEOUT")
            enfant = json.loads(
                chemin_recu_score_enfant(produits[0], empreinte(parent)).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(enfant["process_diagnostic"]["verifier_exit_code"], -9)
            self.assertEqual(
                enfant["process_diagnostic"]["stderr_redacted"],
                expurger_diagnostic_processus(stderr_brut),
            )
            self.assertNotIn("hunter2", enfant["process_diagnostic"]["stderr_redacted"])
            self.assertNotIn("abc123", json.dumps(enfant))

    def test_lancement_simule_reussi(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])

            def fabriquer(*cmd, **_k):
                card_id = cmd[0][cmd[0].index("--card") + 1]
                card = next(c for c in lock["axes"] if c["id"] == card_id)
                payload = _resultat_scored(card)

                class Proc:
                    returncode = 0

                    def communicate(self, timeout=None):
                        return json.dumps(payload), ""

                return Proc()

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne.subprocess, "Popen", side_effect=fabriquer),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"],
                    lock,
                    ctx["collection_id"],
                    instrument_root=instrument,
                )
            self.assertEqual(len(produits), 5)
            for path in produits:
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))["etat"], "SCORED"
                )
                self.assertFalse(Path(f"{path.with_suffix('')}.d").exists())

    def test_erreur_processus_simulee_expurge_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            stderr_brut = (
                "password=hunter2\nclient_secret=verysecret\n"
                "Cookie: session=abc123\n"
                "https://user:pass@example.invalid/path\n"
            )

            def fabriquer(*cmd, **_k):
                card_id = cmd[0][cmd[0].index("--card") + 1]

                class Proc:
                    returncode = 17

                    def communicate(self, timeout=None):
                        if card_id == lock["axes"][0]["id"]:
                            return "", stderr_brut
                        card = next(c for c in lock["axes"] if c["id"] == card_id)
                        return json.dumps(_resultat_scored(card)), ""

                if card_id != lock["axes"][0]["id"]:
                    class Ok:
                        returncode = 0

                        def communicate(self, timeout=None):
                            card = next(c for c in lock["axes"] if c["id"] == card_id)
                            return json.dumps(_resultat_scored(card)), ""

                    return Ok()
                return Proc()

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne.subprocess, "Popen", side_effect=fabriquer),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"],
                    lock,
                    ctx["collection_id"],
                    instrument_root=instrument,
                )
            parent = json.loads(produits[0].read_text(encoding="utf-8"))
            enfant = json.loads(
                chemin_recu_score_enfant(produits[0], empreinte(parent)).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(enfant["process_diagnostic"]["verifier_exit_code"], 17)
            self.assertEqual(
                enfant["process_diagnostic"]["stderr_redacted"],
                expurger_diagnostic_processus(stderr_brut),
            )
            for fragment in ("hunter2", "verysecret", "abc123", "user:pass"):
                self.assertNotIn(fragment, json.dumps(enfant, ensure_ascii=False))

    def test_spawn_oserror_produit_unknown_enfant_et_continue(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            cible = lock["axes"][0]["id"]

            def fabriquer(*cmd, **_k):
                card_id = cmd[0][cmd[0].index("--card") + 1]
                if card_id == cible:
                    raise OSError(2, "No such file or directory", "uv")
                card = next(c for c in lock["axes"] if c["id"] == card_id)

                class Ok:
                    returncode = 0

                    def communicate(self, timeout=None):
                        return json.dumps(_resultat_scored(card)), ""

                return Ok()

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne.subprocess, "Popen", side_effect=fabriquer),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"],
                    lock,
                    ctx["collection_id"],
                    instrument_root=instrument,
                )
            self.assertEqual(len(produits), 5)
            parent = json.loads(produits[0].read_text(encoding="utf-8"))
            self.assertEqual(parent["etat"], "UNKNOWN")
            self.assertEqual(parent["cause_code"], "VERIFY_PROCESS_ERROR")
            self.assertNotIn("process_diagnostic", parent)
            enfant = json.loads(
                chemin_recu_score_enfant(produits[0], empreinte(parent)).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(enfant["process_diagnostic"]["failure_stage"], "spawn")
            self.assertIsNone(enfant["process_diagnostic"]["verifier_exit_code"])
            valider_recu_score_enfant(enfant, parent)
            for path in produits[1:]:
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))["etat"], "SCORED"
                )
                self.assertFalse(Path(f"{path.with_suffix('')}.d").exists())

    def test_output_invalide_produit_unknown_enfant_et_continue(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            cible = lock["axes"][0]["id"]

            def fabriquer(*cmd, **_k):
                card_id = cmd[0][cmd[0].index("--card") + 1]
                if card_id == cible:

                    class Proc:
                        returncode = 0

                        def communicate(self, timeout=None):
                            return "{pas-du-json", "sortie non conforme"

                    return Proc()
                card = next(c for c in lock["axes"] if c["id"] == card_id)

                class Ok:
                    returncode = 0

                    def communicate(self, timeout=None):
                        return json.dumps(_resultat_scored(card)), ""

                return Ok()

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne.subprocess, "Popen", side_effect=fabriquer),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"],
                    lock,
                    ctx["collection_id"],
                    instrument_root=instrument,
                )
            self.assertEqual(len(produits), 5)
            parent = json.loads(produits[0].read_text(encoding="utf-8"))
            self.assertEqual(parent["etat"], "UNKNOWN")
            self.assertEqual(parent["cause_code"], "VERIFY_PROCESS_ERROR")
            self.assertNotIn("process_diagnostic", parent)
            enfant = json.loads(
                chemin_recu_score_enfant(produits[0], empreinte(parent)).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(enfant["process_diagnostic"]["failure_stage"], "output")
            self.assertEqual(enfant["process_diagnostic"]["verifier_exit_code"], 0)
            valider_recu_score_enfant(enfant, parent)
            for path in produits[1:]:
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))["etat"], "SCORED"
                )
                self.assertFalse(Path(f"{path.with_suffix('')}.d").exists())

    def test_sortie_structure_invalide_produit_unknown_enfant_et_continue(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            cible = lock["axes"][0]["id"]

            def fabriquer(*cmd, **_k):
                card_id = cmd[0][cmd[0].index("--card") + 1]
                if card_id == cible:

                    class Proc:
                        returncode = 0

                        def communicate(self, timeout=None):
                            # JSON valide, bon card_id, structure contractuelle invalide
                            return json.dumps({
                                "etat": "SCORED",
                                "cause_code": None,
                                "verdict": "PASS",
                                "niveau": None,
                                "frontiere": None,
                                "predicates": {},
                                "measurements": {},
                                "card_id": card_id,
                            }), "structure invalide"

                    return Proc()
                card = next(c for c in lock["axes"] if c["id"] == card_id)

                class Ok:
                    returncode = 0

                    def communicate(self, timeout=None):
                        return json.dumps(_resultat_scored(card)), ""

                return Ok()

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne.subprocess, "Popen", side_effect=fabriquer),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"],
                    lock,
                    ctx["collection_id"],
                    instrument_root=instrument,
                )
            self.assertEqual(len(produits), 5)
            parent = json.loads(produits[0].read_text(encoding="utf-8"))
            self.assertEqual(parent["etat"], "UNKNOWN")
            self.assertEqual(parent["cause_code"], "VERIFY_PROCESS_ERROR")
            self.assertNotIn("process_diagnostic", parent)
            enfant = json.loads(
                chemin_recu_score_enfant(produits[0], empreinte(parent)).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(enfant["process_diagnostic"]["failure_stage"], "output")
            self.assertEqual(enfant["process_diagnostic"]["verifier_exit_code"], 0)
            valider_recu_score_enfant(enfant, parent)
            for path in produits[1:]:
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))["etat"], "SCORED"
                )
                self.assertFalse(Path(f"{path.with_suffix('')}.d").exists())

    def test_predicats_non_booleens_produit_unknown_enfant_et_continue(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            cible = lock["axes"][0]
            cible_id = cible["id"]

            def fabriquer(*cmd, **_k):
                card_id = cmd[0][cmd[0].index("--card") + 1]
                if card_id == cible_id:

                    class Proc:
                        returncode = 0

                        def communicate(self, timeout=None):
                            # JSON valide, card_id correct, clés présentes, valeurs non booléennes
                            return json.dumps({
                                "etat": "SCORED",
                                "cause_code": None,
                                "verdict": "PASS",
                                "niveau": None,
                                "frontiere": None,
                                "predicates": {p: "oui" for p in cible["predicates"]},
                                "measurements": {},
                                "card_id": card_id,
                            }), "predicats non booleens"

                    return Proc()
                card = next(c for c in lock["axes"] if c["id"] == card_id)

                class Ok:
                    returncode = 0

                    def communicate(self, timeout=None):
                        return json.dumps(_resultat_scored(card)), ""

                return Ok()

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne.subprocess, "Popen", side_effect=fabriquer),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"],
                    lock,
                    ctx["collection_id"],
                    instrument_root=instrument,
                )
            self.assertEqual(len(produits), 5)
            parent = json.loads(produits[0].read_text(encoding="utf-8"))
            self.assertEqual(parent["etat"], "UNKNOWN")
            self.assertEqual(parent["cause_code"], "VERIFY_PROCESS_ERROR")
            self.assertNotIn("process_diagnostic", parent)
            enfant = json.loads(
                chemin_recu_score_enfant(produits[0], empreinte(parent)).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(enfant["process_diagnostic"]["failure_stage"], "output")
            self.assertEqual(enfant["process_diagnostic"]["verifier_exit_code"], 0)
            valider_recu_score_enfant(enfant, parent)
            for path in produits[1:]:
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))["etat"], "SCORED"
                )
                self.assertFalse(Path(f"{path.with_suffix('')}.d").exists())

    def test_timeout_sans_returncode_produit_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            for card in lock["axes"][1:]:
                ecrire_json_immuable(
                    _chemin_parent(ctx, card),
                    _score_pour_axe(ctx["score_modele"], lock, card, "SCORED"),
                )
            chemin_cible = _chemin_parent(ctx, lock["axes"][0])

            class Processus:
                pid = 4242

                def __init__(self):
                    self.returncode = None

                def communicate(self, timeout=None):
                    if timeout is not None:
                        raise subprocess.TimeoutExpired(["uv"], timeout)
                    return "", "timeout sans code"

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(
                    noter_campagne.subprocess,
                    "Popen",
                    side_effect=lambda *a, **k: Processus(),
                ),
                patch.object(noter_campagne.os, "killpg"),
                patch.object(noter_campagne.os, "getpgid", return_value=4242),
            ):
                with self.assertRaisesRegex(
                    ContratV2Invalide,
                    "code de sortie du vérificateur absent après timeout",
                ):
                    noter_campagne.noter_collection(
                        ctx["campaign"],
                        lock,
                        ctx["collection_id"],
                        instrument_root=instrument,
                    )
            self.assertFalse(chemin_cible.exists())
            self.assertFalse(Path(f"{chemin_cible.with_suffix('')}.d").exists())

    def test_timeout_returncode_nul_produit_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            for card in lock["axes"][1:]:
                ecrire_json_immuable(
                    _chemin_parent(ctx, card),
                    _score_pour_axe(ctx["score_modele"], lock, card, "SCORED"),
                )
            chemin_cible = _chemin_parent(ctx, lock["axes"][0])

            class Processus:
                pid = 4242

                def __init__(self):
                    self.returncode = None

                def communicate(self, timeout=None):
                    if timeout is not None:
                        raise subprocess.TimeoutExpired(["uv"], timeout)
                    self.returncode = 0
                    return "", "timeout avec code nul"

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(
                    noter_campagne.subprocess,
                    "Popen",
                    side_effect=lambda *a, **k: Processus(),
                ),
                patch.object(noter_campagne.os, "killpg"),
                patch.object(noter_campagne.os, "getpgid", return_value=4242),
            ):
                with self.assertRaisesRegex(
                    ContratV2Invalide,
                    "code de sortie du vérificateur absent ou nul après timeout",
                ):
                    noter_campagne.noter_collection(
                        ctx["campaign"],
                        lock,
                        ctx["collection_id"],
                        instrument_root=instrument,
                    )
            self.assertFalse(chemin_cible.exists())
            self.assertFalse(Path(f"{chemin_cible.with_suffix('')}.d").exists())

    def test_repertoire_enfant_symlink_refuse_avant_ecriture(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            card = lock["axes"][0]
            for autre in lock["axes"][1:]:
                ecrire_json_immuable(
                    _chemin_parent(ctx, autre),
                    _score_pour_axe(ctx["score_modele"], lock, autre, "SCORED"),
                )
            chemin_parent = _chemin_parent(ctx, card)
            chemin_parent.parent.mkdir(parents=True, exist_ok=True)
            cible_externe = racine / "cible-externe"
            cible_externe.mkdir()
            enfant_lien = Path(f"{chemin_parent.with_suffix('')}.d")
            enfant_lien.symlink_to(cible_externe)

            def faux_noter(card_arg, *_a, **_k):
                return {
                    "etat": "UNKNOWN",
                    "cause_code": "VERIFY_PROCESS_ERROR",
                    "predicates": {},
                    "measurements": {},
                    "process_diagnostic": construire_process_diagnostic(
                        "exit", 7, "password=hunter2"
                    ),
                }

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne, "_noter_une_carte", side_effect=faux_noter),
            ):
                with self.assertRaises(ContratV2Invalide):
                    noter_campagne.noter_collection(
                        ctx["campaign"], lock, ctx["collection_id"]
                    )
            self.assertEqual(list(cible_externe.iterdir()), [])
            self.assertTrue(enfant_lien.is_symlink())

    def test_handoff_compact_est_deterministe_et_ignore_enfant_pour_classement(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            cellule = lock["collections"][0]
            score_reel = _unknown_parent(
                lock, lock["axes"][0], cellule, "VERIFY_TIMEOUT"
            )
            parent_path = (
                racine / "scores" / ("1" * 64) / ("2" * 64)
                / lock["axes"][0]["id"] / f"{lock['axes'][0]['verify_hash']}.json"
            )
            ecrire_json_immuable(parent_path, score_reel)
            ecrire_json_immuable(
                chemin_recu_score_enfant(parent_path, empreinte(score_reel)),
                _enfant_pour(score_reel, code=-9),
            )
            scores_run = []
            for run in range(1, 7):
                scores_run.append({
                    "alias": "modele",
                    "run": run,
                    "etat": "UNKNOWN" if run == 1 else "SCORED",
                    "cause_code": "VERIFY_TIMEOUT" if run == 1 else None,
                    "verdict": None if run == 1 else "PASS",
                    "niveau": None,
                    "frontiere": None,
                    "predicats": {},
                    "mesures": {},
                    "measurement_context_hash": "6" * 64,
                    "collection_receipt_hash": f"{run:064x}",
                    "served": {"model": "m", "provider": "p"},
                    "provider_route_order": ["p"],
                })
            resultat = _resultat_serie_fixture([lock["axes"][0]["id"]], scores_run)
            acquisition = SimpleNamespace(
                slot_id=cellule["collection_id"],
                source_lock={"axes": lock["axes"]},
            )
            finalisation = SimpleNamespace(
                composition=SimpleNamespace(acquisitions=(acquisition,)),
                score_dir=racine / "scores",
            )

            def faux_chemin(_finalisation, _acquisition, card):
                if card["id"] == lock["axes"][0]["id"]:
                    return parent_path
                return racine / "scores" / "absent" / card["id"] / "x.json"

            self.assertFalse(resultat["conformite"]["page_validee"])
            sortie = io.StringIO()
            with (
                patch.object(
                    rapport_campagne,
                    "_resultat_serie",
                    return_value=(finalisation, resultat),
                ),
                patch.object(rapport_campagne, "chemin_score", side_effect=faux_chemin),
                contextlib.redirect_stdout(sortie),
            ):
                code = rapport_campagne.handoff_serie(racine / "lock.json")
            self.assertEqual(code, 0)
            ligne = sortie.getvalue().strip()
            self.assertEqual(ligne.count("\n"), 0)
            handoff = json.loads(ligne)
            self.assertEqual(handoff["schema_version"], SCHEMA_STATUS_HANDOFF)
            self.assertEqual(handoff["score_counts"]["UNKNOWN"], 1)
            self.assertEqual(handoff["score_counts"]["SCORED"], 5)
            self.assertEqual(handoff["child_diagnostics_count"], 1)
            self.assertFalse(handoff["conformite"]["page_validee"])
            self.assertEqual(
                ligne,
                json.dumps(
                    handoff, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ),
            )

    def test_main_handoff_et_sans_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            resultat = _resultat_serie_fixture(
                ["axe"],
                [{
                    "alias": "modele",
                    "run": r,
                    "etat": "SCORED",
                    "cause_code": None,
                    "verdict": "PASS",
                    "niveau": None,
                    "frontiere": None,
                    "predicats": {},
                    "mesures": {},
                    "measurement_context_hash": "6" * 64,
                    "collection_receipt_hash": f"{r:064x}",
                    "served": {"model": "m", "provider": "p"},
                    "provider_route_order": ["p"],
                } for r in range(1, 7)],
            )
            resultat["conformite"]["page_validee"] = True
            finalisation = SimpleNamespace(
                composition=SimpleNamespace(acquisitions=()),
                score_dir=racine / "scores",
            )
            (racine / "scores").mkdir()
            lock_path = racine / "lock.json"

            sortie_h = io.StringIO()
            with (
                patch.object(sys, "argv", [
                    "rapport_campagne.py", "--finalization-lock", str(lock_path), "--handoff",
                ]),
                patch.object(
                    rapport_campagne,
                    "_resultat_serie",
                    return_value=(finalisation, resultat),
                ),
                contextlib.redirect_stdout(sortie_h),
            ):
                code = rapport_campagne.main()
            self.assertEqual(code, 0)
            ligne = sortie_h.getvalue().strip()
            self.assertEqual(ligne.count("\n"), 0)
            self.assertEqual(json.loads(ligne)["schema_version"], SCHEMA_STATUS_HANDOFF)

            sortie_r = io.StringIO()
            with (
                patch.object(sys, "argv", [
                    "rapport_campagne.py", "--finalization-lock", str(lock_path),
                ]),
                patch.object(
                    rapport_campagne,
                    "_resultat_serie",
                    return_value=(finalisation, resultat),
                ),
                contextlib.redirect_stdout(sortie_r),
            ):
                code = rapport_campagne.main()
            self.assertEqual(code, 0)
            historique = sortie_r.getvalue()
            self.assertIn("\n", historique.strip())
            self.assertEqual(
                json.loads(historique)["schema_version"],
                resultat["schema_version"],
            )

    def test_enfant_invalide_produit_hold_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            cellule = lock["collections"][0]
            score_reel = _unknown_parent(
                lock, lock["axes"][0], cellule, "VERIFY_TIMEOUT"
            )
            parent_path = (
                racine / "scores" / ("1" * 64) / ("2" * 64)
                / lock["axes"][0]["id"] / f"{lock['axes'][0]['verify_hash']}.json"
            )
            ecrire_json_immuable(parent_path, score_reel)
            enfant_dir = Path(f"{parent_path.with_suffix('')}.d")
            enfant_dir.mkdir(parents=True)
            (enfant_dir / "fichier-extra.txt").write_text("x", encoding="utf-8")
            resultat = _resultat_serie_fixture(
                [lock["axes"][0]["id"]],
                [{
                    "alias": "modele",
                    "run": 1,
                    "etat": "UNKNOWN",
                    "cause_code": "VERIFY_TIMEOUT",
                    "verdict": None,
                    "niveau": None,
                    "frontiere": None,
                    "predicats": {},
                    "mesures": {},
                    "measurement_context_hash": "6" * 64,
                    "collection_receipt_hash": "1" * 64,
                    "served": {"model": "m", "provider": "p"},
                    "provider_route_order": ["p"],
                }],
            )
            acquisition = SimpleNamespace(
                slot_id=cellule["collection_id"],
                source_lock={"axes": [lock["axes"][0]]},
            )
            finalisation = SimpleNamespace(
                composition=SimpleNamespace(acquisitions=(acquisition,)),
                score_dir=racine / "scores",
            )
            err = io.StringIO()
            with (
                patch.object(
                    rapport_campagne,
                    "_resultat_serie",
                    return_value=(finalisation, resultat),
                ),
                patch.object(
                    rapport_campagne, "chemin_score", return_value=parent_path
                ),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(err),
            ):
                code = rapport_campagne.handoff_serie(racine / "lock.json")
            self.assertEqual(code, 2)
            self.assertIn("HOLD:", err.getvalue())

    def test_temporaire_de_notation_ne_contient_que_response_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            observe = {}

            def faux_exec(cmd, delai, env=None):
                neutre = Path(cmd[-1])
                dossier = neutre.parent
                observe["contenus"] = sorted(p.name for p in dossier.iterdir())
                observe["suffixes"] = {p.suffix for p in dossier.iterdir()}
                card_id = cmd[cmd.index("--card") + 1]
                card = next(c for c in lock["axes"] if c["id"] == card_id)
                return subprocess.CompletedProcess(
                    cmd, 0, json.dumps(_resultat_scored(card)), ""
                )

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne, "_executer_borne", side_effect=faux_exec),
            ):
                noter_campagne.noter_collection(
                    ctx["campaign"],
                    lock,
                    ctx["collection_id"],
                    instrument_root=instrument,
                )
            self.assertEqual(observe["contenus"], ["response.md"])
            self.assertEqual(observe["suffixes"], {".md"})

    def test_rapport_et_handoff_refusent_ancetre_score_symlink_hors_score_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            cellule = lock["collections"][0]
            card = lock["axes"][0]
            score_dir = racine / "scores"
            score_dir.mkdir()
            hors = racine / "hors-score"
            hors.mkdir()
            secret = "SECRET_EXTERNE_NE_PAS_LIRE"
            intermediaire = "1" * 64
            cible_externe = hors / intermediaire
            cible_externe.mkdir()
            (cible_externe / "fuite.txt").write_text(secret, encoding="utf-8")
            (score_dir / intermediaire).symlink_to(cible_externe)
            parent_path = (
                score_dir
                / intermediaire
                / ("2" * 64)
                / card["id"]
                / f"{card['verify_hash']}.json"
            )
            # Contenu externe derrière le lien : toute lecture suivrait le symlink.
            parent_path.parent.mkdir(parents=True, exist_ok=True)
            parent_path.write_text(
                json.dumps({"fuite": secret}, ensure_ascii=False),
                encoding="utf-8",
            )
            served = {"model": "m", "provider": "p"}
            acquisition = SimpleNamespace(
                slot_id=cellule["collection_id"],
                source_lock={"axes": [card]},
                source_lock_hash="1" * 64,
                cellule={
                    "collection_id": cellule["collection_id"],
                    "execution_manifest": {
                        "provider_pinned": "p",
                        "provider_routes": [{"provider_pinned": "p"}],
                    },
                },
                collection_receipt={"served": served},
                collection_receipt_hash="2" * 64,
            )
            acquisitions_by_id = {
                f"modele__r{run}": acquisition for run in range(1, 7)
            }
            composition = SimpleNamespace(
                acquisitions=(acquisition,),
                objet={
                    "series_id": "serie-fixture",
                    "panel": ["modele"],
                    "instrument_context": {
                        "task": {
                            "task_version": "task-v1",
                            "prompt_sha256": "4" * 64,
                        },
                        "axes": [card],
                    },
                },
            )
            finalisation = SimpleNamespace(
                composition=composition,
                acquisitions_by_id=acquisitions_by_id,
                score_dir=score_dir,
                lock_hash="5" * 64,
                audits_dir=racine / "audits",
                coverage_receipt={"qualified": True},
            )
            (racine / "audits").mkdir()
            lectures: list[Path] = []
            charger_origine = rapport_campagne.charger_json

            def charger_espion(path):
                lectures.append(Path(path))
                return charger_origine(path)

            # rapport_serie : refus via _score_serie avant lecture du parent.
            lectures.clear()
            sortie = io.StringIO()
            err = io.StringIO()
            with (
                patch.object(
                    rapport_campagne,
                    "charger_finalisation",
                    return_value=finalisation,
                ),
                patch.object(
                    rapport_campagne, "chemin_score", return_value=parent_path
                ),
                patch.object(
                    rapport_campagne, "charger_json", side_effect=charger_espion
                ),
                contextlib.redirect_stdout(sortie),
                contextlib.redirect_stderr(err),
            ):
                code = rapport_campagne.rapport_serie(racine / "lock.json")
            self.assertEqual(code, 2)
            self.assertIn("HOLD:", err.getvalue())
            self.assertEqual(sortie.getvalue().strip(), "")
            self.assertNotIn(secret, sortie.getvalue())
            self.assertNotIn(secret, err.getvalue())
            hors_resolu = hors.resolve()
            for lu in lectures:
                resolu = Path(lu).resolve()
                self.assertFalse(
                    resolu == hors_resolu or hors_resolu in resolu.parents,
                    f"lecture externe: {resolu}",
                )

            # handoff_serie : refus via _compter_diagnostics_enfants / ancêtres.
            resultat = _resultat_serie_fixture(
                [card["id"]],
                [{
                    "alias": "modele",
                    "run": 1,
                    "etat": "SCORED",
                    "cause_code": None,
                    "verdict": "PASS",
                    "niveau": None,
                    "frontiere": None,
                    "predicats": {},
                    "mesures": {},
                    "measurement_context_hash": "6" * 64,
                    "collection_receipt_hash": "2" * 64,
                    "served": served,
                    "provider_route_order": ["p"],
                }],
            )
            lectures.clear()
            sortie = io.StringIO()
            err = io.StringIO()
            with (
                patch.object(
                    rapport_campagne,
                    "_resultat_serie",
                    return_value=(finalisation, resultat),
                ),
                patch.object(
                    rapport_campagne, "chemin_score", return_value=parent_path
                ),
                patch.object(
                    rapport_campagne, "charger_json", side_effect=charger_espion
                ),
                contextlib.redirect_stdout(sortie),
                contextlib.redirect_stderr(err),
            ):
                code = rapport_campagne.handoff_serie(racine / "lock.json")
            self.assertEqual(code, 2)
            self.assertIn("HOLD:", err.getvalue())
            self.assertEqual(sortie.getvalue().strip(), "")
            self.assertNotIn(secret, sortie.getvalue())
            self.assertNotIn(secret, err.getvalue())
            for lu in lectures:
                resolu = Path(lu).resolve()
                self.assertFalse(
                    resolu == hors_resolu or hors_resolu in resolu.parents,
                    f"lecture externe: {resolu}",
                )

    def test_stdout_non_utf8_produit_unknown_enfant_et_continue(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            lock = lock_minimal()
            instrument = _preparer_instrument(racine, lock)
            ctx = _preparer_collecte(racine, lock)
            env = copy.deepcopy(lock["environments"]["measurement"]["descriptor"])
            cible = lock["axes"][0]["id"]
            brut = b"\xff\xfe{\"card_id\":\"x\"}"

            def fabriquer(*cmd, **_k):
                card_id = cmd[0][cmd[0].index("--card") + 1]
                if card_id == cible:

                    class Proc:
                        returncode = 0

                        def communicate(self, timeout=None):
                            raise UnicodeDecodeError(
                                "utf-8", brut, 0, 1, "invalid start byte"
                            )

                    return Proc()
                card = next(c for c in lock["axes"] if c["id"] == card_id)

                class Ok:
                    returncode = 0

                    def communicate(self, timeout=None):
                        return json.dumps(_resultat_scored(card)), ""

                return Ok()

            with (
                patch.object(noter_campagne, "descripteur", return_value=env),
                patch.object(noter_campagne.subprocess, "Popen", side_effect=fabriquer),
            ):
                produits = noter_campagne.noter_collection(
                    ctx["campaign"],
                    lock,
                    ctx["collection_id"],
                    instrument_root=instrument,
                )
            self.assertEqual(len(produits), 5)
            parent = json.loads(produits[0].read_text(encoding="utf-8"))
            self.assertEqual(parent["etat"], "UNKNOWN")
            self.assertEqual(parent["cause_code"], "VERIFY_PROCESS_ERROR")
            self.assertNotIn("process_diagnostic", parent)
            enfant = json.loads(
                chemin_recu_score_enfant(produits[0], empreinte(parent)).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(enfant["process_diagnostic"]["failure_stage"], "output")
            self.assertEqual(enfant["process_diagnostic"]["verifier_exit_code"], 0)
            valider_recu_score_enfant(enfant, parent)
            publie = json.dumps(parent, ensure_ascii=False) + json.dumps(
                enfant, ensure_ascii=False
            )
            self.assertNotIn("\xff", publie)
            self.assertNotIn(brut.decode("latin-1"), publie)
            for path in produits[1:]:
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))["etat"], "SCORED"
                )
                self.assertFalse(Path(f"{path.with_suffix('')}.d").exists())


if __name__ == "__main__":
    unittest.main()
