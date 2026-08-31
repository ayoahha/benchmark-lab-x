#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from tools import graph_engineering_pilot_v1 as v1

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "benchmark-lab-x/graph-engineering-v2.2"
VERDICT_READY = "READY_FOR_OWNER_REVIEW_LOCAL"
VERDICT_HOLD = "HOLD_GRAPH_ENGINEERING_LOCAL"
GRAPH = {
    "nodes": ["D", "S", "A", "B", "J"],
    "routes": {
        "A": ["D", "S", "A", "J"],
        "B": ["D", "S", "B", "J"],
    },
    "edges": {
        "A": ["D->S", "D->A", "S->J", "A->J"],
        "B": ["D->S", "D->B", "S->J", "B->J"],
    },
}
EXECUTABLE_PATHS = {
    "runner": "tools/graph_engineering_v2_2.py",
    "helper_v1": "tools/graph_engineering_pilot_v1.py",
    "helper_v1_dependency": "tools/preuve_u025_p2_manual_v3.py",
    "adapter": "tools/graph_engineering_v2_2_adapter.py",
    "evaluator": "tools/graph_engineering_v2_2_evaluator.py",
}
EXTERNAL_EFFECTS_FORBIDDEN = [
    "benchmark_candidate_call",
    "commit",
    "push",
    "pull_request",
    "merge",
    "publication",
    "activation",
    "deployment",
]
SHELLS = {"bash", "dash", "fish", "sh", "zsh"}


class GraphHold(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return v1.canonical(value)


def digest(content: bytes) -> str:
    return v1.digest(content)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_object(path: Path) -> dict[str, Any]:
    value = v1.read_json(path)
    if path.read_bytes() != canonical(value):
        raise GraphHold(f"JSON non canonique: {path}")
    return value


def run_process(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[bytes]:
    try:
        process = subprocess.run(argv, cwd=cwd, capture_output=True, check=False)
    except (OSError, ValueError) as error:
        raise GraphHold(f"commande impossible: {argv[0]}") from error
    return process


def git_bytes(worktree: Path, *arguments: str, check: bool = True) -> bytes:
    process = run_process(["git", "-C", str(worktree), *arguments], worktree)
    if check and process.returncode != 0:
        detail = process.stderr.decode(errors="replace").strip()
        raise GraphHold(f"Git refuse {' '.join(arguments)}: {detail}")
    return process.stdout


def git_text(worktree: Path, *arguments: str) -> str:
    return git_bytes(worktree, *arguments).decode().strip()


def absolute_git_path(worktree: Path, *arguments: str) -> Path:
    return Path(git_text(worktree, "rev-parse", "--path-format=absolute", *arguments)).resolve()


def relative_path(value: object, field: str) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise GraphHold(f"chemin {field} invalide")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise GraphHold(f"chemin {field} non relatif ou traversant")
    return path


def inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def checked_path(
    root: Path,
    relative: Path,
    *,
    kind: str,
    allow_missing_leaf: bool = False,
) -> Path:
    root = root.resolve()
    current = root
    parts = relative.parts
    for index, part in enumerate(parts):
        current = current / part
        missing_leaf = allow_missing_leaf and index == len(parts) - 1 and not current.exists()
        if missing_leaf:
            continue
        try:
            metadata = current.lstat()
        except FileNotFoundError as error:
            raise GraphHold(f"chemin absent: {relative.as_posix()}") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise GraphHold(f"lien symbolique interdit: {relative.as_posix()}")
    resolved = current.resolve(strict=not allow_missing_leaf)
    if not inside(root, resolved):
        raise GraphHold(f"chemin hors dépôt: {relative.as_posix()}")
    if kind == "file" and not missing_leaf and not resolved.is_file():
        raise GraphHold(f"fichier attendu: {relative.as_posix()}")
    if kind == "directory" and not resolved.is_dir():
        raise GraphHold(f"dossier attendu: {relative.as_posix()}")
    return resolved


def parse_status(raw: bytes) -> tuple[list[str], bool, bool]:
    entries = raw.split(b"\0")
    changed: list[str] = []
    index_changed = False
    conflicts = False
    index = 0
    while index < len(entries) and entries[index]:
        entry = entries[index]
        if len(entry) < 4:
            raise GraphHold("état Git illisible")
        code = entry[:2].decode(errors="replace")
        path = entry[3:].decode(errors="surrogateescape")
        changed.append(path)
        index_changed = index_changed or code[0] not in {" ", "?"}
        conflicts = conflicts or "U" in code or code in {"AA", "DD", "AU", "UA", "DU", "UD"}
        if code[0] in {"R", "C"}:
            index += 1
            if index >= len(entries) or not entries[index]:
                raise GraphHold("renommage Git illisible")
            changed.append(entries[index].decode(errors="surrogateescape"))
        index += 1
    return sorted(set(changed)), index_changed, conflicts


def tree_sha256(worktree: Path, runner_root: Path) -> str:
    rows: list[list[object]] = []
    for directory, names, files in os.walk(worktree, topdown=True, followlinks=False):
        directory_path = Path(directory)
        relative_directory = directory_path.relative_to(worktree)
        kept_names = []
        for name in sorted(names):
            path = directory_path / name
            relative = path.relative_to(worktree)
            if relative == runner_root or runner_root in relative.parents:
                continue
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                rows.append([relative.as_posix(), "symlink", os.readlink(path)])
            else:
                kept_names.append(name)
        names[:] = kept_names
        for name in sorted(files):
            path = directory_path / name
            relative = path.relative_to(worktree)
            if relative == runner_root or runner_root in relative.parents:
                continue
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                rows.append([relative.as_posix(), "symlink", os.readlink(path)])
            elif stat.S_ISREG(metadata.st_mode):
                rows.append([
                    relative.as_posix(),
                    "file",
                    stat.S_IMODE(metadata.st_mode),
                    digest(path.read_bytes()),
                ])
            else:
                rows.append([relative.as_posix(), "special", metadata.st_mode])
        if relative_directory == Path(".") and ".git" in files:
            continue
    return digest(canonical(rows))


def repository_state(worktree: Path, runner_root: Path) -> dict[str, Any]:
    status_raw = git_bytes(worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    changed_paths, index_changed, status_conflicts = parse_status(status_raw)
    conflicts_raw = git_bytes(worktree, "ls-files", "-u")
    branch = git_text(worktree, "symbolic-ref", "--short", "HEAD")
    index_path = absolute_git_path(worktree, "--git-path", "index")
    return {
        "head": git_text(worktree, "rev-parse", "HEAD"),
        "branch": branch,
        "branch_tip": git_text(worktree, "rev-parse", f"refs/heads/{branch}"),
        "index_sha256": digest(index_path.read_bytes()),
        "status_sha256": digest(status_raw),
        "changed_paths": changed_paths,
        "index_changed": index_changed,
        "conflicts": status_conflicts or bool(conflicts_raw),
        "tree_sha256": tree_sha256(worktree, runner_root),
    }


def validate_acceptance(raw: object, worktree: Path) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise GraphHold("commandes d’acceptation absentes")
    commands: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"id", "argv", "cwd", "test_parser"}:
            raise GraphHold("commande d’acceptation invalide")
        identifier = item["id"]
        argv = item["argv"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise GraphHold("identité d’acceptation invalide")
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
            raise GraphHold(f"arguments d’acceptation invalides: {identifier}")
        if Path(argv[0]).name in SHELLS:
            raise GraphHold(f"shell libre interdit: {identifier}")
        cwd = relative_path(item["cwd"], f"acceptance.{identifier}.cwd")
        checked_path(worktree, cwd, kind="directory")
        if item["test_parser"] not in {"none", "unittest"}:
            raise GraphHold(f"parseur de tests inconnu: {identifier}")
        identifiers.add(identifier)
        commands.append({"id": identifier, "argv": argv, "cwd": cwd.as_posix(), "test_parser": item["test_parser"]})
    return commands


def request_value(path: Path) -> dict[str, Any]:
    value = read_object(path)
    required = {
        "run_id",
        "task",
        "canonical_repository",
        "worktree",
        "runner_root",
        "route",
        "prompt",
        "agent_root",
        "agent_paths",
        "immutable_paths",
        "acceptance",
        "harness",
    }
    if set(value) != required:
        raise GraphHold("champs de requête divergents")
    return value


def create_contract(request_path: Path) -> dict[str, Any]:
    request_path = request_path.resolve()
    request = request_value(request_path)
    if not isinstance(request["run_id"], str) or not request["run_id"]:
        raise GraphHold("run_id invalide")
    if not isinstance(request["task"], str) or not request["task"]:
        raise GraphHold("tâche invalide")
    if request["route"] not in {"A", "B"}:
        raise GraphHold("route inconnue")
    worktree = Path(request["worktree"]).resolve()
    canonical_repository = Path(request["canonical_repository"]).resolve()
    if not worktree.is_dir() or not canonical_repository.is_dir():
        raise GraphHold("dépôt ou worktree absent")
    if Path(git_text(worktree, "rev-parse", "--show-toplevel")).resolve() != worktree:
        raise GraphHold("worktree Git divergent")
    common_worktree = absolute_git_path(worktree, "--git-common-dir")
    common_canonical = absolute_git_path(canonical_repository, "--git-common-dir")
    if common_worktree != common_canonical:
        raise GraphHold("dépôt canonique et worktree ne partagent pas Git")
    runner_root = relative_path(request["runner_root"], "runner_root")
    if not runner_root.parts or runner_root.parts[0] != "runs":
        raise GraphHold("le périmètre runner doit rester sous runs/")
    run_dir = checked_path(worktree, runner_root, kind="directory")
    if request_path.parent != run_dir or request_path.name != "request.json":
        raise GraphHold("la requête doit être run_dir/request.json")
    prompt = relative_path(request["prompt"], "prompt")
    prompt_path = checked_path(worktree, prompt, kind="file")
    agent_root = relative_path(request["agent_root"], "agent_root")
    checked_path(worktree, agent_root, kind="directory")
    if runner_root == agent_root or runner_root in agent_root.parents or agent_root in runner_root.parents:
        raise GraphHold("périmètres agent et runner se chevauchent")
    raw_agent_paths = request["agent_paths"]
    if not isinstance(raw_agent_paths, list) or not raw_agent_paths:
        raise GraphHold("périmètre agent vide")
    agent_paths: list[str] = []
    for raw in raw_agent_paths:
        path = relative_path(raw, "agent_paths")
        checked_path(worktree, path, kind="file")
        if agent_root not in path.parents:
            raise GraphHold(f"fichier agent hors agent_root: {path}")
        agent_paths.append(path.as_posix())
    if len(set(agent_paths)) != len(agent_paths):
        raise GraphHold("périmètre agent dupliqué")
    raw_immutable = request["immutable_paths"]
    if not isinstance(raw_immutable, list):
        raise GraphHold("périmètre immuable invalide")
    immutable_paths = set(EXECUTABLE_PATHS.values()) | {prompt.as_posix()}
    for raw in raw_immutable:
        immutable_paths.add(relative_path(raw, "immutable_paths").as_posix())
    for raw in sorted(immutable_paths):
        path = relative_path(raw, "immutable_paths")
        checked_path(worktree, path, kind="file")
        if path.as_posix() in agent_paths or agent_root == path or agent_root in path.parents:
            raise GraphHold(f"fichier immuable dans le périmètre agent: {path}")
    acceptance = validate_acceptance(request["acceptance"], worktree)
    harness = request["harness"]
    if not isinstance(harness, dict) or set(harness) != {"kind", "binary", "model"}:
        raise GraphHold("harnais invalide")
    if harness["kind"] != "codex-exec" or not isinstance(harness["model"], str) or not harness["model"]:
        raise GraphHold("harnais ou modèle invalide")
    binary = shutil.which(harness["binary"])
    if binary is None:
        raise GraphHold("binaire du harnais absent")
    binary_path = Path(binary).resolve()
    if binary_path.is_symlink() or not binary_path.is_file():
        raise GraphHold("binaire du harnais ambigu")
    version_process = run_process([str(binary_path), "--version"], worktree)
    if version_process.returncode != 0:
        raise GraphHold("version du harnais non observable")
    state = repository_state(worktree, runner_root)
    if state["changed_paths"] or state["index_changed"] or state["conflicts"]:
        raise GraphHold("worktree non propre avant contrat")
    git_dir = absolute_git_path(worktree, "--git-dir")
    executables = {
        name: {"path": path, "sha256": digest((worktree / path).read_bytes())}
        for name, path in EXECUTABLE_PATHS.items()
    }
    contract = {
        "schema_version": f"{SCHEMA}/contract/v1",
        "run_id": request["run_id"],
        "task": request["task"],
        "route": request["route"],
        "graph": GRAPH,
        "repository": {
            "canonical": str(canonical_repository),
            "git_common_dir": str(common_worktree),
            "git_dir": str(git_dir),
            "worktree": str(worktree),
            "head": state["head"],
            "branch": state["branch"],
        },
        "request": {"path": str(request_path), "sha256": digest(request_path.read_bytes())},
        "executables": executables,
        "prompt": {"path": prompt.as_posix(), "sha256": digest(prompt_path.read_bytes())},
        "scope": {
            "agent_root": agent_root.as_posix(),
            "agent_paths": sorted(agent_paths),
            "runner_root": runner_root.as_posix(),
            "immutable_paths": sorted(immutable_paths),
        },
        "acceptance": acceptance,
        "harness": {
            "kind": "codex-exec",
            "binary_path": str(binary_path),
            "binary_sha256": digest(binary_path.read_bytes()),
            "version": version_process.stdout.decode(errors="replace").strip(),
            "model_expected": harness["model"],
        },
        "max_logical_attempts": 1,
        "external_effects_forbidden": EXTERNAL_EFFECTS_FORBIDDEN,
        "writer_id": str(uuid4()),
        "created_utc": utc_now(),
    }
    contract_path = run_dir / "contract.json"
    v1.write_new(contract_path, contract)
    return {
        "state": "CONTRACT_CREATED_LOCAL",
        "contract": str(contract_path),
        "contract_sha256": digest(contract_path.read_bytes()),
        "head": state["head"],
        "branch": state["branch"],
    }


def load_contract(contract_path: Path) -> tuple[dict[str, Any], str]:
    contract_path = contract_path.resolve()
    contract = read_object(contract_path)
    required = {
        "schema_version",
        "run_id",
        "task",
        "route",
        "graph",
        "repository",
        "request",
        "executables",
        "prompt",
        "scope",
        "acceptance",
        "harness",
        "max_logical_attempts",
        "external_effects_forbidden",
        "writer_id",
        "created_utc",
    }
    if set(contract) != required or contract["schema_version"] != f"{SCHEMA}/contract/v1":
        raise GraphHold("contrat V2.2 invalide")
    if contract["route"] not in {"A", "B"} or contract["graph"] != GRAPH:
        raise GraphHold("graphe contractuel divergent")
    if contract["max_logical_attempts"] != 1:
        raise GraphHold("max_logical_attempts doit être égal à 1")
    if contract["external_effects_forbidden"] != EXTERNAL_EFFECTS_FORBIDDEN:
        raise GraphHold("effets externes contractuels divergents")
    repository = contract["repository"]
    if not isinstance(repository, dict) or set(repository) != {
        "canonical", "git_common_dir", "git_dir", "worktree", "head", "branch"
    }:
        raise GraphHold("identité Git contractuelle invalide")
    worktree = Path(repository["worktree"]).resolve()
    canonical_repository = Path(repository["canonical"]).resolve()
    runner_root = relative_path(contract["scope"].get("runner_root"), "runner_root")
    run_dir = checked_path(worktree, runner_root, kind="directory")
    if contract_path != run_dir / "contract.json":
        raise GraphHold("chemin du contrat divergent")
    if Path(repository["git_common_dir"]).resolve() != absolute_git_path(worktree, "--git-common-dir"):
        raise GraphHold("git_common_dir divergent")
    if Path(repository["git_common_dir"]).resolve() != absolute_git_path(canonical_repository, "--git-common-dir"):
        raise GraphHold("dépôt canonique divergent")
    if Path(repository["git_dir"]).resolve() != absolute_git_path(worktree, "--git-dir"):
        raise GraphHold("git_dir divergent")
    request = contract["request"]
    request_path = Path(request.get("path", ""))
    if not request_path.is_file() or digest(request_path.read_bytes()) != request.get("sha256"):
        raise GraphHold("requête contractuelle divergente")
    if request_path.parent != run_dir or request_path.name != "request.json":
        raise GraphHold("chemin de requête divergent")
    executables = contract["executables"]
    if not isinstance(executables, dict) or set(executables) != set(EXECUTABLE_PATHS):
        raise GraphHold("dépendances exécutables divergentes")
    for name, expected_path in EXECUTABLE_PATHS.items():
        item = executables[name]
        if not isinstance(item, dict) or item.get("path") != expected_path:
            raise GraphHold(f"dépendance exécutable invalide: {name}")
        path = checked_path(worktree, relative_path(expected_path, name), kind="file")
        if digest(path.read_bytes()) != item.get("sha256"):
            raise GraphHold(f"dépendance exécutable modifiée: {name}")
    prompt = contract["prompt"]
    prompt_path = checked_path(worktree, relative_path(prompt.get("path"), "prompt"), kind="file")
    if digest(prompt_path.read_bytes()) != prompt.get("sha256"):
        raise GraphHold("prompt modifié")
    scope = contract["scope"]
    if not isinstance(scope, dict) or set(scope) != {
        "agent_root", "agent_paths", "runner_root", "immutable_paths"
    }:
        raise GraphHold("périmètres contractuels invalides")
    agent_root = relative_path(scope["agent_root"], "agent_root")
    checked_path(worktree, agent_root, kind="directory")
    if not isinstance(scope["agent_paths"], list) or not scope["agent_paths"]:
        raise GraphHold("périmètre agent invalide")
    for raw in scope["agent_paths"]:
        path = relative_path(raw, "agent_paths")
        checked_path(worktree, path, kind="file")
        if agent_root not in path.parents:
            raise GraphHold("fichier agent hors agent_root")
    expected_immutable = set(EXECUTABLE_PATHS.values()) | {prompt["path"]}
    if not isinstance(scope["immutable_paths"], list) or not expected_immutable.issubset(scope["immutable_paths"]):
        raise GraphHold("périmètre immuable incomplet")
    for raw in scope["immutable_paths"]:
        checked_path(worktree, relative_path(raw, "immutable_paths"), kind="file")
    validate_acceptance(contract["acceptance"], worktree)
    harness = contract["harness"]
    if not isinstance(harness, dict) or set(harness) != {
        "kind", "binary_path", "binary_sha256", "version", "model_expected"
    }:
        raise GraphHold("harnais contractuel invalide")
    binary = Path(harness["binary_path"])
    if not binary.is_file() or binary.is_symlink() or digest(binary.read_bytes()) != harness["binary_sha256"]:
        raise GraphHold("binaire du harnais modifié")
    if harness["kind"] != "codex-exec" or not harness["model_expected"]:
        raise GraphHold("harnais contractuel divergent")
    return contract, digest(contract_path.read_bytes())


def run_dir(contract: dict[str, Any]) -> Path:
    return Path(contract["repository"]["worktree"]) / contract["scope"]["runner_root"]


def worktree_path(contract: dict[str, Any]) -> Path:
    return Path(contract["repository"]["worktree"])


def runner_root_path(contract: dict[str, Any]) -> Path:
    return Path(contract["scope"]["runner_root"])


def writer_lock_path(contract: dict[str, Any]) -> Path:
    return Path(contract["repository"]["git_dir"]) / "graph-engineering-v2-2.lock.json"


def writer_lock_value(contract: dict[str, Any], contract_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": f"{SCHEMA}/writer-lock/v1",
        "contract_sha256": contract_sha256,
        "run_id": contract["run_id"],
        "run_dir": str(run_dir(contract)),
        "writer_id": contract["writer_id"],
        "state": "ACTIVE_UNTIL_OWNER_REVIEW",
    }


def create_writer_lock(contract: dict[str, Any], contract_sha256: str) -> dict[str, Any]:
    lock = writer_lock_value(contract, contract_sha256)
    v1.write_new(writer_lock_path(contract), lock)
    return lock


def load_writer_lock(contract: dict[str, Any], contract_sha256: str) -> dict[str, Any]:
    path = writer_lock_path(contract)
    lock = read_object(path)
    if lock != writer_lock_value(contract, contract_sha256):
        raise GraphHold("verrou concurrent, divergent ou potentiellement orphelin")
    return lock


@contextmanager
def operation(contract: dict[str, Any], contract_sha256: str, name: str) -> Iterator[dict[str, Any]]:
    directory = run_dir(contract)
    active = directory / "operation.active.json"
    history = directory / "operations"
    if active.exists() or active.is_symlink():
        raise GraphHold("verrou d’opération concurrent ou potentiellement orphelin")
    existing = sorted(history.glob("*.json")) if history.exists() else []
    if history.exists() and (history.is_symlink() or len(existing) != len(list(history.iterdir()))):
        raise GraphHold("historique d’opérations ambigu")
    number = len(existing) + 1
    claim = {
        "schema_version": f"{SCHEMA}/operation/v1",
        "contract_sha256": contract_sha256,
        "number": number,
        "name": name,
        "pid": os.getpid(),
        "started_utc": utc_now(),
    }
    v1.write_new(active, claim)
    try:
        yield claim
    finally:
        history.mkdir(exist_ok=True)
        destination = history / f"{number:03d}-{name}.json"
        if destination.exists():
            raise GraphHold("historique d’opération déjà présent")
        os.replace(active, destination)
        v1.sync_directory(history)
        v1.sync_directory(directory)


def assert_repository_identity(
    contract: dict[str, Any],
    *,
    clean: bool,
    expected_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    worktree = worktree_path(contract)
    state = repository_state(worktree, runner_root_path(contract))
    repository = contract["repository"]
    if state["head"] != repository["head"] or state["branch"] != repository["branch"]:
        raise GraphHold("HEAD ou branche divergent")
    if state["branch_tip"] != repository["head"]:
        raise GraphHold("référence de branche modifiée")
    if state["conflicts"] or state["index_changed"]:
        raise GraphHold("index modifié ou conflictuel")
    if clean and state["changed_paths"]:
        raise GraphHold("worktree sale")
    if expected_state is not None and state != expected_state:
        raise GraphHold("état du worktree divergent de la preuve agent")
    return state


def genesis_path(contract: dict[str, Any]) -> Path:
    return run_dir(contract) / "genesis.json"


def receipt_path(contract: dict[str, Any], node: str) -> Path:
    return run_dir(contract) / "nodes" / node / "receipt.json"


def receipt_hash(receipt: dict[str, Any]) -> str:
    return digest(canonical({key: value for key, value in receipt.items() if key != "receipt_sha256"}))


def write_receipt(
    contract: dict[str, Any],
    contract_sha256: str,
    node: str,
    parents: dict[str, str],
    edges: list[str],
    output: dict[str, Any],
) -> dict[str, Any]:
    base = {
        "schema_version": f"{SCHEMA}/node-receipt/v1",
        "contract_sha256": contract_sha256,
        "run_id": contract["run_id"],
        "node_id": node,
        "attempt": 1,
        "state": "evaluated",
        "parent_receipts": parents,
        "consumed_edges": edges,
        "input_sha256": digest(canonical({"contract_sha256": contract_sha256, "parents": parents})),
        "output": output,
        "output_sha256": digest(canonical(output)),
        "evaluation": {"contract": f"{SCHEMA}/node/{node}/v1", "verdict": "PASS"},
        "writer_id": contract["writer_id"],
        "created_utc": utc_now(),
    }
    receipt = {**base, "receipt_sha256": digest(canonical(base))}
    v1.write_new(receipt_path(contract, node), receipt)
    return receipt


def load_receipt(contract: dict[str, Any], contract_sha256: str, node: str) -> dict[str, Any]:
    receipt = read_object(receipt_path(contract, node))
    if receipt.get("receipt_sha256") != receipt_hash(receipt):
        raise GraphHold(f"reçu {node} divergent")
    if (
        receipt.get("schema_version") != f"{SCHEMA}/node-receipt/v1"
        or receipt.get("contract_sha256") != contract_sha256
        or receipt.get("run_id") != contract["run_id"]
        or receipt.get("node_id") != node
        or receipt.get("attempt") != 1
        or receipt.get("state") != "evaluated"
        or receipt.get("writer_id") != contract["writer_id"]
        or receipt.get("evaluation") != {"contract": f"{SCHEMA}/node/{node}/v1", "verdict": "PASS"}
        or receipt.get("output_sha256") != digest(canonical(receipt.get("output")))
        or receipt.get("input_sha256")
        != digest(canonical({"contract_sha256": contract_sha256, "parents": receipt.get("parent_receipts")}))
    ):
        raise GraphHold(f"reçu {node} invalide")
    return receipt


def genesis_value(contract: dict[str, Any], contract_sha256: str, lock: dict[str, Any]) -> dict[str, Any]:
    route = contract["route"]
    return {
        "schema_version": f"{SCHEMA}/genesis/v1",
        "contract_sha256": contract_sha256,
        "run_id": contract["run_id"],
        "route": route,
        "selected_nodes": GRAPH["routes"][route],
        "selected_edges": GRAPH["edges"][route],
        "writer_lock_sha256": digest(canonical(lock)),
        "max_logical_attempts": 1,
    }


def load_genesis(contract: dict[str, Any], contract_sha256: str) -> dict[str, Any]:
    lock = load_writer_lock(contract, contract_sha256)
    genesis = read_object(genesis_path(contract))
    if genesis != genesis_value(contract, contract_sha256, lock):
        raise GraphHold("genèse divergente")
    return genesis


def prepare(contract_path: Path) -> dict[str, Any]:
    contract, contract_sha256 = load_contract(contract_path)
    assert_repository_identity(contract, clean=True)
    if writer_lock_path(contract).exists() or writer_lock_path(contract).is_symlink():
        raise GraphHold("verrou concurrent ou potentiellement orphelin")
    lock = create_writer_lock(contract, contract_sha256)
    with operation(contract, contract_sha256, "prepare"):
        state = assert_repository_identity(contract, clean=True)
        genesis = genesis_value(contract, contract_sha256, lock)
        v1.write_new(genesis_path(contract), genesis)
        d_output = {"route": contract["route"], "selected_nodes": GRAPH["routes"][contract["route"]]}
        d = write_receipt(contract, contract_sha256, "D", {}, [], d_output)
        s_output = {
            "contract_sha256": contract_sha256,
            "repository_state": state,
            "executables": contract["executables"],
            "prompt_sha256": contract["prompt"]["sha256"],
            "writer_lock_sha256": digest(canonical(lock)),
        }
        s = write_receipt(
            contract,
            contract_sha256,
            "S",
            {"D": d["receipt_sha256"]},
            ["D->S"],
            s_output,
        )
        if contract["route"] == "A":
            after = assert_repository_identity(contract, clean=True)
            a_output = {"agent_invoked": False, "before_state": state, "after_state": after}
            a = write_receipt(
                contract,
                contract_sha256,
                "A",
                {"D": d["receipt_sha256"]},
                ["D->A"],
                a_output,
            )
            j_output = {
                "route": "A",
                "parents": {"S": s["receipt_sha256"], "A": a["receipt_sha256"]},
                "consumed_edges": GRAPH["edges"]["A"],
            }
            write_receipt(
                contract,
                contract_sha256,
                "J",
                j_output["parents"],
                ["S->J", "A->J"],
                j_output,
            )
            return {"state": "GRAPH_CLOSED_PENDING_INDEPENDENT_EVALUATION", "route": "A"}
        return {"state": "NEEDS_TRUSTED_ADAPTER", "route": "B"}


def load_prefix(contract: dict[str, Any], contract_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    load_genesis(contract, contract_sha256)
    d = load_receipt(contract, contract_sha256, "D")
    expected_d = {"route": contract["route"], "selected_nodes": GRAPH["routes"][contract["route"]]}
    if d.get("parent_receipts") != {} or d.get("consumed_edges") != [] or d.get("output") != expected_d:
        raise GraphHold("préfixe D divergent")
    s = load_receipt(contract, contract_sha256, "S")
    expected_s = {
        "contract_sha256": contract_sha256,
        "repository_state": s.get("output", {}).get("repository_state"),
        "executables": contract["executables"],
        "prompt_sha256": contract["prompt"]["sha256"],
        "writer_lock_sha256": digest(canonical(load_writer_lock(contract, contract_sha256))),
    }
    if (
        s.get("parent_receipts") != {"D": d["receipt_sha256"]}
        or s.get("consumed_edges") != ["D->S"]
        or s.get("output") != expected_s
    ):
        raise GraphHold("préfixe S divergent")
    return d, s


def load_adapter_manifest(contract: dict[str, Any], contract_sha256: str) -> dict[str, Any]:
    adapter_dir = run_dir(contract) / "adapter"
    path = adapter_dir / "manifest.json"
    manifest = read_object(path)
    stored = manifest.get("manifest_sha256")
    base = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    required = {
        "schema_version",
        "contract_sha256",
        "run_id",
        "node_id",
        "logical_attempt",
        "producer_sha256",
        "prompt_sha256",
        "command_history",
        "cwd",
        "confinement",
        "harness",
        "model_requested",
        "model_observed",
        "session_id",
        "session_rollout",
        "started_utc",
        "ended_utc",
        "exit_code",
        "stdout_sha256",
        "stderr_sha256",
        "worktree_before",
        "worktree_after",
        "agent_logical_sessions",
        "adapter_process_invocations",
        "benchmark_candidate_calls",
        "artifact_hashes",
    }
    if (
        set(base) != required
        or stored != digest(canonical(base))
        or manifest.get("schema_version") != f"{SCHEMA}/adapter-manifest/v1"
        or manifest.get("contract_sha256") != contract_sha256
        or manifest.get("run_id") != contract["run_id"]
        or manifest.get("node_id") != "B"
        or manifest.get("logical_attempt") != 1
        or manifest.get("producer_sha256") != contract["executables"]["adapter"]["sha256"]
        or manifest.get("prompt_sha256") != contract["prompt"]["sha256"]
        or manifest.get("cwd") != str(worktree_path(contract) / contract["scope"]["agent_root"])
        or manifest.get("harness") != contract["harness"]["version"]
        or manifest.get("model_requested") != contract["harness"]["model_expected"]
        or manifest.get("model_observed") != contract["harness"]["model_expected"]
        or manifest.get("exit_code") != 0
        or manifest.get("agent_logical_sessions") != 1
        or manifest.get("adapter_process_invocations") not in {1, 2}
        or manifest.get("benchmark_candidate_calls") != 0
    ):
        raise GraphHold("manifeste adaptateur divergent")
    artifacts = manifest.get("artifact_hashes")
    if not isinstance(artifacts, dict) or not artifacts:
        raise GraphHold("artefacts adaptateur absents")
    actual_files = {
        path.relative_to(adapter_dir).as_posix()
        for path in adapter_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != set(artifacts) | {"manifest.json"}:
        raise GraphHold("artefact adaptateur requis manquant ou supplémentaire")
    for relative, expected in artifacts.items():
        artifact = checked_path(adapter_dir, relative_path(relative, "adapter artifact"), kind="file")
        if digest(artifact.read_bytes()) != expected:
            raise GraphHold(f"artefact adaptateur modifié: {relative}")
    after = manifest.get("worktree_after")
    if not isinstance(after, dict):
        raise GraphHold("état final agent absent")
    assert_repository_identity(contract, clean=False, expected_state=after)
    before = manifest.get("worktree_before")
    if not isinstance(before, dict) or before.get("changed_paths"):
        raise GraphHold("état initial agent invalide")
    if before.get("head") != after.get("head") or before.get("branch") != after.get("branch"):
        raise GraphHold("identité Git modifiée par l’agent")
    if before.get("branch_tip") != after.get("branch_tip") or before.get("index_sha256") != after.get("index_sha256"):
        raise GraphHold("index ou référence Git modifié par l’agent")
    allowed = set(contract["scope"]["agent_paths"])
    if not set(after.get("changed_paths", [])).issubset(allowed):
        raise GraphHold("écriture agent hors périmètre")
    if after.get("conflicts") or after.get("index_changed"):
        raise GraphHold("index agent modifié ou conflictuel")
    return manifest


def close_agent_branch(contract_path: Path) -> dict[str, Any]:
    contract, contract_sha256 = load_contract(contract_path)
    if contract["route"] != "B":
        raise GraphHold("la clôture agent exige la route B")
    load_writer_lock(contract, contract_sha256)
    d, s = load_prefix(contract, contract_sha256)
    if receipt_path(contract, "B").exists() or receipt_path(contract, "J").exists():
        raise GraphHold("clôture B ou J déjà présente")
    manifest = load_adapter_manifest(contract, contract_sha256)
    with operation(contract, contract_sha256, "close-agent"):
        manifest = load_adapter_manifest(contract, contract_sha256)
        b_output = {
            "manifest_sha256": manifest["manifest_sha256"],
            "session_id": manifest["session_id"],
            "worktree_after_sha256": digest(canonical(manifest["worktree_after"])),
            "agent_logical_sessions": 1,
            "adapter_process_invocations": manifest["adapter_process_invocations"],
            "benchmark_candidate_calls": 0,
        }
        b = write_receipt(
            contract,
            contract_sha256,
            "B",
            {"D": d["receipt_sha256"]},
            ["D->B"],
            b_output,
        )
        j_output = {
            "route": "B",
            "parents": {"S": s["receipt_sha256"], "B": b["receipt_sha256"]},
            "consumed_edges": GRAPH["edges"]["B"],
        }
        write_receipt(
            contract,
            contract_sha256,
            "J",
            j_output["parents"],
            ["S->J", "B->J"],
            j_output,
        )
    return {
        "state": "GRAPH_CLOSED_PENDING_INDEPENDENT_EVALUATION",
        "route": "B",
        "session_id": manifest["session_id"],
        "agent_reinvoked": False,
    }


def hold(error: Exception) -> dict[str, Any]:
    return {"verdict": VERDICT_HOLD, "error": str(error)}


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    contract_parser = commands.add_parser("contract")
    contract_parser.add_argument("--request", type=Path, required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--contract", type=Path, required=True)
    close_parser = commands.add_parser("close")
    close_parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "contract":
            result = create_contract(args.request)
        elif args.command == "prepare":
            result = prepare(args.contract)
        else:
            result = close_agent_branch(args.contract)
        exit_code = 0
    except (GraphHold, v1.PilotError, OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError) as error:
        result, exit_code = hold(error), 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
