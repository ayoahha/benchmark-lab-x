# Verification — incident reply

## Binary checklist

- [ ] 1. The output contains only the email body between `<email>` and `</email>`.
- [ ] 2. The email body contains no more than 200 words.
- [ ] 3. The cause is accurate: the migration script left locks on the sessions table, after which the connection pool became saturated.
- [ ] 4. The agreed corrective measure is accurate: a lock-release check was added to the migration procedure and a dedicated residual-lock alert was created.
- [ ] 5. A goodwill gesture is explicitly proposed without being presented as already decided in the provided documents.
- [ ] 6. No numeric resolution deadline is promised.
- [ ] 7. The email does not admit contractual fault.
- [ ] 8. Every necessary technical term is explained in plain language.
- [ ] 9. No fact, time, commitment, or progress status contradicts the provided documents.
- [ ] 10. The tone is neutral, professional, and ready to send to the client.

## Reference facts

| Item | Reference |
| --- | --- |
| Total outage | 14 April 2026, from 06:40 to 10:47, or 4 hours 7 minutes |
| First internal alert | 06:12; the platform was still accessible then |
| Root cause | Locks not released by the migration script on the sessions table; connection-pool saturation during the morning peak |
| Restoration | Locks cleared completely by hand and controlled restart at 10:47 |
| Measure agreed on 15 April | Lock-release verification in the migration procedure and a dedicated alert |
| First client notification | 08:15, more than one hour after the total outage began at 06:40; the contractual deadline was missed even using this conservative starting point |
| Progress updates | None between 08:15 and the restoration email at 11:30 |
| Maintenance | The client was not notified of the migration 72 hours in advance, so it cannot be excluded as scheduled maintenance under Clause 12.1 |
| Calculated monthly availability | 99.43% for April 2026, below the contractual threshold of 99.5%, assuming no other interruption occurred that month; this reference assumption must not be required of the candidate |
| Goodwill gesture | No gesture is agreed in the provided documents; any wording must remain a proposal |

