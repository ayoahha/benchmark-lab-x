#!/usr/bin/env python3
"""Offline pre-provider order guard. Loads private objects, never prints them"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
RAW_STORE = Path("/Users/ayo/Documents/benchmark-lab-x-private/p3-v1/raw/sha256/")
HEX64 = r"^[0-9a-f]{64}$"


class Hold(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Hold("HARNESS_ERROR: objet JSON attendu")
    return value


def require_regular_0600(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise Hold("INCONNU: objet prive absent")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or (st.st_mode & 0o777) != 0o600:
        raise Hold("HARNESS_ERROR: objet prive non regulier 0600")
    data = path.read_bytes()
    if path.name != sha256_bytes(data):
        raise Hold("HARNESS_ERROR: objet prive non adresse par contenu")
    return data


def verify_permutation(salt: bytes, attempt_ids: list[str], table: dict[str, Any]) -> dict[str, int]:
    if len(attempt_ids) != 6 or len(set(attempt_ids)) != 6:
        raise Hold("HARNESS_ERROR: identifiants de tentative non uniques")
    ranked = []
    for aid in attempt_ids:
        digest = hmac.new(salt, aid.encode("utf-8"), hashlib.sha256).digest()
        ranked.append((digest, aid.encode("utf-8"), aid))
    ranked.sort(key=lambda item: (item[0], item[1]))
    expected = {aid: idx for idx, (_, _, aid) in enumerate(ranked, start=1)}
    assignments = table.get("assignments")
    if not isinstance(assignments, list) or len(assignments) != 6:
        raise Hold("HARNESS_ERROR: table privee incomplete")
    observed: dict[str, int] = {}
    positions: list[int] = []
    for row in assignments:
        if not isinstance(row, dict):
            raise Hold("HARNESS_ERROR: ligne de table invalide")
        aid = row.get("attempt_id")
        pos = row.get("position")
        if not isinstance(aid, str) or not isinstance(pos, int):
            raise Hold("HARNESS_ERROR: affectation privee invalide")
        observed[aid] = pos
        positions.append(pos)
    if set(positions) != set(range(1, 7)) or len(positions) != 6:
        raise Hold("HARNESS_ERROR: permutation hors 1..6")
    if observed != expected:
        raise Hold("HARNESS_ERROR: HMAC et table privee divergents")
    return expected


def verify_chain(position: int, prev_path: Path, prev_sha: str, genesis_sha: str) -> None:
    if not isinstance(prev_sha, str) or len(prev_sha) != 64:
        raise Hold("INCONNU: empreinte du predecesseur manquante")
    if not prev_path.is_file() or prev_path.is_symlink():
        raise Hold("INCONNU: predecesseur absent")
    actual = sha256_bytes(prev_path.read_bytes())
    if actual != prev_sha:
        raise Hold("HARNESS_ERROR: empreinte du predecesseur non concordante")
    genesis = ROOT / "zero-execution-receipt.json"
    if position == 1:
        if prev_sha != genesis_sha or sha256_bytes(genesis.read_bytes()) != genesis_sha:
            raise Hold("HARNESS_ERROR: genese d'ordre non concordante")
        if prev_path.resolve() != genesis.resolve() and actual != genesis_sha:
            raise Hold("HARNESS_ERROR: predecesseur de position 1 hors genese")
        return
    previous = json.loads(prev_path.read_text(encoding="utf-8"))
    previous_position = previous.get("attempt", {}).get("position")
    if previous_position != position - 1:
        raise Hold("HARNESS_ERROR: chaine de positions non consecutive")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-id")
    parser.add_argument("--prev-receipt", type=Path)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    manifest = load_json(ROOT / "order-manifest.json")
    commitment = manifest.get("commitment", {})
    published = commitment.get("commitment_sha256")
    mapping_digest = commitment.get("mapping_digest_sha256")
    if not isinstance(published, str) or not isinstance(mapping_digest, str):
        raise Hold("HOLD: engagement d'ordre non publie")
    if not RAW_STORE.is_dir() or RAW_STORE.is_symlink():
        raise Hold("INCONNU: stockage prive absent")
    salt = require_regular_0600(RAW_STORE / published)
    if len(salt) != 32:
        raise Hold("HARNESS_ERROR: sel hors contrat")
    if sha256_bytes(salt) != published:
        raise Hold("HARNESS_ERROR: engagement de sel non concordant")
    table_bytes = require_regular_0600(RAW_STORE / mapping_digest)
    table = json.loads(table_bytes.decode("utf-8"))
    if not isinstance(table, dict):
        raise Hold("HARNESS_ERROR: table privee illisible")
    cells = manifest.get("cells")
    if not isinstance(cells, list) or len(cells) != 6:
        raise Hold("HARNESS_ERROR: manifeste d'ordre incomplet")
    attempt_ids = [cell.get("attempt_id") for cell in cells if isinstance(cell, dict)]
    positions = verify_permutation(salt, [str(aid) for aid in attempt_ids], table)
    genesis = ROOT / "zero-execution-receipt.json"
    genesis_sha = str(manifest.get("chain", {}).get("genesis_sha256"))
    if args.self_check or not args.attempt_id:
        genesis_ok = 0
        later_reject_genesis = 0
        for aid, position in positions.items():
            if position == 1:
                verify_chain(1, genesis, sha256_bytes(genesis.read_bytes()), genesis_sha)
                genesis_ok += 1
            else:
                try:
                    verify_chain(position, genesis, sha256_bytes(genesis.read_bytes()), genesis_sha)
                except Hold:
                    later_reject_genesis += 1
                else:
                    raise Hold("HARNESS_ERROR: chaine accepte la genese hors position 1")
        if genesis_ok != 1 or later_reject_genesis != 5:
            raise Hold("HARNESS_ERROR: chaine pre-fournisseur invalide")
        print(json.dumps({
            "status": "PASS",
            "unique_ids": 6,
            "permutation_1_to_6": True,
            "commitment_concordant": True,
            "mapping_digest_concordant": True,
            "chain_pre_provider": True,
            "provider_contacted": False,
        }, ensure_ascii=False, separators=(",", ":")))
        return 0
    if args.attempt_id not in positions or args.prev_receipt is None:
        raise Hold("HARNESS_ERROR: tentative hors manifeste")
    position = positions[args.attempt_id]
    verify_chain(
        position,
        args.prev_receipt,
        sha256_bytes(args.prev_receipt.read_bytes()) if args.prev_receipt.is_file() else "",
        genesis_sha,
    )
    print(json.dumps({
        "status": "PASS",
        "attempt_id_known": True,
        "position_in_1_6": True,
        "permutation_1_to_6": True,
        "commitment_concordant": True,
        "mapping_digest_concordant": True,
        "chain_ready": True,
        "provider_contacted": False,
    }, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Hold as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(78)
