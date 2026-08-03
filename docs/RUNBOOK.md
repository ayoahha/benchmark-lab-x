# Campaign runbook

Step-by-step procedure for one V0 campaign. Everything here is manual except the single API call per run (`tools/collect.py`, the §2.1 collector).

## 0. Prerequisites

- `OPENROUTER_API_KEY` present in the environment (env var, keychain, or direnv): never in argv, never in the repo, never pasted into chat. See README "Key setup".
- Model list for the campaign (4-5 max), each with its OpenRouter id AND its pinned provider, e.g. `openai/gpt-5.6` + `openai`.
- `uv` installed (the collector declares its own dependency; Python ≥ 3.12).

## 1. Freeze the campaign

1. Create `runs/<YYYY-MM-DD>/`: the campaign folder. Everything in it is frozen after judgment.
2. Write `runs/<date>/campaign.md`: model list (id + provider + date), card versions used (each task.md's `— vN`), and any deviation from this runbook.

## 2. Collect

For each task × model, honoring the card's stability field (closed = run 1 only, generative = runs 1 and 2):

```sh
uv run tools/collect.py tasks/dev/<slug> --model <id> --provider <pin> --run 1
uv run tools/collect.py tasks/dev/<slug> --model <id> --provider <pin> --run 2   # generative only
```

One command per run, launched by hand. No loop, no retry: a failed call is relaunched by hand once its cause is understood; an ambiguous response is never regenerated.

After each successful call, confirm in the printed line (and `meta.json`) that `provider_served` and `model_served` match the pin. The collector fails non-zero on mismatch and leaves the folder marked `FAILED`; do not judge a failed run. Failed folders are evidence: never delete them: fix the cause, then relaunch with `--attempt 2` (each attempt gets its own folder). When a provider's display name legitimately differs from its pin slug (e.g. pin `google-vertex`, served `Google`), pass `--expect-provider` and record it in `campaign.md`.

A valid run folder ends with a `COMPLETE` marker (written last). A folder without `COMPLETE` was interrupted: treat it as failed.

## 3. Anonymize before judging

1. For each task, gather the `response.md` files of all models (skip any folder marked `FAILED` or missing `COMPLETE`).
2. Copy them to `runs/<date>/judging/<slug>/` under shuffled neutral names (`out-1.md`, `out-2.md`, …) and write the mapping to `runs/<date>/judging/<slug>/mapping.txt`.
3. Do not open `mapping.txt` until every output of that task is judged.

## 4. Judge

Per task, per anonymized output, in one sitting per task:

1. Automatic checks first: the format/counting items listed in task.md (word counts, required sections, verbatim quote lookups). A broken but readable template, ignored instructions, or wrong content is model-attributable → continue scoring toward `FAIL`, not `UNKNOWN`.
2. Then the `verify.md` checklist, item by item, against the ground truth and the two anchors. Mark each item pass/fail.
3. Derive the verdict mechanically (SPEC §2.5):
   - any `[C]` failed → `FAIL`
   - all items passed → `PASS`
   - only `[S]` failed → `PARTIAL`
   - `UNKNOWN` only for external causes (corrupted evidence, invalidated run, ambiguous card). Every `UNKNOWN` triggers a card or infrastructure action.
   Record the item score (passed/total) and one line of evidence. Item score is a diagnostic only.
4. Only then open `mapping.txt` and attribute results to models.

## 5. Record

Fill `runs/<date>/grid.md`: one row per task × model × run:

| task | model | provider served | run | verdict | item score | evidence | cost | duration | rework | UNSTABLE |
|---|---|---|---|---|---|---|---|---|---|---|

Then the family scoreboard (per model per family): four counts `PASS` / `PARTIAL` / `FAIL` / `UNKNOWN`, plus `judgeable = total − UNKNOWN` and pass rate `PASS / judgeable`. Publish mean item score, `UNSTABLE` count, median cost and duration as diagnostics only: they never break a tie.

Apply the paired comparison of SPEC §2.5 for each model pair: per-task rank `PASS` > `PARTIAL` > `FAIL`, drop pairs with `UNKNOWN`, require ≥ 4 judgeable pairs else `INCONCLUSIVE`, else A `BEATS` B only if victories > defeats and victories ≥ 2, otherwise `TIE`. Output is always explicit: `BEATS` / `TIE` / `INCONCLUSIVE`. V0 families with 2–3 tasks are an index only, never a head-to-head verdict.

## 6. Close the campaign

1. Increment the exposure counter in every card used; any card reaching 2 gets its twin variant before the next campaign.
2. Freeze `runs/<date>/`: no edits after this point.
3. Before any commit that touches `runs/`, scan `runs/**` for accidental key material (shell paste, debug dumps).
4. Two weeks later: cold re-judgment of a small sample (SPEC V1 exit criterion): re-judge 3-4 outputs without looking at the recorded verdicts, then compare.
