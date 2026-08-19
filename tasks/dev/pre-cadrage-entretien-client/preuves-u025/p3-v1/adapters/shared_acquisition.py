#!/usr/bin/env python3
"""P3 shared acquisition core, inert unless authenticatable authorizations verify"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any
import uuid


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[4]
STIMULUS = REPO / "tasks/dev/pre-cadrage-entretien-client/stimulus.md"
RAW_STORE = Path("/Users/ayo/Documents/benchmark-lab-x-private/p3-v1/raw/sha256/")
RAW_STORE_URI = "/Users/ayo/Documents/benchmark-lab-x-private/p3-v1/raw/sha256/"
GROK = Path("/Users/ayo/.grok/bin/grok")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
GO_URL = re.compile(
    r"^https://github\.com/ayoahha/benchmark-lab-x/issues/[0-9]+#issuecomment-[0-9]+$"
)
CONFIGS = {"grok46_xai_build_oauth", "kimi_k3_opencode_zen"}
PATHS = {"promptfoo", "ori", "manual"}
STAGES = {"canary", "campaign"}
STIMULUS_SHA256 = "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4"
VALIDATOR_SHA256 = "e631184b84270c4b3dbf931910436ad65b7d08c02016c94d2dfe53e27ead2056"
VALIDATOR = REPO / "tools/validateur_pre_cadrage_v0.py"
PACKAGE_DIR = REPO / "tasks/dev/pre-cadrage-entretien-client"
MANIFESTE_SHA256 = "8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10"
EFFORT_KEYS = (
    "configuration",
    "integration",
    "execution",
    "human_review",
    "verification",
    "maintenance",
    "report_production",
)
UNKNOWN = {"status": "INCONNU"}


class Hold(RuntimeError):
    pass


NO_AUTOMATIC_RETRY = True


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Hold(f"HARNESS_ERROR: objet JSON attendu: {path}")
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def prepare_raw_store() -> None:
    previous_umask = os.umask(0o077)
    try:
        RAW_STORE.mkdir(parents=True, exist_ok=True)
    finally:
        os.umask(previous_umask)
    if not RAW_STORE.is_dir() or RAW_STORE.is_symlink():
        raise Hold("HARNESS_ERROR: stockage brut invalide")
    RAW_STORE.chmod(0o700)


def content_address_write(data: bytes) -> dict[str, str]:
    digest = sha256_bytes(data)
    destination = RAW_STORE / digest
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if destination.is_symlink() or not destination.is_file():
            raise Hold("HARNESS_ERROR: objet de stockage invalide")
        if destination.read_bytes() != data:
            raise Hold("HARNESS_ERROR: collision du stockage adressé par contenu")
    else:
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    return {"sha256": digest, "path": str(destination)}


def verify_package() -> tuple[dict[str, Any], dict[str, Any]]:
    checksums_path = ROOT / "checksums.json"
    proof_path = ROOT / "proof-root.json"
    checksums = load_json(checksums_path)
    proof = load_json(proof_path)
    entries = checksums.get("files")
    if not isinstance(entries, dict) or not entries:
        raise Hold("HARNESS_ERROR: index de checksums absent")
    for rel, expected in entries.items():
        path = ROOT / rel
        if not path.is_file() or sha256_file(path) != expected:
            raise Hold(f"HARNESS_ERROR: dérive du lock: {rel}")
    if sha256_file(checksums_path) != proof.get("checksums_sha256"):
        raise Hold("HARNESS_ERROR: checksum du registre incohérent")
    if sha256_file(ROOT / "lock.json") != proof.get("lock_sha256"):
        raise Hold("HARNESS_ERROR: checksum du lock incohérent")
    if sha256_file(ROOT / "budget.json") != proof.get("budget_sha256"):
        raise Hold("HARNESS_ERROR: checksum du budget incohérent")
    lock = load_json(ROOT / "lock.json")
    python_runtime = lock.get("runtimes", {}).get("python", {})
    if sha256_file(Path(sys.executable)) != python_runtime.get("sha256"):
        raise Hold("HARNESS_ERROR: runtime Python non figé")
    if sha256_file(STIMULUS) != STIMULUS_SHA256:
        raise Hold("HARNESS_ERROR: stimulus non figé")
    root_payload = {k: v for k, v in proof.items() if k != "root_sha256"}
    if sha256_bytes(canonical_bytes(root_payload)) != proof.get("root_sha256"):
        raise Hold("HARNESS_ERROR: racine de preuve incohérente")
    return checksums, proof


def resolve_artifact(auth_file: Path, relative: Any, name: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise Hold(f"INCONNU: contrat {name} sans chemin d'artefact")
    path = Path(relative)
    if not path.is_absolute():
        path = (auth_file.parent / relative).resolve()
    if not path.is_file() or path.is_symlink():
        raise Hold(f"INCONNU: artefact {name} absent")
    return path


def verify_artifact_bytes(
    path: Path, expected_sha: Any, bindings: list[str], name: str
) -> bytes:
    if not isinstance(expected_sha, str) or not HEX64.fullmatch(expected_sha):
        raise Hold(f"INCONNU: empreinte {name} manquante")
    data = path.read_bytes()
    if sha256_bytes(data) != expected_sha:
        raise Hold(f"HARNESS_ERROR: empreinte {name} non concordante")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Hold(f"INCONNU: artefact {name} illisible") from error
    missing = [item for item in bindings if item not in text]
    if missing:
        raise Hold(f"INCONNU: liaison {name} manquante")
    return data


def verify_predecessor(auth: dict[str, Any], auth_file: Path, manifest: dict[str, Any]) -> None:
    prev_sha = auth.get("prev_receipt_sha256")
    prev_path_value = auth.get("prev_receipt_path")
    position = auth.get("order", {}).get("position")
    if not isinstance(prev_sha, str) or not HEX64.fullmatch(prev_sha):
        raise Hold("INCONNU: empreinte du prédécesseur manquante")
    path = resolve_artifact(auth_file, prev_path_value, "prédécesseur")
    if sha256_file(path) != prev_sha:
        raise Hold("HARNESS_ERROR: empreinte du prédécesseur non concordante")
    chain = manifest.get("chain", {})
    genesis_sha = chain.get("genesis_sha256")
    genesis_path = ROOT / "zero-execution-receipt.json"
    if position == 1:
        if prev_sha != genesis_sha or sha256_file(genesis_path) != genesis_sha:
            raise Hold("HARNESS_ERROR: genèse d'ordre non concordante")
        if path.resolve() != genesis_path.resolve() and sha256_file(path) != genesis_sha:
            raise Hold("HARNESS_ERROR: prédécesseur de position 1 hors genèse")
        return
    previous = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(previous, dict):
        raise Hold("INCONNU: prédécesseur illisible")
    previous_position = previous.get("attempt", {}).get("position")
    if previous_position != position - 1:
        raise Hold("HARNESS_ERROR: chaîne de positions non consécutive")


def verify_order_commitment(auth: dict[str, Any], manifest: dict[str, Any]) -> None:
    commitment = manifest.get("commitment", {})
    published = commitment.get("commitment_sha256")
    if not isinstance(published, str) or not HEX64.fullmatch(published):
        raise Hold("HOLD: engagement d'ordre non publié")
    order = auth.get("order")
    if not isinstance(order, dict):
        raise Hold("INCONNU: contrat d'ordre manquant")
    if order.get("commitment_sha256") != published:
        raise Hold("HARNESS_ERROR: engagement d'ordre divergent")
    if order.get("salt_revealed") is not False:
        raise Hold("HARNESS_ERROR: révélation d'ordre avant gel")
    if order.get("position") not in range(1, 7):
        raise Hold("HARNESS_ERROR: position d'ordre hors manifeste")
    cells = manifest.get("cells")
    if not isinstance(cells, list) or len(cells) != 6:
        raise Hold("HARNESS_ERROR: manifeste d'ordre incomplet")
    attempt_ids = [cell.get("attempt_id") for cell in cells if isinstance(cell, dict)]
    if len(set(attempt_ids)) != 6 or auth.get("attempt_id") not in attempt_ids:
        raise Hold("HARNESS_ERROR: tentative hors manifeste")


def run_pre_provider_guards(auth: dict[str, Any], auth_file: Path) -> None:
    gate = subprocess.run(
        [sys.executable, str(ROOT / "controls/verify_evidence_gate.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    if gate.returncode != 0:
        raise Hold((gate.stderr or "INCONNU: porte d'autorité fermée").strip())
    prev = auth.get("prev_receipt_path")
    prev_path = Path(str(prev or ""))
    if not prev_path.is_absolute():
        prev_path = (auth_file.parent / prev_path).resolve()
    order = subprocess.run(
        [
            sys.executable,
            str(ROOT / "controls/verify_order.py"),
            "--attempt-id",
            str(auth.get("attempt_id") or ""),
            "--prev-receipt",
            str(prev_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if order.returncode != 0:
        raise Hold((order.stderr or "INCONNU: garde d'ordre fermee").strip())


def validate_authorization(
    auth: dict[str, Any],
    proof: dict[str, Any],
    path: str,
    configuration: str,
    stage: str,
    auth_file: Path,
) -> None:
    expected = {
        "schema_version": "u025/p3-authorization/v3",
        "lock_root_sha256": proof["root_sha256"],
        "budget_sha256": proof["budget_sha256"],
        "stage": stage,
        "path": path,
        "configuration": configuration,
        "stimulus_sha256": STIMULUS_SHA256,
        "new_charge_allowed": False,
        "extra_spend_cap_usd": 0,
        "retry_of": None,
    }
    for key, value in expected.items():
        if auth.get(key) != value:
            raise Hold(f"HARNESS_ERROR: autorisation incompatible: {key}")
    if path not in PATHS or configuration not in CONFIGS or stage not in STAGES:
        raise Hold("HARNESS_ERROR: cible hors lock")
    for key in ("authorization_id", "attempt_id"):
        if not isinstance(auth.get(key), str) or not auth[key]:
            raise Hold(f"INCONNU: champ absent: {key}")
    prefix = "p3-canary-r1" if stage == "canary" else "p3-r1"
    expected_attempt_id = f"{prefix}-{path}-{configuration}"
    if auth["attempt_id"] != expected_attempt_id:
        raise Hold("HARNESS_ERROR: identifiant de tentative hors matrice")
    flags = auth.get("authorizations")
    if not isinstance(flags, dict) or any(
        flags.get(key) is not True
        for key in ("candidate_call", "provider_attempt", "stage", "spend_or_quota")
    ):
        raise Hold("HARNESS_ERROR: quatre autorisations distinctes requises")
    gos = auth.get("go_evidence")
    if not isinstance(gos, dict):
        raise Hold("INCONNU: contrat des GO manquant")
    go_hashes: list[str] = []
    go_ids: list[str] = []
    shared_bindings = [
        auth["lock_root_sha256"],
        auth["budget_sha256"],
        auth["attempt_id"],
        path,
        configuration,
        stage,
        "ayoahha",
    ]
    for key in ("candidate_call", "provider_attempt", "stage", "spend_or_quota"):
        go = gos.get(key)
        if not isinstance(go, dict) or go.get("authorized_by") != "ayoahha":
            raise Hold(f"INCONNU: GO propriétaire absent: {key}")
        if not isinstance(go.get("go_id"), str) or not go["go_id"]:
            raise Hold(f"INCONNU: identifiant GO absent: {key}")
        if not isinstance(go.get("url"), str) or not GO_URL.fullmatch(go["url"]):
            raise Hold(f"INCONNU: URL GO invalide: {key}")
        body_sha = go.get("body_sha256")
        if not isinstance(body_sha, str) or not HEX64.fullmatch(body_sha):
            raise Hold(f"INCONNU: empreinte GO manquante: {key}")
        go_path = resolve_artifact(auth_file, go.get("artifact_path"), f"GO {key}")
        verify_artifact_bytes(go_path, body_sha, [*shared_bindings, key], f"GO {key}")
        go_hashes.append(body_sha)
        go_ids.append(go["go_id"])
    if len(set(go_hashes)) != 4 or len(set(go_ids)) != 4:
        raise Hold("HARNESS_ERROR: les quatre GO ne sont pas distincts")
    manifest = load_json(ROOT / "order-manifest.json")
    verify_order_commitment(auth, manifest)
    run_pre_provider_guards(auth, auth_file)
    verify_predecessor(auth, auth_file, manifest)
    storage = auth.get("storage")
    if not isinstance(storage, dict):
        raise Hold("INCONNU: contrat de stockage manquant")
    if storage.get("uri") != RAW_STORE_URI or storage.get("content_addressed_write") is not True:
        raise Hold("HARNESS_ERROR: autorisation de stockage incompatible")


def grok_summary(session_id: str) -> dict[str, Any]:
    base = Path("/Users/ayo/.grok/sessions")
    matches = list(base.glob(f"**/{session_id}/summary.json"))
    if len(matches) != 1:
        return {
            "served_model": "INCONNU",
            "served_provider": "INCONNU",
            "served_route": "INCONNU",
            "served_reasoning_effort": "INCONNU",
            "status": "INCONNU",
            "reason": "summary.json unique absent",
        }
    summary = load_json(matches[0])
    return {
        "served_model": summary["current_model_id"]
        if isinstance(summary.get("current_model_id"), str)
        else "INCONNU",
        "served_provider": "INCONNU",
        "served_route": "INCONNU",
        "served_reasoning_effort": summary["reasoning_effort"]
        if isinstance(summary.get("reasoning_effort"), str)
        else "INCONNU",
        "status": "OBSERVED",
        "summary_sha256": sha256_file(matches[0]),
    }


def run_grok() -> dict[str, Any]:
    expected_sha = "3dfa7f04fbb5427a8fbead286591543aaecb478b3a0ab222c4329eca1a3b2f86"
    if not GROK.is_file() or sha256_file(GROK) != expected_sha:
        raise Hold("HARNESS_ERROR: binaire Grok Build non figé")
    session_id = str(uuid.uuid4())
    system_prompt = (ROOT / "system-prompt.txt").read_text(encoding="utf-8").rstrip("\n")
    command = [
        str(GROK), "--oauth", "--no-plan", "--no-subagents",
        "--disable-web-search", "--permission-mode", "dontAsk",
        "--sandbox", "strict", "--tools", "", "--deny", "*",
        "--max-turns", "1", "--verbatim", "--model", "grok-4.6",
        "--reasoning-effort", "xhigh", "--system-prompt-override", system_prompt,
        "--output-format", "plain", "--session-id", session_id,
        "--prompt-file", str(STIMULUS), "--cwd", str(REPO),
    ]
    allowed_environment = (
        "HOME", "PATH", "TMPDIR", "LANG", "LC_ALL", "SHELL", "TERM",
        "USER", "LOGNAME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME",
        "SSL_CERT_FILE", "SSL_CERT_DIR",
    )
    env = {key: os.environ[key] for key in allowed_environment if key in os.environ}
    started_at = utc_now()
    start_ns = time.monotonic_ns()
    process = subprocess.run(command, env=env, capture_output=True, check=False)
    elapsed_ns = time.monotonic_ns() - start_ns
    ended_at = utc_now()
    raw = canonical_bytes({
        "request": {
            "command": command,
            "stimulus_sha256": STIMULUS_SHA256,
            "system_prompt_sha256": sha256_file(ROOT / "system-prompt.txt"),
        },
        "stdout_utf8": process.stdout.decode("utf-8", errors="replace"),
        "stderr_utf8": process.stderr.decode("utf-8", errors="replace"),
        "exit_code": process.returncode,
        "session_id": session_id,
    })
    return {
        "output": process.stdout.decode("utf-8", errors="strict"),
        "raw": raw,
        "success": process.returncode == 0,
        "observed": grok_summary(session_id),
        "usage": {},
        "latency": {"started_at": started_at, "ended_at": ended_at, "elapsed_ns": elapsed_ns},
        "provider_status": process.returncode,
    }


def run_kimi() -> dict[str, Any]:
    api_key = os.environ.get("OPENCODE_ZEN_API_KEY")
    if not api_key:
        raise Hold("INCONNU: OPENCODE_ZEN_API_KEY absente")
    body = canonical_bytes({
        "model": "kimi-k3",
        "messages": [
            {
                "role": "system",
                "content": (ROOT / "system-prompt.txt").read_text(encoding="utf-8").rstrip("\n"),
            },
            {"role": "user", "content": STIMULUS.read_text(encoding="utf-8")},
        ],
        "reasoning_effort": "max",
        "max_completion_tokens": 131072,
        "stream": False,
    })
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    started_at = utc_now()
    start_ns = time.monotonic_ns()
    connection = http.client.HTTPSConnection("opencode.ai", 443)
    response_bytes = b""
    status: int | None = None
    provider_error: dict[str, str] | None = None
    try:
        connection.request("POST", "/zen/v1/chat/completions", body=body, headers=headers)
        response = connection.getresponse()
        response_bytes = response.read()
        status = response.status
    except Exception as error:
        provider_error = {"class": type(error).__name__, "message": str(error)}
    finally:
        connection.close()
    elapsed_ns = time.monotonic_ns() - start_ns
    ended_at = utc_now()
    output = ""
    usage: dict[str, Any] = {}
    observed: dict[str, Any] = {
        "served_model": "INCONNU",
        "served_provider": "INCONNU",
        "served_route": "INCONNU",
        "served_reasoning_effort": "INCONNU",
        "provider_error": provider_error,
    }
    response_valid = False
    if status is not None and 200 <= status < 300:
        try:
            decoded = json.loads(response_bytes)
            output = decoded["choices"][0]["message"]["content"]
            usage = decoded.get("usage") if isinstance(decoded.get("usage"), dict) else {}
            if isinstance(decoded.get("model"), str):
                observed["served_model"] = decoded["model"]
            response_valid = isinstance(output, str)
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, UnicodeDecodeError) as error:
            observed["response_error"] = type(error).__name__
    raw = canonical_bytes({
        "request_utf8": body.decode("utf-8"),
        "response_base64": base64.b64encode(response_bytes).decode("ascii"),
        "status": status,
    })
    return {
        "output": output,
        "raw": raw,
        "success": response_valid,
        "observed": observed,
        "usage": usage,
        "latency": {"started_at": started_at, "ended_at": ended_at, "elapsed_ns": elapsed_ns},
        "provider_status": status if status is not None else provider_error["class"],
    }


def tariff_source(configuration: str) -> dict[str, Any]:
    budget = load_json(ROOT / "budget.json")
    cfg = budget["configurations"][configuration]
    return cfg["tariff"]


def cost_fields(configuration: str, usage: Any) -> dict[str, Any]:
    budget = load_json(ROOT / "budget.json")
    cfg = budget["configurations"][configuration]
    units: dict[str, Any] = dict(UNKNOWN)
    cache: dict[str, Any] = dict(UNKNOWN)
    billed: dict[str, Any] = dict(UNKNOWN)
    calculated: dict[str, Any] = dict(UNKNOWN)
    if isinstance(usage, dict) and usage:
        observed_units = {
            key: usage[key]
            for key in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cached_tokens",
            )
            if key in usage
        }
        if observed_units:
            units = {"status": "OBSERVED", "values": observed_units}
        cache_values = {
            key: usage[key]
            for key in ("cache_read_input_tokens", "cached_tokens")
            if key in usage
        }
        if cache_values:
            cache = {"status": "OBSERVED", "values": cache_values}
        for key in ("cost", "cost_usd", "billed_usd"):
            if key in usage and usage[key] is not None:
                billed = {"status": "OBSERVED", "usd": usage[key], "field": key}
                break
    limitation: str | None = "INCONNU"
    if billed["status"] == "OBSERVED":
        limitation = None
    return {
        "currency": "USD",
        "tariff_source": tariff_source(configuration),
        "observed_units": units,
        "cache": cache,
        "calculated_provider_cost": calculated,
        "observed_billed": billed,
        "extra_spend_usd": 0,
        "counts_as_attempt": True,
        "limitation": limitation,
    }


def run_controls(candidate_text: str) -> dict[str, Any]:
    if not VALIDATOR.is_file() or sha256_file(VALIDATOR) != VALIDATOR_SHA256:
        raise Hold("HARNESS_ERROR: validateur canonique absent ou dérivé")
    spec = importlib.util.spec_from_file_location("validateur_pre_cadrage_v0", VALIDATOR)
    if spec is None or spec.loader is None:
        raise Hold("HARNESS_ERROR: validateur canonique illisible")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    paquet = module.PaquetApprouveV0(
        manifeste=PACKAGE_DIR / "manifeste-paquet.json",
        empreinte_manifeste_approuvee=MANIFESTE_SHA256,
        approbateur="Ayo",
        verdict_approbation="APPROUVE",
    )
    with tempfile.TemporaryDirectory() as folder:
        sortie = Path(folder) / "sortie-candidate.md"
        sortie.write_text(candidate_text, encoding="utf-8")
        resultat = module.valider_pre_cadrage_v0(paquet, sortie)
    return {
        "status": resultat.statut,
        "gates": [list(gate) for gate in resultat.gates],
        "validator_sha256": VALIDATOR_SHA256,
    }


def build_receipt(
    auth: dict[str, Any], auth_sha: str, proof: dict[str, Any], result: dict[str, Any],
    path: str, configuration: str, stage: str, raw_sha: str, output_sha: str,
    controls: dict[str, Any],
) -> dict[str, Any]:
    lock = load_json(ROOT / "lock.json")
    identity = lock["configurations"][configuration]
    return {
        "schema_version": "u025/p3-receipt/v3",
        "receipt_id": auth["attempt_id"],
        "prev_receipt_sha256": auth["prev_receipt_sha256"],
        "prev_receipt_path": auth["prev_receipt_path"],
        "lock_root_sha256": proof["root_sha256"],
        "authorization_sha256": auth_sha,
        "attempt": {
            "stage": stage,
            "attempt_id": auth["attempt_id"],
            "path": path,
            "configuration": configuration,
            "retry_of": None,
            "position": auth["order"]["position"],
        },
        "input": {
            "stimulus_sha256": STIMULUS_SHA256,
            "system_prompt_sha256": sha256_file(ROOT / "system-prompt.txt"),
        },
        "requested": identity["requested"],
        "expected": identity["expected"],
        "observed": result["observed"],
        "artifacts": {
            "raw_response_sha256": raw_sha,
            "candidate_output_sha256": output_sha,
            "raw_store_uri": RAW_STORE_URI,
        },
        "latency": result["latency"],
        "cost": cost_fields(configuration, result["usage"]),
        "incident": None if result["success"] else {
            "class": "PROVIDER_FAILURE",
            "status": result["provider_status"],
        },
        "automatic_controls": controls,
        "human_review": {
            "status": "PENDING",
            "rubric": "HR-001",
            "verdict": None,
            "llm_judge": False,
        },
        "effort": {key: None for key in EFFORT_KEYS},
        "report": {
            "status": "PENDING",
            "public_path": "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p3-v1/",
        },
        "result": "INCONNU" if result["success"] else "PROVIDER_FAILURE",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--path", required=True, choices=sorted(PATHS))
    parser.add_argument("--configuration", required=True, choices=sorted(CONFIGS))
    parser.add_argument("--stage", required=True, choices=sorted(STAGES))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _, proof = verify_package()
    if not args.authorization.is_file():
        raise Hold("INCONNU: fichier d'autorisation absent")
    auth_bytes = args.authorization.read_bytes()
    auth = json.loads(auth_bytes)
    if not isinstance(auth, dict):
        raise Hold("HARNESS_ERROR: autorisation non objet")
    validate_authorization(
        auth, proof, args.path, args.configuration, args.stage, args.authorization
    )
    prepare_raw_store()
    stored_authorization = content_address_write(auth_bytes)
    if args.configuration == "grok46_xai_build_oauth":
        result = run_grok()
    else:
        result = run_kimi()
    raw_sha = sha256_bytes(result["raw"])
    output_bytes = result["output"].encode("utf-8")
    output_sha = sha256_bytes(output_bytes)
    controls = run_controls(result["output"])
    receipt = build_receipt(
        auth,
        sha256_bytes(auth_bytes),
        proof,
        result,
        args.path,
        args.configuration,
        args.stage,
        raw_sha,
        output_sha,
        controls,
    )
    receipt_bytes = canonical_bytes(receipt)
    stored_raw_response = content_address_write(result["raw"])
    stored_receipt = content_address_write(receipt_bytes)
    print(json.dumps({
        "output": result["output"],
        "raw_response_base64": base64.b64encode(result["raw"]).decode("ascii"),
        "raw_response_sha256": raw_sha,
        "candidate_output_sha256": output_sha,
        "receipt": receipt,
        "receipt_sha256": sha256_bytes(receipt_bytes),
        "provider_success": result["success"],
        "storage_action": "CONTENT_ADDRESS_WRITE_COMPLETED",
        "stored_objects": {
            "authorization": stored_authorization,
            "raw_response": stored_raw_response,
            "receipt": stored_receipt,
        },
    }, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["success"] else 75


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Hold as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(78)
