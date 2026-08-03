# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""Call collector (SPEC section 2.1).

Loads one task's prompt and input files, makes ONE OpenRouter call with a
pinned provider, records the raw response and metadata, and stops.
No scoring, no parsing, no task loop, no retry.

Usage:
    OPENROUTER_API_KEY=... uv run tools/collect.py tasks/dev/<slug> \
        --model openai/gpt-5.6 --provider openai --run 1
"""

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"
EXCLUDED = {"task.md", "verify.md", "prompt.txt"}  # judge-side files never sent


def assemble_prompt(task_dir: Path) -> tuple[str, dict[str, str]]:
    """Verbatim instructions block from task.md, then each input file appended"""
    override = task_dir / "prompt.txt"
    if override.exists():
        instructions = override.read_text(encoding="utf-8").strip()
    else:
        card = (task_dir / "task.md").read_text(encoding="utf-8")
        m = re.search(
            r"^## Instructions visible to the model.*?\n(.*?)(?=^## )",
            card,
            re.DOTALL | re.MULTILINE,
        )
        if not m:
            sys.exit("error: no 'Instructions visible to the model' section in task.md")
        quoted = [l for l in m.group(1).splitlines() if l.startswith(">")]
        instructions = "\n".join(l.lstrip("> ").rstrip() for l in quoted).strip()
        if not instructions:
            sys.exit("error: empty instructions block in task.md")

    inputs: dict[str, str] = {}
    for f in sorted(task_dir.glob("*.md")):
        if f.name in EXCLUDED or f.name.startswith("anchor-"):
            continue
        inputs[f.name] = f.read_text(encoding="utf-8")

    parts = [instructions]
    for name, content in inputs.items():
        parts.append(f"\n--- FILE: {name} ---\n{content}")
    return "\n".join(parts), inputs


def main() -> None:
    ap = argparse.ArgumentParser(description="benchmark-lab-x call collector")
    ap.add_argument("task_dir", type=Path)
    ap.add_argument("--model", required=True, help="OpenRouter model id")
    ap.add_argument("--provider", required=True, help="pinned provider (provider.only)")
    ap.add_argument("--run", type=int, default=1, help="run number (1 or 2)")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-root", type=Path, default=Path("runs") / date.today().isoformat())
    args = ap.parse_args()

    import os

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("error: OPENROUTER_API_KEY not set")
    if not (args.task_dir / "task.md").exists():
        sys.exit(f"error: {args.task_dir} is not a task folder")

    prompt, inputs = assemble_prompt(args.task_dir)

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

    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {key}"},
        json=body,
        timeout=600,
    )
    duration = time.monotonic() - t0
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        sys.exit(f"error from API: {json.dumps(data['error'])}")

    slug = args.task_dir.name
    model_slug = re.sub(r"[^a-zA-Z0-9.-]+", "-", args.model)
    out = args.out_root / f"{slug}__{model_slug}__r{args.run}"
    if out.exists():
        sys.exit(f"error: {out} already exists (runs are never overwritten)")
    out.mkdir(parents=True)

    content = data["choices"][0]["message"]["content"]
    (out / "response.md").write_text(content, encoding="utf-8")
    (out / "raw.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    meta = {
        "task": slug,
        "run": args.run,
        "date": started.isoformat(),
        "duration_s": round(duration, 2),
        "model_requested": args.model,
        "model_served": data.get("model"),
        "provider_pinned": args.provider,
        "provider_served": data.get("provider"),
        "params": {
            "temperature": args.temperature,
            "top_p": 1,
            "max_tokens": args.max_tokens,
            "seed": args.seed,
        },
        "usage": data.get("usage"),
        "finish_reason": data["choices"][0].get("finish_reason"),
        "input_hashes": {
            name: hashlib.sha256(text.encode()).hexdigest()[:16]
            for name, text in inputs.items()
        },
        "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest()[:16],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"{out}  provider_served={meta['provider_served']}  {meta['duration_s']}s")


if __name__ == "__main__":
    main()
