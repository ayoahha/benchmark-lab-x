# vendor-incident-email — v1

- **Set**: dev
- **Family**: constrained writing
- **Stability**: generative (2 runs)
- **Exposures**: 0

## User objective

Write a vendor's reply to a client after a service outage, ready to send.

## Context and provided files

- `timeline.md`: fictitious factual timeline of the incident (1 page)
- `commitments.md`: 3 fictitious contract clauses

## Instructions visible to the model (verbatim)

> Write the reply email to the client based on `timeline.md` and `commitments.md`.
> Constraints: 200 words maximum. Must contain: the identified cause, the corrective measure, the proposed goodwill gesture. Forbidden: promising a numeric resolution deadline, admitting contractual fault, using an unexplained technical term.
> Output: only the email body, between the `<email>` and `</email>` tags. Nothing else.

## Expected result

A factual email, neutral tone, compliant with the 3 obligations and 3 prohibitions.

## Success conditions

The 3 mandatory elements present and accurate against the timeline; no prohibition violated; ≤ 200 words; tags respected.

## Disqualifying errors

A fact absent from the timeline; a numeric deadline; an admission of fault; overage > 10%.

## Possible automatic verification

Word count; presence of the tags; number+time-unit pattern near "resolved/restored".

## Human review

10 binary items: 3 obligations, 3 prohibitions, output format, length, factual accuracy, tone. Anchors: `anchor-pass.md`, `anchor-fail.md` (to be written before the first run).

## Limits

5 min, 1 attempt.

## Twin variant

Same checklist, different incident (delivery delay instead of an outage), renumbered clauses.
