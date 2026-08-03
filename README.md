# benchmark-lab-x

Private benchmark of everyday tasks for comparing AI models under reproducible conditions.

## What this benchmark is?

- A folder of Markdown tasks + a results grid filled in by hand.
- Everyday work tasks an average person would do: writing, summarizing, organizing, searching through provided documents.
- A directional signal between models, never a general-purpose ranking.

## What this benchmark is not?

- Not a harness: **no evaluation engine**. The only code allowed is a call collector (see Boundary).
- No single LLM judge, no aggregate score, no free web search.
- Does not predict the product experience of vendor apps (the model is tested bare, via API).

## Code / no-code boundary

The call collector does exactly this, and nothing else:

1. loads the prompt and files for a task;
2. makes **one** API call, no retry;
3. records the raw response + metadata: model, provider actually served, parameters, tokens, cost, duration, date, input file fingerprints;
4. stops.

Forbidden: scoring, parsing the response, multi-task loops, retries, rephrasing, aggregation. If a `run_all_tasks()` function shows up, the boundary has been crossed. Judgment lives in each task's `verify.md` and stays human. No automated linting either: card compliance is checked against this README's checklist.

## Call layer

OpenRouter, pinned:

- `provider.only` (explicit provider), `allow_fallbacks: false`, `require_parameters: true`;
- the provider actually served (as returned by the API) is logged with every run: 2 campaigns are only comparable if the route is identical;
- output template enforced in the prompt;
- format is checked before any substantive judgment (otherwise you're measuring native formatting style, not competence).

Groq: possible complement for open models, never the primary layer (narrow catalog, fast deprecations).

Privacy: a task sent to an API is seen by the aggregator and the provider; ZDR limits retention, not disclosure. Hence 100% synthetic data, and "private" means: never published, never pasted into an online chat, never reused to design prompts.

## Families (V0: 10 tasks)

| Family                      | Tasks | Verification                                                 |
| --------------------------- | ----- | ------------------------------------------------------------ |
| Constrained writing         | 3     | binary checklist ≤ 10 items, human review                    |
| Document synthesis          | 3     | known ground truth (planted contradictions/obligations)      |
| Organization and trade-offs | 2     | violated constraints counted                                 |
| Research on a fixed corpus  | 2     | citations checked against the corpus (~2x verification cost) |

V1 reserve: forms and administrative procedures.

## Task card contract

Each task = a folder `tasks/<set>/<slug>/` containing `task.md`, the input files, `verify.md`. `task.md` follows `TEMPLATE.md`: one-sentence objective, context/files, visible instructions (verbatim, output template included), expected result, success conditions, disqualifying errors, possible automatic verification, elements for human review, limits (time/budget/attempts), stability (closed/generative: fixes the number of runs upfront), exposure counter, twin variant.

## Protocol

1. **Three sealed sets**: `tasks/dev/` (tuning, burnable), `tasks/calibration/` (a known model must get the expected score), `tasks/prive/` (never exposed outside runs).
2. **Identical conditions**: same verbatim prompt, same files, same limits for every model; config + date logged per run.
3. **Runs**: 2 runs on any generative task (decided in the card, never after the fact), 1 on closed-form response. Two diverging verdicts get an `UNSTABLE` label, displayed as-is, no 3rd tie-breaking run, no averaging.
4. **Judgment**: automatic verification first (observable properties), then human review on anonymized outputs in random order. PASS/FAIL anchor examples fixed per task at design time; cold re-judgment of a sample after 2 weeks to measure the judge's own drift. Never a single LLM judge on its own output.
5. **Result**: `PASS` / `PARTIAL` / `FAIL` / `UNKNOWN` + short evidence. Ambiguous failure = `UNKNOWN`, no retry; it's the card that gets improved (new version), not the run that gets redone.
6. **Wear**: exposure counter per card, max 2; beyond that, generate the twin variant (same skills, changed parameters), versioned, never published.
7. **Campaigns**: frozen in `runs/<date>/`, 4-5 models max, reported by family ("3/3, 2/3, 1/2, 2/2"), never a single score.

## Results grid

One row per task × model × run: task, model+version, provider served, date, result, evidence, cost, duration, human rework (`none` / `minor` < 2 min / `major`).

## Task card review checklist

- [ ] all TEMPLATE fields present
- [ ] verbatim instructions, output template included
- [ ] stability (closed/generative) declared, resulting run count
- [ ] PASS/FAIL anchor examples attached
- [ ] 100% synthetic data, no real name/fact
- [ ] twin variant sketched
- [ ] exposure counter at 0

## Known limits

- 10 tasks: directional signal, a one-task gap is noise.
- Consumable tasks: burned after 2 exposures or any publication.
- Compares model+route pairs; a provider change behind OpenRouter invalidates longitudinal comparison.
- The single human judge remains a stable bias, bounded by anchoring and cold re-judgment, not eliminated.
