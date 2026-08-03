# Verification — nonprofit weekend schedule

## Binary checklist

- [ ] [S] 1. The schedule contains two distinct Markdown tables, one for Saturday and one for Sunday.
- [ ] [S] 2. A final section titled exactly `## Unmet constraints` follows the two tables.
- [ ] [C] 3. C1: there are exactly two plenary sessions, both in Room A, on Saturday from 09:00 to 12:00 and Sunday from 09:30 to 12:30.
- [ ] [C] 4. C2 and C10: there are exactly three workshops, all in Room B for a complete bookable slot, with at least one on each day; Nadia leads exactly two and Sophie exactly one.
- [ ] [C] 5. C3 and C9: Amelia runs reception at both plenary sessions and is assigned to no activity after 18:00; the Saturday 17:30–19:30 review meeting in Room A, which requires Amelia, Kevin, and Thomas, is flagged as impossible because of C3, with no invented solution.
- [ ] [C] 6. C4: Kevin manages sound at both plenary sessions and is not assigned on Sunday afternoon.
- [ ] [C] 7. C5: every workshop has exactly one authorized facilitator working within her availability.
- [ ] [C] 8. C6: Julian runs the catering point during every workshop and during the Saturday 17:30–19:30 slot if it is used; his Sunday-morning unavailability is respected.
- [ ] [C] 9. C7: Thomas is scheduled 30 minutes before every plenary session and workshop, within his availability.
- [ ] [C] 10. C8: no workshop or other use of Room B is scheduled during the Sunday-morning plenary session.

## Reference facts

### Unsolvable conflict

C3 limits Amelia's availability to 18:00. C9 requires her attendance for the entire Saturday review meeting from 17:30 to 19:30. The two constraints cannot both be satisfied. The reference schedule below omits C9 and satisfies C1 through C8 and C10.

### Reference schedule

| Day | Time | Room | Activity | People in charge and required support |
| --- | --- | --- | --- | --- |
| Saturday, 9 May | 09:00–12:00 | A | Opening plenary | Amelia at reception; Kevin on sound; Thomas opens at 08:30 |
| Saturday, 9 May | 14:00–17:00 | B | Workshop 1 | Nadia facilitates; Julian runs catering; Thomas opens at 13:30 |
| Saturday, 9 May | 17:30–19:30 | B | Workshop 2 | Sophie facilitates; Julian runs catering; Thomas opens at 17:00 |
| Sunday, 10 May | 09:30–12:30 | A | Closing plenary | Amelia at reception; Kevin on sound; Thomas opens at 09:00 |
| Sunday, 10 May | 14:00–16:30 | B | Workshop 3 | Nadia facilitates; Julian runs catering; Thomas opens at 13:30 |

Room A does not host the review meeting required by C9. No other constraint is sacrificed.

