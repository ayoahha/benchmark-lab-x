#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

from tools import graph_engineering_pilot_v1 as v1
from tools import graph_engineering_v2_2 as ge
from tools import graph_engineering_v2_2_adapter as adapter


def validate_operation_history(
    contract: dict[str, Any],
    contract_sha256: str,
    expected_names: list[str],
) -> list[dict[str, Any]]:
    directory = ge.run_dir(contract) / "operations"
    if not directory.is_dir() or directory.is_symlink():
        raise ge.GraphHold("historique d’opérations absent ou ambigu")
    paths = sorted(directory.iterdir())
    if any(path.is_symlink() or not path.is_file() or path.suffix != ".json" for path in paths):
        raise ge.GraphHold("historique d’opérations ambigu")
    if len(paths) != len(expected_names):
        raise ge.GraphHold("nombre d’opérations divergent")
    history = []
    for number, (path, expected_name) in enumerate(zip(paths, expected_names, strict=True), 1):
        expected_filename = f"{number:03d}-{expected_name}.json"
        value = ge.read_object(path)
        if path.name != expected_filename or value != {
            "schema_version": f"{ge.SCHEMA}/operation/v1",
            "contract_sha256": contract_sha256,
            "number": number,
            "name": expected_name,
            "pid": value.get("pid"),
            "started_utc": value.get("started_utc"),
        }:
            raise ge.GraphHold("opération divergente")
        if not isinstance(value["pid"], int) or value["pid"] <= 0:
            raise ge.GraphHold("pid d’opération invalide")
        history.append(value)
    return history


def scan_artifacts(run_directory: Path) -> set[str]:
    files: set[str] = set()
    for directory, names, filenames in os.walk(run_directory, topdown=True, followlinks=False):
        directory_path = Path(directory)
        for name in list(names):
            path = directory_path / name
            if stat.S_ISLNK(path.lstat().st_mode):
                raise ge.GraphHold(f"lien symbolique dans les artefacts: {path}")
        for name in filenames:
            path = directory_path / name
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise ge.GraphHold(f"artefact non régulier: {path}")
            files.add(path.relative_to(run_directory).as_posix())
    return files


def expected_artifacts(
    contract: dict[str, Any],
    manifest: dict[str, Any] | None,
    operation_names: list[str],
    *,
    evaluated: bool,
) -> set[str]:
    route = contract["route"]
    expected = {
        "request.json",
        "contract.json",
        "genesis.json",
        "nodes/D/receipt.json",
        "nodes/S/receipt.json",
        f"nodes/{route}/receipt.json",
        "nodes/J/receipt.json",
    }
    expected.update(
        f"operations/{number:03d}-{name}.json"
        for number, name in enumerate(operation_names, 1)
    )
    if manifest is not None:
        expected.add("adapter/manifest.json")
        expected.update(f"adapter/{path}" for path in manifest["artifact_hashes"])
    if evaluated:
        expected.update({"evaluation/results.json", "pilot-report.json"})
    return expected


def validate_graph(
    contract: dict[str, Any],
    contract_sha256: str,
    *,
    session_roots: list[Path] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    d, s = ge.load_prefix(contract, contract_sha256)
    route = contract["route"]
    manifest = None
    if route == "A":
        branch = ge.load_receipt(contract, contract_sha256, "A")
        state = ge.assert_repository_identity(contract, clean=True)
        expected_output = {
            "agent_invoked": False,
            "before_state": s["output"]["repository_state"],
            "after_state": state,
        }
        if (
            branch["parent_receipts"] != {"D": d["receipt_sha256"]}
            or branch["consumed_edges"] != ["D->A"]
            or branch["output"] != expected_output
        ):
            raise ge.GraphHold("reçu A divergent")
    else:
        manifest = ge.load_adapter_manifest(contract, contract_sha256)
        adapter.validate_manifest_session(contract, manifest, roots=session_roots)
        branch = ge.load_receipt(contract, contract_sha256, "B")
        expected_output = {
            "manifest_sha256": manifest["manifest_sha256"],
            "session_id": manifest["session_id"],
            "worktree_after_sha256": ge.digest(ge.canonical(manifest["worktree_after"])),
            "agent_logical_sessions": 1,
            "adapter_process_invocations": manifest["adapter_process_invocations"],
            "benchmark_candidate_calls": 0,
        }
        if (
            branch["parent_receipts"] != {"D": d["receipt_sha256"]}
            or branch["consumed_edges"] != ["D->B"]
            or branch["output"] != expected_output
        ):
            raise ge.GraphHold("reçu B divergent")
    join = ge.load_receipt(contract, contract_sha256, "J")
    parents = {"S": s["receipt_sha256"], route: branch["receipt_sha256"]}
    join_output = {"route": route, "parents": parents, "consumed_edges": ge.GRAPH["edges"][route]}
    if (
        join["parent_receipts"] != parents
        or join["consumed_edges"] != ["S->J", f"{route}->J"]
        or join["output"] != join_output
        or len(join["parent_receipts"]) != 2
    ):
        raise ge.GraphHold("jointure J divergente")
    receipts = {node: ge.load_receipt(contract, contract_sha256, node) for node in ge.GRAPH["routes"][route]}
    return manifest, receipts


def parse_test_count(command: dict[str, Any], stdout: bytes, stderr: bytes) -> int | None:
    if command["test_parser"] == "none":
        return None
    matches = re.findall(rb"Ran (\d+) tests?", stdout + b"\n" + stderr)
    if len(matches) != 1:
        raise ge.GraphHold(f"nombre de tests non observable: {command['id']}")
    return int(matches[0])


def run_acceptance(
    contract: dict[str, Any],
    expected_state: dict[str, Any],
) -> list[dict[str, Any]]:
    worktree = ge.worktree_path(contract)
    results = []
    with TemporaryDirectory(prefix="ge22-evaluator-cache-") as cache_directory:
        environment = dict(os.environ)
        environment.update({
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": str(Path(cache_directory) / "pycache"),
            "UV_CACHE_DIR": str(Path(cache_directory) / "uv"),
            "XDG_CACHE_HOME": str(Path(cache_directory) / "xdg"),
            "GRAPH_ENGINEERING_PILOT_V1_OUTPUT": str(
                Path(cache_directory) / "graph-engineering-pilot-v1"
            ),
        })
        for command in contract["acceptance"]:
            started = perf_counter()
            process = subprocess.run(
                command["argv"],
                cwd=worktree / command["cwd"],
                env=environment,
                capture_output=True,
                check=False,
            )
            wall_seconds = perf_counter() - started
            state_after = ge.repository_state(worktree, ge.runner_root_path(contract))
            if state_after != expected_state:
                raise ge.GraphHold(f"la validation {command['id']} a modifié le candidat")
            test_count = parse_test_count(command, process.stdout, process.stderr)
            result = {
                "id": command["id"],
                "argv": command["argv"],
                "cwd": command["cwd"],
                "exit_code": process.returncode,
                "wall_seconds": wall_seconds,
                "stdout_sha256": ge.digest(process.stdout),
                "stderr_sha256": ge.digest(process.stderr),
                "stdout": process.stdout.decode(errors="replace"),
                "stderr": process.stderr.decode(errors="replace"),
                "tests_discovered": test_count,
            }
            results.append(result)
            if process.returncode != 0:
                raise ge.GraphHold(f"validation en échec: {command['id']}")
    return results


def load_existing_report(contract: dict[str, Any], contract_sha256: str) -> dict[str, Any]:
    path = ge.run_dir(contract) / "pilot-report.json"
    report = ge.read_object(path)
    stored = report.get("report_sha256")
    base = {key: value for key, value in report.items() if key != "report_sha256"}
    if (
        stored != ge.digest(ge.canonical(base))
        or report.get("schema_version") != f"{ge.SCHEMA}/report/v1"
        or report.get("contract_sha256") != contract_sha256
        or report.get("verdict") != ge.VERDICT_READY
    ):
        raise ge.GraphHold("rapport terminal divergent")
    results = ge.read_object(ge.run_dir(contract) / "evaluation" / "results.json")
    if report.get("evaluation_results_sha256") != ge.digest(ge.canonical(results)):
        raise ge.GraphHold("résultats d’évaluation divergents")
    return report


def evaluate(
    contract_path: Path,
    *,
    session_roots: list[Path] | None = None,
) -> dict[str, Any]:
    contract, contract_sha256 = ge.load_contract(contract_path)
    ge.load_writer_lock(contract, contract_sha256)
    if (ge.run_dir(contract) / "operation.active.json").exists():
        raise ge.GraphHold("verrou d’opération concurrent ou potentiellement orphelin")
    manifest, receipts = validate_graph(contract, contract_sha256, session_roots=session_roots)
    operation_names = ["prepare"]
    if manifest is not None:
        operation_names.extend(
            f"adapter-{number}" for number in range(1, manifest["adapter_process_invocations"] + 1)
        )
        operation_names.append("close-agent")
    report_path = ge.run_dir(contract) / "pilot-report.json"
    evaluated = report_path.exists()
    if evaluated:
        operation_names.append("evaluate")
    validate_operation_history(contract, contract_sha256, operation_names)
    actual = scan_artifacts(ge.run_dir(contract))
    expected = expected_artifacts(contract, manifest, operation_names, evaluated=evaluated)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ge.GraphHold(f"artefacts divergents: manquants={missing} supplémentaires={extra}")
    if evaluated:
        report = load_existing_report(contract, contract_sha256)
        return {
            "verdict": ge.VERDICT_READY,
            "contract_sha256": contract_sha256,
            "report_sha256": report["report_sha256"],
            "reused_terminal_report": True,
        }
    expected_state = (
        manifest["worktree_after"]
        if manifest is not None
        else receipts[contract["route"]]["output"]["after_state"]
    )
    before = ge.assert_repository_identity(contract, clean=contract["route"] == "A", expected_state=expected_state)
    with ge.operation(contract, contract_sha256, "evaluate"):
        results = run_acceptance(contract, before)
        after = ge.assert_repository_identity(contract, clean=contract["route"] == "A", expected_state=before)
        results_object = {
            "schema_version": f"{ge.SCHEMA}/evaluation-results/v1",
            "contract_sha256": contract_sha256,
            "candidate_state_sha256": ge.digest(ge.canonical(before)),
            "state_unchanged": before == after,
            "commands": results,
        }
        v1.write_new(ge.run_dir(contract) / "evaluation" / "results.json", results_object)
        tests_discovered = {
            result["id"]: result["tests_discovered"]
            for result in results
            if result["tests_discovered"] is not None
        }
        receipt_hashes = {node: receipt["receipt_sha256"] for node, receipt in receipts.items()}
        base = {
            "schema_version": f"{ge.SCHEMA}/report/v1",
            "verdict": ge.VERDICT_READY,
            "meaning": "Contrat et provenance cohérents, périmètres respectés, tentative durable, validations locales réussies et diff prêt pour Ayo",
            "contract_sha256": contract_sha256,
            "run_id": contract["run_id"],
            "task": contract["task"],
            "route": contract["route"],
            "graph": contract["graph"],
            "repository": contract["repository"],
            "candidate_state_sha256": ge.digest(ge.canonical(before)),
            "evaluation_start_matches_agent_end": manifest is None or before == manifest["worktree_after"],
            "receipt_sha256": receipt_hashes,
            "manifest_sha256": manifest["manifest_sha256"] if manifest else None,
            "session_id": manifest["session_id"] if manifest else None,
            "agent_logical_sessions": manifest["agent_logical_sessions"] if manifest else 0,
            "adapter_process_invocations": manifest["adapter_process_invocations"] if manifest else 0,
            "benchmark_candidate_calls": 0,
            "tests_discovered": tests_discovered,
            "acceptance": [
                {
                    key: result[key]
                    for key in (
                        "id", "argv", "cwd", "exit_code", "wall_seconds",
                        "stdout_sha256", "stderr_sha256", "tests_discovered",
                    )
                }
                for result in results
            ],
            "evaluation_results_sha256": ge.digest(ge.canonical(results_object)),
            "git_effects": {
                "agent_commits": 0,
                "pushes": 0,
                "pull_requests": 0,
                "merges": 0,
                "publications": 0,
            },
            "limits": [
                "Validation locale sur macOS et Codex CLI observé",
                "Aucune activation V2-alpha ni généralisation",
                "Le verrou reste actif jusqu’à la revue propriétaire",
            ],
            "created_utc": ge.utc_now(),
        }
        report = {**base, "report_sha256": ge.digest(ge.canonical(base))}
        v1.write_new(report_path, report)
    return {
        "verdict": ge.VERDICT_READY,
        "contract_sha256": contract_sha256,
        "report_sha256": report["report_sha256"],
        "tests_discovered": tests_discovered,
        "reused_terminal_report": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = evaluate(args.contract)
        exit_code = 0
    except (ge.GraphHold, v1.PilotError, OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError) as error:
        result, exit_code = ge.hold(error), 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
