# Campaign runbook

Step-by-step procedure for one V0 campaign. Everything here is manual except the single API call per run (`tools/collect.py`, the §2.1 collector).

## 0. Prerequisites

- `OPENROUTER_API_KEY` exported in the shell (never written to the repo).
- Model list for the campaign (4-5 max), each with its OpenRouter id AND its pinned provider, e.g. `openai/gpt-5.6` + `openai`.
- `uv` installed (the collector declares its own dependency).

## 1. Freeze the campaign

1. Create `runs/<YYYY-MM-DD>/` — the campaign folder. Everything in it is frozen after judgment.
2. Write `runs/<date>/campaign.md`: model list (id + provider + date), card versions used (each task.md's `— vN`), and any deviation from this runbook.

## 2. Collect

For each task × model, honoring the card's stability field (closed = run 1 only, generative = runs 1 and 2):

```sh
uv run tools/collect.py tasks/dev/<slug> --model <id> --provider <pin> --run 1
uv run tools/collect.py tasks/dev/<slug> --model <id> --provider <pin> --run 2   # generative only
```

One command per run, launched by hand. No loop, no retry: a failed call is relaunched by hand once its cause is understood; an ambiguous response is never regenerated.

After each call, check in the printed line (and `meta.json`) that `provider_served` matches the pin. A mismatched route invalidates the run: delete the folder, fix the pin, relaunch.

## 3. Anonymize before judging

1. For each task, gather the `response.md` files of all models.
2. Copy them to `runs/<date>/judging/<slug>/` under shuffled neutral names (`out-1.md`, `out-2.md`, …) and write the mapping to `runs/<date>/judging/<slug>/mapping.txt`.
3. Do not open `mapping.txt` until every output of that task is judged.

## 4. Judge

Per task, per anonymized output, in one sitting per task:

1. Automatic checks first: the format/counting items listed in task.md (word counts, required sections, verbatim quote lookups). A broken output template stops there → `UNKNOWN`.
2. Then the `verify.md` checklist, item by item, against the ground truth and the two anchors. Mark each item pass/fail.
3. Derive the verdict mechanically (SPEC §2.5): any `[C]` failed → FAIL; all passed → PASS; only `[S]` failed → PARTIAL; unjudgeable → UNKNOWN. Record the item score (passed/total) and one line of evidence.
4. Only then open `mapping.txt` and attribute results to models.

## 5. Record

Fill `runs/<date>/grid.md` — one row per task × model × run:

| task | model | provider served | run | verdict | item score | evidence | cost | duration | rework |
|---|---|---|---|---|---|---|---|---|---|

Then the family scoreboard (per model per family): PASS/tasks, mean item score, UNSTABLE count, median cost and duration. Apply the comparison rule of SPEC §2.5; a one-task gap is reported as noise.

## 6. Close the campaign

1. Increment the exposure counter in every card used; any card reaching 2 gets its twin variant before the next campaign.
2. Freeze `runs/<date>/` — no edits after this point.
3. Two weeks later: cold re-judgment of a small sample (SPEC V1 exit criterion) — re-judge 3-4 outputs without looking at the recorded verdicts, then compare.
