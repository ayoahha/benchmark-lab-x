from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import preuve_u025_p2_manual_v3 as p2v3


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()


def digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def append_rehashed_suffix(proof_dir: Path) -> None:
    register_path = proof_dir / "evidence-register.jsonl"
    entries = [json.loads(line) for line in register_path.read_bytes().splitlines()]
    receipt_base = {
        "schema_version": "u025/p2-manual-v3-receipt/v1",
        "proof_id": "U025-P2-MANUAL-V3",
        "stage": "UNEXPECTED_STAGE",
        "logical_name": "unexpected/suffix",
        "previous_receipt_sha256": entries[-1]["receipt_sha256"],
        "candidate_calls": 0,
        "provider_attempts": 0,
        "supplier_spend": "0",
        "source_v2_object_sha256": "0" * 64,
        "source_v2_receipt_sha256": "1" * 64,
        "payload": {"case_id": "WT-ACCEPTABLE"},
    }
    receipt = {**receipt_base, "receipt_sha256": digest(canonical(receipt_base))}
    receipt_bytes = canonical(receipt)
    object_sha256 = digest(receipt_bytes)
    (proof_dir / "artifacts" / object_sha256).write_bytes(receipt_bytes)
    entry_base = {
        "sequence": len(entries) + 1,
        "proof_id": "U025-P2-MANUAL-V3",
        "stage": receipt["stage"],
        "logical_name": receipt["logical_name"],
        "object_sha256": object_sha256,
        "receipt_sha256": receipt["receipt_sha256"],
        "previous_entry_sha256": entries[-1]["entry_sha256"],
    }
    entry = {**entry_base, "entry_sha256": digest(canonical(entry_base))}
    with register_path.open("ab") as stream:
        stream.write(canonical(entry))


def rewrite_rehashed_payload(
    proof_dir: Path,
    receipt_index: int,
    field: str,
    divergent_value: object,
) -> None:
    register_path = proof_dir / "evidence-register.jsonl"
    entries = [json.loads(line) for line in register_path.read_bytes().splitlines()]
    receipts = [
        json.loads((proof_dir / "artifacts" / entry["object_sha256"]).read_bytes())
        for entry in entries
    ]
    old_objects = {entry["object_sha256"] for entry in entries[receipt_index:]}
    receipts[receipt_index]["payload"][field] = divergent_value
    previous_receipt = (
        entries[receipt_index - 1]["receipt_sha256"] if receipt_index else None
    )
    previous_entry = (
        entries[receipt_index - 1]["entry_sha256"] if receipt_index else None
    )
    new_objects: set[str] = set()
    for index in range(receipt_index, len(entries)):
        receipt = receipts[index]
        receipt["previous_receipt_sha256"] = previous_receipt
        receipt_base = {
            key: value for key, value in receipt.items() if key != "receipt_sha256"
        }
        receipt["receipt_sha256"] = digest(canonical(receipt_base))
        receipt_bytes = canonical(receipt)
        object_sha256 = digest(receipt_bytes)
        (proof_dir / "artifacts" / object_sha256).write_bytes(receipt_bytes)
        new_objects.add(object_sha256)
        entry = entries[index]
        entry["object_sha256"] = object_sha256
        entry["receipt_sha256"] = receipt["receipt_sha256"]
        entry["previous_entry_sha256"] = previous_entry
        entry_base = {key: value for key, value in entry.items() if key != "entry_sha256"}
        entry["entry_sha256"] = digest(canonical(entry_base))
        previous_receipt = receipt["receipt_sha256"]
        previous_entry = entry["entry_sha256"]
    for object_sha256 in old_objects - new_objects:
        (proof_dir / "artifacts" / object_sha256).unlink()
    register_path.write_bytes(b"".join(canonical(entry) for entry in entries))


class PreuveU025P2ManualV3Tests(unittest.TestCase):
    def test_prepare_refuse_un_suffix_semantique_inattendu_mais_rehashe(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            proof_dir = Path(temporary_directory) / "p2-manual-v3"
            p2v3.prepare(p2v3.GIT_BASE, proof_dir=proof_dir)
            append_rehashed_suffix(proof_dir)

            with self.assertRaises(p2v3.InvalidProof):
                p2v3.prepare(p2v3.GIT_BASE, proof_dir=proof_dir)

    def test_prepare_refuse_un_resultat_automatique_divergent_mais_rehashe(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            proof_dir = Path(temporary_directory) / "p2-manual-v3"
            p2v3.prepare(p2v3.GIT_BASE, proof_dir=proof_dir)
            rewrite_rehashed_payload(
                proof_dir,
                receipt_index=0,
                field="automatic_result",
                divergent_value="HARNESS_ERROR",
            )

            with self.assertRaises(p2v3.InvalidProof):
                p2v3.prepare(p2v3.GIT_BASE, proof_dir=proof_dir)

    def test_finalize_refuse_un_etat_humain_divergent_mais_rehashe(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            proof_dir = Path(temporary_directory) / "p2-manual-v3"
            p2v3.prepare(p2v3.GIT_BASE, proof_dir=proof_dir)
            p2v3.finalize(proof_dir=proof_dir)
            rewrite_rehashed_payload(
                proof_dir,
                receipt_index=16,
                field="state",
                divergent_value="FAIL",
            )

            with self.assertRaises(p2v3.InvalidProof):
                p2v3.finalize(proof_dir=proof_dir)


if __name__ == "__main__":
    unittest.main()
