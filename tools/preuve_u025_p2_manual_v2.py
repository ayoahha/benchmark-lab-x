#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p2-manual-v2"
V1_PROOF = ROOT / "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p2-manual-v1"
PROCEDURE = PROOF / "procedure.md"
TEST_FILE = ROOT / "tests/test_preuve_u025_p2_manual_v2.py"
PROOF_ID = "U025-P2-MANUAL-V2"
GIT_BASE = "b47f86124c2c4dfd5faa10db71311fc13f1ef5bb"
V1_ROOT_SHA256 = "c031c405b059fd9f9eca0219892066bbc3c1f9e62457537f60c6c34f7d3b2e72"
V1_LOCK_SHA256 = "6199bf92d58fff21e2f471a60b4675ecfe55844ff81a5a4310ab57ebd0c9f621"
V1_REGISTER_SHA256 = "c65c3df32bd9dca07bd1c1edb72fef7e9d3e5fbaa64b95e2ffa1634ee928d2b1"
V1_REGISTER_TAIL_SHA256 = "5d204a158101fb3fa5cd1b5addd3067c771facd736476a2984753cc72c794f47"
V1_REVIEW_INDEX_SHA256 = "43a9ef76f8ec495c2e735991cbdaa0f2012b89942ae1c4556cd4f7bf637284a1"
V1_HUMAN_INPUT_SHA256 = "909ed2eb07a04d6a906c7b824845000567a66fb2a5275215c1868df5ba2df7c8"
V1_NETWORK_AUDIT_SHA256 = "9f4a3340464b149b1acf176f694b49c9ed3ae9595faaada6ae75fa9fbfea456b"
V1_BYTE_FINGERPRINT = "b00e7dc0049d6a9b3e49098495918300161cf96c714bc9ac53e0849066072c39"


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
        raise InvalidProof(f"objet JSON non dictionnaire: {path}")
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


def _v1_protected_paths() -> list[Path]:
    return [
        ROOT / "tools/preuve_u025_p2_manual.py",
        ROOT / "tests/test_preuve_u025_p2_manual.py",
        *sorted(path for path in V1_PROOF.rglob("*") if path.is_file()),
    ]


def v1_byte_fingerprint() -> str:
    lines = bytearray()
    for path in _v1_protected_paths():
        relative = path.relative_to(ROOT).as_posix()
        lines.extend(f"{digest(path.read_bytes())}  {relative}\n".encode())
    return digest(bytes(lines))


def _require_digest(path: Path, expected: str) -> None:
    observed = digest(path.read_bytes()) if path.is_file() else None
    if observed != expected:
        raise InvalidProof(
            f"empreinte divergente: {path.relative_to(ROOT)} attendu={expected} observé={observed}"
        )


def verify_v1() -> dict[str, Any]:
    observed_fingerprint = v1_byte_fingerprint()
    if observed_fingerprint != V1_BYTE_FINGERPRINT:
        raise InvalidProof(
            f"octets V1 divergents: attendu={V1_BYTE_FINGERPRINT} observé={observed_fingerprint}"
        )
    _require_digest(V1_PROOF / "proof-lock.json", V1_LOCK_SHA256)
    _require_digest(V1_PROOF / "evidence-register.jsonl", V1_REGISTER_SHA256)
    _require_digest(V1_PROOF / "review/index.json", V1_REVIEW_INDEX_SHA256)
    _require_digest(V1_PROOF / "human-input.json", V1_HUMAN_INPUT_SHA256)
    _require_digest(V1_PROOF / "network-audit.jsonl", V1_NETWORK_AUDIT_SHA256)
    root = read_json(V1_PROOF / "proof-root.json")
    if root.get("root_sha256") != V1_ROOT_SHA256:
        raise InvalidProof("racine V1 divergente")
    if root.get("evidence_register_tail_sha256") != V1_REGISTER_TAIL_SHA256:
        raise InvalidProof("tail V1 divergent")
    review = read_json(V1_PROOF / "review/index.json")
    dossiers = review.get("dossiers")
    if not isinstance(dossiers, list) or len(dossiers) != 11:
        raise InvalidProof("inventaire des dossiers V1 divergent")
    for dossier in dossiers:
        rendered_path = ROOT / dossier["rendered_path"]
        _require_digest(rendered_path, dossier["rendered_sha256"])
        _require_digest(
            V1_PROOF / "artifacts" / dossier["dossier_sha256"],
            dossier["dossier_sha256"],
        )
    human_input = read_json(V1_PROOF / "human-input.json")
    if human_input.get("manual_reviewer") != "AYO":
        raise InvalidProof("relecteur humain V1 divergent")
    if human_input.get("owner_decision") != "APPROUVE_REVUE_HUMAINE_M3_11":
        raise InvalidProof("décision propriétaire V1 divergente")
    register = [
        json.loads(line)
        for line in (V1_PROOF / "evidence-register.jsonl").read_bytes().splitlines()
    ]
    logical_sequences = {entry["logical_name"]: entry["sequence"] for entry in register}
    if logical_sequences.get("human_input") != 61:
        raise InvalidProof("frontière de gel humain V1 divergente")
    if any(
        logical_sequences.get(f"blind_dossier/D-{index:03d}") != 48 + index
        for index in range(1, 12)
    ):
        raise InvalidProof("ordre des dossiers aveugles V1 divergent")
    if min(
        entry["sequence"]
        for entry in register
        if entry["logical_name"].startswith("receipt/human/")
    ) != 62:
        raise InvalidProof("révélation des correspondances V1 prématurée")
    return {
        "root": root,
        "review": review,
        "human_input": human_input,
        "logical_sequences": logical_sequences,
    }


def _source_manifest(v1: dict[str, Any]) -> dict[str, Any]:
    review = v1["review"]
    return {
        "schema_version": "u025/p2-manual-v2-source/v1",
        "proof_id": PROOF_ID,
        "v1": {
            "proof_id": "U025-P2-MANUAL-V1",
            "root_sha256": V1_ROOT_SHA256,
            "lock_sha256": V1_LOCK_SHA256,
            "register_sha256": V1_REGISTER_SHA256,
            "register_tail_sha256": V1_REGISTER_TAIL_SHA256,
            "review_index_sha256": V1_REVIEW_INDEX_SHA256,
            "human_input_sha256": V1_HUMAN_INPUT_SHA256,
            "byte_fingerprint": V1_BYTE_FINGERPRINT,
            "network_audit_sha256": V1_NETWORK_AUDIT_SHA256,
        },
        "blind_review_reuse": {
            "source_frozen_before_revelation": True,
            "new_blind_review_simulated": False,
            "rendered_and_content_addressed_objects_exact": True,
            "source_register_order": {
                "first_blind_dossier_sequence": 49,
                "last_unavailable_dossier_sequence": 60,
                "human_input_freeze_sequence": 61,
                "first_case_mapping_reveal_sequence": 62,
            },
            "dossiers": [
                {
                    "dossier_id": item["dossier_id"],
                    "rendered_sha256": item["rendered_sha256"],
                    "object_sha256": item["dossier_sha256"],
                }
                for item in review["dossiers"]
            ],
        },
    }


def _lock(git_base: str, source_manifest_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "u025/p2-manual-v2-lock/v1",
        "proof_id": PROOF_ID,
        "git_base": {"expected": GIT_BASE, "observed": git_base},
        "source_manifest_sha256": source_manifest_sha256,
        "instrument": {
            "path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "sha256": digest(Path(__file__).read_bytes()),
            "version": "u025-p2-manual-resume/2",
        },
        "test_contract": {
            "path": TEST_FILE.relative_to(ROOT).as_posix(),
            "sha256": digest(TEST_FILE.read_bytes()),
        },
        "procedure": {
            "path": PROCEDURE.relative_to(ROOT).as_posix(),
            "sha256": digest(PROCEDURE.read_bytes()),
        },
        "manual_reviewer": "AYO",
        "manual_method_owner": "AYO",
        "resume_policy": "VALID_PREFIX_FIRST_INCOMPLETE_NO_REPLAY",
        "network_self_test_policy": "REUSE_VALID_V1_NO_SECOND_SELF_TEST",
        "candidate_calls": 0,
        "provider_attempt_count": 0,
        "supplier_spend_total": "0",
        "write_scope": [
            "tools/preuve_u025_p2_manual_v2.py",
            "tests/test_preuve_u025_p2_manual_v2.py",
            "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p2-manual-v2/",
        ],
        "stop_condition": "STOP_BEFORE_M3_12",
    }


def _bootstrap(proof_dir: Path, git_base: str) -> dict[str, Any]:
    if git_base != GIT_BASE:
        raise InvalidProof(f"base Git divergente: {git_base}")
    v1 = verify_v1()
    write_or_match(proof_dir / "procedure.md", PROCEDURE.read_bytes())
    source = _source_manifest(v1)
    source_bytes = canonical(source)
    lock = _lock(git_base, digest(source_bytes))
    write_or_match(proof_dir / "source-manifest.json", source_bytes)
    write_or_match(proof_dir / "proof-lock.json", canonical(lock))
    network_record = {
        "schema_version": "u025/p2-manual-v2-network-proof/v1",
        "proof_id": PROOF_ID,
        "action": "REUSE_VALID_V1_NETWORK_SELF_TEST",
        "source_network_audit_sha256": V1_NETWORK_AUDIT_SHA256,
        "second_self_test_executed": False,
        "state": "PASS",
    }
    write_or_match(proof_dir / "network-audit.jsonl", canonical(network_record))
    return v1


def _register_entries(proof_dir: Path) -> list[dict[str, Any]]:
    path = proof_dir / "evidence-register.jsonl"
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_bytes().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as error:
            raise InvalidProof("registre V2 illisible") from error
        if not isinstance(entry, dict):
            raise InvalidProof("entrée de registre V2 invalide")
        entries.append(entry)
    return entries


def _verify_register(proof_dir: Path) -> list[dict[str, Any]]:
    entries = _register_entries(proof_dir)
    previous: str | None = None
    previous_receipt: str | None = None
    registered_objects: set[str] = set()
    for sequence, entry in enumerate(entries, start=1):
        base = {key: value for key, value in entry.items() if key != "entry_sha256"}
        if entry.get("sequence") != sequence:
            raise InvalidProof("séquence de registre V2 divergente")
        if entry.get("previous_entry_sha256") != previous:
            raise InvalidProof("préfixe ou tail V2 divergent")
        if digest(canonical(base)) != entry.get("entry_sha256"):
            raise InvalidProof("empreinte d’entrée V2 divergente")
        object_sha256 = entry.get("object_sha256")
        artifact = proof_dir / "artifacts" / str(object_sha256)
        _require_digest(artifact, str(object_sha256))
        receipt = read_json(artifact)
        receipt_base = {
            key: value for key, value in receipt.items() if key != "receipt_sha256"
        }
        if digest(canonical(receipt_base)) != receipt.get("receipt_sha256"):
            raise InvalidProof("empreinte de reçu V2 divergente")
        if receipt.get("previous_receipt_sha256") != previous_receipt:
            raise InvalidProof("chaîne de reçus V2 divergente")
        if entry.get("receipt_sha256") != receipt.get("receipt_sha256"):
            raise InvalidProof("lien registre-reçu V2 divergent")
        registered_objects.add(str(object_sha256))
        previous = entry["entry_sha256"]
        previous_receipt = receipt["receipt_sha256"]
    artifacts = proof_dir / "artifacts"
    observed_objects = (
        {path.name for path in artifacts.iterdir() if path.is_file()}
        if artifacts.exists()
        else set()
    )
    if observed_objects != registered_objects:
        raise InvalidProof("objet V2 orphelin ou absent")
    return entries


def _append_receipt(
    proof_dir: Path,
    stage: str,
    logical_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    entries = _verify_register(proof_dir)
    previous_receipt = entries[-1]["receipt_sha256"] if entries else None
    receipt_base = {
        "schema_version": "u025/p2-manual-v2-receipt/v1",
        "proof_id": PROOF_ID,
        "stage": stage,
        "logical_name": logical_name,
        "previous_receipt_sha256": previous_receipt,
        "candidate_calls": 0,
        "provider_attempts": 0,
        "supplier_spend": "0",
        **payload,
    }
    receipt = {**receipt_base, "receipt_sha256": digest(canonical(receipt_base))}
    receipt_bytes = canonical(receipt)
    object_sha256 = digest(receipt_bytes)
    write_new(proof_dir / "artifacts" / object_sha256, receipt_bytes)
    previous_entry = entries[-1]["entry_sha256"] if entries else None
    entry_base = {
        "sequence": len(entries) + 1,
        "proof_id": PROOF_ID,
        "stage": stage,
        "logical_name": logical_name,
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
    return receipt


def _resume_events(proof_dir: Path) -> list[dict[str, Any]]:
    path = proof_dir / "resume-events.jsonl"
    if not path.exists():
        return []
    events = [json.loads(line) for line in path.read_bytes().splitlines()]
    previous: str | None = None
    for sequence, event in enumerate(events, start=1):
        base = {key: value for key, value in event.items() if key != "event_sha256"}
        if event.get("sequence") != sequence:
            raise InvalidProof("séquence de reprise V2 divergente")
        if event.get("previous_event_sha256") != previous:
            raise InvalidProof("chaîne de reprise V2 divergente")
        if digest(canonical(base)) != event.get("event_sha256"):
            raise InvalidProof("empreinte de reprise V2 divergente")
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


def _prepare_sources() -> list[dict[str, Any]]:
    case_index = read_json(V1_PROOF / "case-index.json")
    report = read_json(V1_PROOF / "report.json")
    cases = case_index.get("cases")
    if not isinstance(cases, list) or len(cases) != 16:
        raise InvalidProof("index des cas V1 divergent")
    return [
        {
            "case_id": item["case_id"],
            "specification_sha256": item["specification_sha256"],
            "candidate_fixture_sha256": item["candidate_fixture_sha256"],
            "automatic_result": report["automatic_results"][item["case_id"]],
        }
        for item in cases
    ]


def prepare(
    git_base: str,
    *,
    proof_dir: Path = PROOF,
    interrupt_after_receipts: int | None = None,
) -> dict[str, Any]:
    _bootstrap(proof_dir, git_base)
    entries = _verify_register(proof_dir)
    if any(entry["stage"] != "PREPARE" for entry in entries):
        prepare_count = sum(entry["stage"] == "PREPARE" for entry in entries)
        if prepare_count != 16:
            raise InvalidProof("finalisation présente avant prepare complet")
        return {"proof_id": PROOF_ID, "state": "PREPARED", "prepare_receipts": 16}
    sources = _prepare_sources()
    if len(entries) > len(sources):
        raise InvalidProof("préfixe prepare V2 trop long")
    for index, entry in enumerate(entries):
        if entry["logical_name"] != f"prepare/{sources[index]['case_id']}":
            raise InvalidProof("ordre du préfixe prepare V2 divergent")
    completed = len(entries)
    if 0 < completed < len(sources):
        _append_resume_event(
            proof_dir,
            "RESUME_AT_FIRST_INCOMPLETE",
            "PREPARE",
            completed,
        )
    for source in sources[completed:]:
        _append_receipt(
            proof_dir,
            "PREPARE",
            f"prepare/{source['case_id']}",
            {"source_v1_root_sha256": V1_ROOT_SHA256, **source},
        )
        completed += 1
        if interrupt_after_receipts is not None and completed >= interrupt_after_receipts:
            _append_resume_event(
                proof_dir,
                "INTERRUPT_AFTER_RECEIPT_BOUNDARY",
                "PREPARE",
                completed,
            )
            return {
                "proof_id": PROOF_ID,
                "state": "INTERRUPTED",
                "prepare_receipts": completed,
            }
    entries = _verify_register(proof_dir)
    root = {
        "schema_version": "u025/p2-manual-v2-prepare-root/v1",
        "proof_id": PROOF_ID,
        "source_v1_root_sha256": V1_ROOT_SHA256,
        "receipt_count": 16,
        "register_entry_count": len(entries),
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "network_audit_sha256": digest((proof_dir / "network-audit.jsonl").read_bytes()),
    }
    write_or_match(proof_dir / "prepare-root.json", canonical(root))
    return {"proof_id": PROOF_ID, "state": "PREPARED", "prepare_receipts": 16}


def _v1_receipt_sources(prefix: str) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for line in (V1_PROOF / "evidence-register.jsonl").read_bytes().splitlines():
        entry = json.loads(line)
        logical_name = entry.get("logical_name", "")
        if not logical_name.startswith(prefix):
            continue
        object_sha256 = entry["object_sha256"]
        artifact = V1_PROOF / "artifacts" / object_sha256
        _require_digest(artifact, object_sha256)
        receipt = read_json(artifact)
        sources.append(
            {
                "case_id": receipt["case_id"],
                "source_object_sha256": object_sha256,
                "source_receipt_sha256": receipt["receipt_sha256"],
                "observed": receipt["observed"],
                "state": receipt["state"],
            }
        )
    return sources


def _validate_finalize_prefix(
    entries: list[dict[str, Any]],
    human_sources: list[dict[str, Any]],
    final_sources: list[dict[str, Any]],
) -> tuple[int, int]:
    if len(entries) < 16:
        raise InvalidProof("prepare V2 incomplet avant finalize")
    prepare_names = [f"prepare/{item['case_id']}" for item in _prepare_sources()]
    human_names = [f"human/{item['case_id']}" for item in human_sources]
    final_names = [f"final/{item['case_id']}" for item in final_sources]
    expected = [
        *[("PREPARE", name) for name in prepare_names],
        *[("HUMAN", name) for name in human_names],
        *[("FINAL", name) for name in final_names],
    ]
    if len(entries) > len(expected):
        raise InvalidProof("préfixe finalize V2 trop long")
    for entry, (stage, logical_name) in zip(entries, expected, strict=False):
        if (entry["stage"], entry["logical_name"]) != (stage, logical_name):
            raise InvalidProof("ordre du préfixe finalize V2 divergent")
    human_count = min(max(len(entries) - 16, 0), len(human_sources))
    final_count = max(len(entries) - 16 - len(human_sources), 0)
    return human_count, final_count


def _verify_prepare_root(proof_dir: Path, entries: list[dict[str, Any]]) -> None:
    if len(entries) < 16:
        raise InvalidProof("prepare V2 incomplet")
    observed = read_json(proof_dir / "prepare-root.json")
    expected = {
        "schema_version": "u025/p2-manual-v2-prepare-root/v1",
        "proof_id": PROOF_ID,
        "source_v1_root_sha256": V1_ROOT_SHA256,
        "receipt_count": 16,
        "register_entry_count": 16,
        "register_tail_sha256": entries[15]["entry_sha256"],
        "network_audit_sha256": digest((proof_dir / "network-audit.jsonl").read_bytes()),
    }
    if observed != expected:
        raise InvalidProof("prepare-root ou tail V2 divergent")


def _evidence_manifest_value(
    proof_dir: Path, entries: list[dict[str, Any]]
) -> dict[str, Any]:
    file_names = [
        "procedure.md",
        "source-manifest.json",
        "proof-lock.json",
        "network-audit.jsonl",
        "evidence-register.jsonl",
        "resume-events.jsonl",
        "prepare-root.json",
        "report.json",
        "effort-register.json",
        "resume-evidence.json",
    ]
    return {
        "schema_version": "u025/p2-manual-v2-evidence-manifest/v1",
        "proof_id": PROOF_ID,
        "files": {
            name: digest((proof_dir / name).read_bytes()) for name in file_names
        },
        "artifacts": [entry["object_sha256"] for entry in entries],
        "artifact_count": len(entries),
    }


def _write_closure_objects(proof_dir: Path, entries: list[dict[str, Any]]) -> None:
    source_report = read_json(V1_PROOF / "report.json")
    report = {
        "schema_version": "u025/p2-manual-v2-report/v1",
        "proof_id": PROOF_ID,
        "source_v1_report_sha256": digest((V1_PROOF / "report.json").read_bytes()),
        "source_v1_root_sha256": V1_ROOT_SHA256,
        "case_count": source_report["case_count"],
        "counts": source_report["counts"],
        "decidable_denominator": source_report["decidable_denominator"],
        "coverage": source_report["coverage"],
        "official_acceptance_rate": source_report["official_acceptance_rate"],
        "automatic_results": source_report["automatic_results"],
        "human_verdicts": source_report["human_verdicts"],
        "candidate_calls": 0,
        "provider_attempt_count": 0,
        "supplier_spend_total": "0",
        "conclusion": "INCONNU",
        "unknowns": source_report["unknowns"],
    }
    write_or_match(proof_dir / "report.json", canonical(report))
    source_effort = read_json(V1_PROOF / "effort-register.json")
    facts = source_effort.get("facts")
    if not isinstance(facts, list) or len(facts) != 14:
        raise InvalidProof("faits d’effort V1 divergents")
    effort = {
        "schema_version": "u025/p2-manual-v2-effort/v1",
        "proof_id": PROOF_ID,
        "source_v1_effort_sha256": digest((V1_PROOF / "effort-register.json").read_bytes()),
        "fact_count": 14,
        "facts": facts,
    }
    write_or_match(proof_dir / "effort-register.json", canonical(effort))
    events = _resume_events(proof_dir)
    events_path = proof_dir / "resume-events.jsonl"
    resume_evidence = {
        "schema_version": "u025/p2-manual-v2-resume-evidence/v1",
        "proof_id": PROOF_ID,
        "events_sha256": digest(events_path.read_bytes() if events_path.exists() else b""),
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
    write_or_match(proof_dir / "resume-evidence.json", canonical(resume_evidence))
    manifest = _evidence_manifest_value(proof_dir, entries)
    write_or_match(proof_dir / "evidence-manifest.json", canonical(manifest))
    root_base = {
        "schema_version": "u025/p2-manual-v2-proof-root/v1",
        "proof_id": PROOF_ID,
        "source_v1_root_sha256": V1_ROOT_SHA256,
        "source_manifest_sha256": digest((proof_dir / "source-manifest.json").read_bytes()),
        "proof_lock_sha256": digest((proof_dir / "proof-lock.json").read_bytes()),
        "evidence_register_sha256": digest((proof_dir / "evidence-register.jsonl").read_bytes()),
        "evidence_register_tail_sha256": entries[-1]["entry_sha256"],
        "report_sha256": digest((proof_dir / "report.json").read_bytes()),
        "effort_register_sha256": digest((proof_dir / "effort-register.json").read_bytes()),
        "resume_evidence_sha256": digest((proof_dir / "resume-evidence.json").read_bytes()),
        "evidence_manifest_sha256": digest(
            (proof_dir / "evidence-manifest.json").read_bytes()
        ),
        "verdict": "PASS_PR55_V2_LOCAL_PROOF",
    }
    root = {**root_base, "root_sha256": digest(canonical(root_base))}
    write_or_match(proof_dir / "proof-root.json", canonical(root))
    final_state = {
        "schema_version": "u025/p2-manual-v2-final-state/v1",
        "proof_id": PROOF_ID,
        "prepare_receipts": 16,
        "human_receipts": 12,
        "final_receipts": 16,
        "register_entry_count": len(entries),
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "root_sha256": root["root_sha256"],
        "verdict": "PASS_PR55_V2_LOCAL_PROOF",
    }
    write_or_match(proof_dir / "final-state.json", canonical(final_state))
    closure = """# Fermeture P2 manuelle V2

Verdict binaire : `PASS_PR55_V2_LOCAL_PROOF`.

La reprise de `prepare` et de `finalize` est prouvée aux frontières de reçus. La preuve V1 reste la source immuable des observations et des verdicts humains gelés. Aucun nouvel examen aveugle n’est simulé.

Conclusion méthodologique : `INCONNU`. Aucun comportement fournisseur, coût, latence, candidat réel ou dominance U-025 n’est prouvé.

Style gate: pass
"""
    write_or_match(proof_dir / "closure.md", closure.encode())


def finalize(
    human_input_path: Path,
    *,
    proof_dir: Path = PROOF,
    interrupt_after_human_receipts: int | None = None,
) -> dict[str, Any]:
    _bootstrap(proof_dir, GIT_BASE)
    if digest(human_input_path.read_bytes()) != V1_HUMAN_INPUT_SHA256:
        raise InvalidProof("human-input V1 divergent")
    if not (proof_dir / "prepare-root.json").is_file():
        raise InvalidProof("prepare-root V2 absent")
    entries = _verify_register(proof_dir)
    _verify_prepare_root(proof_dir, entries)
    human_sources = _v1_receipt_sources("receipt/human/")
    final_sources = _v1_receipt_sources("receipt/final/")
    if len(human_sources) != 12 or len(final_sources) != 16:
        raise InvalidProof("inventaire des reçus V1 divergent")
    human_count, final_count = _validate_finalize_prefix(
        entries, human_sources, final_sources
    )
    if 0 < human_count < len(human_sources):
        _append_resume_event(
            proof_dir,
            "RESUME_AT_FIRST_INCOMPLETE",
            "HUMAN",
            human_count,
        )
    for source in human_sources[human_count:]:
        _append_receipt(
            proof_dir,
            "HUMAN",
            f"human/{source['case_id']}",
            {"source_v1_root_sha256": V1_ROOT_SHA256, **source},
        )
        human_count += 1
        if (
            interrupt_after_human_receipts is not None
            and human_count >= interrupt_after_human_receipts
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
    entries = _verify_register(proof_dir)
    _, final_count = _validate_finalize_prefix(entries, human_sources, final_sources)
    if 0 < final_count < len(final_sources):
        _append_resume_event(
            proof_dir,
            "RESUME_AT_FIRST_INCOMPLETE",
            "FINAL",
            final_count,
        )
    for source in final_sources[final_count:]:
        _append_receipt(
            proof_dir,
            "FINAL",
            f"final/{source['case_id']}",
            {"source_v1_root_sha256": V1_ROOT_SHA256, **source},
        )
        final_count += 1
    entries = _verify_register(proof_dir)
    _validate_finalize_prefix(entries, human_sources, final_sources)
    _write_closure_objects(proof_dir, entries)
    return {
        "proof_id": PROOF_ID,
        "state": "FINALIZED",
        "human_receipts": 12,
        "final_receipts": 16,
    }


def verify(proof_dir: Path = PROOF) -> dict[str, Any]:
    v1 = verify_v1()
    expected_source = canonical(_source_manifest(v1))
    if (proof_dir / "source-manifest.json").read_bytes() != expected_source:
        raise InvalidProof("manifeste source V2 divergent")
    expected_lock = canonical(_lock(GIT_BASE, digest(expected_source)))
    if (proof_dir / "proof-lock.json").read_bytes() != expected_lock:
        raise InvalidProof("lock V2 divergent")
    if (proof_dir / "procedure.md").read_bytes() != PROCEDURE.read_bytes():
        raise InvalidProof("procédure V2 divergente")
    network_lines = (proof_dir / "network-audit.jsonl").read_bytes().splitlines()
    if len(network_lines) != 1:
        raise InvalidProof("preuve réseau V2 dupliquée")
    network = json.loads(network_lines[0])
    if (
        network.get("state") != "PASS"
        or network.get("source_network_audit_sha256") != V1_NETWORK_AUDIT_SHA256
        or network.get("second_self_test_executed") is not False
    ):
        raise InvalidProof("preuve réseau V2 divergente")
    entries = _verify_register(proof_dir)
    if len(entries) != 44:
        raise InvalidProof("nombre de reçus V2 divergent")
    _verify_prepare_root(proof_dir, entries)
    prepare_sources = _prepare_sources()
    human_sources = _v1_receipt_sources("receipt/human/")
    final_sources = _v1_receipt_sources("receipt/final/")
    human_count, final_count = _validate_finalize_prefix(
        entries, human_sources, final_sources
    )
    if (human_count, final_count) != (12, 16):
        raise InvalidProof("finalisation V2 incomplète")
    for entry, source in zip(entries[:16], prepare_sources, strict=True):
        receipt = read_json(proof_dir / "artifacts" / entry["object_sha256"])
        for field in (
            "case_id",
            "specification_sha256",
            "candidate_fixture_sha256",
            "automatic_result",
        ):
            if receipt.get(field) != source[field]:
                raise InvalidProof(f"source prepare V2 divergente: {source['case_id']}")
    for offset, source in enumerate(human_sources, start=16):
        receipt = read_json(proof_dir / "artifacts" / entries[offset]["object_sha256"])
        for field in (
            "case_id",
            "source_object_sha256",
            "source_receipt_sha256",
            "observed",
            "state",
        ):
            if receipt.get(field) != source[field]:
                raise InvalidProof(f"source humaine V2 divergente: {source['case_id']}")
    final_results: dict[str, int] = {}
    for offset, source in enumerate(final_sources, start=28):
        receipt = read_json(proof_dir / "artifacts" / entries[offset]["object_sha256"])
        for field in (
            "case_id",
            "source_object_sha256",
            "source_receipt_sha256",
            "observed",
            "state",
        ):
            if receipt.get(field) != source[field]:
                raise InvalidProof(f"source finale V2 divergente: {source['case_id']}")
        result = receipt["observed"]["result"]
        final_results[result] = final_results.get(result, 0) + 1
    final_results["PROVIDER_FAILURE"] = 0
    report = read_json(proof_dir / "report.json")
    if report.get("counts") != final_results:
        raise InvalidProof("rapport V2 non reproductible depuis les reçus")
    expected_report_fields = {
        "case_count": 16,
        "decidable_denominator": 14,
        "coverage": "14/16",
        "official_acceptance_rate": "1/14",
        "candidate_calls": 0,
        "provider_attempt_count": 0,
        "supplier_spend_total": "0",
        "conclusion": "INCONNU",
    }
    if any(report.get(key) != value for key, value in expected_report_fields.items()):
        raise InvalidProof("agrégat du rapport V2 divergent")
    effort = read_json(proof_dir / "effort-register.json")
    facts = effort.get("facts")
    if effort.get("fact_count") != 14 or not isinstance(facts, list) or len(facts) != 14:
        raise InvalidProof("registre d’effort V2 divergent")
    if any(
        fact["responsibility"] != "AYO"
        for fact in facts
        if fact["component"] in {"revue_humaine", "maintenance"}
    ):
        raise InvalidProof("responsabilité humaine ou méthode V2 divergente")
    events = _resume_events(proof_dir)
    required_events = {
        ("INTERRUPT_AFTER_RECEIPT_BOUNDARY", "PREPARE"),
        ("RESUME_AT_FIRST_INCOMPLETE", "PREPARE"),
        ("INTERRUPT_AFTER_RECEIPT_BOUNDARY", "HUMAN"),
        ("RESUME_AT_FIRST_INCOMPLETE", "HUMAN"),
    }
    observed_events = {(event["action"], event["stage"]) for event in events}
    if not required_events.issubset(observed_events):
        raise InvalidProof("chemins de reprise V2 non prouvés")
    for stage in ("PREPARE", "HUMAN"):
        interruption = next(
            event
            for event in events
            if event["action"] == "INTERRUPT_AFTER_RECEIPT_BOUNDARY"
            and event["stage"] == stage
        )
        resumption = next(
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
            if interruption[field] != resumption[field]:
                raise InvalidProof(f"objets fermés réécrits pendant la reprise {stage}")
    resume_evidence = read_json(proof_dir / "resume-evidence.json")
    if not all(
        resume_evidence.get(field) is True
        for field in (
            "prepare_interruption_proven",
            "prepare_resume_proven",
            "finalize_interruption_proven",
            "finalize_resume_proven",
        )
    ):
        raise InvalidProof("fermeture de reprise V2 divergente")
    expected_manifest = _evidence_manifest_value(proof_dir, entries)
    if read_json(proof_dir / "evidence-manifest.json") != expected_manifest:
        raise InvalidProof("manifeste de preuve V2 divergent")
    root = read_json(proof_dir / "proof-root.json")
    root_base = {key: value for key, value in root.items() if key != "root_sha256"}
    if digest(canonical(root_base)) != root.get("root_sha256"):
        raise InvalidProof("racine V2 divergente")
    root_links = {
        "source_v1_root_sha256": V1_ROOT_SHA256,
        "source_manifest_sha256": digest((proof_dir / "source-manifest.json").read_bytes()),
        "proof_lock_sha256": digest((proof_dir / "proof-lock.json").read_bytes()),
        "evidence_register_sha256": digest((proof_dir / "evidence-register.jsonl").read_bytes()),
        "evidence_register_tail_sha256": entries[-1]["entry_sha256"],
        "report_sha256": digest((proof_dir / "report.json").read_bytes()),
        "effort_register_sha256": digest((proof_dir / "effort-register.json").read_bytes()),
        "resume_evidence_sha256": digest((proof_dir / "resume-evidence.json").read_bytes()),
        "evidence_manifest_sha256": digest((proof_dir / "evidence-manifest.json").read_bytes()),
        "verdict": "PASS_PR55_V2_LOCAL_PROOF",
    }
    if any(root.get(key) != value for key, value in root_links.items()):
        raise InvalidProof("lien de racine V2 divergent")
    final_state = read_json(proof_dir / "final-state.json")
    expected_state = {
        "schema_version": "u025/p2-manual-v2-final-state/v1",
        "proof_id": PROOF_ID,
        "prepare_receipts": 16,
        "human_receipts": 12,
        "final_receipts": 16,
        "register_entry_count": 44,
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "root_sha256": root["root_sha256"],
        "verdict": "PASS_PR55_V2_LOCAL_PROOF",
    }
    if final_state != expected_state:
        raise InvalidProof("état final V2 divergent")
    if "PASS_PR55_V2_LOCAL_PROOF" not in (proof_dir / "closure.md").read_text():
        raise InvalidProof("fermeture binaire V2 absente")
    secret_markers = (b"sk-", b"BEGIN PRIVATE KEY", b"api_key", b"access_token")
    for path in proof_dir.rglob("*"):
        if path.is_file() and any(marker in path.read_bytes() for marker in secret_markers):
            raise InvalidProof(f"secret potentiel détecté: {path.relative_to(ROOT)}")
    return {
        "proof_id": PROOF_ID,
        "verdict": "PASS",
        "root_sha256": root["root_sha256"],
        "source_v1_root_sha256": V1_ROOT_SHA256,
        "v1_byte_fingerprint": V1_BYTE_FINGERPRINT,
        "prepare_receipts": 16,
        "human_receipts": 12,
        "final_receipts": 16,
        "register_entries": 44,
        "register_tail_sha256": entries[-1]["entry_sha256"],
        "effort_facts": 14,
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
    finalize_parser.add_argument("--human-input", type=Path, required=True)
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
                args.human_input,
                interrupt_after_human_receipts=args.interrupt_after_human_receipts,
            )
        elif args.command == "verify":
            result = verify()
        else:
            raise InvalidProof("commande inconnue")
    except InvalidProof as error:
        print(json.dumps({"verdict": "HOLD_PR55_V2_CORRECTION", "error": str(error)}, ensure_ascii=False))
        raise SystemExit(1) from error
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
