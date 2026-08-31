#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools import graph_engineering_pilot_v1 as v1
from tools import graph_engineering_v2_2 as ge

RESUME_PROMPT = (
    "Continue la même tâche dans cette session. Termine le critère du prompt initial, "
    "reste dans le même périmètre d’écriture et arrête-toi dès que le résultat demandé est prouvé."
)


def session_roots_default() -> list[Path]:
    base = Path.home() / ".codex"
    return [base / "sessions", base / "archived_sessions"]


def observe_session(
    session_id: str,
    contract: dict[str, Any],
    *,
    roots: list[Path] | None = None,
) -> dict[str, Any]:
    matches: list[Path] = []
    for root in roots or session_roots_default():
        if root.is_dir():
            matches.extend(root.rglob(f"*{session_id}.jsonl"))
    matches = sorted({path.resolve() for path in matches})
    if len(matches) != 1:
        raise ge.GraphHold("session Codex attestée absente ou ambiguë")
    path = matches[0]
    meta_ids: set[str] = set()
    contexts: list[dict[str, Any]] = []
    for line in path.read_bytes().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ge.GraphHold("journal de session Codex illisible") from error
        if event.get("type") == "session_meta":
            payload = event.get("payload") or {}
            observed_id = payload.get("id")
            if isinstance(observed_id, str):
                meta_ids.add(observed_id)
        elif event.get("type") == "turn_context":
            payload = event.get("payload")
            if isinstance(payload, dict):
                contexts.append(payload)
    expected_cwd = str(ge.worktree_path(contract) / contract["scope"]["agent_root"])
    if meta_ids != {session_id} or not contexts:
        raise ge.GraphHold("identité de session Codex non attestée")
    models = {context.get("model") for context in contexts}
    cwd_values = {context.get("cwd") for context in contexts}
    sandbox_types = {
        context.get("sandbox_policy", {}).get("type")
        for context in contexts
        if isinstance(context.get("sandbox_policy"), dict)
    }
    network_values = {
        context.get("sandbox_policy", {}).get("network_access")
        for context in contexts
        if isinstance(context.get("sandbox_policy"), dict)
    }
    if models != {contract["harness"]["model_expected"]}:
        raise ge.GraphHold("modèle Codex observé divergent")
    if cwd_values != {expected_cwd}:
        raise ge.GraphHold("cwd de session Codex divergent")
    if sandbox_types != {"workspace-write"}:
        raise ge.GraphHold("confinement Codex non attesté")
    if network_values - {False, None}:
        raise ge.GraphHold("réseau agent autorisé")
    return {
        "path": str(path),
        "sha256": ge.digest(path.read_bytes()),
        "session_id": session_id,
        "models": sorted(models),
        "cwd": expected_cwd,
        "sandbox": "workspace-write",
        "network_access": False if False in network_values else None,
        "turn_contexts": len(contexts),
    }


def command_for(contract: dict[str, Any], *, resume: bool, session_id: str | None) -> list[str]:
    binary = contract["harness"]["binary_path"]
    model = contract["harness"]["model_expected"]
    agent_root = str(ge.worktree_path(contract) / contract["scope"]["agent_root"])
    if resume:
        if not session_id:
            raise ge.GraphHold("session attestée requise pour reprendre")
        return [binary, "exec", "resume", "--model", model, "--json", session_id, "-"]
    return [binary, "exec", "--model", model, "--sandbox", "workspace-write", "--cd", agent_root, "--json", "-"]


def adapter_dir(contract: dict[str, Any]) -> Path:
    return ge.run_dir(contract) / "adapter"


def session_receipt_path(contract: dict[str, Any]) -> Path:
    return adapter_dir(contract) / "session.json"


def load_session_receipt(contract: dict[str, Any], contract_sha256: str) -> dict[str, Any]:
    receipt = ge.read_object(session_receipt_path(contract))
    if receipt != {
        "schema_version": f"{ge.SCHEMA}/adapter-session/v1",
        "contract_sha256": contract_sha256,
        "run_id": contract["run_id"],
        "session_id": receipt.get("session_id"),
    } or not isinstance(receipt.get("session_id"), str) or not receipt["session_id"]:
        raise ge.GraphHold("reçu de session divergent")
    return receipt


def validate_scope(
    contract: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    if before["head"] != after["head"] or before["branch"] != after["branch"]:
        raise ge.GraphHold("HEAD ou branche modifié par l’agent")
    if before["branch_tip"] != after["branch_tip"] or before["index_sha256"] != after["index_sha256"]:
        raise ge.GraphHold("index ou référence Git modifié par l’agent")
    if after["index_changed"] or after["conflicts"]:
        raise ge.GraphHold("index agent modifié ou conflictuel")
    allowed = set(contract["scope"]["agent_paths"])
    if not set(after["changed_paths"]).issubset(allowed):
        raise ge.GraphHold("écriture agent hors périmètre")
    worktree = ge.worktree_path(contract)
    for raw in contract["scope"]["agent_paths"]:
        ge.checked_path(worktree, ge.relative_path(raw, "agent_paths"), kind="file")


def invocation_files(contract: dict[str, Any]) -> list[Path]:
    directory = adapter_dir(contract) / "invocations"
    return sorted(directory.glob("*.json")) if directory.exists() else []


def read_invocation_starts(contract: dict[str, Any]) -> list[dict[str, Any]]:
    starts = []
    for path in invocation_files(contract):
        if path.name.endswith("-start.json"):
            starts.append(ge.read_object(path))
    return sorted(starts, key=lambda item: item["invocation"])


def artifact_hashes(contract: dict[str, Any]) -> dict[str, str]:
    directory = adapter_dir(contract)
    return {
        path.relative_to(directory).as_posix(): ge.digest(path.read_bytes())
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }


def persist_session(contract: dict[str, Any], contract_sha256: str, session_id: str) -> None:
    path = session_receipt_path(contract)
    expected = {
        "schema_version": f"{ge.SCHEMA}/adapter-session/v1",
        "contract_sha256": contract_sha256,
        "run_id": contract["run_id"],
        "session_id": session_id,
    }
    if path.exists():
        if ge.read_object(path) != expected:
            raise ge.GraphHold("second session_id refusé")
        return
    v1.write_new(path, expected)


def stream_agent(
    contract: dict[str, Any],
    contract_sha256: str,
    command: list[str],
    invocation: int,
    prompt: bytes,
    *,
    expected_session_id: str | None,
    interrupt_after_session: bool,
) -> tuple[int, str | None, Path, Path, bool]:
    directory = adapter_dir(contract)
    stdout_path = directory / f"stdout-{invocation}.jsonl"
    stderr_path = directory / f"stderr-{invocation}.log"
    cwd = ge.worktree_path(contract) / contract["scope"]["agent_root"]
    observed_session_id: str | None = None
    interrupted = False
    with TemporaryDirectory(prefix="ge22-agent-cache-") as cache_directory:
        environment = dict(os.environ)
        environment.update({
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": str(Path(cache_directory) / "pycache"),
            "UV_CACHE_DIR": str(Path(cache_directory) / "uv"),
            "XDG_CACHE_HOME": str(Path(cache_directory) / "xdg"),
        })
        with stdout_path.open("xb") as stdout_stream, stderr_path.open("xb") as stderr_stream:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr_stream,
                env=environment,
            )
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(prompt)
            process.stdin.close()
            for line in iter(process.stdout.readline, b""):
                stdout_stream.write(line)
                stdout_stream.flush()
                os.fsync(stdout_stream.fileno())
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "thread.started":
                    continue
                session_id = event.get("thread_id")
                if not isinstance(session_id, str) or not session_id:
                    process.terminate()
                    raise ge.GraphHold("thread.started sans session_id")
                if observed_session_id not in {None, session_id}:
                    process.terminate()
                    raise ge.GraphHold("plusieurs session_id dans une invocation")
                if expected_session_id is not None and session_id != expected_session_id:
                    process.terminate()
                    raise ge.GraphHold("second session_id refusé")
                observed_session_id = session_id
                persist_session(contract, contract_sha256, session_id)
                if interrupt_after_session:
                    process.terminate()
                    interrupted = True
                    break
            if interrupted:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            else:
                process.stdout.read()
                process.wait()
            process.stdout.close()
            stdout_stream.flush()
            stderr_stream.flush()
            os.fsync(stdout_stream.fileno())
            os.fsync(stderr_stream.fileno())
            return process.returncode, observed_session_id, stdout_path, stderr_path, interrupted


def run_adapter(
    contract_path: Path,
    *,
    resume: bool,
    interrupt_after_session: bool,
    session_roots: list[Path] | None = None,
) -> dict[str, Any]:
    contract, contract_sha256 = ge.load_contract(contract_path)
    if contract["route"] != "B":
        raise ge.GraphHold("l’adaptateur exige la route B")
    ge.load_writer_lock(contract, contract_sha256)
    _, s = ge.load_prefix(contract, contract_sha256)
    directory = adapter_dir(contract)
    directory.mkdir(exist_ok=True)
    if (directory / "manifest.json").exists():
        raise ge.GraphHold("invocation supplémentaire après manifeste refusée")
    starts = read_invocation_starts(contract)
    session_id: str | None = None
    if resume:
        if len(starts) != 1:
            raise ge.GraphHold("reprise sans unique invocation interrompue")
        session_id = load_session_receipt(contract, contract_sha256)["session_id"]
        interruption = directory / "invocations" / "1-interrupted.json"
        if not interruption.is_file() or (directory / "invocations" / "1-finish.json").exists():
            raise ge.GraphHold("interruption agent durable absente")
        invocation = 2
    else:
        if starts or session_receipt_path(contract).exists():
            raise ge.GraphHold("invocation précédente non reprenable")
        invocation = 1
    if invocation > 2:
        raise ge.GraphHold("invocation adaptateur supplémentaire refusée")
    initial_before = s["output"]["repository_state"]
    current_before = ge.assert_repository_identity(contract, clean=not resume)
    if not resume and current_before != initial_before:
        raise ge.GraphHold("état initial divergent du nœud S")
    if resume:
        validate_scope(contract, initial_before, current_before)
    command = command_for(contract, resume=resume, session_id=session_id)
    start = {
        "schema_version": f"{ge.SCHEMA}/adapter-invocation-start/v1",
        "contract_sha256": contract_sha256,
        "run_id": contract["run_id"],
        "invocation": invocation,
        "mode": "resume" if resume else "initial",
        "command": command,
        "cwd": str(ge.worktree_path(contract) / contract["scope"]["agent_root"]),
        "prompt_sha256": ge.digest(RESUME_PROMPT.encode()) if resume else contract["prompt"]["sha256"],
        "worktree_state": current_before,
        "started_utc": ge.utc_now(),
    }
    invocation_directory = directory / "invocations"
    v1.write_new(invocation_directory / f"{invocation}-start.json", start)
    prompt = RESUME_PROMPT.encode() if resume else (
        ge.worktree_path(contract) / contract["prompt"]["path"]
    ).read_bytes()
    with ge.operation(contract, contract_sha256, f"adapter-{invocation}"):
        returncode, observed_session_id, stdout_path, stderr_path, interrupted = stream_agent(
            contract,
            contract_sha256,
            command,
            invocation,
            prompt,
            expected_session_id=session_id,
            interrupt_after_session=interrupt_after_session,
        )
        if observed_session_id is None:
            raise ge.GraphHold("session_id agent non observé")
        after = ge.assert_repository_identity(contract, clean=False)
        validate_scope(contract, initial_before, after)
        if interrupted:
            interruption = {
                "schema_version": f"{ge.SCHEMA}/adapter-interruption/v1",
                "contract_sha256": contract_sha256,
                "run_id": contract["run_id"],
                "invocation": invocation,
                "session_id": observed_session_id,
                "process_returncode": returncode,
                "worktree_state": after,
                "interrupted_utc": ge.utc_now(),
            }
            v1.write_new(invocation_directory / f"{invocation}-interrupted.json", interruption)
            return {
                "state": "INTERRUPTED_AGENT_SESSION",
                "session_id": observed_session_id,
                "same_session_resume_required": True,
            }
        finish = {
            "schema_version": f"{ge.SCHEMA}/adapter-invocation-finish/v1",
            "contract_sha256": contract_sha256,
            "run_id": contract["run_id"],
            "invocation": invocation,
            "session_id": observed_session_id,
            "exit_code": returncode,
            "stdout_sha256": ge.digest(stdout_path.read_bytes()),
            "stderr_sha256": ge.digest(stderr_path.read_bytes()),
            "worktree_state": after,
            "ended_utc": ge.utc_now(),
        }
        v1.write_new(invocation_directory / f"{invocation}-finish.json", finish)
        if returncode != 0:
            raise ge.GraphHold(f"harnais agent en échec: {returncode}")
        session = observe_session(observed_session_id, contract, roots=session_roots)
        starts = read_invocation_starts(contract)
        command_history = [item["command"] for item in starts]
        logs_stdout = [directory / f"stdout-{number}.jsonl" for number in range(1, invocation + 1)]
        logs_stderr = [directory / f"stderr-{number}.log" for number in range(1, invocation + 1)]
        artifacts = artifact_hashes(contract)
        base = {
            "schema_version": f"{ge.SCHEMA}/adapter-manifest/v1",
            "contract_sha256": contract_sha256,
            "run_id": contract["run_id"],
            "node_id": "B",
            "logical_attempt": 1,
            "producer_sha256": contract["executables"]["adapter"]["sha256"],
            "prompt_sha256": contract["prompt"]["sha256"],
            "command_history": command_history,
            "cwd": str(ge.worktree_path(contract) / contract["scope"]["agent_root"]),
            "confinement": {
                "mode": "codex-workspace-write",
                "write_root": str(ge.worktree_path(contract) / contract["scope"]["agent_root"]),
                "network_access": False,
            },
            "harness": contract["harness"]["version"],
            "model_requested": contract["harness"]["model_expected"],
            "model_observed": session["models"][0],
            "session_id": observed_session_id,
            "session_rollout": session,
            "started_utc": starts[0]["started_utc"],
            "ended_utc": finish["ended_utc"],
            "exit_code": 0,
            "stdout_sha256": ge.digest(b"".join(path.read_bytes() for path in logs_stdout)),
            "stderr_sha256": ge.digest(b"".join(path.read_bytes() for path in logs_stderr)),
            "worktree_before": initial_before,
            "worktree_after": after,
            "agent_logical_sessions": 1,
            "adapter_process_invocations": invocation,
            "benchmark_candidate_calls": 0,
            "artifact_hashes": artifacts,
        }
        manifest = {**base, "manifest_sha256": ge.digest(ge.canonical(base))}
        v1.write_new(directory / "manifest.json", manifest)
        return {
            "state": "DURABLE_AGENT_ATTEMPT_READY_FOR_GRAPH_CLOSE",
            "manifest_sha256": manifest["manifest_sha256"],
            "session_id": observed_session_id,
            "adapter_process_invocations": invocation,
        }


def validate_manifest_session(
    contract: dict[str, Any],
    manifest: dict[str, Any],
    *,
    roots: list[Path] | None = None,
) -> dict[str, Any]:
    observed = observe_session(manifest["session_id"], contract, roots=roots)
    if observed != manifest["session_rollout"]:
        raise ge.GraphHold("journal de session divergent du manifeste")
    if manifest["confinement"] != {
        "mode": "codex-workspace-write",
        "write_root": str(ge.worktree_path(contract) / contract["scope"]["agent_root"]),
        "network_access": False,
    }:
        raise ge.GraphHold("confinement du manifeste divergent")
    starts = read_invocation_starts(contract)
    expected_commands = []
    session_id = None
    for item in starts:
        resume = item["mode"] == "resume"
        if resume:
            session_id = manifest["session_id"]
        expected_commands.append(command_for(contract, resume=resume, session_id=session_id))
    if manifest["command_history"] != expected_commands:
        raise ge.GraphHold("commande agent divergente")
    if manifest["adapter_process_invocations"] == 2:
        interruption = adapter_dir(contract) / "invocations" / "1-interrupted.json"
        if not interruption.is_file() or ge.read_object(interruption).get("session_id") != manifest["session_id"]:
            raise ge.GraphHold("reprise sans interruption de la même session")
    return observed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--interrupt-after-session", action="store_true")
    args = parser.parse_args()
    try:
        if args.resume and args.interrupt_after_session:
            raise ge.GraphHold("la reprise ne peut pas être réinterrompue")
        result = run_adapter(
            args.contract,
            resume=args.resume,
            interrupt_after_session=args.interrupt_after_session,
        )
        exit_code = 75 if result.get("state") == "INTERRUPTED_AGENT_SESSION" else 0
    except (ge.GraphHold, v1.PilotError, OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError) as error:
        result, exit_code = ge.hold(error), 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
