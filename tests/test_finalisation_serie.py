from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import noter_campagne  # noqa: E402
import rapport_campagne  # noqa: E402
from finalisation_serie import (  # noqa: E402
    AcquisitionComposee,
    CompositionValidee,
    FinalisationSerie,
    SCHEMA_AUTORISATION_NOTATION,
    chemin_score,
    integrer_couverture_exacte,
    valider_autorisation_notation,
)
from protocole_v2 import ContratV2Invalide  # noqa: E402


def acquisition_fixture(tmp: Path) -> tuple[AcquisitionComposee, dict]:
    card = {
        "id": "axe",
        "kind": "binary",
        "verify_version": "verify-v1",
        "verify_hash": "3" * 64,
    }
    acquisition = AcquisitionComposee(
        slot_id="modele__r1",
        alias="modele",
        run=1,
        source_campaign_dir=tmp / "source",
        source_lock={"axes": [card]},
        source_lock_hash="1" * 64,
        cellule={"collection_id": "modele__r1"},
        attempt_receipt={},
        collection_receipt={},
        collection_receipt_hash="2" * 64,
        response_path=tmp / "response.md",
        raw_response_path=tmp / "raw.json",
    )
    return acquisition, card


class FinalisationSerieTests(unittest.TestCase):
    def test_chemin_score_lie_lock_source_et_recu(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            acquisition, card = acquisition_fixture(racine)
            finalisation = SimpleNamespace(score_dir=racine / "scores")
            self.assertEqual(
                chemin_score(finalisation, acquisition, card),
                racine / "scores" / ("1" * 64) / ("2" * 64)
                / "axe" / f"{'3' * 64}.json",
            )

    def test_integration_r016_est_idempotente_et_refuse_un_autre_recu(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            source = racine / "source.json"
            destination = racine / "canonique.json"
            source.write_bytes(b'{"qualified":true}\n')
            integrer_couverture_exacte(source, destination)
            integrer_couverture_exacte(source, destination)
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            source.write_bytes(b'{"qualified":false}\n')
            with self.assertRaisesRegex(ContratV2Invalide, "canonique différent"):
                integrer_couverture_exacte(source, destination)

    def test_autorisation_chromium_est_liee_au_verrou(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            path = racine / "autorisation.json"
            objet = {
                "schema_version": SCHEMA_AUTORISATION_NOTATION,
                "decision": "GO_OFFLINE_SCORING",
                "finalization_lock_hash": "a" * 64,
                "expected_score_receipts": 570,
                "approved_by": "Ayo",
                "approved_at": "2026-08-10T00:00:00Z",
            }
            path.write_text(json.dumps(objet), encoding="utf-8")
            finalisation = SimpleNamespace(
                lock_hash="a" * 64,
                lock={
                    "scoring_authorization": {"path": "autorisation.json"},
                    "expected": {"score_receipts": 570},
                },
            )
            self.assertEqual(
                valider_autorisation_notation(finalisation, racine), objet
            )
            objet["finalization_lock_hash"] = "b" * 64
            path.write_text(json.dumps(objet), encoding="utf-8")
            with self.assertRaisesRegex(ContratV2Invalide, "autre finalisation"):
                valider_autorisation_notation(finalisation, racine)

    def test_scoreur_compose_ecrit_hors_des_campagnes_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            acquisition, card = acquisition_fixture(racine)
            composition = CompositionValidee(
                path=racine / "composition.json",
                sha256="4" * 64,
                objet={"instrument_context": {"axes": [card]}},
                acquisitions=(acquisition,),
                source_locks=(),
                instrument_commit="5" * 40,
                measurement_environment={},
            )
            finalisation = FinalisationSerie(
                lock_path=racine / "lock.json",
                lock={"expected": {"score_receipts": 1}},
                lock_hash="6" * 64,
                composition=composition,
                coverage_receipt={},
                score_dir=racine / "scores",
                audits_dir=racine / "audits",
                results_path=racine / "results.json",
            )
            attendu = chemin_score(finalisation, acquisition, card)

            @contextlib.contextmanager
            def instrument(_finalisation, _racine):
                yield racine / "instrument"

            with (
                patch.object(noter_campagne, "charger_finalisation", return_value=finalisation),
                patch.object(noter_campagne, "valider_autorisation_notation"),
                patch.object(noter_campagne, "instrument_fige", instrument),
                patch.object(noter_campagne, "noter_collection", return_value=[attendu]) as noter,
            ):
                recus = noter_campagne.noter_serie(racine / "lock.json")
            self.assertEqual(recus, [attendu])
            self.assertEqual(noter.call_args.kwargs["score_dir"], finalisation.score_dir)
            self.assertTrue(noter.call_args.kwargs["offline"])
            self.assertEqual(
                noter.call_args.kwargs["instrument_root"], racine / "instrument"
            )

    def test_rapport_compose_reconnait_r016_avant_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            card = {
                "id": "axe",
                "kind": "binary",
                "verify_version": "verify-v1",
                "verify_hash": "3" * 64,
            }
            composition = SimpleNamespace(objet={
                "series_id": "serie",
                "panel": ["modele"],
                "instrument_context": {
                    "task": {
                        "task_version": "task-v1",
                        "prompt_sha256": "4" * 64,
                    },
                    "axes": [card],
                },
            })
            finalisation = SimpleNamespace(
                composition=composition,
                lock_hash="5" * 64,
                audits_dir=racine / "audits",
                coverage_receipt={"qualified": True},
            )

            def score(_finalisation, _card, alias, run):
                return {
                    "alias": alias,
                    "run": run,
                    "etat": "SCORED",
                    "cause_code": None,
                    "verdict": "PASS",
                    "niveau": None,
                    "frontiere": None,
                    "predicats": {},
                    "mesures": {},
                    "measurement_context_hash": "6" * 64,
                    "collection_receipt_hash": f"{run:064x}",
                    "served": {"model": "m", "provider": "p"},
                    "provider_route_order": ["p"],
                }

            sortie = io.StringIO()
            with (
                patch.object(rapport_campagne, "charger_finalisation", return_value=finalisation),
                patch.object(rapport_campagne, "_score_serie", side_effect=score),
                contextlib.redirect_stdout(sortie),
            ):
                code = rapport_campagne.rapport_serie(racine / "lock.json")
            resultat = json.loads(sortie.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(resultat["conformite"]["instrument_qualifie"])
            self.assertFalse(resultat["conformite"]["page_validee"])
            self.assertEqual(resultat["campaign_status"], "complete")
            self.assertEqual(
                resultat["axes"][0]["blocages"],
                [{"audit": "reçu d'audit fondé sur le risque absent"}],
            )


if __name__ == "__main__":
    unittest.main()
