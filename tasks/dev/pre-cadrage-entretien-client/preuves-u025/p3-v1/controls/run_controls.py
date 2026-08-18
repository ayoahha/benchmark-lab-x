#!/usr/bin/env python3
"""P3 G-001..G-005 bound to canonical validator e631184b. Inert until invoked"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


CANONICAL_SHA256 = "e631184b84270c4b3dbf931910436ad65b7d08c02016c94d2dfe53e27ead2056"
GATE_ORDER = ("G-005", "G-001", "G-002", "G-003", "G-004")
ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[4]
VALIDATOR = REPO / "tools/validateur_pre_cadrage_v0.py"
PACKAGE_DIR = REPO / "tasks/dev/pre-cadrage-entretien-client"
MANIFESTE = PACKAGE_DIR / "manifeste-paquet.json"
MANIFESTE_SHA256 = "8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_validator() -> Any:
    if not VALIDATOR.is_file() or sha256_file(VALIDATOR) != CANONICAL_SHA256:
        raise RuntimeError("HARNESS_ERROR: validateur canonique absent ou dérivé")
    spec = importlib.util.spec_from_file_location("validateur_pre_cadrage_v0", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("HARNESS_ERROR: validateur canonique illisible")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_candidate(candidate_text: str) -> dict[str, Any]:
    module = load_validator()
    paquet = module.PaquetApprouveV0(
        manifeste=MANIFESTE,
        empreinte_manifeste_approuvee=MANIFESTE_SHA256,
        approbateur="Ayo",
        verdict_approbation="APPROUVE",
    )
    with tempfile.TemporaryDirectory() as folder:
        sortie = Path(folder) / "sortie-candidate.md"
        sortie.write_text(candidate_text, encoding="utf-8")
        resultat = module.valider_pre_cadrage_v0(paquet, sortie)
    return {
        "status": resultat.statut,
        "origin": resultat.origine,
        "gates": [list(gate) for gate in resultat.gates],
        "validator_sha256": CANONICAL_SHA256,
    }


def gate_pass(result: dict[str, Any], gate_id: str) -> bool:
    for name, passed in result["gates"]:
        if name == gate_id:
            return bool(passed)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--gate", choices=GATE_ORDER)
    args = parser.parse_args()
    if not args.candidate.is_file():
        print("HARNESS_ERROR: sortie candidate absente", file=sys.stderr)
        return 78
    try:
        result = evaluate_candidate(args.candidate.read_text(encoding="utf-8"))
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 78
    if args.gate:
        result = {
            "gate": args.gate,
            "pass": gate_pass(result, args.gate),
            "status": result["status"],
            "origin": result["origin"],
            "gates": result["gates"],
            "validator_sha256": CANONICAL_SHA256,
        }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
