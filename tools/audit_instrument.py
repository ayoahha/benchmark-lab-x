# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Finaliser un reçu d'audit humain fondé sur le risque, sans modifier les notes

Le plan, sa taille et sa méthode de sélection viennent du campaign.lock v3.
Ce programme lie une revue déjà menée en aveugle aux unités effectivement
scorées, puis produit le reçu immuable consommé par le rapporteur

Usage :
    uv run tools/audit_instrument.py runs/<campagne> \
      --axis <axe> --review <revue.json> --out <recu.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from empreintes import empreinte  # noqa: E402
from protocole_v2 import (  # noqa: E402
    SCHEMA_AUDIT,
    ContratV2Invalide,
    charger_json,
    ecrire_json_immuable,
    empreinte_lock,
    valider_lock,
    valider_recu_audit,
)


CHAMPS_REVUE = {
    "schema_version", "selection_method", "identity_blinded", "score_changes",
    "sample", "completed_at", "auditor_role", "conclusion",
}


def construire_recu(
    lock: dict[str, Any], results: dict[str, Any], axis_id: str, review: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(review, dict) or set(review) != CHAMPS_REVUE:
        raise ContratV2Invalide("champs de la revue humaine différents du contrat fermé")
    if review.get("schema_version") != "benchmark-lab-x/axis-audit-review/v1":
        raise ContratV2Invalide("axis-audit-review/v1 absent")
    if not isinstance(review.get("sample"), list):
        raise ContratV2Invalide("échantillon de revue absent")
    lock_hash = empreinte_lock(lock)
    if results.get("schema_version") != "benchmark-lab-x/results-data/v3":
        raise ContratV2Invalide("results-data/v3 absent")
    if results.get("campaign_lock_hash") != lock_hash:
        raise ContratV2Invalide("résultats liés à un autre lock")
    axes_lock = [axe for axe in lock["axes"] if axe["id"] == axis_id]
    axes_resultat = [axe for axe in results.get("axes") or [] if axe.get("id") == axis_id]
    if len(axes_lock) != 1 or len(axes_resultat) != 1:
        raise ContratV2Invalide("axe absent ou dupliqué")
    axe = axes_lock[0]
    resultat = axes_resultat[0]
    contexte = resultat.get("measurement_context_hash")
    if not isinstance(contexte, str):
        raise ContratV2Invalide("contexte de mesure unique absent")
    hashes_collecte = {
        score["collection_receipt_hash"]
        for candidat in resultat.get("candidats") or []
        for score in candidat.get("scores") or []
        if score.get("etat") == "SCORED" and score.get("collection_receipt_hash")
    }
    receipt = {
        "schema_version": SCHEMA_AUDIT,
        "campaign_lock_hash": lock_hash,
        "axis_id": axis_id,
        "verify_hash": axe["verify_hash"],
        "measurement_context_hash": contexte,
        "audit_plan_hash": empreinte(axe["audit_plan"]),
        "selection_method": review["selection_method"],
        "identity_blinded": review["identity_blinded"],
        "score_changes": review["score_changes"],
        "sample": review["sample"],
        "decision": (
            "ACCEPTED"
            if all(
                isinstance(item, dict) and item.get("code_result_correct") is True
                for item in review["sample"]
            )
            else "REJECTED"
        ),
        "completed_at": review["completed_at"],
        "auditor_role": review["auditor_role"],
        "conclusion": review["conclusion"],
    }
    valider_recu_audit(receipt, lock_hash, axe, contexte, hashes_collecte)
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign_dir", type=Path)
    ap.add_argument("--axis", required=True)
    ap.add_argument("--review", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    try:
        lock = valider_lock(
            charger_json(args.campaign_dir / "campaign.lock.json"), RACINE
        )
        results = charger_json(args.campaign_dir / "results-data.json")
        receipt = construire_recu(lock, results, args.axis, charger_json(args.review))
        ecrire_json_immuable(args.out, receipt)
    except (ContratV2Invalide, OSError, TypeError) as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": receipt["decision"],
        "axis_id": receipt["axis_id"],
        "audit_receipt": str(args.out),
    }, ensure_ascii=False, indent=2))
    return 0 if receipt["decision"] == "ACCEPTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
