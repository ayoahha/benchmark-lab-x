# Verification — health insurance choice

## Binary checklist

- [ ] 1. The output contains exactly the sections `## Recommendation`, `## Points of caution`, and `## Unknowns`.
- [ ] 2. Offer B is recommended; if a score is calculated under the reference assumption “statutory health insurance optical share = €0,” its overall score is 83.27 points. Omitting an exact score is acceptable when the missing component is identified as unknown.
- [ ] 3. The recommendation gives three comparative reasons grounded in the profile and supported by exact quotations from the documents.
- [ ] 4. Every quoted passage exists word for word in the cited document and actually supports the associated claim.
- [ ] 5. Offer C's adverse exclusion is identified: no contact-lens reimbursement during the first eleven months despite the displayed allowance.
- [ ] 6. The exclusion's first-year effect is applied; under the reference assumption, Offer C's optical out-of-pocket cost is €350, not €100. Declining to calculate it is acceptable if the missing component is explicitly identified.
- [ ] 7. The absence from all three offers of a quantified statutory health insurance share for optical care is identified as unknown.
- [ ] 8. Budget and waiting-period filters, benefits, and periods are compared without adding external data.
- [ ] 9. No amount, benefit, exclusion, period, or quotation absent from the corpus is invented.

## Reference facts

### Simplifying assumption and evaluation rule

Any component absent from the corpus must be treated as an unknown and reported, not silently replaced with zero. The tables below are conditional reference calculations: the statutory health insurance share of optical care is set to €0. This assumption is not established as fact by the provided documents.

A candidate must not be penalized for declining to calculate a complete out-of-pocket amount or exact score because this component is missing, provided it is reported under `## Unknowns`. If the candidate chooses to calculate under the reference assumption, the values below apply.

### Eligibility and scores under the reference assumption

| Offer | Monthly contribution | Hospitalization waiting period | Eligible | Conditional optical out-of-pocket cost | Conditional overall score |
| --- | ---: | ---: | --- | ---: | ---: |
| A | €220 | 2 months | Yes | €370 | 77.81 |
| B | €240 | 0 months | Yes | €230 | 83.27 |
| C | €260 | 3 months | Yes | €350 | 59.35 |

All three offers earn the maximum score for the hospitalization criterion. Offer B wins through its balance of optical care, no hospitalization waiting period, acceptable cost, and hospitalization benefits.

### Conditional reference calculations

| Criterion | Offer A | Offer B | Offer C |
| --- | ---: | ---: | ---: |
| K1 — optical care | 53.75 | 71.25 | 56.25 after exclusion |
| K2 — hospitalization | 100 | 100 | 100 |
| K3 — budget | 100 | 66.67 | 33.33 |
| K4 — hospitalization waiting period | 60 | 100 | 20 |

Formula: 0.35 × K1 + 0.30 × K2 + 0.20 × K3 + 0.15 × K4.

### Exclusion to identify

Document: `offer-c.md`, final section. Reference passage:

> **Extended waiting-period clause — contact lenses.** Contact-lens allowances become available only after **twelve (12) months** of continuous membership. No contact-lens reimbursement is payable during the first eleven months, including when a prescription is renewed. This provision takes precedence over the general 4-month optical waiting period for the contact-lens benefit only.

The €250 contact-lens allowance does not apply during the first year. The contact-lens out-of-pocket cost is therefore €300, and Offer C's total optical out-of-pocket cost is €350.

### Missing information

None of the three brochures quantifies the statutory scheme's share of the optical equipment and contact lenses. The complete out-of-pocket cost, combining statutory and supplemental insurance, therefore cannot be established to the euro from the brochures alone. The score calculation above follows only the conditional assumption “statutory scheme share = €0” adopted in this verification document.

