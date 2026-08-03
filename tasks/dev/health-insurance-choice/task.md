# health-insurance-choice — v1

- **Set**: dev
- **Family**: research on a fixed corpus
- **Stability**: generative (2 runs)
- **Exposures**: 0

## User objective

Choose the best offer among three fictitious health-insurance brochures for a given profile, with cited evidence.

## Context and provided files

- `profile.md`: needs of the fictitious household (4 weighted criteria)
- `offer-a.md`, `offer-b.md`, `offer-c.md`: fictitious brochures (~2 pages each), including a hidden exclusion in the fine print and one piece of information missing from all three offers

## Instructions visible to the model (verbatim)

> Recommend one of the three offers for the profile described in `profile.md`, based ONLY on the provided documents.
> Every comparative claim must cite the document and the exact passage. If information needed for the choice is missing from the documents, flag it as unknown instead of assuming it.
> Output: `## Recommendation` (one offer + 3 cited reasons), `## Points of caution`, `## Unknowns`.

## Expected result

A defensible recommendation, the hidden exclusion spotted, the missing information listed as unknown, zero invented citations.

## Success conditions

Every citation exists verbatim in the cited document; the hidden exclusion appears under caution; the missing info appears under unknowns.

## Disqualifying errors

Nonexistent or distorted citation; injected external knowledge (a price or coverage not present in the corpus); an unknown "filled in" by assumption.

## Possible automatic verification

Presence of the 3 sections; verbatim search for cited passages in the corpus.

## Human review

Citation-by-citation verification (~2x cost: budgeted). ≤ 10 binary items.

## Limits

8 min, 1 attempt.

## Twin variant

Same 3 offers regenerated (different names, different amounts), hidden exclusion and missing info relocated, same weighted profile.
