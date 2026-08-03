# nonprofit-weekend-planning — v1

- **Set**: dev
- **Family**: organization and trade-offs
- **Stability**: generative (2 runs)
- **Exposures**: 0

## User objective

Draw up the schedule for a fictitious nonprofit event weekend while respecting partially conflicting availabilities and constraints.

## Context and provided files

- `constraints.md`: 10 explicit constraints (availability of 6 fictitious volunteers, 2 rooms, time slots, 1 deliberately planted unsolvable conflict)

## Instructions visible to the model (verbatim)

> Draw up the Saturday and Sunday schedule from `constraints.md`.
> Each slot: time, room, activity, person in charge. Any constraint that cannot be satisfied must be flagged with the reason, not silently worked around.
> Output: one Markdown table per day, then a `## Unmet constraints` section.

## Expected result

A schedule satisfying 9 of 10 constraints and explicitly flagging the unsolvable conflict.

## Success conditions

What gets counted: constraints satisfied / silently violated / flagged. PASS = 0 silent violations and the planted conflict flagged.

## Disqualifying errors

Silent violation of a constraint; an invented volunteer or room; the unsolvable conflict "resolved" with an invented fact.

## Possible automatic verification

Table format; presence of the `## Unmet constraints` section.

## Human review

Going through the 10 constraints one by one against the produced schedule (10 binary items).

## Limits

5 min, 1 attempt.

## Twin variant

Regenerate availabilities and the planted conflict (different volunteer, different time slot), same structure of 10 constraints including 1 unsolvable.
