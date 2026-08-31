#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import difflib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter, process_time
from typing import Any

from tools import graph_engineering_pilot_v1 as v1


ROOT = Path(__file__).resolve().parents[1]
PILOT_ID = "graph-engineering-pilot-v2-agentic"
GIT_BASE = "73ec72f4a3a908c8dd0494ca901c68469b103f51"
OWNER = "graph-engineering-pilot-v2-single-writer"
SOURCE = ROOT / "tools" / "choisir_provider.py"
CORRECT_LINE = "        brut = min(brut, ctx - MARGE_PROMPT)"
DEFECT_LINE = "        brut = min(brut, ctx)"
ACCEPTANCE = """from choisir_provider import budget_de
assert budget_de({"max_completion_tokens": 20000, "context_length": 24000}) == 15808
assert budget_de({"max_completion_tokens": 10000, "context_length": 24000}) == 10000
assert budget_de({"context_length": 8192}) == 0
"""
CONTRACTS = {
    "D": "select-control-or-agent-route/v1",
    "S": "lock-source-and-acceptance/v1",
    "A": "verify-canonical-source/v1",
    "B": "repair-isolated-defect/v1",
    "J": "join-source-and-selected-branch/v1",
}


PilotError = v1.PilotError


def receipt_path(run_dir: Path, node: str) -> Path:
    return run_dir / "nodes" / node / "receipt.json"


def attempt_path(run_dir: Path, attempt: int) -> Path:
    return run_dir / "nodes" / "B" / "attempts" / f"{attempt}.json"


def utc_value(value: str | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PilotError("horodatage UTC invalide") from error
    if parsed.tzinfo is None:
        raise PilotError("horodatage UTC sans fuseau")
    return parsed.astimezone(timezone.utc)


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def genesis_value(
    run_id: str,
    scenario: str,
    started_utc: str,
    duration_seconds: int,
    clock_mode: str,
) -> dict[str, Any]:
    if scenario not in {"control", "defect"}:
        raise PilotError("scénario inconnu")
    if not isinstance(duration_seconds, int) or duration_seconds < 0:
        raise PilotError("durée invalide")
    if scenario == "defect" and duration_seconds == 0:
        raise PilotError("le scénario defect exige une durée positive")
    if clock_mode not in {"system", "synthetic"}:
        raise PilotError("mode d’horloge invalide")
    start = utc_value(started_utc)
    route = "A" if scenario == "control" else "B"
    return {
        "schema_version": "graph-engineering-pilot-v2/genesis/v1",
        "pilot_id": PILOT_ID,
        "run_id": run_id,
        "scenario": scenario,
        "git_base": GIT_BASE,
        "route": route,
        "selected_nodes": ["D", "S", route, "J"],
        "external_effects_authorized": False,
        "owner": OWNER,
        "started_utc": utc_text(start),
        "duration_seconds": duration_seconds,
        "not_before_utc": utc_text(start + timedelta(seconds=duration_seconds)),
        "clock_mode": clock_mode,
    }


def validated_genesis(run_dir: Path, scenario: str | None = None) -> dict[str, Any]:
    genesis = v1.read_json(run_dir / "genesis.json")
    observed_scenario = genesis.get("scenario")
    if scenario is not None and observed_scenario != scenario:
        raise PilotError("scénario de genèse divergent")
    try:
        expected = genesis_value(
            run_dir.name,
            observed_scenario,
            genesis["started_utc"],
            genesis["duration_seconds"],
            genesis["clock_mode"],
        )
    except (KeyError, TypeError):
        raise PilotError("genèse temporelle invalide") from None
    if genesis != expected:
        raise PilotError("genèse divergente")
    return genesis


def run_acceptance(module_directory: Path) -> dict[str, Any]:
    started = perf_counter()
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run(
        [sys.executable, "-B", "-c", ACCEPTANCE],
        cwd=module_directory,
        capture_output=True,
        text=True,
        timeout=10,
        env=environment,
        check=False,
    )
    return {
        "verdict": "PASS" if process.returncode == 0 else "FAIL",
        "exit_code": process.returncode,
        "wall_seconds": perf_counter() - started,
        "stderr": process.stderr[-1000:],
    }


def close_node(
    run_dir: Path,
    genesis_sha256: str,
    node: str,
    parents: dict[str, str],
    edges: list[str],
    output: dict[str, Any],
    expected: dict[str, Any],
    write_scope: list[str],
    *,
    cost: dict[str, Any] | None = None,
    attempt: int = 1,
    interrupt_before_publish: bool = False,
) -> dict[str, Any]:
    wall_start, cpu_start = perf_counter(), process_time()
    if output != expected:
        raise PilotError(f"sortie du nœud {node} refusée par son évaluateur")
    evaluation = {
        "contract": CONTRACTS[node],
        "contract_sha256": v1.digest(v1.canonical(CONTRACTS[node])),
        "verdict": "PASS",
    }
    base = {
        "schema_version": "graph-engineering-pilot-v2/node-receipt/v1",
        "pilot_id": PILOT_ID,
        "node_id": node,
        "attempt": attempt,
        "state": "evaluated",
        "parent_receipts": parents,
        "consumed_edges": edges,
        "input_sha256": v1.input_sha256(genesis_sha256, parents),
        "output": output,
        "output_sha256": v1.digest(v1.canonical(output)),
        "evaluation": evaluation,
        "time": {
            "wall_seconds": perf_counter() - wall_start,
            "cpu_seconds": process_time() - cpu_start,
        },
        "cost": cost or {"external_cost_usd": "0", "candidate_calls": 0},
        "human_interventions": 0,
        "effect": "none",
        "owner": OWNER,
        "writer_pid": os.getpid(),
        "write_scope": write_scope,
        "context": {"genesis_sha256": genesis_sha256},
    }
    receipt = {**base, "receipt_sha256": v1.digest(v1.canonical(base))}
    v1.write_new(
        receipt_path(run_dir, node),
        receipt,
        interrupt_before_publish=interrupt_before_publish,
    )
    return receipt


def source_lock() -> dict[str, Any]:
    defective = defective_source()
    return {
        "source_path": "tools/choisir_provider.py",
        "source_sha256": v1.digest(SOURCE.read_bytes()),
        "defect_sha256": v1.digest(defective),
        "acceptance_sha256": v1.digest(ACCEPTANCE.encode()),
    }


def defective_source() -> bytes:
    source = SOURCE.read_text(encoding="utf-8")
    if source.count(CORRECT_LINE) != 1:
        raise PilotError("point d’injection du défaut divergent")
    return source.replace(CORRECT_LINE, DEFECT_LINE).encode()


def prepare_agent_workspace(run_dir: Path) -> Path:
    workspace = run_dir / "nodes" / "B" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "choisir_provider.py").write_bytes(defective_source())
    (workspace / "test_budget.py").write_text(ACCEPTANCE, encoding="utf-8")
    return workspace


def remove_agent_python_cache(run_dir: Path) -> None:
    workspace = run_dir / "nodes" / "B" / "workspace"
    cache = workspace / "__pycache__"
    if not cache.exists():
        return
    entries = list(cache.iterdir()) if cache.is_dir() and not cache.is_symlink() else []
    if (
        not entries
        or any(
            entry.is_symlink()
            or not entry.is_file()
            or not entry.name.startswith("choisir_provider.")
            or entry.suffix != ".pyc"
            for entry in entries
        )
    ):
        raise PilotError("cache Python agent inattendu")
    shutil.rmtree(cache)
    v1.sync_directory(workspace)


def execute_prefix(
    run_dir: Path,
    genesis: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    genesis_sha = v1.digest(v1.canonical(genesis))
    d_output = {"route": genesis["route"], "selected_nodes": genesis["selected_nodes"]}
    d = close_node(run_dir, genesis_sha, "D", {}, [], d_output, d_output, ["nodes/D/receipt.json"])
    s_output = source_lock()
    s = close_node(
        run_dir,
        genesis_sha,
        "S",
        {"D": d["receipt_sha256"]},
        ["D->S"],
        s_output,
        source_lock(),
        ["nodes/S/receipt.json"],
    )
    return d, s


def execute_control(run_dir: Path, genesis: dict[str, Any]) -> dict[str, Any]:
    genesis_sha = v1.digest(v1.canonical(genesis))
    d, s = execute_prefix(run_dir, genesis)
    acceptance = run_acceptance(SOURCE.parent)
    a_output = {
        "source_sha256": v1.digest(SOURCE.read_bytes()),
        "acceptance_verdict": acceptance["verdict"],
        "acceptance_exit_code": acceptance["exit_code"],
    }
    a_expected = {
        "source_sha256": s["output"]["source_sha256"],
        "acceptance_verdict": "PASS",
        "acceptance_exit_code": 0,
    }
    a = close_node(
        run_dir,
        genesis_sha,
        "A",
        {"D": d["receipt_sha256"]},
        ["D->A"],
        a_output,
        a_expected,
        ["nodes/A/receipt.json"],
    )
    j_output = {
        "route": "A",
        "parents": {"S": s["receipt_sha256"], "A": a["receipt_sha256"]},
        "consumed_edges": ["D->S", "D->A", "S->J", "A->J"],
    }
    close_node(
        run_dir,
        genesis_sha,
        "J",
        j_output["parents"],
        ["S->J", "A->J"],
        j_output,
        j_output,
        ["nodes/J/receipt.json"],
    )
    return {
        "state": "EXECUTION_COMPLETE_PENDING_TERMINAL_VERIFICATION",
        "route": "A",
        "last_closed_node": "J",
    }


def run_graph(
    run_dir: Path,
    scenario: str,
    *,
    resume: bool,
    duration_seconds: int,
    now_utc: str | None,
) -> dict[str, Any]:
    if resume:
        if scenario != "defect":
            raise PilotError("reprise réservée au scénario defect")
        genesis = validated_genesis(run_dir, scenario)
        nodes = run_dir / "nodes"
        if run_dir.is_symlink() or not run_dir.is_dir() or nodes.is_symlink() or not nodes.is_dir():
            raise PilotError("périmètre de reprise invalide")
        if receipt_path(run_dir, "B").exists() or receipt_path(run_dir, "J").exists():
            raise PilotError("reprise ambiguë: B ou J existe déjà")
        load_prefix(run_dir, genesis)
        b_directory = nodes / "B"
        if b_directory.is_symlink() or not b_directory.is_dir():
            raise PilotError("périmètre B non engagé invalide")
        allowed = {"workspace", "attempts"}
        temporary_receipts = []
        for path in b_directory.iterdir():
            if path.name in allowed:
                continue
            if path.name.startswith(".receipt.json.") and path.name.endswith(".tmp"):
                if path.is_symlink() or not path.is_file():
                    raise PilotError("reçu B partiel invalide")
                temporary_receipts.append(path)
                continue
            raise PilotError("périmètre B non engagé ambigu")
        if load_agent_attempts(run_dir):
            raise PilotError("tentative déjà journalisée: utiliser la reprise exacte")
        workspace = b_directory / "workspace"
        if workspace.is_symlink() or not workspace.is_dir():
            raise PilotError("workspace B non engagé invalide")
        shutil.rmtree(workspace)
        for path in temporary_receipts:
            path.unlink()
        v1.sync_directory(b_directory)
        workspace = prepare_agent_workspace(run_dir)
        return {
            "state": "NEEDS_AGENT_B",
            "route": "B",
            "first_executed_node": "B",
            "replayed_nodes": [],
            "workspace": str(workspace),
        }
    if scenario == "control" and duration_seconds != 0:
        raise PilotError("le contrôle ne doit pas attendre")
    genesis = genesis_value(
        run_dir.name,
        scenario,
        utc_text(utc_value(now_utc)),
        duration_seconds,
        "synthetic" if now_utc is not None else "system",
    )
    v1.write_new(run_dir / "genesis.json", genesis)
    if scenario == "control":
        return execute_control(run_dir, genesis)
    execute_prefix(run_dir, genesis)
    workspace = prepare_agent_workspace(run_dir)
    return {
        "state": "NEEDS_AGENT_B",
        "route": "B",
        "first_executed_node": "B",
        "replayed_nodes": [],
        "workspace": str(workspace),
    }


def load_receipt(run_dir: Path, node: str) -> dict[str, Any]:
    path = receipt_path(run_dir, node)
    receipt = v1.read_json(path)
    if path.read_bytes() != v1.canonical(receipt):
        raise PilotError(f"reçu {node} non canonique")
    stored_hash = receipt.pop("receipt_sha256", None)
    if stored_hash != v1.digest(v1.canonical(receipt)):
        raise PilotError(f"reçu {node} divergent")
    return {**receipt, "receipt_sha256": stored_hash}


def validate_receipt(
    receipt: dict[str, Any],
    node: str,
    genesis_sha256: str,
    parents: dict[str, str],
    edges: list[str],
    output: dict[str, Any],
    *,
    attempt: int = 1,
) -> None:
    required = {
        "schema_version", "pilot_id", "node_id", "attempt", "state",
        "parent_receipts", "consumed_edges", "input_sha256", "output",
        "output_sha256", "evaluation", "time", "cost", "human_interventions",
        "effect", "owner", "writer_pid", "write_scope", "context",
        "receipt_sha256",
    }
    expected_scope = (
        ["nodes/B/workspace/", "nodes/B/attempts/", "nodes/B/receipt.json"]
        if node == "B"
        else [f"nodes/{node}/receipt.json"]
    )
    expected_cost = (
        {"external_cost_usd": "INCONNU", "candidate_calls": attempt}
        if node == "B"
        else {"external_cost_usd": "0", "candidate_calls": 0}
    )
    if (
        set(receipt) != required
        or receipt.get("schema_version") != "graph-engineering-pilot-v2/node-receipt/v1"
        or receipt.get("pilot_id") != PILOT_ID
        or receipt.get("node_id") != node
        or receipt.get("attempt") != attempt
        or receipt.get("state") != "evaluated"
        or receipt.get("parent_receipts") != parents
        or receipt.get("consumed_edges") != edges
        or receipt.get("input_sha256") != v1.input_sha256(genesis_sha256, parents)
        or receipt.get("output") != output
        or receipt.get("output_sha256") != v1.digest(v1.canonical(output))
        or receipt.get("evaluation")
        != {
            "contract": CONTRACTS[node],
            "contract_sha256": v1.digest(v1.canonical(CONTRACTS[node])),
            "verdict": "PASS",
        }
        or receipt.get("owner") != OWNER
        or receipt.get("effect") != "none"
        or receipt.get("cost") != expected_cost
        or receipt.get("human_interventions") != 0
        or receipt.get("write_scope") != expected_scope
        or not isinstance(receipt.get("writer_pid"), int)
        or receipt["writer_pid"] <= 0
        or receipt.get("context") != {"genesis_sha256": genesis_sha256}
    ):
        raise PilotError(f"reçu {node} divergent")


def load_prefix(
    run_dir: Path,
    genesis: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    genesis_sha = v1.digest(v1.canonical(genesis))
    d = load_receipt(run_dir, "D")
    d_output = {"route": genesis["route"], "selected_nodes": genesis["selected_nodes"]}
    validate_receipt(d, "D", genesis_sha, {}, [], d_output)
    s = load_receipt(run_dir, "S")
    validate_receipt(
        s,
        "S",
        genesis_sha,
        {"D": d["receipt_sha256"]},
        ["D->S"],
        source_lock(),
    )
    return d, s


def validate_agent_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "harness",
        "model_requested",
        "model_observed",
        "session_id",
        "wall_seconds",
        "tokens",
    }
    if (
        set(evidence) != required
        or evidence.get("schema_version") != "graph-engineering-pilot-v2/agent-evidence/v1"
        or not all(isinstance(evidence.get(field), str) and evidence[field] for field in (
            "harness", "model_requested", "model_observed", "session_id"
        ))
        or not isinstance(evidence.get("wall_seconds"), (int, float))
        or evidence["wall_seconds"] < 0
        or not isinstance(evidence.get("tokens"), (str, dict))
    ):
        raise PilotError("preuve agent invalide")
    return evidence


def load_agent_evidence(path: Path) -> dict[str, Any]:
    return validate_agent_evidence(v1.read_json(path))


def load_agent_attempts(run_dir: Path) -> list[dict[str, Any]]:
    directory = run_dir / "nodes" / "B" / "attempts"
    if not directory.exists():
        return []
    if directory.is_symlink() or not directory.is_dir():
        raise PilotError("journal des tentatives B invalide")
    paths = list(directory.iterdir())
    if any(
        path.is_symlink()
        or not path.is_file()
        or path.suffix != ".json"
        or not path.stem.isdigit()
        for path in paths
    ):
        raise PilotError("journal des tentatives B ambigu")
    paths.sort(key=lambda path: int(path.stem))
    numbers = [int(path.stem) for path in paths]
    if numbers != list(range(1, len(paths) + 1)):
        raise PilotError("journal des tentatives B discontinu")
    attempts = []
    previous = None
    required = {
        "schema_version", "pilot_id", "node_id", "attempt",
        "previous_attempt_sha256", "output", "output_sha256",
        "evaluation", "attempt_sha256",
    }
    output_fields = {
        "defect_sha256", "candidate_sha256", "acceptance_verdict",
        "acceptance_exit_code", "candidate_diff", "candidate_source_utf8", "agent",
    }
    for number, path in zip(numbers, paths, strict=True):
        attempt = v1.read_json(path)
        if path.read_bytes() != v1.canonical(attempt):
            raise PilotError("tentative B non canonique")
        stored_hash = attempt.get("attempt_sha256")
        base = {key: value for key, value in attempt.items() if key != "attempt_sha256"}
        output = attempt.get("output")
        if (
            set(attempt) != required
            or stored_hash != v1.digest(v1.canonical(base))
            or attempt.get("schema_version") != "graph-engineering-pilot-v2/agent-attempt/v1"
            or attempt.get("pilot_id") != PILOT_ID
            or attempt.get("node_id") != "B"
            or attempt.get("attempt") != number
            or attempt.get("previous_attempt_sha256") != previous
            or not isinstance(output, dict)
            or set(output) != output_fields
            or output.get("defect_sha256") != source_lock()["defect_sha256"]
            or not isinstance(output.get("candidate_sha256"), str)
            or len(output["candidate_sha256"]) != 64
            or not isinstance(output.get("candidate_source_utf8"), str)
            or v1.digest(output["candidate_source_utf8"].encode())
            != output["candidate_sha256"]
            or output.get("acceptance_verdict") != "PASS"
            or output.get("acceptance_exit_code") != 0
            or not isinstance(output.get("candidate_diff"), str)
            or not output["candidate_diff"]
            or attempt.get("output_sha256") != v1.digest(v1.canonical(output))
            or attempt.get("evaluation")
            != {
                "contract": CONTRACTS["B"],
                "contract_sha256": v1.digest(v1.canonical(CONTRACTS["B"])),
                "verdict": "PASS",
            }
        ):
            raise PilotError("tentative B divergente")
        validate_agent_evidence(output["agent"])
        attempts.append(attempt)
        previous = stored_hash
    return attempts


def write_agent_attempt(run_dir: Path, output: dict[str, Any]) -> dict[str, Any]:
    attempts = load_agent_attempts(run_dir)
    number = len(attempts) + 1
    base = {
        "schema_version": "graph-engineering-pilot-v2/agent-attempt/v1",
        "pilot_id": PILOT_ID,
        "node_id": "B",
        "attempt": number,
        "previous_attempt_sha256": attempts[-1]["attempt_sha256"] if attempts else None,
        "output": output,
        "output_sha256": v1.digest(v1.canonical(output)),
        "evaluation": {
            "contract": CONTRACTS["B"],
            "contract_sha256": v1.digest(v1.canonical(CONTRACTS["B"])),
            "verdict": "PASS",
        },
    }
    attempt = {**base, "attempt_sha256": v1.digest(v1.canonical(base))}
    v1.write_new(attempt_path(run_dir, number), attempt)
    return attempt


def evaluate_agent_workspace(
    run_dir: Path,
    evidence: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    workspace = run_dir / "nodes" / "B" / "workspace"
    if workspace.is_symlink() or not workspace.is_dir():
        raise PilotError("workspace B invalide")
    children = {path.name for path in workspace.iterdir()}
    if children != {"choisir_provider.py", "test_budget.py"}:
        raise PilotError("écriture agent hors périmètre attendu")
    if any(path.is_symlink() for path in workspace.iterdir()):
        raise PilotError("lien symbolique agent interdit")
    test_path = workspace / "test_budget.py"
    if test_path.read_text(encoding="utf-8") != ACCEPTANCE:
        raise PilotError("oracle agent modifié")
    candidate_path = workspace / "choisir_provider.py"
    candidate = candidate_path.read_bytes()
    try:
        candidate_text = candidate.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PilotError("source candidate non UTF-8") from error
    defective = defective_source()
    if candidate == defective:
        raise PilotError("défaut non corrigé")
    acceptance = run_acceptance(workspace)
    output = {
        "defect_sha256": v1.digest(defective),
        "candidate_sha256": v1.digest(candidate),
        "acceptance_verdict": acceptance["verdict"],
        "acceptance_exit_code": acceptance["exit_code"],
        "candidate_source_utf8": candidate_text,
        "candidate_diff": "".join(difflib.unified_diff(
            defective.decode().splitlines(keepends=True),
            candidate_text.splitlines(keepends=True),
            fromfile="a/tools/choisir_provider.py",
            tofile="b/tools/choisir_provider.py",
        )),
        "agent": evidence,
    }
    expected = {
        **output,
        "defect_sha256": source_lock()["defect_sha256"],
        "acceptance_verdict": "PASS",
        "acceptance_exit_code": 0,
    }
    return output, expected


def timing_state(genesis: dict[str, Any], now_utc: str | None) -> dict[str, Any]:
    if genesis["clock_mode"] == "system" and now_utc is not None:
        raise PilotError("substitution d’horloge interdite pour un pilote réel")
    if genesis["clock_mode"] == "synthetic" and now_utc is None:
        raise PilotError("horloge synthétique requise")
    now = utc_value(now_utc)
    started = utc_value(genesis["started_utc"])
    deadline = utc_value(genesis["not_before_utc"])
    elapsed = (now - started).total_seconds()
    if elapsed < 0:
        raise PilotError("horloge antérieure au début du pilote")
    return {
        "elapsed_seconds": elapsed,
        "not_before_utc": genesis["not_before_utc"],
        "ready": now >= deadline,
    }


def pending_agent_state(
    run_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    genesis = validated_genesis(run_dir, "defect")
    if receipt_path(run_dir, "B").exists() or receipt_path(run_dir, "J").exists():
        raise PilotError("reprise ambiguë")
    b_directory = run_dir / "nodes" / "B"
    if b_directory.is_symlink() or not b_directory.is_dir():
        raise PilotError("périmètre B invalide")
    if {path.name for path in b_directory.iterdir()} != {"workspace", "attempts"}:
        raise PilotError("état B en attente ambigu")
    d, s = load_prefix(run_dir, genesis)
    attempts = load_agent_attempts(run_dir)
    if len(attempts) != 1:
        raise PilotError("une tentative B durable exacte est requise")
    output = attempts[0]["output"]
    observed, expected = evaluate_agent_workspace(run_dir, output["agent"])
    if observed != expected or observed != output:
        raise PilotError("workspace B divergent de la tentative durable")
    return genesis, d, s, attempts[0]


def pending_status(run_dir: Path, now_utc: str | None) -> dict[str, Any]:
    before = v1.scope_snapshot(run_dir)
    genesis, _, _, attempt = pending_agent_state(run_dir)
    timing = timing_state(genesis, now_utc)
    result = {
        "state": "READY_TO_RESUME" if timing["ready"] else "WAITING_UNTIL_DEADLINE",
        "candidate_calls": attempt["attempt"],
        "elapsed_seconds": timing["elapsed_seconds"],
        "not_before_utc": timing["not_before_utc"],
    }
    if v1.scope_snapshot(run_dir) != before:
        raise PilotError("le contrôle d’attente a écrit")
    return result


def close_agent_branch(
    run_dir: Path,
    genesis: dict[str, Any],
    d: dict[str, Any],
    s: dict[str, Any],
    attempt: dict[str, Any],
    *,
    interrupt_before_b_receipt: bool,
) -> dict[str, Any]:
    output = attempt["output"]
    genesis_sha = v1.digest(v1.canonical(genesis))
    try:
        b = close_node(
            run_dir,
            genesis_sha,
            "B",
            {"D": d["receipt_sha256"]},
            ["D->B"],
            output,
            output,
            ["nodes/B/workspace/", "nodes/B/attempts/", "nodes/B/receipt.json"],
            cost={"external_cost_usd": "INCONNU", "candidate_calls": attempt["attempt"]},
            attempt=attempt["attempt"],
            interrupt_before_publish=interrupt_before_b_receipt,
        )
    except v1.ControlledStop:
        return {
            "state": "STOPPED_DURING_B_RECEIPT",
            "last_closed_node": "S",
            "uncommitted_node": "B",
        }
    j_output = {
        "route": "B",
        "parents": {"S": s["receipt_sha256"], "B": b["receipt_sha256"]},
        "consumed_edges": ["D->S", "D->B", "S->J", "B->J"],
        "candidate_sha256": b["output"]["candidate_sha256"],
    }
    close_node(
        run_dir,
        genesis_sha,
        "J",
        j_output["parents"],
        ["S->J", "B->J"],
        j_output,
        j_output,
        ["nodes/J/receipt.json"],
    )
    return {
        "state": "EXECUTION_COMPLETE_PENDING_TERMINAL_VERIFICATION",
        "route": "B",
        "last_closed_node": "J",
        "first_executed_node": "B",
        "replayed_nodes": [],
    }


def continue_agent(
    run_dir: Path,
    agent_evidence_path: Path | None,
    *,
    interrupt_before_b_receipt: bool,
    crash_after_attempt: bool,
    reuse_last_attempt: bool,
    now_utc: str | None,
) -> dict[str, Any]:
    if reuse_last_attempt and (interrupt_before_b_receipt or crash_after_attempt):
        raise PilotError("la reprise exacte ne peut pas être réinterrompue")
    if interrupt_before_b_receipt and crash_after_attempt:
        raise PilotError("modes d’interruption incompatibles")
    if reuse_last_attempt:
        genesis, d, s, attempt = pending_agent_state(run_dir)
        if not timing_state(genesis, now_utc)["ready"]:
            raise PilotError("deadline de reprise non atteinte")
        return close_agent_branch(
            run_dir,
            genesis,
            d,
            s,
            attempt,
            interrupt_before_b_receipt=False,
        )
    if agent_evidence_path is None:
        raise PilotError("preuve agent requise")
    genesis = validated_genesis(run_dir, "defect")
    if receipt_path(run_dir, "B").exists() or receipt_path(run_dir, "J").exists():
        raise PilotError("continuation ambiguë")
    b_directory = run_dir / "nodes" / "B"
    if any(
        path.name.startswith(".receipt.json.") and path.name.endswith(".tmp")
        for path in b_directory.iterdir()
    ):
        raise PilotError("reprise requise après interruption de B")
    d, s = load_prefix(run_dir, genesis)
    if load_agent_attempts(run_dir):
        raise PilotError("tentative déjà journalisée: utiliser la reprise exacte")
    evidence = load_agent_evidence(agent_evidence_path)
    remove_agent_python_cache(run_dir)
    output, expected = evaluate_agent_workspace(run_dir, evidence)
    if output != expected:
        raise PilotError("sortie du nœud B refusée par son évaluateur")
    attempt = write_agent_attempt(run_dir, output)
    if crash_after_attempt:
        os._exit(86)
    return close_agent_branch(
        run_dir,
        genesis,
        d,
        s,
        attempt,
        interrupt_before_b_receipt=interrupt_before_b_receipt,
    )


def terminal_verdict(run_dir: Path, now_utc: str | None = None) -> dict[str, Any]:
    before = v1.scope_snapshot(run_dir)
    try:
        genesis = validated_genesis(run_dir)
        timing = timing_state(genesis, now_utc)
        if not timing["ready"]:
            raise PilotError("condition temporelle terminale non atteinte")
        if {path.name for path in run_dir.iterdir()} != {"genesis.json", "nodes"}:
            raise PilotError("état racine ambigu")
        selected = set(genesis["selected_nodes"])
        if {path.name for path in (run_dir / "nodes").iterdir()} != selected:
            raise PilotError("ensemble des nœuds divergent")
        receipts = {node: load_receipt(run_dir, node) for node in genesis["selected_nodes"]}
        d, s = load_prefix(run_dir, genesis)
        genesis_sha = v1.digest(v1.canonical(genesis))
        route = genesis["route"]
        if route == "A":
            acceptance = run_acceptance(SOURCE.parent)
            a_output = {
                "source_sha256": source_lock()["source_sha256"],
                "acceptance_verdict": "PASS",
                "acceptance_exit_code": 0,
            }
            if acceptance["verdict"] != "PASS":
                raise PilotError("contrôle A divergent")
            validate_receipt(
                receipts["A"],
                "A",
                genesis_sha,
                {"D": d["receipt_sha256"]},
                ["D->A"],
                a_output,
            )
            branch = receipts["A"]
        else:
            if {path.name for path in (run_dir / "nodes" / "B").iterdir()} != {
                "workspace", "attempts", "receipt.json",
            }:
                raise PilotError("état B ambigu")
            attempts = load_agent_attempts(run_dir)
            if len(attempts) != 1:
                raise PilotError("le terminal exige une tentative B unique")
            evidence = receipts["B"].get("output", {}).get("agent")
            if not isinstance(evidence, dict):
                raise PilotError("preuve agent absente")
            b_output, b_expected = evaluate_agent_workspace(run_dir, evidence)
            if b_output != b_expected:
                raise PilotError("sortie B non évaluée")
            if attempts[-1]["output"] != b_output:
                raise PilotError("reçu B non aligné sur la dernière tentative")
            validate_receipt(
                receipts["B"],
                "B",
                genesis_sha,
                {"D": d["receipt_sha256"]},
                ["D->B"],
                b_output,
                attempt=len(attempts),
            )
            branch = receipts["B"]
        expected_parents = {
            "S": s["receipt_sha256"],
            route: branch["receipt_sha256"],
        }
        j_output = {
            "route": route,
            "parents": expected_parents,
            "consumed_edges": ["D->S", f"D->{route}", "S->J", f"{route}->J"],
        }
        if route == "B":
            j_output["candidate_sha256"] = branch["output"]["candidate_sha256"]
        validate_receipt(
            receipts["J"],
            "J",
            genesis_sha,
            expected_parents,
            ["S->J", f"{route}->J"],
            j_output,
        )
        result = {
            "verdict": "PASS_PILOTE_AGENTIQUE_LOCAL",
            "route": route,
            "elapsed_seconds": timing["elapsed_seconds"],
            "not_before_utc": timing["not_before_utc"],
        }
    except (PilotError, KeyError, TypeError, ValueError) as error:
        result = {"verdict": "HOLD_PILOTE_AGENTIQUE_LOCAL", "error": str(error)}
    if v1.scope_snapshot(run_dir) != before:
        return {"verdict": "HOLD_PILOTE_AGENTIQUE_LOCAL", "error": "le vérificateur a écrit"}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--scenario", choices=("control", "defect"), required=True)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--duration-seconds", type=int, default=0)
    run_parser.add_argument("--now-utc")
    continue_parser = subparsers.add_parser("continue")
    continue_parser.add_argument("--run-dir", type=Path, required=True)
    continuation = continue_parser.add_mutually_exclusive_group(required=True)
    continuation.add_argument("--agent-evidence", type=Path)
    continuation.add_argument("--reuse-last-attempt", action="store_true")
    continue_parser.add_argument("--interrupt-before-b-receipt", action="store_true")
    continue_parser.add_argument("--crash-after-attempt", action="store_true")
    continue_parser.add_argument("--now-utc")
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--run-dir", type=Path, required=True)
    status_parser.add_argument("--expect", choices=("waiting", "ready"), required=True)
    status_parser.add_argument("--now-utc")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--run-dir", type=Path, required=True)
    verify_parser.add_argument("--now-utc")
    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run_graph(
                args.run_dir,
                args.scenario,
                resume=args.resume,
                duration_seconds=args.duration_seconds,
                now_utc=args.now_utc,
            )
            exit_code = 0
        elif args.command == "continue":
            result = continue_agent(
                args.run_dir,
                args.agent_evidence,
                interrupt_before_b_receipt=args.interrupt_before_b_receipt,
                crash_after_attempt=args.crash_after_attempt,
                reuse_last_attempt=args.reuse_last_attempt,
                now_utc=args.now_utc,
            )
            exit_code = 0
        elif args.command == "status":
            result = pending_status(args.run_dir, args.now_utc)
            expected = {
                "waiting": "WAITING_UNTIL_DEADLINE",
                "ready": "READY_TO_RESUME",
            }[args.expect]
            exit_code = 0 if result["state"] == expected else 1
        else:
            result = terminal_verdict(args.run_dir, args.now_utc)
            exit_code = 0 if result["verdict"] == "PASS_PILOTE_AGENTIQUE_LOCAL" else 1
    except (PilotError, OSError, subprocess.SubprocessError) as error:
        result, exit_code = {"state": "HOLD_PILOTE_AGENTIQUE_LOCAL", "error": str(error)}, 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
