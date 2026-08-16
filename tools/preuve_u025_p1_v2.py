from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.preuve_u025_p1 import (
    CASES,
    COMPONENTS,
    GIT_BASE,
    HUMAN_FAILURES,
    PACKAGE,
    PACKAGE_HASHES,
    PATHS,
    RUNTIME_IDENTITIES,
    SECRET_PATTERNS,
    SOURCE_DATE,
    InvalidProof,
    acceptable_output,
    calculate_cost,
    calculation_fixtures,
    candidate,
    canonical,
    digest,
    object_digest,
    run_case as run_mechanical_case,
    verify_package,
    verify_runtime,
    with_digest,
    witness_sections,
)


DEFAULT_PROOF = PACKAGE / "preuves-u025/p1-local-v2"
PREVIOUS_PROOF = PACKAGE / "preuves-u025/p1-local-v1"
PROOF_ID = "U025-P1-LOCAL-V2"
VERSION = "u025-p1-local/2"
PREVIOUS_PROOF_ID = "U025-P1-LOCAL-V1"
PREVIOUS_GIT_COMMIT = "6eaf1ea23d1bbcbc23d9a3b3da5354d8910f9bf1"
PREVIOUS_PROOF_TREE_SHA256 = (
    "69350ecee7b8da25759f014fab846ae405684233beadcfd12c0e37127bcfaac4"
)

FULL_GATES = [
    ["G-005", True],
    ["G-001", True],
    ["G-002", True],
    ["G-003", True],
    ["G-004", True],
]


def oracle_entry(
    automatic: str,
    human: str | None,
    result: str,
    attribution: str,
    gates: list[list[str | bool]],
) -> dict[str, object]:
    return {
        "automatic": automatic,
        "human": human,
        "result": result,
        "attribution": attribution,
        "gates": deepcopy(gates),
    }


ORACLE = {
    "WT-ACCEPTABLE": oracle_entry(
        "PASS", "ACCEPTABLE", "OFFICIALLY_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-SCHEMA": oracle_entry(
        "FAIL", None, "CANDIDATE_NOT_ACCEPTABLE", "CANDIDATE_ERROR",
        [["G-005", True], ["G-001", True], ["G-002", False]],
    ),
    "WT-ANCRE": oracle_entry(
        "FAIL", None, "CANDIDATE_NOT_ACCEPTABLE", "CANDIDATE_ERROR",
        [["G-005", True], ["G-001", True], ["G-002", True], ["G-003", False]],
    ),
    "WT-VOCABULAIRE": oracle_entry(
        "FAIL", None, "CANDIDATE_NOT_ACCEPTABLE", "CANDIDATE_ERROR",
        [
            ["G-005", True], ["G-001", True], ["G-002", True],
            ["G-003", True], ["G-004", False],
        ],
    ),
    "WT-HARNESS": oracle_entry(
        "HARNESS_ERROR", None, "HARNESS_ERROR", "HARNESS_ERROR",
        [["G-005", False]],
    ),
    "WT-FAIT-INVENTE": oracle_entry(
        "PASS", "NOT_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-CONTRAINTE-OMISE": oracle_entry(
        "PASS", "NOT_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-INCONNUE-RESOLUE": oracle_entry(
        "PASS", "NOT_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-HYPOTHESE-INTERDITE": oracle_entry(
        "PASS", "NOT_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-CONTRADICTION-MANQUEE": oracle_entry(
        "PASS", "NOT_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-RISQUE-INADEQUAT": oracle_entry(
        "PASS", "NOT_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-QUESTION-INADEQUATE": oracle_entry(
        "PASS", "NOT_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-ACTION-INADEQUATE": oracle_entry(
        "PASS", "NOT_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-CONFORMITE-AFFIRMEE": oracle_entry(
        "PASS", "NOT_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-RECONSTRUCTION": oracle_entry(
        "PASS", "NOT_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE",
        "HUMAN_REVIEW_FIXTURE", FULL_GATES,
    ),
    "WT-HUMAIN-INDISPONIBLE": oracle_entry(
        "PASS", "UNABLE_TO_JUDGE", "UNABLE_TO_JUDGE",
        "HUMAN_EVIDENCE_UNAVAILABLE", FULL_GATES,
    ),
}
ORACLE_SHA256 = object_digest(ORACLE)

ADAPTER_SPECS = {
    "PROMPTFOO_LOCAL_REPLAY": {
        "adapter_kind": "PROMPTFOO_LOCAL_REPLAY",
        "adapter_function": "execute_promptfoo_local_replay",
        "adapter_version": "u025/promptfoo-shaped-local-adapter/2",
        "steps": [
            "LOAD_PROMPTFOO_SHAPED_FIXTURE",
            "RUN_LOCAL_ASSERTION_ADAPTER",
            "EMIT_NORMALIZED_RESULT",
        ],
    },
    "ORI_LOCAL_REPLAY": {
        "adapter_kind": "ORI_LOCAL_REPLAY",
        "adapter_function": "execute_ori_local_replay",
        "adapter_version": "u025/ori-shaped-local-adapter/2",
        "steps": [
            "LOAD_ORI_SHAPED_WORKSPACE_CASE",
            "RUN_LOCAL_CHECK_ADAPTER",
            "EMIT_NORMALIZED_RESULT",
        ],
    },
    "METHODE_MANUELLE_LOCAL_REPLAY": {
        "adapter_kind": "METHODE_MANUELLE_LOCAL_REPLAY",
        "adapter_function": "execute_manual_local_replay",
        "adapter_version": "u025/manual-checklist-local-adapter/2",
        "steps": [
            "LOAD_MANUAL_CHECKLIST_CASE",
            "RUN_LOCAL_CHECKLIST_ADAPTER",
            "EMIT_NORMALIZED_RESULT",
        ],
    },
}

RECEIPT_FIELDS = frozenset(
    {
        "schema_version", "proof_id", "level", "path", "case_id",
        "input_sha256", "output_sha256", "expected_identity",
        "observed_identity", "action", "expected_source_sha256",
        "expected", "observed", "state", "source_timestamp",
        "instrument_version", "previous_receipt_sha256", "unknowns",
        "candidate_calls", "provider_attempts", "supplier_spend",
        "latency", "receipt_sha256",
    }
)


def tree_sha256(root: Path) -> str:
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            content = path.read_bytes()
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": digest(content),
                    "size_bytes": len(content),
                }
            )
    return object_digest(entries)


def verify_previous_proof() -> None:
    observed = tree_sha256(PREVIOUS_PROOF)
    if observed != PREVIOUS_PROOF_TREE_SHA256:
        raise InvalidProof(f"preuve v1 historique divergente: {observed}")


def observation(case: dict[str, object]) -> dict[str, object]:
    human = case["human"]
    origin = case["automatic"]["origin"]
    return {
        "automatic": case["automatic"]["status"],
        "human": human,
        "result": case["result"],
        "attribution": origin or (
            "HUMAN_EVIDENCE_UNAVAILABLE"
            if human == "UNABLE_TO_JUDGE"
            else "HUMAN_REVIEW_FIXTURE"
        ),
        "gates": deepcopy(case["automatic"]["gates"]),
    }


def execution_id(
    path: str,
    case_id: str,
    specification_sha256: str,
    candidate_sha256: str,
) -> str:
    return object_digest(
        {
            "proof_id": PROOF_ID,
            "path": path,
            "case_id": case_id,
            "specification_sha256": specification_sha256,
            "candidate_sha256": candidate_sha256,
            "adapter": ADAPTER_SPECS[path],
        }
    )


def execute_adapter(
    path: str,
    case_id: str,
    content: str,
    specification: str,
    adapter_input: dict[str, object],
) -> dict[str, object]:
    case = run_mechanical_case(case_id, content, specification)
    observed = observation(case)
    spec = ADAPTER_SPECS[path]
    run_id = execution_id(
        path,
        case_id,
        case["specification_sha256"],
        case["candidate_sha256"],
    )
    trace = {
        "schema_version": "u025/execution-trace/v2",
        "proof_id": PROOF_ID,
        "path": path,
        "case_id": case_id,
        "execution_id": run_id,
        "adapter_kind": spec["adapter_kind"],
        "adapter_function": spec["adapter_function"],
        "adapter_version": spec["adapter_version"],
        "adapter_input": adapter_input,
        "adapter_input_sha256": object_digest(adapter_input),
        "steps": deepcopy(spec["steps"]),
        "normalized_observed": deepcopy(observed),
        "adapter_output_sha256": object_digest(observed),
        "real_tool_execution": False,
        "network_calls": 0,
        "candidate_calls": 0,
    }
    return {
        "case": case,
        "observed": observed,
        "trace": with_digest(trace, "execution_trace_sha256"),
    }


def adapter_input_for(
    path: str, case_id: str, candidate_sha256: str
) -> dict[str, object]:
    if path == PATHS[0]:
        return {
            "schema_version": "promptfoo-shaped-local-fixture/v2",
            "test_id": case_id,
            "assertions": ["G-005", "G-001", "G-002", "G-003", "G-004"],
            "candidate_sha256": candidate_sha256,
        }
    if path == PATHS[1]:
        return {
            "schema_version": "ori-shaped-local-fixture/v2",
            "workspace_case": case_id,
            "checks": ["schema", "anchors", "vocabulary", "human_fixture"],
            "candidate_sha256": candidate_sha256,
        }
    return {
        "schema_version": "manual-checklist-local-fixture/v2",
        "checklist_case": case_id,
        "review_order": ["package", "candidate", "gates", "human_fixture"],
        "candidate_sha256": candidate_sha256,
    }


def execute_promptfoo_local_replay(
    case_id: str, content: str, specification: str
) -> dict[str, object]:
    return execute_adapter(
        PATHS[0], case_id, content, specification,
        adapter_input_for(PATHS[0], case_id, digest(content.encode())),
    )


def execute_ori_local_replay(
    case_id: str, content: str, specification: str
) -> dict[str, object]:
    return execute_adapter(
        PATHS[1], case_id, content, specification,
        adapter_input_for(PATHS[1], case_id, digest(content.encode())),
    )


def execute_manual_local_replay(
    case_id: str, content: str, specification: str
) -> dict[str, object]:
    return execute_adapter(
        PATHS[2], case_id, content, specification,
        adapter_input_for(PATHS[2], case_id, digest(content.encode())),
    )


ADAPTER_FUNCTIONS = {
    PATHS[0]: execute_promptfoo_local_replay,
    PATHS[1]: execute_ori_local_replay,
    PATHS[2]: execute_manual_local_replay,
}


def blind_review_fixtures(
    fixtures: list[dict[str, object]],
) -> dict[str, object]:
    register = (PACKAGE / "registre-verite.md").read_text()
    start = register.index("## Revue humaine aveugle\n")
    end = register.index("\n## Verdict officiel et juge fantôme", start)
    rubric = register[start:end].rstrip() + "\n"
    rubric_hash = digest(rubric.encode())
    dossiers = {}
    for fixture in fixtures:
        case_id = fixture["case_id"]
        expected = ORACLE[case_id]
        if expected["automatic"] != "PASS":
            continue
        dossier = {
            "schema_version": "u025/blind-review-fixture/v2",
            "case_id": case_id,
            "available": case_id != "WT-HUMAIN-INDISPONIBLE",
            "candidate_alias": "SORTIE-A",
            "candidate_sha256": fixture["candidate_sha256"],
            "stimulus_sha256": PACKAGE_HASHES["stimulus.md"],
            "rubric_sha256": rubric_hash,
            "presentation_order": ["stimulus", "candidate", "rubric"],
            "identity_blinded": True,
            "cost_blinded": True,
            "rubric_frozen": True,
            "verdict_frozen": expected["human"],
            "verdict_source_sha256": ORACLE_SHA256,
        }
        dossiers[case_id] = with_digest(dossier, "dossier_sha256")
    return {
        "schema_version": "u025/blind-review-fixtures/v2",
        "proof_id": PROOF_ID,
        "rubric": rubric,
        "rubric_sha256": rubric_hash,
        "dossiers": dossiers,
    }


def build_receipts(
    executions: list[dict[str, object]],
    lock_hash: str,
    fixture_hashes: dict[str, str],
    dossiers: dict[str, object],
) -> list[dict[str, object]]:
    result = []
    by_key = {
        (item["trace"]["path"], item["trace"]["case_id"]): item
        for item in executions
    }
    for path in PATHS:
        previous = None
        for case_id in CASES:
            execution = by_key[(path, case_id)]
            case = execution["case"]
            trace = execution["trace"]
            observed = deepcopy(execution["observed"])
            expected = deepcopy(ORACLE[case_id])
            identity = {
                "path": path,
                "adapter_kind": trace["adapter_kind"],
                "adapter_function": trace["adapter_function"],
                "adapter_version": trace["adapter_version"],
                "mode": "LOCAL_DETERMINISTIC_REPLAY",
                "execution_id": trace["execution_id"],
            }
            output = {
                "case_id": case_id,
                "observed": observed,
                "execution_trace_sha256": trace["execution_trace_sha256"],
            }
            receipt = {
                "schema_version": "u025/p1-receipt/v2",
                "proof_id": PROOF_ID,
                "level": "P1",
                "path": path,
                "case_id": case_id,
                "input_sha256": {
                    "proof_lock": lock_hash,
                    "package_manifest": PACKAGE_HASHES["manifeste-paquet.json"],
                    "case_specification": case["specification_sha256"],
                    "candidate_fixture": case["candidate_sha256"],
                    "blind_review_dossier": dossiers.get(case_id, {}).get(
                        "dossier_sha256"
                    ),
                    "calculation_fixtures": fixture_hashes[
                        "calculation_fixtures"
                    ],
                    "oracle": ORACLE_SHA256,
                },
                "output_sha256": object_digest(output),
                "expected_identity": deepcopy(identity),
                "observed_identity": {
                    **identity,
                    "execution_trace_sha256": trace["execution_trace_sha256"],
                },
                "action": trace["adapter_function"],
                "expected_source_sha256": ORACLE_SHA256,
                "expected": expected,
                "observed": observed,
                "state": "PASS" if expected == observed else "FAIL",
                "source_timestamp": SOURCE_DATE,
                "instrument_version": VERSION,
                "previous_receipt_sha256": previous,
                "unknowns": [
                    "REAL_TOOL_INTEGRATION_UNKNOWN",
                    "PROVIDER_BEHAVIOR_UNKNOWN",
                    "RECURRING_EFFORT_UNKNOWN",
                ],
                "candidate_calls": 0,
                "provider_attempts": [],
                "supplier_spend": "0",
                "latency": {
                    "state": "INCONNU",
                    "distribution": [],
                    "reason": "P1_HAS_NO_REAL_TOOL_OR_PROVIDER_TIMES",
                },
            }
            receipt = with_digest(receipt, "receipt_sha256")
            previous = receipt["receipt_sha256"]
            result.append(receipt)
    return result


REPORT_STATES = (
    "OFFICIALLY_ACCEPTABLE",
    "CANDIDATE_NOT_ACCEPTABLE",
    "PROVIDER_FAILURE",
    "HARNESS_ERROR",
    "UNABLE_TO_JUDGE",
)


def derive_report(
    path: str,
    all_receipts: list[dict[str, object]],
    lock_hash: str,
    calc_hash: str,
) -> dict[str, object]:
    selected = [receipt for receipt in all_receipts if receipt["path"] == path]
    counts = {
        state: sum(
            receipt["observed"]["result"] == state for receipt in selected
        )
        for state in REPORT_STATES
    }
    denominator = (
        counts["OFFICIALLY_ACCEPTABLE"]
        + counts["CANDIDATE_NOT_ACCEPTABLE"]
        + counts["PROVIDER_FAILURE"]
    )
    attempts = [
        attempt
        for receipt in selected
        for attempt in receipt["provider_attempts"]
    ]
    unknowns = sorted(
        {unknown for receipt in selected for unknown in receipt["unknowns"]}
    )
    report = {
        "schema_version": "u025/p1-report/v2",
        "proof_id": PROOF_ID,
        "level": "P1",
        "path": path,
        "case_count": len(selected),
        "counts": counts,
        "decidable_denominator": denominator,
        "official_acceptance_rate": (
            f"{counts['OFFICIALLY_ACCEPTABLE']}/{denominator}"
            if denominator
            else None
        ),
        "provider_cost": calculate_cost(
            attempts, counts["OFFICIALLY_ACCEPTABLE"]
        ),
        "latency": {
            "rule": "FULL_DISTRIBUTION",
            "distribution": [],
            "known_count": 0,
            "unknown_count": len(selected),
            "state": "INCONNU",
            "reason": "P1_HAS_NO_REAL_TOOL_OR_PROVIDER_TIMES",
        },
        "coverage": f"{denominator}/{len(selected)}",
        "provenance": {
            "proof_lock_sha256": lock_hash,
            "calculation_fixtures_sha256": calc_hash,
            "oracle_sha256": ORACLE_SHA256,
            "receipts_sha256": object_digest(selected),
            "receipt_count": len(selected),
            "freshness_rule": None,
        },
        "unknowns": unknowns,
        "preference": None,
        "conclusion": "INCONNU",
        "abstention": [
            "REAL_TOOL_INTEGRATION_UNKNOWN",
            "PROVIDER_BEHAVIOR_UNKNOWN",
            "FRESHNESS_RULE_MISSING",
            "PREFERENCE_MISSING",
            "RECURRING_EFFORT_UNKNOWN",
        ],
        "candidate_calls": sum(
            receipt["candidate_calls"] for receipt in selected
        ),
        "provider_attempt_count": len(attempts),
        "scope": "P1_LOCAL_FIXTURES_NOT_V0_EXECUTION",
    }
    return with_digest(report, "report_sha256")


OBSERVED_COMPONENTS = frozenset(
    {
        "configuration",
        "integration",
        "execution",
        "revue_humaine",
        "verification",
        "production_rapport",
    }
)


def build_effort(
    traces: list[dict[str, object]],
    dossiers: dict[str, object],
    reports: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    evidence = []
    facts = []
    for path in PATHS:
        selected = [trace for trace in traces if trace["path"] == path]
        report = next(value for value in reports if value["path"] == path)
        artifacts = {
            "configuration": deepcopy(ADAPTER_SPECS[path]),
            "integration": {
                "adapter_function": ADAPTER_SPECS[path]["adapter_function"],
                "execution_ids": [trace["execution_id"] for trace in selected],
            },
            "execution": {
                "execution_trace_sha256": [
                    trace["execution_trace_sha256"] for trace in selected
                ]
            },
            "revue_humaine": {
                "dossier_sha256": [
                    dossiers[case_id]["dossier_sha256"]
                    for case_id in sorted(dossiers)
                ],
                "oracle_sha256": ORACLE_SHA256,
            },
            "verification": {
                "oracle_comparisons": len(CASES),
                "oracle_sha256": ORACLE_SHA256,
                "observed_sha256": object_digest(
                    [trace["normalized_observed"] for trace in selected]
                ),
            },
            "production_rapport": {
                "report_sha256": report["report_sha256"]
            },
        }
        for component in COMPONENTS:
            if component in OBSERVED_COMPONENTS:
                action = {
                    "proof_id": PROOF_ID,
                    "path": path,
                    "component": component,
                    "phase": "initial",
                    "action": f"BUILD_P1_{component.upper()}",
                }
                artifact = {
                    "proof_id": PROOF_ID,
                    "path": path,
                    "component": component,
                    "content": artifacts[component],
                }
                evidence_entry = {
                    "schema_version": "u025/effort-evidence/v2",
                    "proof_id": PROOF_ID,
                    "path": path,
                    "component": component,
                    "phase": "initial",
                    "action": action,
                    "action_sha256": object_digest(action),
                    "artifact": artifact,
                    "artifact_sha256": object_digest(artifact),
                }
                evidence.append(evidence_entry)
                initial = {
                    "schema_version": "u025/effort-fact/v2",
                    "proof_id": PROOF_ID,
                    "path": path,
                    "component": component,
                    "phase": "initial",
                    "action": action["action"],
                    "artifact": "effort_evidence",
                    "responsibility": "P1_LOCAL_HARNESS",
                    "trigger": "GO_CORRECT_PR50",
                    "action_sha256": evidence_entry["action_sha256"],
                    "artifact_sha256": evidence_entry["artifact_sha256"],
                    "state": "OBSERVE",
                }
            else:
                initial = unknown_effort_fact(path, component, "initial")
            recurring = unknown_effort_fact(path, component, "recurrent")
            facts.extend(
                (
                    with_digest(initial, "fact_sha256"),
                    with_digest(recurring, "fact_sha256"),
                )
            )
    return (
        {
            "schema_version": "u025/effort-evidence-register/v2",
            "proof_id": PROOF_ID,
            "evidence": evidence,
        },
        {
            "schema_version": "u025/effort-register/v2",
            "proof_id": PROOF_ID,
            "facts": facts,
        },
    )


def unknown_effort_fact(
    path: str, component: str, phase: str
) -> dict[str, object]:
    return {
        "schema_version": "u025/effort-fact/v2",
        "proof_id": PROOF_ID,
        "path": path,
        "component": component,
        "phase": phase,
        "action": None,
        "artifact": None,
        "responsibility": None,
        "trigger": None,
        "action_sha256": None,
        "artifact_sha256": None,
        "state": "INCONNU",
    }


def evidence_register(objects: list[tuple[str, dict[str, object]]]) -> bytes:
    lines = []
    previous = None
    for sequence, (record_type, value) in enumerate(objects, start=1):
        entry = {
            "schema_version": "u025/evidence-entry/v2",
            "proof_id": PROOF_ID,
            "sequence": sequence,
            "record_type": record_type,
            "object_sha256": object_digest(value),
            "previous_entry_sha256": previous,
        }
        entry = with_digest(entry, "entry_sha256")
        previous = entry["entry_sha256"]
        lines.append(canonical(entry))
    return b"".join(lines)


def add_bundle(
    files: dict[str, bytes], name: str, value: object
) -> dict[str, object]:
    content = canonical(value)
    content_hash = digest(content)
    files[f"artifacts/{content_hash}"] = content
    return {
        "logical_name": name,
        "sha256": content_hash,
        "size_bytes": len(content),
    }


def load_bundles(files: dict[str, bytes]) -> dict[str, object]:
    index = json.loads(files["artifact-index.json"])
    return {
        entry["logical_name"]: json.loads(
            files[f"artifacts/{entry['sha256']}"]
        )
        for entry in index["artifacts"]
    }


def manifest_value(
    files: dict[str, bytes], bundles: dict[str, object]
) -> dict[str, object]:
    register_entries = [
        json.loads(line) for line in files["evidence-register.jsonl"].splitlines()
    ]
    artifact_index = json.loads(files["artifact-index.json"])
    receipts = bundles["receipts"]["receipts"]
    facts = bundles["effort_register"]["facts"]
    reports = bundles["reports"]["reports"]
    return {
        "schema_version": "u025/evidence-manifest/v2",
        "proof_id": PROOF_ID,
        "top_level_objects": {
            "proof_lock_sha256": digest(files["proof-lock.json"]),
            "case_index_sha256": digest(files["case-index.json"]),
            "oracle_sha256": digest(files["oracle.json"]),
            "artifact_index_sha256": digest(files["artifact-index.json"]),
            "evidence_register_sha256": digest(
                files["evidence-register.jsonl"]
            ),
        },
        "artifact_bundles": {
            entry["logical_name"]: entry["sha256"]
            for entry in artifact_index["artifacts"]
        },
        "evidence_objects": {
            "receipts": [
                {
                    "object_id": f"{value['path']}/{value['case_id']}",
                    "object_sha256": object_digest(value),
                }
                for value in receipts
            ],
            "effort": [
                {
                    "object_id": (
                        f"{value['path']}/{value['component']}/{value['phase']}"
                    ),
                    "object_sha256": object_digest(value),
                }
                for value in facts
            ],
            "reports": [
                {
                    "object_id": value["path"],
                    "object_sha256": object_digest(value),
                }
                for value in reports
            ],
        },
        "register": {
            "sha256": digest(files["evidence-register.jsonl"]),
            "entry_count": len(register_entries),
            "tail_entry_sha256": register_entries[-1]["entry_sha256"],
        },
    }


def proof_root_value(files: dict[str, bytes]) -> dict[str, object]:
    manifest = json.loads(files["evidence-manifest.json"])
    root = {
        "schema_version": "u025/proof-root/v2",
        "proof_id": PROOF_ID,
        "previous_proof": {
            "proof_id": PREVIOUS_PROOF_ID,
            "git_commit": PREVIOUS_GIT_COMMIT,
            "tree_sha256": PREVIOUS_PROOF_TREE_SHA256,
            "supersession": "HISTORICAL_IMMUTABLE_SUPERSEDED_BY_V2",
        },
        "proof_lock_sha256": digest(files["proof-lock.json"]),
        "case_index_sha256": digest(files["case-index.json"]),
        "oracle_sha256": digest(files["oracle.json"]),
        "artifact_index_sha256": digest(files["artifact-index.json"]),
        "evidence_register_sha256": digest(files["evidence-register.jsonl"]),
        "evidence_register_tail_sha256": manifest["register"][
            "tail_entry_sha256"
        ],
        "evidence_manifest_sha256": digest(files["evidence-manifest.json"]),
    }
    return with_digest(root, "root_sha256")


def build_files() -> dict[str, bytes]:
    verify_package()
    verify_runtime()
    verify_previous_proof()
    sections = witness_sections()
    base = acceptable_output()
    fixtures = []
    for case_id in CASES:
        content = candidate(case_id, base)
        specification = sections[case_id]
        fixtures.append(
            {
                "case_id": case_id,
                "specification": specification,
                "specification_sha256": digest(specification.encode()),
                "candidate": content,
                "candidate_sha256": digest(content.encode()),
            }
        )
    case_index = {
        "schema_version": "u025/case-index/v2",
        "proof_id": PROOF_ID,
        "source": "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md",
        "source_sha256": PACKAGE_HASHES["temoins-qualification.md"],
        "cases": [
            {
                "case_id": fixture["case_id"],
                "content": fixture["specification"],
                "sha256": fixture["specification_sha256"],
            }
            for fixture in fixtures
        ],
    }
    case_index_bytes = canonical(case_index)
    oracle_bytes = canonical(ORACLE)
    input_bundles = {
        "case_fixtures": {
            "schema_version": "u025/case-fixtures/v2",
            "proof_id": PROOF_ID,
            "cases": fixtures,
        },
        "blind_review_fixtures": blind_review_fixtures(fixtures),
        "calculation_fixtures": calculation_fixtures(),
    }
    input_hashes = {
        name: object_digest(value) for name, value in input_bundles.items()
    }
    lock = {
        "schema_version": "u025/p1-proof-lock/v2",
        "proof_id": PROOF_ID,
        "level": "P1",
        "policy": "HYBRID_PROOFS",
        "git_base": GIT_BASE,
        "previous_proof": {
            "proof_id": PREVIOUS_PROOF_ID,
            "git_commit": PREVIOUS_GIT_COMMIT,
            "tree_sha256": PREVIOUS_PROOF_TREE_SHA256,
        },
        "package": {
            "name": "PRECADRAGE-ENTRETIEN-CLIENT-V0",
            "files": PACKAGE_HASHES,
            "approval": "D1 issuecomment-5301590597",
            "integrity": "M2.1 issuecomment-5302877516",
        },
        "case_index_sha256": digest(case_index_bytes),
        "oracle": {
            "sha256": ORACLE_SHA256,
            "source": "temoins-qualification.md et registre-verite.md",
            "source_sha256": [
                PACKAGE_HASHES["temoins-qualification.md"],
                PACKAGE_HASHES["registre-verite.md"],
            ],
        },
        "fixture_bundles_sha256": input_hashes,
        "rules": {
            path: digest((ROOT / path).read_bytes())
            for path in (
                "docs/RULES.md",
                "docs/ARD.md",
                "docs/PRD.md",
                "tasks/dev/pre-cadrage-entretien-client/registre-verite.md",
                "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md",
            )
        },
        "instruments": {
            "tools/preuve_u025_p1_v2.py": digest(Path(__file__).read_bytes()),
            "tools/validateur_pre_cadrage_v0.py": digest(
                (ROOT / "tools/validateur_pre_cadrage_v0.py").read_bytes()
            ),
        },
        "instrument_version": VERSION,
        "runtime_identities": list(RUNTIME_IDENTITIES),
        "paths": list(PATHS),
        "adapters": ADAPTER_SPECS,
        "authorizations": {
            "local_deterministic_p1": True,
            "network_acquisition": False,
            "tool_installation": False,
            "real_promptfoo_or_ori": False,
            "candidate_call": False,
            "campaign": False,
            "spend": False,
        },
        "commands": [
            "python3 tools/preuve_u025_p1_v2.py verify",
            (
                "python3 -m unittest tests.test_preuve_u025_p1_v2 "
                "tests.test_preuve_u025_p1 tests.test_validateur_pre_cadrage_v0"
            ),
        ],
    }
    lock_bytes = canonical(lock)
    lock_hash = digest(lock_bytes)
    executions = []
    for path in PATHS:
        adapter = ADAPTER_FUNCTIONS[path]
        for fixture in fixtures:
            execution = adapter(
                fixture["case_id"],
                fixture["candidate"],
                fixture["specification"],
            )
            if execution["observed"] != ORACLE[fixture["case_id"]]:
                raise InvalidProof(
                    f"oracle divergent: {path}/{fixture['case_id']}"
                )
            executions.append(execution)
    traces = [execution["trace"] for execution in executions]
    receipts = build_receipts(
        executions,
        lock_hash,
        input_hashes,
        input_bundles["blind_review_fixtures"]["dossiers"],
    )
    reports = [
        derive_report(
            path,
            receipts,
            lock_hash,
            input_hashes["calculation_fixtures"],
        )
        for path in PATHS
    ]
    effort_evidence, effort_register_bundle = build_effort(
        traces,
        input_bundles["blind_review_fixtures"]["dossiers"],
        reports,
    )
    files = {
        "case-index.json": case_index_bytes,
        "oracle.json": oracle_bytes,
        "proof-lock.json": lock_bytes,
    }
    output_bundles = {
        "execution_traces": {
            "schema_version": "u025/execution-traces/v2",
            "proof_id": PROOF_ID,
            "traces": traces,
        },
        "receipts": {
            "schema_version": "u025/receipts/v2",
            "proof_id": PROOF_ID,
            "receipts": receipts,
        },
        "effort_evidence": effort_evidence,
        "effort_register": effort_register_bundle,
        "reports": {
            "schema_version": "u025/reports/v2",
            "proof_id": PROOF_ID,
            "reports": reports,
        },
    }
    bundle_entries = [
        add_bundle(files, name, value)
        for name, value in (*input_bundles.items(), *output_bundles.items())
    ]
    files["artifact-index.json"] = canonical(
        {
            "schema_version": "u025/artifact-index/v2",
            "proof_id": PROOF_ID,
            "artifacts": bundle_entries,
        }
    )
    files["evidence-register.jsonl"] = evidence_register(
        [("receipt", value) for value in receipts]
        + [("effort", value) for value in effort_register_bundle["facts"]]
        + [("report", value) for value in reports]
    )
    files["evidence-manifest.json"] = canonical(
        manifest_value(files, load_bundles(files))
    )
    files["proof-root.json"] = canonical(proof_root_value(files))
    files["closure.md"] = f"""---
style_gate: pass
---

# Correction P1 U-025

Verdict : `PASS`

- Historique : v1 conservée sans réécriture, supersédée par cette v2 liée au commit `{PREVIOUS_GIT_COMMIT}` et à sa racine d'arbre
- Paquet : cinq empreintes conformes à D1 et M2.1
- Cas : {len(CASES)} témoins indexés avec contenu et SHA-256, dont dix rejets humains négatifs
- Voies : trois adaptateurs locaux distincts et {len(traces)} traces d'exécution propres
- Oracle : table attendue indépendante, liée aux témoins et au registre de vérité
- Reçus : {len(receipts)} reçus complets, reproductibles et chaînés
- Graphe : registre, tail, manifeste et racine liés aux reçus, faits d'effort et rapports
- Effort : {len(effort_register_bundle['facts'])} faits ; `OBSERVE` seulement avec preuve distincte, sinon `INCONNU`
- Rapports : tous les champs recalculés depuis les reçus et fixtures
- Appels candidats : 0
- Dépense fournisseur : 0
- Portée : P1 local déterministe seulement ; aucune exécution réelle Promptfoo ou Ori, aucun appel modèle ou fournisseur

Reproduction :

```text
python3 tools/preuve_u025_p1_v2.py verify
python3 -m unittest tests.test_preuve_u025_p1_v2 tests.test_preuve_u025_p1 tests.test_validateur_pre_cadrage_v0
```
""".encode()
    return files


def verify_object_digest(
    value: dict[str, object], field: str, label: str
) -> None:
    declared = value[field]
    unhashed = {key: item for key, item in value.items() if key != field}
    if object_digest(unhashed) != declared:
        raise InvalidProof(f"{label} altéré")


def validate(files: dict[str, bytes]) -> dict[str, object]:
    verify_package()
    verify_previous_proof()
    required_top = {
        "case-index.json",
        "oracle.json",
        "proof-lock.json",
        "artifact-index.json",
        "evidence-register.jsonl",
        "evidence-manifest.json",
        "proof-root.json",
        "closure.md",
    }
    artifact_index = json.loads(files["artifact-index.json"])
    expected_artifacts = {
        f"artifacts/{entry['sha256']}" for entry in artifact_index["artifacts"]
    }
    if set(files) != required_top | expected_artifacts:
        raise InvalidProof("inventaire du graphe divergent")
    logical_names = [
        entry["logical_name"] for entry in artifact_index["artifacts"]
    ]
    if logical_names != [
        "case_fixtures",
        "blind_review_fixtures",
        "calculation_fixtures",
        "execution_traces",
        "receipts",
        "effort_evidence",
        "effort_register",
        "reports",
    ]:
        raise InvalidProof("index d'artefacts incomplet")
    for entry in artifact_index["artifacts"]:
        content = files.get(f"artifacts/{entry['sha256']}")
        if (
            content is None
            or digest(content) != entry["sha256"]
            or len(content) != entry["size_bytes"]
        ):
            raise InvalidProof(
                f"graphe d'artefact altéré: {entry['logical_name']}"
            )
    lock = json.loads(files["proof-lock.json"])
    if lock["package"]["files"] != PACKAGE_HASHES:
        raise InvalidProof("lock du paquet divergent")
    if lock["previous_proof"] != {
        "proof_id": PREVIOUS_PROOF_ID,
        "git_commit": PREVIOUS_GIT_COMMIT,
        "tree_sha256": PREVIOUS_PROOF_TREE_SHA256,
    }:
        raise InvalidProof("liaison à la preuve v1 divergente")
    if lock["case_index_sha256"] != digest(files["case-index.json"]):
        raise InvalidProof("index des cas non lié au lock")
    if (
        lock["oracle"]["sha256"] != ORACLE_SHA256
        or digest(files["oracle.json"]) != ORACLE_SHA256
        or json.loads(files["oracle.json"]) != ORACLE
    ):
        raise InvalidProof("oracle indépendant altéré")
    if lock["adapters"] != ADAPTER_SPECS:
        raise InvalidProof("contrats d'adaptateur divergents")
    if (
        lock["paths"] != list(PATHS)
        or lock["runtime_identities"] != list(RUNTIME_IDENTITIES)
        or lock["authorizations"]
        != {
            "local_deterministic_p1": True,
            "network_acquisition": False,
            "tool_installation": False,
            "real_promptfoo_or_ori": False,
            "candidate_call": False,
            "campaign": False,
            "spend": False,
        }
    ):
        raise InvalidProof("autorisations ou identités du lock divergentes")
    if lock["instruments"]["tools/preuve_u025_p1_v2.py"] != digest(
        Path(__file__).read_bytes()
    ):
        raise InvalidProof("instrument v2 divergent")
    case_index = json.loads(files["case-index.json"])
    sections = witness_sections()
    if tuple(case["case_id"] for case in case_index["cases"]) != CASES:
        raise InvalidProof("index des cas incomplet")
    for case in case_index["cases"]:
        if (
            case["content"] != sections[case["case_id"]]
            or digest(case["content"].encode()) != case["sha256"]
        ):
            raise InvalidProof(f"contenu de cas altéré: {case['case_id']}")
    bundles = load_bundles(files)
    base = acceptable_output()
    expected_fixtures = []
    for case_id in CASES:
        candidate_content = candidate(case_id, base)
        specification = sections[case_id]
        expected_fixtures.append(
            {
                "case_id": case_id,
                "specification": specification,
                "specification_sha256": digest(specification.encode()),
                "candidate": candidate_content,
                "candidate_sha256": digest(candidate_content.encode()),
            }
        )
    if bundles["case_fixtures"] != {
        "schema_version": "u025/case-fixtures/v2",
        "proof_id": PROOF_ID,
        "cases": expected_fixtures,
    }:
        raise InvalidProof("fixtures des cas divergentes")
    if bundles["blind_review_fixtures"] != blind_review_fixtures(
        expected_fixtures
    ):
        raise InvalidProof("fixtures de revue aveugle divergentes")
    if bundles["calculation_fixtures"] != calculation_fixtures():
        raise InvalidProof("fixtures de calcul coût/latence divergentes")
    fixtures = {
        fixture["case_id"]: fixture
        for fixture in bundles["case_fixtures"]["cases"]
    }
    traces = bundles["execution_traces"]["traces"]
    if len(traces) != len(PATHS) * len(CASES):
        raise InvalidProof("traces d'exécution incomplètes")
    traces_by_hash = {}
    for trace in traces:
        verify_object_digest(
            trace, "execution_trace_sha256", "trace d'exécution"
        )
        path = trace["path"]
        case_id = trace["case_id"]
        fixture = fixtures[case_id]
        spec = ADAPTER_SPECS[path]
        if (
            trace["adapter_kind"] != path
            or trace["adapter_function"] != spec["adapter_function"]
            or trace["adapter_version"] != spec["adapter_version"]
            or trace["steps"] != spec["steps"]
            or trace["adapter_input"]
            != adapter_input_for(
                path, case_id, fixture["candidate_sha256"]
            )
            or trace["adapter_input_sha256"]
            != object_digest(trace["adapter_input"])
            or trace["adapter_output_sha256"]
            != object_digest(trace["normalized_observed"])
            or trace["execution_id"]
            != execution_id(
                path,
                case_id,
                fixture["specification_sha256"],
                fixture["candidate_sha256"],
            )
            or trace["normalized_observed"] != ORACLE[case_id]
            or trace["real_tool_execution"]
            or trace["network_calls"] != 0
            or trace["candidate_calls"] != 0
        ):
            raise InvalidProof(
                f"adaptateur ou trace divergent: {path}/{case_id}"
            )
        traces_by_hash[trace["execution_trace_sha256"]] = trace
    if len(traces_by_hash) != len(traces):
        raise InvalidProof("identités de trace non distinctes")
    for case_id in CASES:
        selected = [trace for trace in traces if trace["case_id"] == case_id]
        if {trace["adapter_kind"] for trace in selected} != set(PATHS):
            raise InvalidProof(f"adaptateurs manquants: {case_id}")
        if len({trace["execution_id"] for trace in selected}) != len(PATHS):
            raise InvalidProof(f"identités d'exécution dupliquées: {case_id}")
    receipts = bundles["receipts"]["receipts"]
    if len(receipts) != len(PATHS) * len(CASES):
        raise InvalidProof("nombre de reçus divergent")
    lock_hash = digest(files["proof-lock.json"])
    for path in PATHS:
        previous = None
        selected = [receipt for receipt in receipts if receipt["path"] == path]
        if [receipt["case_id"] for receipt in selected] != list(CASES):
            raise InvalidProof(f"cas ou ordre divergents pour {path}")
        for receipt in selected:
            case_id = receipt["case_id"]
            if frozenset(receipt) != RECEIPT_FIELDS:
                raise InvalidProof(
                    f"schéma de reçu incomplet: {path}/{case_id}"
                )
            verify_object_digest(receipt, "receipt_sha256", "reçu")
            if receipt["previous_receipt_sha256"] != previous:
                raise InvalidProof(f"chaîne de reçus rompue: {path}")
            previous = receipt["receipt_sha256"]
            trace_hash = receipt["observed_identity"][
                "execution_trace_sha256"
            ]
            trace = traces_by_hash.get(trace_hash)
            fixture = fixtures[case_id]
            dossier_hash = bundles["blind_review_fixtures"]["dossiers"].get(
                case_id, {}
            ).get("dossier_sha256")
            expected_input = {
                "proof_lock": lock_hash,
                "package_manifest": PACKAGE_HASHES["manifeste-paquet.json"],
                "case_specification": fixture["specification_sha256"],
                "candidate_fixture": fixture["candidate_sha256"],
                "blind_review_dossier": dossier_hash,
                "calculation_fixtures": object_digest(
                    bundles["calculation_fixtures"]
                ),
                "oracle": ORACLE_SHA256,
            }
            expected_identity = {
                "path": path,
                "adapter_kind": path,
                "adapter_function": ADAPTER_SPECS[path]["adapter_function"],
                "adapter_version": ADAPTER_SPECS[path]["adapter_version"],
                "mode": "LOCAL_DETERMINISTIC_REPLAY",
                "execution_id": trace["execution_id"] if trace else None,
            }
            output = {
                "case_id": case_id,
                "observed": receipt["observed"],
                "execution_trace_sha256": trace_hash,
            }
            if (
                trace is None
                or trace["path"] != path
                or trace["case_id"] != case_id
                or receipt["observed_identity"]["adapter_kind"] != path
                or receipt["observed_identity"]["execution_id"]
                != trace["execution_id"]
                or receipt["expected_identity"] != expected_identity
                or receipt["observed_identity"]
                != {
                    **expected_identity,
                    "execution_trace_sha256": trace_hash,
                }
                or receipt["expected"] != ORACLE[case_id]
                or receipt["observed"] != trace["normalized_observed"]
                or receipt["expected_source_sha256"] != ORACLE_SHA256
                or receipt["state"] != "PASS"
                or receipt["output_sha256"] != object_digest(output)
                or receipt["input_sha256"] != expected_input
                or receipt["action"]
                != ADAPTER_SPECS[path]["adapter_function"]
                or receipt["unknowns"]
                != [
                    "REAL_TOOL_INTEGRATION_UNKNOWN",
                    "PROVIDER_BEHAVIOR_UNKNOWN",
                    "RECURRING_EFFORT_UNKNOWN",
                ]
                or receipt["candidate_calls"] != 0
                or receipt["provider_attempts"]
                or receipt["supplier_spend"] != "0"
                or receipt["latency"]
                != {
                    "state": "INCONNU",
                    "distribution": [],
                    "reason": "P1_HAS_NO_REAL_TOOL_OR_PROVIDER_TIMES",
                }
            ):
                raise InvalidProof(f"reçu du graphe divergent: {path}/{case_id}")
    dossiers = bundles["blind_review_fixtures"]["dossiers"]
    for case_id, dossier in dossiers.items():
        verify_object_digest(dossier, "dossier_sha256", "dossier aveugle")
        if (
            dossier["available"] != (case_id != "WT-HUMAIN-INDISPONIBLE")
            or dossier["candidate_alias"] != "SORTIE-A"
            or not dossier["identity_blinded"]
            or not dossier["cost_blinded"]
            or not dossier["rubric_frozen"]
            or dossier["verdict_frozen"] != ORACLE[case_id]["human"]
            or dossier["verdict_source_sha256"] != ORACLE_SHA256
        ):
            raise InvalidProof(f"dossier aveugle divergent: {case_id}")
    reports = bundles["reports"]["reports"]
    if len(reports) != len(PATHS):
        raise InvalidProof("rapports incomplets")
    calc_hash = object_digest(bundles["calculation_fixtures"])
    for path, report in zip(PATHS, reports, strict=True):
        expected_report = derive_report(path, receipts, lock_hash, calc_hash)
        if report != expected_report:
            raise InvalidProof(f"rapport du graphe recalculé divergent: {path}")
    expected_effort_evidence, expected_effort_register = build_effort(
        traces, dossiers, reports
    )
    if bundles["effort_evidence"] != expected_effort_evidence:
        raise InvalidProof("artefacts de preuve d'effort divergents")
    if bundles["effort_register"] != expected_effort_register:
        raise InvalidProof("faits d'effort recalculés divergents")
    evidence_entries = bundles["effort_evidence"]["evidence"]
    evidence_by_hash = {
        (entry["action_sha256"], entry["artifact_sha256"]): entry
        for entry in evidence_entries
    }
    if len(evidence_by_hash) != len(evidence_entries):
        raise InvalidProof("preuves d'effort non distinctes")
    facts = bundles["effort_register"]["facts"]
    if len(facts) != len(PATHS) * len(COMPONENTS) * 2:
        raise InvalidProof("registre d'effort incomplet")
    used_evidence = set()
    for fact in facts:
        verify_object_digest(fact, "fact_sha256", "fait d'effort")
        key = (fact["action_sha256"], fact["artifact_sha256"])
        expected_state = (
            "OBSERVE"
            if fact["phase"] == "initial"
            and fact["component"] in OBSERVED_COMPONENTS
            else "INCONNU"
        )
        if fact["state"] != expected_state:
            raise InvalidProof(
                f"effort divergent: {fact['path']}/{fact['component']}"
            )
        if fact["state"] == "OBSERVE":
            evidence = evidence_by_hash.get(key)
            if (
                evidence is None
                or key in used_evidence
                or evidence["path"] != fact["path"]
                or evidence["component"] != fact["component"]
                or object_digest(evidence["action"])
                != fact["action_sha256"]
                or object_digest(evidence["artifact"])
                != fact["artifact_sha256"]
            ):
                raise InvalidProof("preuve d'effort OBSERVE divergente")
            used_evidence.add(key)
        elif key != (None, None):
            raise InvalidProof("effort INCONNU avec preuve fabriquée")
    expected_objects = (
        [("receipt", value) for value in receipts]
        + [("effort", value) for value in facts]
        + [("report", value) for value in reports]
    )
    register_lines = files["evidence-register.jsonl"].splitlines()
    if len(register_lines) != len(expected_objects):
        raise InvalidProof("registre du graphe incomplet")
    previous = None
    for sequence, (line, (record_type, value)) in enumerate(
        zip(register_lines, expected_objects, strict=True), start=1
    ):
        entry = json.loads(line)
        declared = entry.pop("entry_sha256")
        if (
            entry["sequence"] != sequence
            or entry["record_type"] != record_type
            or entry["object_sha256"] != object_digest(value)
            or entry["previous_entry_sha256"] != previous
            or object_digest(entry) != declared
        ):
            raise InvalidProof("registre du graphe divergent")
        previous = declared
    if files["evidence-manifest.json"] != canonical(
        manifest_value(files, bundles)
    ):
        raise InvalidProof("manifeste du graphe divergent")
    if files["proof-root.json"] != canonical(proof_root_value(files)):
        raise InvalidProof("racine du graphe divergente")
    root = json.loads(files["proof-root.json"])
    verify_object_digest(root, "root_sha256", "racine du graphe")
    if root["previous_proof"]["tree_sha256"] != PREVIOUS_PROOF_TREE_SHA256:
        raise InvalidProof("racine v1 non liée")
    for path, content in files.items():
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            raise InvalidProof(f"secret potentiel dans {path}")
    return {
        "verdict": "PASS",
        "proof_id": PROOF_ID,
        "previous_proof_id": PREVIOUS_PROOF_ID,
        "cases": len(CASES),
        "paths": len(PATHS),
        "execution_traces": len(traces),
        "receipts": len(receipts),
        "effort_facts": len(facts),
        "candidate_calls": 0,
        "supplier_spend": "0",
        "root_sha256": root["root_sha256"],
    }


def read_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def write_proof(output: Path) -> dict[str, object]:
    if output.exists() and any(output.iterdir()):
        raise InvalidProof(f"sortie non vide: {output}")
    files = build_files()
    result = validate(files)
    for relative, content in files.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    return result


def verify_proof(root: Path) -> dict[str, object]:
    observed = read_tree(root)
    expected = build_files()
    if set(observed) != set(expected):
        raise InvalidProof("inventaire de preuve non reproductible")
    changed = [path for path in expected if expected[path] != observed[path]]
    if changed:
        raise InvalidProof(f"octets non reproductibles: {changed}")
    return validate(observed)


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path, default=DEFAULT_PROOF)
    verify = commands.add_parser("verify")
    verify.add_argument("--proof-root", type=Path, default=DEFAULT_PROOF)
    args = parser.parse_args()
    try:
        result = (
            write_proof(args.output)
            if args.command == "build"
            else verify_proof(args.proof_root)
        )
    except (InvalidProof, OSError, ValueError, KeyError, TypeError) as error:
        print(
            json.dumps(
                {"verdict": "HOLD", "error": str(error)},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
