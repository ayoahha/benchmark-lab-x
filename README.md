# benchmark-lab-x

Private benchmark of everyday tasks for comparing AI models under reproducible conditions.

Markdown task cards, one small call collector, human judgment. Everyday work an average person would do — writing, summarizing, organizing, searching provided documents — not coding. The output is a directional signal per task family, never a general-purpose ranking.

Full design rationale and normative rules live in [`docs/SPEC.md`](docs/SPEC.md).

The benchmarking procedure is in [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

This README covers what you need to run it.

## Getting started

### Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (the collector declares its own Python ≥ 3.12 and dependency)
- An [OpenRouter](https://openrouter.ai) account and API key

### Install

```sh
git clone git@github.com:ayoahha/benchmark-lab-x.git
cd benchmark-lab-x
```

Nothing to build: the only program is `tools/collect.py`, run through `uv`.

### Configure the API key

Create a **dedicated** OpenRouter key with a spend cap (never your personal key), then either:

```sh
cp .env.example .env      # put the key in .env (gitignored, takes precedence)
# or
export OPENROUTER_API_KEY=...   # shell env var
```

Never pass the key as an argument, commit it, or paste it into a chat or issue. Run artifacts (`meta.json`, `raw.json`) never contain it. Revoke the key after any shared or one-off use.

Account-side: keep every "train on request data" endpoint class disabled in OpenRouter's privacy settings, that is the benchmark's anti-contamination line (refer to SPEC §2.2).

### Configure the models

Models live in [`models.toml`](models.toml): one entry per model with its OpenRouter id and pinned provider. Before adding one, check its hosts and pick one that does not train on request data:

```sh
curl -s https://openrouter.ai/api/v1/models/<author/slug>/endpoints
```

If no compliant host exists, the model is not benchmarkable : record it commented-out in `models.toml` with the reason.

### First run

```sh
uv run tools/collect.py tasks/dev/vendor-incident-email --alias deepseek-v4-flash --run 1
```

This makes exactly one API call and writes `runs/<date>/<task>__<model>__r1/` containing `response.md`, `raw.json`, `meta.json`, and a `COMPLETE` marker. Check the printed line: `provider_served` must match the pin, otherwise the run is marked `FAILED` and must not be judged.

## Usage

### Collect a campaign

One command per task × model × run (runs: 2 for generative cards, 1 for closed ones):

```sh
uv run tools/collect.py tasks/dev/<slug> --alias <name> --run 1
uv run tools/collect.py tasks/dev/<slug> --alias <name> --run 2
```

No loop, no retry, no scoring ; The collector stops after recording. A failed call leaves a `FAILED` receipt; keep it as evidence and relaunch with `--attempt 2`. Full procedure, including anonymized judging and the results grid: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

### Judge

Judgment is human and mechanical: automatic checks first, then the task's `verify.md` checklist item by item against the anchors, on anonymized outputs. Verdict derivation and model comparison rules: SPEC §2.5.

### Collector reference

```
uv run tools/collect.py <task_dir> (--alias NAME | --model ID --provider PIN)
    [--run 1|2] [--attempt N] [--expect-provider NAME]
    [--temperature F] [--seed N] [--max-tokens N] [--out-root DIR]
```

Campaign invariants: temperature 0, seed 42 (omitted per-endpoint via `omit_params` in `models.toml` when unsupported), max_tokens 16384. Deviations print a warning and are recorded in `meta.json`. Stable exit codes are listed in the script header.

## Repository layout

```text
tasks/<set>/<slug>/   task.md, input files, verify.md, anchor-pass.md, anchor-fail.md
runs/<date>/          one frozen campaign per folder (campaign.md, run folders, grid.md)
tools/collect.py      the call collector — the only program in the repo
models.toml           model registry used by --alias
docs/SPEC.md          normative specification (boundary, scoring, milestones)
docs/RUNBOOK.md       step-by-step campaign procedure
TEMPLATE.md           task card contract
```

Sets: `dev` (tuning, burnable), `calibration` (a known model must reach the expected result), `private` (never exposed outside runs, never pasted into any online chat).

## Design in brief

- **Families (V0, 10 tasks)**: constrained writing (3), document synthesis (3), organization and trade-offs (2), research on a fixed corpus (2).
- **Boundary**: no evaluation engine. The collector loads one task, makes one pinned API call, records response + metadata, stops. Judgment lives in `verify.md` and stays human; no LLM judges its own output.
- **Scoring**: checklist items tagged `[C]`/`[S]`; failed `[C]` → FAIL, all passed → PASS, only `[S]` failed → PARTIAL, external causes → UNKNOWN. Models compared per family by paired comparison (`BEATS` / `TIE` / `INCONCLUSIVE`); diagnostics (item score, cost, rework, `UNSTABLE`) never break a tie; no cross-family aggregate, ever.
- **Reproducibility**: pinned provider routes, fixed sampling, frozen campaign folders, versioned cards, exposure counter (max 2, then a twin variant replaces the card).

## Known limits

- 10 tasks: directional signal. Families with 2-3 tasks yield an index, never a head-to-head verdict (paired comparison needs ≥ 4 judgeable pairs).
- Tasks are consumable: burned after 2 exposures or any publication.
- Compares model+route pairs; a provider change behind OpenRouter invalidates longitudinal comparison.
- The single human judge remains a stable bias, bounded by anchoring and cold re-judgment, not eliminated.
- `UNSTABLE` measures provider non-determinism under controlled inputs, not real-world usage variability.
- Tested bare via API: does not predict the product experience of vendor apps.
