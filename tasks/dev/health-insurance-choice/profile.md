# Household profile — health insurance comparison exercise

**Synthetic document — does not describe any real person.**

---

## Household members

| Member | Relationship | Age | Status |
| --- | --- | --- | --- |
| Emma Miller | Adult 1 (policyholder) | 41 | Private-sector employee, general statutory scheme |
| Daniel Miller | Adult 2 (spouse) | 44 | Private-sector employee, general statutory scheme |
| Sophie Miller | Child | 12 | Student |
| Leo Miller | Child | 8 | Student |

Synthetic address: 17 Poplar Close, 44100 Nantes.  
Coverage needed from: desired enrollment on **1 June 2026**.

---

## Reported history and needs

1. **Optical care** — Emma wears progressive lenses and expects to replace them in late 2026 (estimated optician's quote: €180 for the frame + €420 for the progressive lenses, or **€600** for a complete set). Daniel wears monthly contact lenses (**about €25/month**, or €300/year). Both children have an annual eye examination and currently need no correction.
2. **Hospitalization** — Daniel underwent knee arthroscopy in 2024. The couple wants a private room whenever hospitalized and strong coverage of fees above the statutory schedule in a private clinic (sector 2).
3. **Budget** — Maximum acceptable contribution for the whole household: **€280/month**. Any offer above that amount is rejected even if its benefits are better.
4. **Waiting periods** — The household rejects any offer with a **hospitalization** waiting period longer than **3 months**. Optical and dental waiting periods of up to 6 months are acceptable.

---

## Weighted selection criteria

The household set the following scoring grid for **eligible** offers after the budget and hospitalization-waiting-period filters:

| Code | Criterion | Weight | Scoring rule |
| --- | --- | --- | --- |
| K1 | Household optical out-of-pocket cost (year of Emma's replacement glasses + Daniel's contact lenses) | **35%** | A lower estimated annual out-of-pocket cost is better. Score 100 if out-of-pocket cost = €0; score 0 if out-of-pocket cost ≥ €800; linear interpolation between the two. |
| K2 | Hospitalization level (private room + fees above the statutory schedule) | **30%** | Score 100 if private room ≥ €80/night **and** fees ≥ 200% RB; score 50 if only one condition is met; score 0 if neither is met. |
| K3 | Budget fit (monthly household contribution) | **20%** | Score 100 if contribution ≤ €220/month; score 0 if contribution = €280/month; linear interpolation between €220 and €280. An offer > €280 is **ineligible** and excluded from comparison. |
| K4 | Hospitalization waiting period | **15%** | Score 100 if waiting period = 0 months; score 60 if 1–2 months; score 20 if 3 months; **ineligible** if > 3 months. |

Overall score = 0.35×K1 + 0.30×K2 + 0.20×K3 + 0.15×K4.

If scores are tied to one decimal place, select the offer with the lower monthly contribution.

---

## Required calculation assumptions

- For this exercise's reference hospitalization services, do **not recalculate** the statutory health insurance reimbursement basis (RB); use only the percentages and allowances stated in each offer.
- Emma's optical care: one complete set of progressive glasses during the year, costing **€600** (€180 + €420).
- Daniel's contact lenses: **€300/year**.
- Benefits for children that are not stated differently from adult benefits apply to Sophie and Leo at the same level as for adults, unless an offer says otherwise.
- Compare a **full year** of contributions and the sample benefits above.

