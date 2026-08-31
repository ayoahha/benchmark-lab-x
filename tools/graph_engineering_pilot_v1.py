#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from tempfile import mkstemp
from time import perf_counter, process_time
from typing import Any, Callable

from tools import preuve_u025_p2_manual_v3 as u025


ROOT = Path(__file__).resolve().parents[1]
PILOT_ID = "graph-engineering-pilot-v1"
GIT_BASE = "81c217e0a585e89c0151090d6cef9581b8a2c741"
OWNER = "graph-engineering-pilot-v1-single-writer"
NODES = ("D", "S", "A", "B", "J")
ROUTES = {"A": ("D", "S", "A", "J"), "B": ("D", "S", "B", "J")}
EDGES = {"A": ("D->S", "D->A", "S->J", "A->J"), "B": ("D->S", "D->B", "S->J", "B->J")}
CONTRACTS = {
    "D": "recalculate-route-and-selected-set/v1",
    "S": "verify-locked-u025-v3-sources/v1",
    "A": "verify-canonical-u025-v3-read-only/v1",
    "B": "rebuild-verify-and-compare-isolated-u025-v3/v1",
    "J": "require-two-distinct-parents-and-four-consumed-edges/v1",
}


class PilotError(RuntimeError):
    pass


class ControlledStop(PilotError):
    pass


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise PilotError(f"objet absent ou illisible: {path}") from error
    if not isinstance(value, dict):
        raise PilotError(f"objet JSON invalide: {path}")
    return value


def sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_new(path: Path, value: object, *, interrupt_before_publish: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    preserve_temporary = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        if interrupt_before_publish:
            preserve_temporary = True
            raise ControlledStop(f"arrêt contrôlé avant publication: {path}")
        os.link(temporary, path)
        temporary.unlink()
        sync_directory(path.parent)
    except FileExistsError as error:
        raise PilotError(f"objet fermé déjà présent: {path}") from error
    finally:
        if temporary.exists() and not preserve_temporary:
            temporary.unlink()


def tree_fingerprint(directory: Path) -> str:
    rows = [
        [path.relative_to(directory).as_posix(), digest(path.read_bytes())]
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ]
    return digest(canonical(rows))


def scope_snapshot(directory: Path) -> bytes:
    return canonical([
        [
            path.relative_to(directory).as_posix(),
            digest(path.read_bytes()),
            path.stat().st_mtime_ns,
        ]
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ])


def tree_bytes(directory: Path) -> int:
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def genesis_value(run_id: str, scenario: str, route: str) -> dict[str, Any]:
    if scenario not in {"S1", "S2"} or route not in ROUTES:
        raise PilotError("scénario ou route inconnu")
    if (scenario, route) not in {("S1", "A"), ("S2", "B")}:
        raise PilotError("route interdite pour ce scénario")
    return {
        "schema_version": "graph-engineering-pilot-v1/genesis/v1",
        "pilot_id": PILOT_ID,
        "run_id": run_id,
        "scenario": scenario,
        "git_base": GIT_BASE,
        "requested_route": route,
        "graph": {"nodes": list(NODES), "selected_nodes": list(ROUTES[route]), "edges": list(EDGES[route])},
        "external_effects_authorized": False,
        "logical_writer": OWNER,
    }


def source_output() -> dict[str, Any]:
    u025.verify_sources()
    return {
        "u025_v1_root_sha256": u025.V1_ROOT_SHA256,
        "u025_v1_byte_fingerprint": u025.V1_BYTE_FINGERPRINT,
        "u025_v2_root_sha256": u025.V2_ROOT_SHA256,
        "u025_v2_byte_fingerprint": u025.V2_BYTE_FINGERPRINT,
        "v3_instrument_sha256": digest(Path(u025.__file__).read_bytes()),
        "v3_test_contract_sha256": digest(u025.TEST_FILE.read_bytes()),
        "v3_procedure_sha256": digest(u025.PROCEDURE.read_bytes()),
    }


def verify_u025_read_only(proof_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    before = scope_snapshot(proof_dir)
    original_counterexamples = u025.exercise_counterexamples
    original_temporary_directory = u025.TemporaryDirectory
    temporary_directory_calls = 0

    def locked_counterexamples() -> dict[str, Any]:
        return u025.read_json(proof_dir / "counterexample-results.json")

    def forbidden_temporary_directory(*args: object, **kwargs: object) -> object:
        nonlocal temporary_directory_calls
        temporary_directory_calls += 1
        raise PilotError("TemporaryDirectory interdit en vérification U-025 read-only")

    u025.exercise_counterexamples = locked_counterexamples
    u025.TemporaryDirectory = forbidden_temporary_directory
    try:
        result = u025.verify(proof_dir)
    finally:
        u025.exercise_counterexamples = original_counterexamples
        u025.TemporaryDirectory = original_temporary_directory
    if scope_snapshot(proof_dir) != before:
        raise PilotError("le vérificateur U-025 read-only a modifié sa portée")
    return result, {
        "mode": "locked-counterexamples-read-only",
        "content_and_mtime_unchanged": True,
        "temporary_directory_calls": temporary_directory_calls,
    }


def verify_canonical_u025() -> dict[str, Any]:
    before = tree_fingerprint(u025.PROOF)
    result, read_only = verify_u025_read_only(u025.PROOF)
    return {
        "u025_root_sha256": result["root_sha256"],
        "u025_source_v2_root_sha256": result["source_v2_root_sha256"],
        "u025_conclusion": result["conclusion"],
        "canonical_tree_sha256": before,
        "read_only": read_only,
    }


def rebuild_u025(proof_dir: Path) -> dict[str, Any]:
    proof_dir.mkdir(parents=True, exist_ok=True)
    temporary_root = proof_dir / ".pilot-temporary"
    temporary_root.mkdir()
    original_temporary_directory = u025.TemporaryDirectory
    temporary_directory_calls = 0

    def owned_temporary_directory(*args: object, **kwargs: object) -> object:
        nonlocal temporary_directory_calls
        temporary_directory_calls += 1
        kwargs["dir"] = temporary_root
        return original_temporary_directory(*args, **kwargs)

    u025.TemporaryDirectory = owned_temporary_directory
    try:
        u025.prepare(u025.GIT_BASE, proof_dir=proof_dir, interrupt_after_receipts=3)
        u025.prepare(u025.GIT_BASE, proof_dir=proof_dir)
        u025.finalize(proof_dir=proof_dir, interrupt_after_human_receipts=2)
        u025.finalize(proof_dir=proof_dir)
        result = u025.verify(proof_dir)
    finally:
        u025.TemporaryDirectory = original_temporary_directory
        if temporary_root.exists() and not any(temporary_root.iterdir()):
            temporary_root.rmdir()
    canonical_result = verify_canonical_u025()
    if result["root_sha256"] != canonical_result["u025_root_sha256"]:
        raise PilotError("la reconstruction U-025 diverge de la preuve canonique")
    return {
        "u025_root_sha256": result["root_sha256"],
        "u025_source_v2_root_sha256": result["source_v2_root_sha256"],
        "u025_conclusion": result["conclusion"],
        "reconstruction_tree_sha256": tree_fingerprint(proof_dir),
        "canonical_tree_sha256": canonical_result["canonical_tree_sha256"],
        "read_only": canonical_result["read_only"],
        "reconstruction_temporary_directory_calls": temporary_directory_calls,
        "reconstruction_temporary_scope": "nodes/B/u025/.pilot-temporary",
        "temporary_writes_outside_b": 0,
    }


def receipt_path(run_dir: Path, node: str) -> Path:
    return run_dir / "nodes" / node / "receipt.json"


def receipt_hash(receipt: dict[str, Any]) -> str:
    return digest(canonical({key: value for key, value in receipt.items() if key != "receipt_sha256"}))


def load_receipt(run_dir: Path, node: str) -> dict[str, Any]:
    receipt = read_json(receipt_path(run_dir, node))
    if receipt_hash(receipt) != receipt.get("receipt_sha256"):
        raise PilotError(f"empreinte du reçu {node} divergente")
    if canonical(receipt) != receipt_path(run_dir, node).read_bytes():
        raise PilotError(f"reçu {node} non canonique")
    return receipt


def load_resume_prefix(run_dir: Path, genesis_sha256: str) -> dict[str, dict[str, Any]]:
    receipts = {node: load_receipt(run_dir, node) for node in ("D", "S")}
    expected_links = {
        "D": ({}, []),
        "S": ({"D": receipts["D"]["receipt_sha256"]}, ["D->S"]),
    }
    for node, receipt in receipts.items():
        parents, edges = expected_links[node]
        if (
            receipt.get("schema_version") != "graph-engineering-pilot-v1/node-receipt/v1"
            or receipt.get("pilot_id") != PILOT_ID
            or receipt.get("node_id") != node
            or receipt.get("attempt") != 1
            or receipt.get("state") != "evaluated"
            or receipt.get("parent_receipts") != parents
            or receipt.get("consumed_edges") != edges
            or receipt.get("input_sha256") != input_sha256(genesis_sha256, parents)
            or receipt.get("output_sha256") != digest(canonical(receipt.get("output")))
            or receipt.get("evaluation")
            != {
                "contract": CONTRACTS[node],
                "contract_sha256": digest(canonical(CONTRACTS[node])),
                "verdict": "PASS",
            }
            or receipt.get("effect") != "none"
            or receipt.get("owner") != OWNER
            or receipt.get("context")
            != {"genesis_sha256": genesis_sha256, "missing_fields": [], "altered_fields": []}
        ):
            raise PilotError(f"checkpoint fermé {node} divergent")
    return receipts


def input_sha256(genesis_sha256: str, parents: dict[str, str]) -> str:
    return digest(canonical({"genesis_sha256": genesis_sha256, "parent_receipts": parents}))


def evaluate_node_output(
    run_dir: Path,
    genesis: dict[str, Any],
    node: str,
    output: dict[str, Any],
    receipts: dict[str, dict[str, Any]],
) -> dict[str, str]:
    if output != expected_output(run_dir, genesis, node, receipts):
        raise PilotError(f"sortie du nœud {node} refusée par son évaluateur")
    contract = CONTRACTS[node]
    return {
        "contract": contract,
        "contract_sha256": digest(canonical(contract)),
        "verdict": "PASS",
    }


def write_receipt(
    run_dir: Path,
    node: str,
    genesis_sha256: str,
    parents: dict[str, str],
    consumed_edges: list[str],
    output_builder: Callable[[], dict[str, Any]],
    evaluator: Callable[[dict[str, Any]], dict[str, str]],
    write_scope: list[str],
    *,
    interrupt_before_publish: bool = False,
) -> dict[str, Any]:
    wall_start, cpu_start = perf_counter(), process_time()
    output = output_builder()
    evaluation = evaluator(output)
    wall_seconds, cpu_seconds = perf_counter() - wall_start, process_time() - cpu_start
    base = {
        "schema_version": "graph-engineering-pilot-v1/node-receipt/v1",
        "pilot_id": PILOT_ID,
        "node_id": node,
        "attempt": 1,
        "state": "evaluated",
        "parent_receipts": parents,
        "consumed_edges": consumed_edges,
        "input_sha256": input_sha256(genesis_sha256, parents),
        "output": output,
        "output_sha256": digest(canonical(output)),
        "evaluation": evaluation,
        "time": {"wall_seconds": wall_seconds, "cpu_seconds": cpu_seconds},
        "cost": {"external_cost_usd": "0", "candidate_calls": 0, "provider_attempts": 0},
        "human_interventions": 0,
        "effect": "none",
        "owner": OWNER,
        "writer_pid": os.getpid(),
        "write_scope": write_scope,
        "context": {"genesis_sha256": genesis_sha256, "missing_fields": [], "altered_fields": []},
    }
    receipt = {**base, "receipt_sha256": digest(canonical(base))}
    write_new(receipt_path(run_dir, node), receipt, interrupt_before_publish=interrupt_before_publish)
    return receipt


def execute_d(run_dir: Path, genesis: dict[str, Any], genesis_sha: str) -> dict[str, Any]:
    route = genesis["requested_route"]
    return write_receipt(
        run_dir,
        "D",
        genesis_sha,
        {},
        [],
        lambda: {"route": route, "selected_nodes": list(ROUTES[route]), "edges": list(EDGES[route])},
        lambda output: evaluate_node_output(run_dir, genesis, "D", output, {}),
        ["nodes/D/receipt.json"],
    )


def execute_s(run_dir: Path, genesis: dict[str, Any], genesis_sha: str, d: dict[str, Any]) -> dict[str, Any]:
    return write_receipt(
        run_dir,
        "S",
        genesis_sha,
        {"D": d["receipt_sha256"]},
        ["D->S"],
        source_output,
        lambda output: evaluate_node_output(run_dir, genesis, "S", output, {"D": d}),
        ["nodes/S/receipt.json"],
    )


def execute_branch(
    run_dir: Path,
    genesis: dict[str, Any],
    genesis_sha: str,
    d: dict[str, Any],
    *,
    interrupt_before_receipt: bool = False,
) -> dict[str, Any]:
    branch = genesis["requested_route"]
    output_builder = verify_canonical_u025 if branch == "A" else lambda: rebuild_u025(run_dir / "nodes" / "B" / "u025")
    scope = [f"nodes/{branch}/receipt.json"] if branch == "A" else ["nodes/B/receipt.json", "nodes/B/u025/"]
    return write_receipt(
        run_dir,
        branch,
        genesis_sha,
        {"D": d["receipt_sha256"]},
        [f"D->{branch}"],
        output_builder,
        lambda output: evaluate_node_output(run_dir, genesis, branch, output, {"D": d}),
        scope,
        interrupt_before_publish=interrupt_before_receipt,
    )


def execute_j(
    run_dir: Path,
    genesis: dict[str, Any],
    genesis_sha: str,
    s: dict[str, Any],
    branch_receipt: dict[str, Any],
    *,
    invalid_output: bool,
) -> dict[str, Any]:
    branch = genesis["requested_route"]

    def output() -> dict[str, Any]:
        aggregate = {
            "route": branch,
            "selected_nodes": list(ROUTES[branch]),
            "parent_output_sha256s": {"S": s["output_sha256"], branch: branch_receipt["output_sha256"]},
            "consumed_graph_edges": [] if invalid_output else list(EDGES[branch]),
        }
        return {**aggregate, "aggregate_sha256": digest(canonical(aggregate))}

    return write_receipt(
        run_dir,
        "J",
        genesis_sha,
        {"S": s["receipt_sha256"], branch: branch_receipt["receipt_sha256"]},
        ["S->J", f"{branch}->J"],
        output,
        lambda value: evaluate_node_output(
            run_dir,
            genesis,
            "J",
            value,
            {"S": s, branch: branch_receipt},
        ),
        ["nodes/J/receipt.json"],
    )


def run_graph(
    run_dir: Path,
    scenario: str,
    route: str,
    *,
    stop_after_s: bool,
    resume: bool,
    fault_injection: str | None,
) -> dict[str, Any]:
    if scenario == "S1" and (stop_after_s or resume or fault_injection not in {None, "invalid-j-output"}):
        raise PilotError("mode d'exécution interdit pour ce scénario")
    if scenario == "S2" and (stop_after_s, resume, fault_injection) not in {
        (True, False, None),
        (False, True, None),
        (False, False, "interrupt-before-b-receipt"),
    }:
        raise PilotError("mode d'exécution interdit pour ce scénario")
    genesis_path = run_dir / "genesis.json"
    if resume:
        genesis = read_json(genesis_path)
        if genesis != genesis_value(genesis["run_id"], scenario, route):
            raise PilotError("genèse divergente à la reprise")
    else:
        genesis = genesis_value(run_dir.name, scenario, route)
        write_new(genesis_path, genesis)
    genesis_sha = digest(canonical(genesis))
    if resume:
        nodes_directory = run_dir / "nodes"
        if run_dir.is_symlink() or not run_dir.is_dir() or nodes_directory.is_symlink() or not nodes_directory.is_dir():
            raise PilotError("périmètre de reprise invalide")
        if receipt_path(run_dir, "B").exists() or receipt_path(run_dir, "J").exists():
            raise PilotError("reprise ambiguë: B ou J existe déjà")
        prefix = load_resume_prefix(run_dir, genesis_sha)
        b_directory = nodes_directory / "B"
        if b_directory.is_symlink():
            raise PilotError("périmètre B non engagé invalide")
        if b_directory.exists():
            if not b_directory.is_dir():
                raise PilotError("périmètre B non engagé invalide")
            shutil.rmtree(b_directory)
            sync_directory(b_directory.parent)
        d, s = prefix["D"], prefix["S"]
    else:
        d = execute_d(run_dir, genesis, genesis_sha)
        s = execute_s(run_dir, genesis, genesis_sha, d)
        if stop_after_s:
            return {"state": "STOPPED_AFTER_S", "last_closed_node": "S", "writer_pid": os.getpid()}
    try:
        branch_receipt = execute_branch(
            run_dir,
            genesis,
            genesis_sha,
            d,
            interrupt_before_receipt=fault_injection == "interrupt-before-b-receipt",
        )
    except ControlledStop:
        return {
            "state": "STOPPED_DURING_B_RECEIPT",
            "last_closed_node": "S",
            "uncommitted_node": "B",
            "writer_pid": os.getpid(),
        }
    execute_j(
        run_dir,
        genesis,
        genesis_sha,
        s,
        branch_receipt,
        invalid_output=fault_injection == "invalid-j-output",
    )
    return {
        "state": "EXECUTION_COMPLETE_PENDING_TERMINAL_VERIFICATION",
        "last_closed_node": "J",
        "writer_pid": os.getpid(),
        "replayed_nodes": [],
        "first_executed_node": "B" if resume else "D",
        "resume_checkpoint_validation": "canonical-hash-and-stored-links-only" if resume else None,
    }


def expected_output(run_dir: Path, genesis: dict[str, Any], node: str, receipts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    route = genesis["requested_route"]
    if node == "D":
        return {"route": route, "selected_nodes": list(ROUTES[route]), "edges": list(EDGES[route])}
    if node == "S":
        return source_output()
    if node == "A":
        return verify_canonical_u025()
    if node == "B":
        proof_dir = run_dir / "nodes" / "B" / "u025"
        result, read_only = verify_u025_read_only(proof_dir)
        canonical_result = verify_canonical_u025()
        if result["root_sha256"] != canonical_result["u025_root_sha256"]:
            raise PilotError("racine B divergente")
        return {
            "u025_root_sha256": result["root_sha256"],
            "u025_source_v2_root_sha256": result["source_v2_root_sha256"],
            "u025_conclusion": result["conclusion"],
            "reconstruction_tree_sha256": tree_fingerprint(proof_dir),
            "canonical_tree_sha256": canonical_result["canonical_tree_sha256"],
            "read_only": read_only,
            "reconstruction_temporary_directory_calls": 6,
            "reconstruction_temporary_scope": "nodes/B/u025/.pilot-temporary",
            "temporary_writes_outside_b": 0,
        }
    s, branch_receipt = receipts["S"], receipts[route]
    aggregate = {
        "route": route,
        "selected_nodes": list(ROUTES[route]),
        "parent_output_sha256s": {"S": s["output_sha256"], route: branch_receipt["output_sha256"]},
        "consumed_graph_edges": list(EDGES[route]),
    }
    return {**aggregate, "aggregate_sha256": digest(canonical(aggregate))}


def expected_parents(route: str, node: str, receipts: dict[str, dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    if node == "D":
        return {}, []
    if node == "S":
        return {"D": receipts["D"]["receipt_sha256"]}, ["D->S"]
    if node == route:
        return {"D": receipts["D"]["receipt_sha256"]}, [f"D->{route}"]
    return {"S": receipts["S"]["receipt_sha256"], route: receipts[route]["receipt_sha256"]}, ["S->J", f"{route}->J"]


def validate_node(run_dir: Path, genesis: dict[str, Any], genesis_sha: str, node: str, receipt: dict[str, Any], receipts: dict[str, dict[str, Any]] | None = None) -> None:
    receipts = receipts or {node: receipt}
    required = {
        "schema_version", "pilot_id", "node_id", "attempt", "state", "parent_receipts", "consumed_edges",
        "input_sha256", "output", "output_sha256", "evaluation", "time", "cost", "human_interventions",
        "effect", "owner", "writer_pid", "write_scope", "context", "receipt_sha256",
    }
    if set(receipt) != required:
        raise PilotError(f"champs du reçu {node} divergents")
    if receipt["schema_version"] != "graph-engineering-pilot-v1/node-receipt/v1" or receipt["pilot_id"] != PILOT_ID:
        raise PilotError(f"identité du reçu {node} divergente")
    if receipt["node_id"] != node or receipt["attempt"] != 1 or receipt["state"] != "evaluated":
        raise PilotError(f"état du nœud {node} non évalué")
    if receipt["effect"] != "none" or receipt["owner"] != OWNER or receipt["human_interventions"] != 0:
        raise PilotError(f"effet, propriétaire ou intervention du nœud {node} divergent")
    if receipt["cost"] != {"external_cost_usd": "0", "candidate_calls": 0, "provider_attempts": 0}:
        raise PilotError(f"coût du nœud {node} divergent")
    if receipt["context"] != {"genesis_sha256": genesis_sha, "missing_fields": [], "altered_fields": []}:
        raise PilotError(f"contexte du nœud {node} divergent")
    if not isinstance(receipt["writer_pid"], int) or receipt["writer_pid"] <= 0:
        raise PilotError(f"processus écrivain du nœud {node} invalide")
    if set(receipt["time"]) != {"wall_seconds", "cpu_seconds"} or any(not isinstance(receipt["time"].get(field), (int, float)) or receipt["time"][field] < 0 for field in ("wall_seconds", "cpu_seconds")):
        raise PilotError(f"temps du nœud {node} invalide")
    expected_scope = [f"nodes/{node}/receipt.json"] if node != "B" else ["nodes/B/receipt.json", "nodes/B/u025/"]
    if receipt["write_scope"] != expected_scope:
        raise PilotError(f"périmètre d'écriture du nœud {node} divergent")
    evaluation = receipt["evaluation"]
    if evaluation != {"contract": CONTRACTS[node], "contract_sha256": digest(canonical(CONTRACTS[node])), "verdict": "PASS"}:
        raise PilotError(f"évaluation du nœud {node} divergente")
    parents, edges = expected_parents(genesis["requested_route"], node, receipts)
    if receipt["parent_receipts"] != parents or receipt["consumed_edges"] != edges:
        raise PilotError(f"parents ou arêtes du nœud {node} divergents")
    if receipt["input_sha256"] != input_sha256(genesis_sha, parents):
        raise PilotError(f"entrée du nœud {node} divergente")
    output = expected_output(run_dir, genesis, node, receipts)
    if receipt["output"] != output or receipt["output_sha256"] != digest(canonical(output)):
        raise PilotError(f"sortie du nœud {node} divergente")


def terminal_verdict(run_dir: Path) -> dict[str, Any]:
    before = scope_snapshot(run_dir)
    try:
        if (run_dir / "terminal.json").exists() or (run_dir / "final-state.json").exists():
            raise PilotError("marqueur terminal non autorisé")
        genesis_path = run_dir / "genesis.json"
        genesis = read_json(genesis_path)
        expected_genesis = genesis_value(genesis.get("run_id", ""), genesis.get("scenario", ""), genesis.get("requested_route", ""))
        if genesis != expected_genesis or genesis_path.read_bytes() != canonical(expected_genesis):
            raise PilotError("genèse non canonique ou divergente")
        route = genesis["requested_route"]
        selected = set(ROUTES[route])
        if {path.name for path in run_dir.iterdir()} != {"genesis.json", "nodes"}:
            raise PilotError("état racine ambigu")
        if {path.name for path in (run_dir / "nodes").iterdir()} != selected:
            raise PilotError("répertoire de nœud inattendu")
        for node in selected:
            expected_children = {"receipt.json", "u025"} if node == "B" else {"receipt.json"}
            if {path.name for path in (run_dir / "nodes" / node).iterdir()} != expected_children:
                raise PilotError(f"état ambigu dans le nœud {node}")
        observed = {path.parent.name for path in (run_dir / "nodes").glob("*/receipt.json")}
        if observed != selected:
            raise PilotError(f"ensemble des nœuds divergent: attendu={sorted(selected)} observé={sorted(observed)}")
        receipts = {node: load_receipt(run_dir, node) for node in ROUTES[route]}
        genesis_sha = digest(canonical(genesis))
        for node in ROUTES[route]:
            validate_node(run_dir, genesis, genesis_sha, node, receipts[node], receipts)
        consumed = [edge for node in ROUTES[route] for edge in receipts[node]["consumed_edges"]]
        if sorted(consumed) != sorted(EDGES[route]) or len(consumed) != 4:
            raise PilotError("jointure ou arêtes consommées divergentes")
        if len(receipts["J"]["parent_receipts"]) != 2 or set(receipts["J"]["parent_receipts"]) != {"S", route}:
            raise PilotError("la jointure n'a pas exactement deux parents distincts")
        result = {
            "verdict": "PASS_PILOTE_LOCAL",
            "route": route,
            "selected_nodes": list(ROUTES[route]),
            "terminal_root_sha256": receipts["J"]["output"]["aggregate_sha256"],
            "false_terminal_accepted": False,
        }
    except (PilotError, u025.InvalidProof, KeyError, TypeError, ValueError) as error:
        result = {"verdict": "HOLD_PILOTE_LOCAL", "error": str(error), "false_terminal_accepted": False}
    after = scope_snapshot(run_dir)
    if after != before:
        return {"verdict": "HOLD_PILOTE_LOCAL", "error": "le vérificateur terminal a écrit", "false_terminal_accepted": False}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--scenario", choices=("S1", "S2"), required=True)
    run_parser.add_argument("--route", choices=("A", "B"), required=True)
    run_parser.add_argument("--stop-after-s", action="store_true")
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument(
        "--fault-injection",
        choices=("invalid-j-output", "interrupt-before-b-receipt"),
    )
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run_graph(
                args.run_dir,
                args.scenario,
                args.route,
                stop_after_s=args.stop_after_s,
                resume=args.resume,
                fault_injection=args.fault_injection,
            )
            exit_code = 0
        else:
            result = terminal_verdict(args.run_dir)
            exit_code = 0 if result["verdict"] == "PASS_PILOTE_LOCAL" else 1
    except (PilotError, u025.InvalidProof) as error:
        result, exit_code = {"state": "HOLD_PILOTE_LOCAL", "error": str(error)}, 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
