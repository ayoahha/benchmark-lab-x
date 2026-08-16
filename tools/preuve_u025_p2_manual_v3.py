#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p2-manual-v3"
V1_PROOF = ROOT / "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p2-manual-v1"
V2_PROOF = ROOT / "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p2-manual-v2"
PROCEDURE = PROOF / "procedure.md"
TEST_FILE = ROOT / "tests/test_preuve_u025_p2_manual_v3.py"
PROOF_ID = "U025-P2-MANUAL-V3"
GIT_BASE = "b47f86124c2c4dfd5faa10db71311fc13f1ef5bb"
V1_ROOT_SHA256 = "c031c405b059fd9f9eca0219892066bbc3c1f9e62457537f60c6c34f7d3b2e72"
V1_BYTE_FINGERPRINT = "b00e7dc0049d6a9b3e49098495918300161cf96c714bc9ac53e0849066072c39"
V2_ROOT_SHA256 = "684ce121f761e560781939928839141a34d3ebc1c474538e01fa89ad3eb99109"
V2_LOCK_SHA256 = "204222690df54ed74d5c41d002d9e1b9ee1802a548d7ea3e56f02b8c03f785d9"
V2_REGISTER_SHA256 = "e48c1c1b9c687d7226a959d8dfe944a012ed6392877b3d452109ba6aefd714c3"
V2_REGISTER_TAIL_SHA256 = "f582f1427bc55d1696cd5493059c0260c50b29e3c9eac494c7faf37a5818a963"
V2_BYTE_FINGERPRINT = "807d13db5f72196da8e4e88c7bd4a01fe6c3325a1a17473060943df2bb429b8a"
V2_NETWORK_AUDIT_SHA256 = "53c64450882a36c83c6e97400b5f84a456f67787b99d964c93907db08d00019c"


class InvalidProof(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()


def digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise InvalidProof(f"objet absent ou illisible: {path}") from error
    if not isinstance(value, dict):
        raise InvalidProof(f"objet JSON invalide: {path}")
    return value


def write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
    except FileExistsError as error:
        raise InvalidProof(f"objet fermé déjà présent: {path}") from error


def write_or_match(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise InvalidProof(f"objet fermé divergent: {path}")
        return
    write_new(path, content)


def _protected_paths(tool: str, test: str, proof: Path) -> list[Path]:
    return [
        ROOT / tool,
        ROOT / test,
        *sorted(path for path in proof.rglob("*") if path.is_file()),
    ]


def _byte_fingerprint(paths: list[Path]) -> str:
    lines = bytearray()
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        lines.extend(f"{digest(path.read_bytes())}  {relative}\n".encode())
    return digest(bytes(lines))


def v1_byte_fingerprint() -> str:
    return _byte_fingerprint(
        _protected_paths(
            "tools/preuve_u025_p2_manual.py",
            "tests/test_preuve_u025_p2_manual.py",
            V1_PROOF,
        )
    )


def v2_byte_fingerprint() -> str:
    return _byte_fingerprint(
        _protected_paths(
            "tools/preuve_u025_p2_manual_v2.py",
            "tests/test_preuve_u025_p2_manual_v2.py",
            V2_PROOF,
        )
    )


def _require_digest(path: Path, expected: str) -> None:
    observed = digest(path.read_bytes()) if path.is_file() else None
    if observed != expected:
        raise InvalidProof(
            f"empreinte divergente: {path.relative_to(ROOT)} attendu={expected} observé={observed}"
        )


def verify_sources() -> None:
    if v1_byte_fingerprint() != V1_BYTE_FINGERPRINT:
        raise InvalidProof("octets V1 divergents")
    if v2_byte_fingerprint() != V2_BYTE_FINGERPRINT:
        raise InvalidProof("octets V2 divergents")
    v1_root = read_json(V1_PROOF / "proof-root.json")
    if v1_root.get("root_sha256") != V1_ROOT_SHA256:
        raise InvalidProof("racine V1 divergente")
    v2_root = read_json(V2_PROOF / "proof-root.json")
    if v2_root.get("root_sha256") != V2_ROOT_SHA256:
        raise InvalidProof("racine V2 divergente")
    if v2_root.get("proof_lock_sha256") != V2_LOCK_SHA256:
        raise InvalidProof("lock V2 divergent")
    if v2_root.get("evidence_register_sha256") != V2_REGISTER_SHA256:
        raise InvalidProof("registre V2 divergent")
    if v2_root.get("evidence_register_tail_sha256") != V2_REGISTER_TAIL_SHA256:
        raise InvalidProof("tail V2 divergent")
    _require_digest(V2_PROOF / "network-audit.jsonl", V2_NETWORK_AUDIT_SHA256)


def _source_manifest() -> dict[str, Any]:
    return {
        "schema_version": "u025/p2-manual-v3-source/v1",
        "proof_id": PROOF_ID,
        "v2": {
            "proof_id": "U025-P2-MANUAL-V2",
            "root_sha256": V2_ROOT_SHA256,
            "lock_sha256": V2_LOCK_SHA256,
            "register_sha256": V2_REGISTER_SHA256,
            "register_tail_sha256": V2_REGISTER_TAIL_SHA256,
            "byte_fingerprint": V2_BYTE_FINGERPRINT,
        },
        "v1": {
            "proof_id": "U025-P2-MANUAL-V1",
            "root_sha256": V1_ROOT_SHA256,
            "byte_fingerprint": V1_BYTE_FINGERPRINT,
        },
    }


def _lock(git_base: str, source_manifest_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "u025/p2-manual-v3-lock/v1",
        "proof_id": PROOF_ID,
        "git_base": {"expected": GIT_BASE, "observed": git_base},
        "source_manifest_sha256": source_manifest_sha256,
        "instrument": {
            "path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "sha256": digest(Path(__file__).read_bytes()),
            "version": "u025-p2-manual-semantic-resume/3",
        },
        "test_contract": {
            "path": TEST_FILE.relative_to(ROOT).as_posix(),
            "sha256": digest(TEST_FILE.read_bytes()),
        },
        "procedure": {
            "path": PROCEDURE.relative_to(ROOT).as_posix(),
            "sha256": digest(PROCEDURE.read_bytes()),
        },
        "resume_policy": "SEMANTICALLY_EXACT_PREFIX_FIRST_INCOMPLETE_NO_REPLAY",
        "network_self_test_policy": "REUSE_VALID_V2_NO_SECOND_SELF_TEST",
        "candidate_calls": 0,
        "provider_attempt_count": 0,
        "supplier_spend_total": "0",
        "write_scope": [
            "tools/preuve_u025_p2_manual_v3.py",
            "tests/test_preuve_u025_p2_manual_v3.py",
            "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p2-manual-v3/",
        ],
        "stop_condition": "STOP_BEFORE_M3_12",
    }


def _bootstrap(proof_dir: Path, git_base: str) -> None:
    if git_base != GIT_BASE:
        raise InvalidProof("base Git divergente")
    verify_sources()
    write_or_match(proof_dir / "procedure.md", PROCEDURE.read_bytes())
    source_bytes = canonical(_source_manifest())
    write_or_match(proof_dir / "source-manifest.json", source_bytes)
    write_or_match(
        proof_dir / "proof-lock.json",
        canonical(_lock(git_base, digest(source_bytes))),
    )
    network = {
        "schema_version": "u025/p2-manual-v3-network-proof/v1",
        "proof_id": PROOF_ID,
        "action": "REUSE_VALID_V2_NETWORK_PROOF",
        "source_network_audit_sha256": V2_NETWORK_AUDIT_SHA256,
        "second_self_test_executed": False,
        "state": "PASS",
    }
    write_or_match(proof_dir / "network-audit.jsonl", canonical(network))


def _v2_entries() -> list[dict[str, Any]]:
    entries = [
        json.loads(line)
        for line in (V2_PROOF / "evidence-register.jsonl").read_bytes().splitlines()
    ]
    if len(entries) != 44:
        raise InvalidProof("inventaire des reçus V2 divergent")
    return entries


def _source_receipts() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    excluded = {
        "schema_version",
        "proof_id",
        "stage",
        "logical_name",
        "previous_receipt_sha256",
        "candidate_calls",
        "provider_attempts",
        "supplier_spend",
        "receipt_sha256",
    }
    for entry in _v2_entries():
        object_sha256 = entry["object_sha256"]
        artifact = V2_PROOF / "artifacts" / object_sha256
        _require_digest(artifact, object_sha256)
        receipt = read_json(artifact)
        sources.append(
            {
                "stage": entry["stage"],
                "logical_name": entry["logical_name"],
                "source_v2_object_sha256": object_sha256,
                "source_v2_receipt_sha256": receipt["receipt_sha256"],
                "payload": {
                    key: value for key, value in receipt.items() if key not in excluded
                },
            }
        )
    return sources


def _expected_receipt(
    source: dict[str, Any], previous_receipt_sha256: str | None
) -> dict[str, Any]:
    base = {
        "schema_version": "u025/p2-manual-v3-receipt/v1",
        "proof_id": PROOF_ID,
        "stage": source["stage"],
        "logical_name": source["logical_name"],
        "previous_receipt_sha256": previous_receipt_sha256,
        "candidate_calls": 0,
        "provider_attempts": 0,
        "supplier_spend": "0",
        "source_v2_object_sha256": source["source_v2_object_sha256"],
        "source_v2_receipt_sha256": source["source_v2_receipt_sha256"],
        "payload": source["payload"],
    }
    return {**base, "receipt_sha256": digest(canonical(base))}


def _register_entries(proof_dir: Path) -> list[dict[str, Any]]:
    path = proof_dir / "evidence-register.jsonl"
    if not path.exists():
        return []
    try:
        return [json.loads(line) for line in path.read_bytes().splitlines()]
    except json.JSONDecodeError as error:
        raise InvalidProof("registre V3 illisible") from error


def _verify_register(proof_dir: Path) -> list[dict[str, Any]]:
    entries = _register_entries(proof_dir)
    previous_entry: str | None = None
    previous_receipt: str | None = None
    objects: set[str] = set()
    for sequence, entry in enumerate(entries, start=1):
        entry_base = {key: value for key, value in entry.items() if key != "entry_sha256"}
        if entry.get("sequence") != sequence:
            raise InvalidProof("séquence V3 divergente")
        if entry.get("previous_entry_sha256") != previous_entry:
            raise InvalidProof("tail V3 divergent")
        if digest(canonical(entry_base)) != entry.get("entry_sha256"):
            raise InvalidProof("empreinte d’entrée V3 divergente")
        object_sha256 = str(entry.get("object_sha256"))
        artifact = proof_dir / "artifacts" / object_sha256
        _require_digest(artifact, object_sha256)
        receipt = read_json(artifact)
        receipt_base = {
            key: value for key, value in receipt.items() if key != "receipt_sha256"
        }
        if digest(canonical(receipt_base)) != receipt.get("receipt_sha256"):
            raise InvalidProof("empreinte de reçu V3 divergente")
        if receipt.get("previous_receipt_sha256") != previous_receipt:
            raise InvalidProof("chaîne de reçus V3 divergente")
        if entry.get("receipt_sha256") != receipt.get("receipt_sha256"):
            raise InvalidProof("lien registre-reçu V3 divergent")
        objects.add(object_sha256)
        previous_entry = entry["entry_sha256"]
        previous_receipt = receipt["receipt_sha256"]
    artifacts = proof_dir / "artifacts"
    observed = (
        {path.name for path in artifacts.iterdir() if path.is_file()}
        if artifacts.exists()
        else set()
    )
    if observed != objects:
        raise InvalidProof("objet V3 orphelin ou absent")
    return entries


def _validate_semantic_prefix(
    proof_dir: Path, entries: list[dict[str, Any]], sources: list[dict[str, Any]]
) -> None:
    if len(entries) > len(sources):
        raise InvalidProof("suffixe sémantique V3 inattendu")
    previous_receipt: str | None = None
    for index, entry in enumerate(entries):
        source = sources[index]
        if entry.get("stage") != source["stage"]:
            raise InvalidProof("stage V3 inattendu")
        if entry.get("logical_name") != source["logical_name"]:
            raise InvalidProof("logical_name V3 inattendu")
        receipt = read_json(proof_dir / "artifacts" / entry["object_sha256"])
        expected = _expected_receipt(source, previous_receipt)
        if receipt != expected:
            raise InvalidProof(f"payload V3 divergent: {source['logical_name']}")
        previous_receipt = receipt["receipt_sha256"]


def _append_receipt(
    proof_dir: Path, source: dict[str, Any], entries: list[dict[str, Any]]
) -> None:
    previous_receipt = entries[-1]["receipt_sha256"] if entries else None
    receipt = _expected_receipt(source, previous_receipt)
    receipt_bytes = canonical(receipt)
    object_sha256 = digest(receipt_bytes)
    write_new(proof_dir / "artifacts" / object_sha256, receipt_bytes)
    previous_entry = entries[-1]["entry_sha256"] if entries else None
    entry_base = {
        "sequence": len(entries) + 1,
        "proof_id": PROOF_ID,
        "stage": source["stage"],
        "logical_name": source["logical_name"],
        "object_sha256": object_sha256,
        "receipt_sha256": receipt["receipt_sha256"],
        "previous_entry_sha256": previous_entry,
    }
    entry = {**entry_base, "entry_sha256": digest(canonical(entry_base))}
    register = proof_dir / "evidence-register.jsonl"
    register.parent.mkdir(parents=True, exist_ok=True)
    with register.open("ab") as stream:
        stream.write(canonical(entry))
        stream.flush()


def _resume_events(proof_dir: Path) -> list[dict[str, Any]]:
    path = proof_dir / "resume-events.jsonl"
    if not path.exists():
        return []
    events = [json.loads(line) for line in path.read_bytes().splitlines()]
    previous: str | None = None
    for sequence, event in enumerate(events, start=1):
        base = {key: value for key, value in event.items() if key != "event_sha256"}
        if event.get("sequence") != sequence:
            raise InvalidProof("séquence de reprise V3 divergente")
        if event.get("previous_event_sha256") != previous:
            raise InvalidProof("chaîne de reprise V3 divergente")
        if digest(canonical(base)) != event.get("event_sha256"):
            raise InvalidProof("empreinte de reprise V3 divergente")
        previous = event["event_sha256"]
    return events


def _append_resume_event(
    proof_dir: Path,
    action: str,
    stage: str,
    completed_receipts: int,
) -> None:
    events = _resume_events(proof_dir)
    entries = _verify_register(proof_dir)
    event_base = {
        "sequence": len(events) + 1,
        "proof_id": PROOF_ID,
        "action": action,
        "stage": stage,
        "completed_receipts": completed_receipts,
        "closed_register_entry_count": len(entries),
        "closed_register_tail_sha256": entries[-1]["entry_sha256"] if entries else None,
        "closed_receipt_tail_sha256": entries[-1]["receipt_sha256"] if entries else None,
        "closed_object_sha256s": [entry["object_sha256"] for entry in entries],
        "previous_event_sha256": events[-1]["event_sha256"] if events else None,
    }
    event = {**event_base, "event_sha256": digest(canonical(event_base))}
    path = proof_dir / "resume-events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write(canonical(event))
        stream.flush()


def _append_unexpected_suffix(proof_dir: Path) -> str:
    entries = _verify_register(proof_dir)
    receipt_base = {
        "schema_version": "u025/p2-manual-v3-receipt/v1",
        "proof_id": PROOF_ID,
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
    write_new(proof_dir / "artifacts" / object_sha256, receipt_bytes)
    entry_base = {
        "sequence": len(entries) + 1,
        "proof_id": PROOF_ID,
        "stage": receipt["stage"],
        "logical_name": receipt["logical_name"],
        "object_sha256": object_sha256,
        "receipt_sha256": receipt["receipt_sha256"],
        "previous_entry_sha256": entries[-1]["entry_sha256"],
    }
    entry = {**entry_base, "entry_sha256": digest(canonical(entry_base))}
    with (proof_dir / "evidence-register.jsonl").open("ab") as stream:
        stream.write(canonical(entry))
        stream.flush()
    return object_sha256


def _rewrite_rehashed_payload(
    proof_dir: Path,
    receipt_index: int,
    field: str,
    divergent_value: object,
) -> str:
    register_path = proof_dir / "evidence-register.jsonl"
    entries = _register_entries(proof_dir)
    receipts = [
        read_json(proof_dir / "artifacts" / entry["object_sha256"])
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
    mutated_object_sha256 = ""
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
        if index == receipt_index:
            mutated_object_sha256 = object_sha256
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
    _verify_register(proof_dir)
    return mutated_object_sha256


def _populate_final_prefix(proof_dir: Path) -> None:
    sources = _source_receipts()
    entries = _verify_register(proof_dir)
    for source in sources[len(entries) :]:
        _append_receipt(proof_dir, source, entries)
        entries = _verify_register(proof_dir)
    _validate_semantic_prefix(proof_dir, entries, sources)


def _observed_refusal(
    counterexample_id: str,
    proof_dir: Path,
    mutated_object_sha256: str,
    action: str,
) -> dict[str, Any]:
    entries = _verify_register(proof_dir)
    try:
        if action == "PREPARE":
            prepare(GIT_BASE, proof_dir=proof_dir)
        elif action == "FINALIZE":
            finalize(proof_dir=proof_dir, close_proof=False)
        else:
            raise InvalidProof("action de contre-exemple inconnue")
    except InvalidProof as error:
        return {
            "counterexample_id": counterexample_id,
            "action": action,
            "mutated_object_sha256": mutated_object_sha256,
            "structural_register_entry_count": len(entries),
            "structural_register_tail_sha256": entries[-1]["entry_sha256"],
            "observed_exception": type(error).__name__,
            "observed_error": str(error),
            "terminal_state_returned": False,
            "state": "REJECTED_AS_REQUIRED",
        }
    raise InvalidProof(f"contre-exemple accepté: {counterexample_id}")


def exercise_counterexamples() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    with TemporaryDirectory() as temporary_directory:
        proof_dir = Path(temporary_directory) / "suffix"
        prepare(GIT_BASE, proof_dir=proof_dir)
        mutated = _append_unexpected_suffix(proof_dir)
        cases.append(
            _observed_refusal("CE-SEMANTIC-SUFFIX", proof_dir, mutated, "PREPARE")
        )
    with TemporaryDirectory() as temporary_directory:
        proof_dir = Path(temporary_directory) / "automatic"
        prepare(GIT_BASE, proof_dir=proof_dir)
        mutated = _rewrite_rehashed_payload(
            proof_dir, 0, "automatic_result", "HARNESS_ERROR"
        )
        cases.append(
            _observed_refusal("CE-AUTOMATIC-PAYLOAD", proof_dir, mutated, "PREPARE")
        )
    with TemporaryDirectory() as temporary_directory:
        proof_dir = Path(temporary_directory) / "human"
        prepare(GIT_BASE, proof_dir=proof_dir)
        _populate_final_prefix(proof_dir)
        mutated = _rewrite_rehashed_payload(proof_dir, 16, "state", "FAIL")
        cases.append(
            _observed_refusal("CE-HUMAN-PAYLOAD", proof_dir, mutated, "FINALIZE")
        )
    return {
        "schema_version": "u025/p2-manual-v3-counterexamples/v1",
        "proof_id": PROOF_ID,
        "cases": cases,
        "case_count": 3,
        "all_rejected": all(case["state"] == "REJECTED_AS_REQUIRED" for case in cases),
    }


def _resume_evidence_value(proof_dir: Path) -> dict[str, Any]:
    events = _resume_events(proof_dir)
    return {
        "schema_version": "u025/p2-manual-v3-resume-evidence/v1",
        "proof_id": PROOF_ID,
        "events_sha256": digest((proof_dir / "resume-events.jsonl").read_bytes()),
        "prepare_interruption_proven": any(
            event["action"] == "INTERRUPT_AFTER_RECEIPT_BOUNDARY"
            and event["stage"] == "PREPARE"
            for event in events
        ),
        "prepare_resume_proven": any(
            event["action"] == "RESUME_AT_FIRST_INCOMPLETE"
            and event["stage"] == "PREPARE"
            for event in events
        ),
        "finalize_interruption_proven": any(
            event["action"] == "INTERRUPT_AFTER_RECEIPT_BOUNDARY"
            and event["stage"] == "HUMAN"
            for event in events
        ),
        "finalize_resume_proven": any(
            event["action"] == "RESUME_AT_FIRST_INCOMPLETE"
            and event["stage"] == "HUMAN"
            for event in events
        ),
    }


def _report_value() -> dict[str, Any]:
    source = read_json(V2_PROOF / "report.json")
    return {
        "schema_version": "u025/p2-manual-v3-report/v1",
        "proof_id": PROOF_ID,
        "source_v2_report_sha256": digest((V2_PROOF / "report.json").read_bytes()),
        "source_v2_root_sha256": V2_ROOT_SHA256,
        "source_v1_root_sha256": V1_ROOT_SHA256,
        "case_count": source["case_count"],
        "counts": source["counts"],
        "decidable_denominator": source["decidable_denominator"],
        "coverage": source["coverage"],
        "official_acceptance_rate": source["official_acceptance_rate"],
        "automatic_results": source["automatic_results"],
        "human_verdicts": source["human_verdicts"],
        "candidate_calls": 0,
        "provider_attempt_count": 0,
        "supplier_spend_total": "0",
        "conclusion": "INCONNU",
        "unknowns": source["unknowns"],
    }


def _effort_value() -> dict[str, Any]:
    source = read_json(V2_PROOF / "effort-register.json")
    facts = source.get("facts")
    if not isinstance(facts, list) or len(facts) != 14:
        raise InvalidProof("faits d’effort V2 divergents")
    return {
        "schema_version": "u025/p2-manual-v3-effort/v1",
        "proof_id": PROOF_ID,
        "source_v2_effort_sha256": digest(
            (V2_PROOF / "effort-register.json").read_bytes()
        ),
        "fact_count": 14,
        "facts": facts,
    }


def _manifest_value(proof_dir: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    file_names = [
        "procedure.md",
        "source-manifest.json",
        "proof-lock.json",
        "network-audit.jsonl",
        "evidence-register.jsonl",
        "resume-events.jsonl",
        "counterexample-results.json",
        "resume-evidence.json",
        "report.json",
        "effort-register.json",
    ]
    return {
        "schema_version": "u025/p2-manual-v3-evidence-manifest/v1",
        "proof_id": PROOF_ID,
        "files": {
            name: digest((proof_dir / name).read_bytes()) for name in file_names
        },
        "artifacts": [entry["object_sha256"] for entry in entries],
        "artifact_count": len(entries),
    }


def _write_closure_objects(proof_dir: Path, entries: list[dict[str, Any]]) -> None:
    resume_path = proof_dir / "resume-events.jsonl"
    if not resume_path.exists():
        write_new(resume_path, b"")
    _resume_events(proof_dir)
    write_or_match(proof_dir / "counterexample-results.json", canonical(exercise_counterexamples()))
    write_or_match(proof_dir / "resume-evidence.json", canonical(_resume_evidence_value(proof_dir)))
    write_or_match(proof_dir / "report.json", canonical(_report_value()))
    write_or_match(proof_dir / "effort-register.json", canonical(_effort_value()))
    manifest = _manifest_value(proof_dir, entries)
    write_or_match(proof_dir / "evidence-manifest.json", canonical(manifest))
    root_base = {
        "schema_version": "u025/p2-manual-v3-proof-root/v1",
        "proof_id": PROOF_ID,
        "source_v2_root_sha256": V2_ROOT_SHA256,
        "source_v2_byte_fingerprint": V2_BYTE_FINGERPRINT,
        "source_v1_root_sha256": V1_ROOT_SHA256,
        "source_v1_byte_fingerprint": V1_BYTE_FINGERPRINT,
        "source_manifest_sha256": digest((proof_dir / "source-manifest.json").read_bytes()),
        "proof_lock_sha256": digest((proof_dir / "proof-lock.json").read_bytes()),
        "evidence_register_sha256": digest(
            (proof_dir / "evidence-register.jsonl").read_bytes()
        ),
        "evidence_register_tail_sha256": entries[-1]["entry_sha256"],
        "counterexample_results_sha256": digest(
            (proof_dir / "counterexample-results.json").read_bytes()
        ),
        "resume_evidence_sha256": digest((proof_dir / "resume-evidence.json").read_bytes()),
        "report_sha256": digest((proof_dir / "report.json").read_bytes()),
        "effort_register_sha256": digest((proof_dir / "effort-register.json").read_bytes()),
        "evidence_manifest_sha256": digest(
            (proof_dir / "evidence-manifest.json").read_bytes()
        ),
        "verdict": "PASS_PR55_V3_LOCAL_PROOF",
    }
    root = {**root_base, "root_sha256": digest(canonical(root_base))}
    write_or_match(proof_dir / "proof-root.json", canonical(root))
    state = {
        "schema_version": "u025/p2-manual-v3-final-state/v1",
        "proof_id": PROOF_ID,
        "prepare_receipts": 16,
        "human_receipts": 12,
        "final_receipts": 16,
        "register_entry_count": 44,
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "root_sha256": root["root_sha256"],
        "verdict": "PASS_PR55_V3_LOCAL_PROOF",
    }
    write_or_match(proof_dir / "final-state.json", canonical(state))
    closure = """---
style_gate: pass
---

# Fermeture P2 manuelle V3

Verdict binaire : `PASS_PR55_V3_LOCAL_PROOF`.

Les reprises de `prepare` et `finalize` conservent les reçus sémantiquement exacts et refusent les trois contre-exemples rehashés. V1 et V2 restent byte-identiques.

Le rapport P2 conserve la conclusion `INCONNU`, sans appel candidat, tentative fournisseur ou dépense.
"""
    write_or_match(proof_dir / "closure.md", closure.encode())


def prepare(
    git_base: str,
    *,
    proof_dir: Path = PROOF,
    interrupt_after_receipts: int | None = None,
) -> dict[str, Any]:
    _bootstrap(proof_dir, git_base)
    sources = _source_receipts()
    entries = _verify_register(proof_dir)
    _validate_semantic_prefix(proof_dir, entries, sources)
    if len(entries) >= 16:
        return {"proof_id": PROOF_ID, "state": "PREPARED", "prepare_receipts": 16}
    if entries:
        _append_resume_event(
            proof_dir,
            "RESUME_AT_FIRST_INCOMPLETE",
            "PREPARE",
            len(entries),
        )
    for source in sources[len(entries) : 16]:
        _append_receipt(proof_dir, source, entries)
        entries = _verify_register(proof_dir)
        _validate_semantic_prefix(proof_dir, entries, sources)
        if interrupt_after_receipts is not None and len(entries) >= interrupt_after_receipts:
            _append_resume_event(
                proof_dir,
                "INTERRUPT_AFTER_RECEIPT_BOUNDARY",
                "PREPARE",
                len(entries),
            )
            return {
                "proof_id": PROOF_ID,
                "state": "INTERRUPTED",
                "prepare_receipts": len(entries),
            }
    return {"proof_id": PROOF_ID, "state": "PREPARED", "prepare_receipts": 16}


def finalize(
    *,
    proof_dir: Path = PROOF,
    interrupt_after_human_receipts: int | None = None,
    close_proof: bool = True,
) -> dict[str, Any]:
    _bootstrap(proof_dir, GIT_BASE)
    sources = _source_receipts()
    entries = _verify_register(proof_dir)
    _validate_semantic_prefix(proof_dir, entries, sources)
    if len(entries) < 16:
        raise InvalidProof("préfixe prepare V3 incomplet")
    human_count = min(max(len(entries) - 16, 0), 12)
    if 0 < human_count < 12:
        _append_resume_event(
            proof_dir,
            "RESUME_AT_FIRST_INCOMPLETE",
            "HUMAN",
            human_count,
        )
    for source in sources[len(entries) :]:
        _append_receipt(proof_dir, source, entries)
        entries = _verify_register(proof_dir)
        _validate_semantic_prefix(proof_dir, entries, sources)
        human_count = min(max(len(entries) - 16, 0), 12)
        if (
            interrupt_after_human_receipts is not None
            and human_count >= interrupt_after_human_receipts
            and len(entries) <= 28
        ):
            _append_resume_event(
                proof_dir,
                "INTERRUPT_AFTER_RECEIPT_BOUNDARY",
                "HUMAN",
                human_count,
            )
            return {
                "proof_id": PROOF_ID,
                "state": "INTERRUPTED",
                "human_receipts": human_count,
                "final_receipts": 0,
            }
    if close_proof:
        _write_closure_objects(proof_dir, entries)
    return {
        "proof_id": PROOF_ID,
        "state": "FINALIZED",
        "prepare_receipts": 16,
        "human_receipts": 12,
        "final_receipts": 16,
    }


def verify(proof_dir: Path = PROOF) -> dict[str, Any]:
    verify_sources()
    source_bytes = canonical(_source_manifest())
    if (proof_dir / "source-manifest.json").read_bytes() != source_bytes:
        raise InvalidProof("manifeste source V3 divergent")
    expected_lock = canonical(_lock(GIT_BASE, digest(source_bytes)))
    if (proof_dir / "proof-lock.json").read_bytes() != expected_lock:
        raise InvalidProof("lock V3 divergent")
    if (proof_dir / "procedure.md").read_bytes() != PROCEDURE.read_bytes():
        raise InvalidProof("procédure V3 divergente")
    network_lines = (proof_dir / "network-audit.jsonl").read_bytes().splitlines()
    if len(network_lines) != 1:
        raise InvalidProof("preuve réseau V3 dupliquée")
    network = json.loads(network_lines[0])
    if (
        network.get("state") != "PASS"
        or network.get("source_network_audit_sha256") != V2_NETWORK_AUDIT_SHA256
        or network.get("second_self_test_executed") is not False
    ):
        raise InvalidProof("preuve réseau V3 divergente")
    sources = _source_receipts()
    entries = _verify_register(proof_dir)
    if len(entries) != 44:
        raise InvalidProof("nombre de reçus V3 divergent")
    _validate_semantic_prefix(proof_dir, entries, sources)
    stage_counts = {
        stage: sum(entry["stage"] == stage for entry in entries)
        for stage in ("PREPARE", "HUMAN", "FINAL")
    }
    if stage_counts != {"PREPARE": 16, "HUMAN": 12, "FINAL": 16}:
        raise InvalidProof("répartition des reçus V3 divergente")
    final_results: dict[str, int] = {}
    for entry in entries[28:]:
        receipt = read_json(proof_dir / "artifacts" / entry["object_sha256"])
        result = receipt["payload"]["observed"]["result"]
        final_results[result] = final_results.get(result, 0) + 1
    final_results["PROVIDER_FAILURE"] = 0
    report = read_json(proof_dir / "report.json")
    if report != _report_value():
        raise InvalidProof("rapport V3 divergent")
    if report["counts"] != final_results:
        raise InvalidProof("rapport V3 non reproductible depuis les reçus")
    expected_report = {
        "case_count": 16,
        "decidable_denominator": 14,
        "coverage": "14/16",
        "official_acceptance_rate": "1/14",
        "candidate_calls": 0,
        "provider_attempt_count": 0,
        "supplier_spend_total": "0",
        "conclusion": "INCONNU",
    }
    if any(report.get(key) != value for key, value in expected_report.items()):
        raise InvalidProof("agrégat P2 V3 divergent")
    effort = read_json(proof_dir / "effort-register.json")
    if effort != _effort_value() or effort.get("fact_count") != 14:
        raise InvalidProof("registre d’effort V3 divergent")
    events = _resume_events(proof_dir)
    required_events = {
        ("INTERRUPT_AFTER_RECEIPT_BOUNDARY", "PREPARE"),
        ("RESUME_AT_FIRST_INCOMPLETE", "PREPARE"),
        ("INTERRUPT_AFTER_RECEIPT_BOUNDARY", "HUMAN"),
        ("RESUME_AT_FIRST_INCOMPLETE", "HUMAN"),
    }
    if not required_events.issubset(
        {(event["action"], event["stage"]) for event in events}
    ):
        raise InvalidProof("chemins de reprise V3 non prouvés")
    for stage in ("PREPARE", "HUMAN"):
        interrupted = next(
            event
            for event in events
            if event["action"] == "INTERRUPT_AFTER_RECEIPT_BOUNDARY"
            and event["stage"] == stage
        )
        resumed = next(
            event
            for event in events
            if event["action"] == "RESUME_AT_FIRST_INCOMPLETE"
            and event["stage"] == stage
        )
        for field in (
            "completed_receipts",
            "closed_register_entry_count",
            "closed_register_tail_sha256",
            "closed_receipt_tail_sha256",
            "closed_object_sha256s",
        ):
            if interrupted[field] != resumed[field]:
                raise InvalidProof(f"reçu fermé rejoué pendant la reprise {stage}")
    resume_evidence = read_json(proof_dir / "resume-evidence.json")
    if resume_evidence != _resume_evidence_value(proof_dir):
        raise InvalidProof("preuve de reprise V3 divergente")
    if not all(
        resume_evidence.get(field) is True
        for field in (
            "prepare_interruption_proven",
            "prepare_resume_proven",
            "finalize_interruption_proven",
            "finalize_resume_proven",
        )
    ):
        raise InvalidProof("reprise V3 incomplètement prouvée")
    counterexamples = read_json(proof_dir / "counterexample-results.json")
    observed_counterexamples = exercise_counterexamples()
    if counterexamples != observed_counterexamples:
        raise InvalidProof("contre-exemples V3 non reproductibles")
    if counterexamples.get("case_count") != 3 or counterexamples.get("all_rejected") is not True:
        raise InvalidProof("refus sémantiques V3 incomplets")
    manifest = read_json(proof_dir / "evidence-manifest.json")
    if manifest != _manifest_value(proof_dir, entries):
        raise InvalidProof("manifeste V3 divergent")
    root = read_json(proof_dir / "proof-root.json")
    root_base = {key: value for key, value in root.items() if key != "root_sha256"}
    if digest(canonical(root_base)) != root.get("root_sha256"):
        raise InvalidProof("racine V3 divergente")
    root_links = {
        "source_v2_root_sha256": V2_ROOT_SHA256,
        "source_v2_byte_fingerprint": V2_BYTE_FINGERPRINT,
        "source_v1_root_sha256": V1_ROOT_SHA256,
        "source_v1_byte_fingerprint": V1_BYTE_FINGERPRINT,
        "source_manifest_sha256": digest((proof_dir / "source-manifest.json").read_bytes()),
        "proof_lock_sha256": digest((proof_dir / "proof-lock.json").read_bytes()),
        "evidence_register_sha256": digest(
            (proof_dir / "evidence-register.jsonl").read_bytes()
        ),
        "evidence_register_tail_sha256": entries[-1]["entry_sha256"],
        "counterexample_results_sha256": digest(
            (proof_dir / "counterexample-results.json").read_bytes()
        ),
        "resume_evidence_sha256": digest((proof_dir / "resume-evidence.json").read_bytes()),
        "report_sha256": digest((proof_dir / "report.json").read_bytes()),
        "effort_register_sha256": digest((proof_dir / "effort-register.json").read_bytes()),
        "evidence_manifest_sha256": digest(
            (proof_dir / "evidence-manifest.json").read_bytes()
        ),
        "verdict": "PASS_PR55_V3_LOCAL_PROOF",
    }
    if any(root.get(key) != value for key, value in root_links.items()):
        raise InvalidProof("lien de racine V3 divergent")
    final_state = read_json(proof_dir / "final-state.json")
    expected_state = {
        "schema_version": "u025/p2-manual-v3-final-state/v1",
        "proof_id": PROOF_ID,
        "prepare_receipts": 16,
        "human_receipts": 12,
        "final_receipts": 16,
        "register_entry_count": 44,
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "root_sha256": root["root_sha256"],
        "verdict": "PASS_PR55_V3_LOCAL_PROOF",
    }
    if final_state != expected_state:
        raise InvalidProof("état final V3 divergent")
    if "PASS_PR55_V3_LOCAL_PROOF" not in (proof_dir / "closure.md").read_text():
        raise InvalidProof("fermeture binaire V3 absente")
    secret_markers = (b"sk-", b"BEGIN PRIVATE KEY", b"api_key", b"access_token")
    for path in proof_dir.rglob("*"):
        if path.is_file() and any(marker in path.read_bytes() for marker in secret_markers):
            raise InvalidProof(f"secret potentiel détecté: {path.relative_to(ROOT)}")
    return {
        "proof_id": PROOF_ID,
        "verdict": "PASS",
        "root_sha256": root["root_sha256"],
        "source_v2_root_sha256": V2_ROOT_SHA256,
        "source_v2_byte_fingerprint": V2_BYTE_FINGERPRINT,
        "source_v1_root_sha256": V1_ROOT_SHA256,
        "source_v1_byte_fingerprint": V1_BYTE_FINGERPRINT,
        "prepare_receipts": 16,
        "human_receipts": 12,
        "final_receipts": 16,
        "register_entries": 44,
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "counterexamples_rejected": 3,
        "candidate_calls": 0,
        "provider_attempt_count": 0,
        "supplier_spend_total": "0",
        "conclusion": "INCONNU",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--git-base", required=True)
    prepare_parser.add_argument("--interrupt-after-receipts", type=int)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--interrupt-after-human-receipts", type=int)
    subparsers.add_parser("verify")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(
                args.git_base,
                interrupt_after_receipts=args.interrupt_after_receipts,
            )
        elif args.command == "finalize":
            result = finalize(
                interrupt_after_human_receipts=args.interrupt_after_human_receipts
            )
        elif args.command == "verify":
            result = verify()
        else:
            raise InvalidProof("commande inconnue")
    except InvalidProof as error:
        print(
            json.dumps(
                {"verdict": "HOLD_PR55_V3_CORRECTION", "error": str(error)},
                ensure_ascii=False,
            )
        )
        raise SystemExit(1) from error
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
