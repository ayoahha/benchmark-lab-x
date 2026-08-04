# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""Call collector (SPEC section 2.1).

Loads one task's prompt and input files, makes ONE OpenRouter call with a
pinned provider, records the raw response and metadata, and stops.
No scoring, no parsing, no task loop, no retry.

Exit codes (stable):
    0  success
    1  usage / bad arguments
    2  API key missing
    3  task directory invalid
    4  prompt assembly failed
    5  HTTP / transport error
    6  API returned an error object
    7  response failed structural validation
    8  provider_served or model_served mismatch (run invalid)
    9  run directory already exists
   10  I/O failure after reservation

Usage:
    uv run tools/collect.py tasks/dev/<slug> \
        --model openai/gpt-5.6 --provider openai --run 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Judge-side files never sent to the model
EXCLUDED = {"task.md", "verify.md", "prompt.txt"}
# Files matching these prefixes are also never sent
EXCLUDED_PREFIXES = ("anchor-",)

# Stable exit codes
EXIT_OK = 0
EXIT_USAGE = 1
EXIT_NO_KEY = 2
EXIT_BAD_TASK = 3
EXIT_PROMPT = 4
EXIT_HTTP = 5
EXIT_API_ERROR = 6
EXIT_VALIDATION = 7
EXIT_ROUTE_MISMATCH = 8
EXIT_EXISTS = 9
EXIT_IO = 10


def die(code: int, msg: str) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def load_dotenv_key() -> str | None:
    """Read OPENROUTER_API_KEY from a repo-local .env (gitignored), if any"""
    env_file = Path(".env")
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY="):
            value = line.split("=", 1)[1].strip().strip("'\"")
            return value or None
    return None


def preflight_key() -> str:
    """Require a key; repo-local .env (dedicated campaign key) wins over the
    shell environment. Never print its value"""
    key = load_dotenv_key()
    if key:
        print("key source: .env (repo-local, gitignored)", file=sys.stderr)
        return key
    key = os.environ.get("OPENROUTER_API_KEY")
    if key is None or not str(key).strip():
        die(EXIT_NO_KEY, "OPENROUTER_API_KEY not set (env var or repo .env; never displayed)")
    print("key source: environment variable", file=sys.stderr)
    return str(key).strip()


def is_excluded(name: str) -> bool:
    if name in EXCLUDED:
        return True
    return any(name.startswith(p) for p in EXCLUDED_PREFIXES)


def assemble_prompt(task_dir: Path) -> tuple[str, dict[str, str], list[str]]:
    """Build the user message byte-faithfully from card inputs.

    Assembly contract:
    - Instructions come from prompt.txt (if present) or the quoted block under
      "## Instructions visible to the model" in task.md, with only the leading
      "> " quote markers stripped — body bytes otherwise unchanged (UTF-8 text)
    - Each non-excluded *.md input is read as UTF-8 text with no rewriting and
      appended under a "--- FILE: <name> ---" header in sorted filename order
    - Returns (prompt, inputs_by_name, warnings)
    """
    warnings: list[str] = []
    override = task_dir / "prompt.txt"
    if override.exists():
        # Canonical override: raw bytes decoded, no newline translation
        instructions = override.read_bytes().decode("utf-8").strip()
        if not instructions:
            die(EXIT_PROMPT, "prompt.txt is empty")
    else:
        card = (task_dir / "task.md").read_bytes().decode("utf-8")
        m = re.search(
            r"^## Instructions visible to the model.*?\n(.*?)(?=^## )",
            card,
            re.DOTALL | re.MULTILINE,
        )
        if not m:
            die(EXIT_PROMPT, "no 'Instructions visible to the model' section in task.md")

        def dequote(line: str) -> str:
            # Remove exactly one "> " (or bare ">") quote prefix, nothing else
            return line[2:] if line.startswith("> ") else line[1:]

        quoted = [line for line in m.group(1).splitlines() if line.startswith(">")]
        instructions = "\n".join(dequote(line) for line in quoted).strip()
        if not instructions:
            die(EXIT_PROMPT, "empty instructions block in task.md")

    inputs: dict[str, str] = {}
    for f in sorted(task_dir.glob("*.md")):
        if is_excluded(f.name):
            continue
        if f.is_symlink():
            warnings.append(f"symlink refused, not sent to model: {f.name}")
            continue
        # Byte-faithful read: raw bytes decoded, no newline translation, no rewrite
        inputs[f.name] = f.read_bytes().decode("utf-8")

    # Warn about non-md files and other paths not covered by the send set
    covered = set(inputs) | EXCLUDED | {override.name if override.exists() else ""}
    for path in sorted(task_dir.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if name in covered or is_excluded(name):
            continue
        if name.startswith("."):
            continue
        warnings.append(f"file not sent to model (not in input manifest): {name}")

    parts = [instructions]
    for name, content in inputs.items():
        parts.append(f"\n--- FILE: {name} ---\n{content}")
    return "\n".join(parts), inputs, warnings


def redact_http_body(text: str) -> str:
    """Strip Authorization-like secrets from an error body before disk write"""
    redacted = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+",
        r"\1[REDACTED]",
        text,
    )
    redacted = re.sub(
        r"(?i)(api[_-]?key\s*[:=]\s*)\S+",
        r"\1[REDACTED]",
        redacted,
    )
    # OpenRouter sk-or-... style tokens if they leaked into the body
    redacted = re.sub(r"\bsk-[a-zA-Z0-9_-]{8,}\b", "[REDACTED]", redacted)
    return redacted


def normalize_cost_usd(usage: Any) -> float | None:
    """Normalize provider cost fields to a float USD amount when present"""
    if not isinstance(usage, dict):
        return None
    for key in ("cost", "total_cost", "cost_usd"):
        val = usage.get(key)
        if val is None:
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return None


def extract_provider_served(data: dict[str, Any]) -> str | None:
    """Best-effort provider id from a chat-completions payload"""
    raw = data.get("provider")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        for key in ("slug", "id", "name"):
            val = raw.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def validate_response(data: Any) -> tuple[str, dict[str, Any]]:
    """Require non-empty choices, string content, minimal structure"""
    if not isinstance(data, dict):
        die(EXIT_VALIDATION, "response is not a JSON object")
    if "error" in data and data["error"]:
        # Caller should have branched earlier; treat as validation miss
        die(EXIT_API_ERROR, "response contains error object")
    choices = data.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        die(EXIT_VALIDATION, "choices missing or empty")
    first = choices[0]
    if not isinstance(first, dict):
        die(EXIT_VALIDATION, "choices[0] is not an object")
    message = first.get("message")
    if not isinstance(message, dict):
        die(EXIT_VALIDATION, "choices[0].message missing or not an object")
    if first.get("error"):
        die(EXIT_API_ERROR, "choices[0] carries an error object (HTTP 200 masking a failure)")
    if first.get("finish_reason") == "error":
        die(EXIT_API_ERROR, "finish_reason=error (HTTP 200 masking a failure)")
    content = message.get("content")
    if not isinstance(content, str):
        die(EXIT_VALIDATION, "choices[0].message.content is not a string (got null or non-string)")
    return content, first


def atomic_write_text(path: Path, text: str) -> None:
    """Write via sibling tmp + os.replace"""
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def mark_failed(out: Path, reason: str, detail: str | None = None) -> None:
    """Leave a single FAILED marker file carrying reason and redacted receipt.

    One file, not a sibling directory: on case-insensitive filesystems (APFS)
    a 'failed/' directory would collide with the 'FAILED' marker
    """
    try:
        body = reason + "\n"
        if detail is not None:
            body += "\n" + redact_http_body(detail) + "\n"
        (out / "FAILED").write_text(body, encoding="utf-8")
    except OSError as exc:
        print(f"warning: could not write FAILED receipt: {exc}", file=sys.stderr)


def cleanup_or_fail(out: Path, reason: str, detail: str | None = None) -> None:
    """On post-reservation failure: mark FAILED (keep dir for diagnosis)"""
    mark_failed(out, reason, detail)


def main() -> None:
    ap = argparse.ArgumentParser(description="benchmark-lab-x call collector")
    ap.add_argument("task_dir", type=Path)
    ap.add_argument("--model", help="OpenRouter model id (or use --alias)")
    ap.add_argument("--provider", help="pinned provider (provider.only) (or use --alias)")
    ap.add_argument(
        "--alias",
        default=None,
        help="model alias resolved from models.toml (fields: model, provider, expect_provider)",
    )
    ap.add_argument(
        "--models-file",
        type=Path,
        default=Path("models.toml"),
        help="registry used by --alias (default: ./models.toml)",
    )
    ap.add_argument("--run", type=int, default=1, help="run number (1 or 2)")
    ap.add_argument("--attempt", type=int, default=1, help="attempt number after a FAILED run (evidence is never deleted)")
    ap.add_argument("--temperature", type=float, default=0.0)
    # 16384: reasoning models spend their budget on reasoning tokens first;
    # 4096 starved content on long cards (finish_reason=length, content null)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--expect-provider",
        default=None,
        help="expected provider display name when it differs from the pin slug (e.g. pin google-vertex, served Google)",
    )
    ap.add_argument("--out-root", type=Path, default=Path("runs") / date.today().isoformat())
    args = ap.parse_args()

    if args.alias:
        if args.model or args.provider:
            die(EXIT_USAGE, "--alias replaces --model/--provider; do not mix them")
        if not args.models_file.is_file():
            die(EXIT_USAGE, f"{args.models_file} not found (needed by --alias)")
        import tomllib

        try:
            registry = tomllib.loads(args.models_file.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            die(EXIT_USAGE, f"invalid {args.models_file}: {exc}")
        entry = registry.get(args.alias)
        if not isinstance(entry, dict) or "model" not in entry or "provider" not in entry:
            known = ", ".join(sorted(k for k, v in registry.items() if isinstance(v, dict)))
            die(EXIT_USAGE, f"alias {args.alias!r} not in {args.models_file} (known: {known})")
        args.model = entry["model"]
        args.provider = entry["provider"]
        if not args.expect_provider and entry.get("expect_provider"):
            args.expect_provider = entry["expect_provider"]
        omit_params = entry.get("omit_params", [])
        if omit_params and not isinstance(omit_params, list):
            die(EXIT_USAGE, "omit_params must be a list of parameter names")
    else:
        omit_params = []
    if not args.model or not args.provider:
        die(EXIT_USAGE, "--model and --provider are required (or --alias)")

    if args.run not in (1, 2):
        die(EXIT_USAGE, "--run must be 1 or 2 (campaign invariant)")
    if args.attempt < 1:
        die(EXIT_USAGE, "--attempt must be >= 1")
    if args.temperature != 0.0 or args.seed != 42 or args.max_tokens != 16384:
        print(
            "warning: sampling parameters deviate from campaign invariants "
            "(temp 0, seed 42, max_tokens 16384) — recorded in meta.json",
            file=sys.stderr,
        )

    key = preflight_key()

    if not args.task_dir.is_dir():
        die(EXIT_BAD_TASK, f"{args.task_dir} is not a directory")
    if not (args.task_dir / "task.md").exists():
        die(EXIT_BAD_TASK, f"{args.task_dir} is not a task folder (missing task.md)")

    try:
        prompt, inputs, warnings = assemble_prompt(args.task_dir)
    except SystemExit:
        raise
    except OSError as exc:
        die(EXIT_PROMPT, f"failed to read task files: {exc}")

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    slug = args.task_dir.name
    model_slug = re.sub(r"[^a-zA-Z0-9.-]+", "-", args.model)
    suffix = f"__a{args.attempt}" if args.attempt > 1 else ""
    out = args.out_root / f"{slug}__{model_slug}__r{args.run}{suffix}"
    if out.exists():
        hint = (
            "previous attempt is FAILED evidence, keep it and pass --attempt "
            f"{args.attempt + 1}"
            if (out / "FAILED").exists()
            else "runs are never overwritten or deleted"
        )
        die(EXIT_EXISTS, f"{out} already exists ({hint})")

    # P0: reserve the run directory before the network call
    try:
        out.mkdir(parents=True)
    except OSError as exc:
        die(EXIT_IO, f"could not reserve {out}: {exc}")

    body = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": args.temperature,
        "top_p": 1,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
        "provider": {
            "only": [args.provider],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
        "usage": {"include": True},
    }
    # Documented deviation: some pinned endpoints reject require_parameters
    # when a sampling knob is unsupported (e.g. seed); the registry may omit
    # those knobs explicitly and the omission is recorded in meta.json
    allowed_omissions = {"seed", "top_p"}
    for name in omit_params:
        if name not in allowed_omissions:
            die(EXIT_USAGE, f"omit_params entry {name!r} not allowed (only {sorted(allowed_omissions)})")
        body.pop(name, None)
        print(f"warning: parameter {name!r} omitted for this endpoint (declared in registry)", file=sys.stderr)
    # Canonical JSON for payload hash (stable separators, sorted keys)
    payload_bytes = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()

    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    try:
        resp = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            data=payload_bytes,
            timeout=600,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        cleanup_or_fail(out, "http_transport", redact_http_body(str(exc)))
        die(EXIT_HTTP, f"HTTP transport failed: {redact_http_body(str(exc))}")

    if resp.is_redirect or resp.is_permanent_redirect:
        cleanup_or_fail(out, f"http_redirect_{resp.status_code}")
        die(EXIT_HTTP, f"unexpected redirect HTTP {resp.status_code} (single-request contract)")

    duration = time.monotonic() - t0

    if not resp.ok:
        cleanup_or_fail(
            out,
            f"http_{resp.status_code}",
            redact_http_body(resp.text),
        )
        die(EXIT_HTTP, f"HTTP {resp.status_code} (redacted receipt in {out / 'FAILED'})")

    try:
        data = resp.json()
    except ValueError:
        cleanup_or_fail(out, "invalid_json", redact_http_body(resp.text))
        die(EXIT_VALIDATION, "response body is not valid JSON")

    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        # Never dump secrets; serialize error object only
        detail = redact_http_body(json.dumps(err, ensure_ascii=False, indent=2))
        cleanup_or_fail(out, "api_error", detail)
        die(EXIT_API_ERROR, "API returned error object (see FAILED receipt)")

    try:
        content, first_choice = validate_response(data)
    except SystemExit:
        # Full raw payload preserved as evidence (redacted), no truncation
        cleanup_or_fail(
            out,
            "validation",
            redact_http_body(json.dumps(data, ensure_ascii=False, indent=2)),
        )
        raise

    model_served = data.get("model") if isinstance(data.get("model"), str) else None
    provider_served = extract_provider_served(data)

    # OpenRouter returns the provider as a display name ("OpenAI") while the
    # pin is a slug ("openai"): compare on a normalized form, still fail-closed
    def normalize_route(value: str | None) -> str | None:
        if value is None:
            return None
        return re.sub(r"[\s_]+", "-", value.strip().lower())

    expected_providers = {normalize_route(args.provider)}
    if args.expect_provider:
        expected_providers.add(normalize_route(args.expect_provider))
    provider_ok = normalize_route(provider_served) in expected_providers
    model_ok = normalize_route(model_served) == normalize_route(args.model)

    if not model_ok or not provider_ok:
        cleanup_or_fail(
            out,
            "route_mismatch",
            (
                f"model_requested={args.model!r} model_served={model_served!r}\n"
                f"provider_pinned={args.provider!r} provider_served={provider_served!r}\n"
                "full raw response:\n"
                + redact_http_body(json.dumps(data, ensure_ascii=False, indent=2))
            ),
        )
        die(
            EXIT_ROUTE_MISMATCH,
            (
                f"route mismatch: model_served={model_served!r} "
                f"(wanted {args.model!r}), provider_served={provider_served!r} "
                f"(wanted {args.provider!r}); run invalid — "
                f"folder marked FAILED under {out}"
            ),
        )

    finish_reason = first_choice.get("finish_reason")
    if finish_reason == "length":
        print(
            "warning: finish_reason=length (output may be truncated)",
            file=sys.stderr,
        )

    usage = data.get("usage")
    cost_usd = normalize_cost_usd(usage)

    # Input fidelity manifest: every file body actually placed in the prompt
    input_manifest = {
        name: {
            "sha256_16": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            "bytes": len(text.encode("utf-8")),
        }
        for name, text in inputs.items()
    }

    meta = {
        "task": slug,
        "run": args.run,
        "date": started.isoformat(),
        "duration_s": round(duration, 2),
        "model_requested": args.model,
        "model_served": model_served,
        "provider_pinned": args.provider,
        "provider_served": provider_served,
        "params": {
            k: body[k]
            for k in ("temperature", "top_p", "max_tokens", "seed")
            if k in body
        },
        "params_omitted": sorted(omit_params),
        "usage": usage,
        "cost_usd": cost_usd,
        "finish_reason": finish_reason,
        "input_manifest": input_manifest,
        # Kept for older grid readers; same hashes as input_manifest
        "input_hashes": {name: info["sha256_16"] for name, info in input_manifest.items()},
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
        "payload_hash": payload_hash[:16],
        "files_sent": sorted(input_manifest.keys()),
        "assembly": (
            "prompt.txt override"
            if (args.task_dir / "prompt.txt").exists()
            else "task.md instructions block + FILE sections"
        ),
    }
    # Invariant: meta/raw never hold the API key
    meta_text = json.dumps(meta, indent=2, ensure_ascii=False)
    raw_text = json.dumps(data, indent=2, ensure_ascii=False)
    if key in meta_text or key in raw_text or key in content:
        cleanup_or_fail(out, "key_leak_guard", "API key appeared in payload to write")
        die(EXIT_IO, "refusing to write: API key would appear in run artifacts")

    try:
        atomic_write_text(out / "response.md", content)
        atomic_write_text(out / "raw.json", raw_text + "\n")
        atomic_write_text(out / "meta.json", meta_text + "\n")
        # Run-level commit marker, written last: a folder without COMPLETE
        # was interrupted and must not be judged
        atomic_write_text(out / "COMPLETE", started.isoformat() + "\n")
    except OSError as exc:
        cleanup_or_fail(out, "write_failed", str(exc))
        die(EXIT_IO, f"failed to write run artifacts: {exc}")

    print(
        f"{out}  provider_served={provider_served}  "
        f"model_served={model_served}  {meta['duration_s']}s  cost_usd={cost_usd}"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — last-resort path for reserved dirs
        print(f"error: unexpected: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_IO) from exc
