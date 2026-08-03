# benchmark-lab-x — POC specification

Normative specification for the first POC, split into versioned milestones (V0 → V2). The README gives the overview; when they disagree, this file wins. Keywords MUST / MUST NOT / SHOULD follow their usual meaning.

## 1. Purpose and final POC objectives

A private benchmark of everyday, non-coding tasks (writing, synthesis, organization, document research) that one person can maintain and rerun on every notable model release.

The POC is complete when all of the following hold:

- **O1 — Verdict on demand**: any new model can be evaluated in at most half a day of human time (runs + judgment), producing a per-family verdict with evidence, never a single aggregate score.
- **O2 — Real signal**: at least one improvement or regression between two model versions has been detected and confirmed by the evidence trail (not by impression).
- **O3 — Longitudinal comparability**: at least three campaigns exist and remain comparable (pinned routes, versioned cards, frozen run folders).
- **O4 — Bounded maintenance**: upkeep outside campaigns stays under ~2 h/month (card repairs, twin variants).
- **O5 — Privacy intact**: the private set has never been published, pasted into an online chat, or reused for design.

## 2. Invariants (all versions)

These rules never change between milestones.

### 2.1 Code boundary

The only program allowed is the call collector. It MUST: load one task's prompt and files, make one API call with no retry, record the raw response and metadata (model, provider actually served, parameters, tokens, cost, duration, date, input-file hashes), and stop. It MUST NOT score, parse responses, loop over tasks, retry, rephrase, or aggregate. Reporting tools added in later milestones MUST be read-only over recorded runs and MUST NOT touch judgment.

### 2.2 Call layer

OpenRouter, pinned: explicit `provider.only`, `allow_fallbacks: false`, `require_parameters: true`. The provider actually served MUST be logged per run; runs with different routes MUST NOT be compared longitudinally. The prompt MUST impose an output template; format is checked before substantive judgment.

### 2.3 Data and privacy

All task data MUST be synthetic — no real name, company, address, or fact. Sets: `dev` (tuning, burnable), `calibration` (a known model must reach the expected result), `private` (never exposed outside runs). Exposure counter per card, max 2, then the twin variant replaces it.

### 2.4 Judgment

Automatic checks first, then human review on anonymized outputs in random order, against `verify.md` and the anchor examples. Verdicts `PASS` / `PARTIAL` / `FAIL` / `UNKNOWN` with short evidence. Ambiguous failure = `UNKNOWN` and a new card version, never a rerun. Two diverging runs = `UNSTABLE`, shown as-is. A model MUST NOT be the sole judge of its own output. Card edits create a new version; silent edits are forbidden.

### 2.5 Repository layout

```
tasks/<set>/<slug>/   task.md, input files, verify.md, anchor-pass.md, anchor-fail.md
runs/<date>/          one frozen campaign per folder
docs/SPEC.md          this file
```

## 3. Milestones

### V0 — prove the card contract (current)

Scope: 4 families (constrained writing, document synthesis, organization and trade-offs, research on a fixed corpus), `dev` set only, 4 complete cards, manual grid.

Exit criteria:
- [ ] 4 dev cards complete (data, `verify.md`, both anchors) and self-consistent
- [ ] 1 pilot campaign on 2-3 models, run and judged end to end
- [ ] every card judgeable in ≤ 10 min including the ~2x research family
- [ ] TEMPLATE stable: pilot required no field additions or removals

### V1 — full task set and trusted judgment

Scope: complete the 10-task set — `calibration` (2 tasks) and `private` (the remaining tasks, authored maintainer-side and kept out of any AI chat), plus the results grid as a committed artifact per campaign.

Exit criteria:
- [ ] 10 tasks live across the three sets; calibration verdicts match expectations
- [ ] 2 full campaigns, frozen under `runs/<date>/`, comparable with each other
- [ ] judge drift measured once: cold re-judgment of a sample after 2 weeks, divergences documented
- [ ] twin-variant flow exercised at least once on a burned card

### V2 — repeatable POC (final)

Scope: make campaigns routine and the archive trustworthy; add the fifth family (forms and administrative procedures) if V1 shows a coverage gap.

Exit criteria:
- [ ] objectives O1-O5 all met
- [ ] a machine-readable copy of each grid (one CSV per campaign) exists alongside the Markdown; produced by hand or by a read-only reporter within the §2.1 boundary
- [ ] a new-model evaluation has been executed start to finish from the written procedure alone (no tribal knowledge)

## 4. Out of scope for the whole POC

Web search, multi-turn sessions, coding tasks, LLM-assisted judging, statistics beyond per-family counts, public leaderboards, more than 5 models per campaign.
