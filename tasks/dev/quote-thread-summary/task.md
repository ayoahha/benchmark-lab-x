# quote-thread-summary — v1

- **Set**: dev
- **Family**: document synthesis
- **Stability**: generative (2 runs)
- **Exposures**: 0

## User objective

Pull, from a disordered email thread, the reliable list of decisions, amounts, and deadlines to prepare a reply to a quote.

## Context and provided files

- `mail-thread.md`: 12 fictitious messages out of order, with 2 planted contradictions (a revised amount, a moved date) and 1 deliberately missing piece of information

## Instructions visible to the model (verbatim)

> From `mail-thread.md`, produce: 1) the list of decisions made with their date, 2) the final agreed amount, 3) upcoming deadlines, 4) points still open or contradictory.
> If a piece of information is missing or contradictory, say so explicitly instead of deciding on one version.
> Output: exactly 4 sections titled `## Decisions`, `## Amount`, `## Deadlines`, `## Open points`.

## Expected result

An accurate synthesis that spots the 2 planted contradictions and flags the missing information.

## Success conditions

Ground truth known to the designer: correctly dated decisions, the last amount retained (or the contradiction flagged), both contradictions spotted, the missing info flagged, no invented fact.

## Disqualifying errors

An outdated amount presented as final without mentioning the revision; an invented fact; a contradiction silently resolved.

## Possible automatic verification

Presence of the 4 sections; presence of the expected amounts/dates (exact patterns).

## Human review

Comparison against the ground-truth sheet (`verify.md`): ≤ 10 binary items.

## Limits

5 min, 1 attempt.

## Twin variant

Same thread generator (12 messages, 2 contradictions, 1 gap), different subject (room rental instead of renovation quote), trap positions moved.
