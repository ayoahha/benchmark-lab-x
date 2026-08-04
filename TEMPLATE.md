# Task card TEMPLATE

Copy this file to `tasks/<set>/<slug>/task.md` and fill in every field. Verification lives in `verify.md` in the same folder.

Review checklist before a card enters a campaign (checked by hand — no linting tool, by design):

- [ ] all TEMPLATE fields present
- [ ] verbatim instructions, output template included
- [ ] stability (closed/generative) declared, resulting run count
- [ ] PASS/FAIL anchor examples attached
- [ ] every `verify.md` item tagged `[C]` or `[S]`
- [ ] 100% synthetic data, no real name/fact
- [ ] twin variant sketched
- [ ] exposure counter at 0

---

# <slug> — v1

- **Set**: dev | calibration | private
- **Family**: constrained writing | document synthesis | organization and trade-offs | research on a fixed corpus
- **Stability**: closed (1 run) | generative (2 runs) — decided here, never after the fact
- **Exposures**: 0 (increment with each campaign; at 2, switch to the twin variant)

## User objective

One sentence.

## Context and provided files

List of the folder's files sent to the model. 100% synthetic data.

## Instructions visible to the model (verbatim)

> The exact prompt, imposed output template included. This is the block that goes out in the call, identical for every model.

## Expected result

Shape and content of the correct output.

## Success conditions

Observable properties, as binary as possible.

## Disqualifying errors

What counts as an outright FAIL (invented fact, violated prohibition, data loss…).

## Possible automatic verification

What can be checked without judgment (counts, patterns, format).

## Human review

Binary checklist ≤ 10 items. Attach the anchor examples: `anchor-pass.md`, `anchor-fail.md`.

## Limits

Time, budget, attempts (default: 1 attempt, never a retry).

## Twin variant

Parameters to change to renew the task without changing the skill being measured.
