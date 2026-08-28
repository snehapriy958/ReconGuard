# ReconLens — Risk Policy (Phase 5)

## The core distinction

**Model confidence** = calibrated probability. **Risk** = known,
measured, structural facts about this candidate's reliability that the
probability alone doesn't communicate. A `HIGH_CONFIDENCE_MATCH` with risk
flags is still a `HIGH_CONFIDENCE_MATCH` — nothing in `backend/app/workflow/risk.py`
touches a probability value or a decision label. This is enforced
structurally: `compute_risk_flags()` takes a feature row and a relationship
type, and returns only a `list[str]`. It has no code path that could alter
`raw_probability` or `calibrated_probability`.

## Why this distinction matters here specifically

Phase 4's held-out test showed one-to-many recall at 66.7% while one-to-one
recall was 98.6% — the *same* calibrated probability threshold does not mean
the *same* reliability across relationship types. Silently lowering the
one-to-many threshold would be one way to react to this, but the spec
explicitly forbids it in Phase 5 (section 29) — not enough many-to-one
validation data exists to tune a second threshold safely yet, and held-out
test cannot be used for that tuning regardless. The risk layer is the
correct-scoped answer: **surface the known limitation as metadata a human
can act on, without pretending the model's own confidence number should be
different than what it measurably is.**

## Risk flags (`backend/app/workflow/risk.py`)

| Flag | Condition | Grounding |
|---|---|---|
| `STRUCTURAL_MATCH` | relationship_type != one_to_one | — |
| `ONE_TO_MANY_RELATIONSHIP` | relationship_type == one_to_many | — |
| `KNOWN_LOW_GENERALIZATION` | relationship_type == one_to_many | Phase 4 held-out test: 66.7% recall (2/6 missed) |
| `MANY_TO_ONE_RELATIONSHIP` | relationship_type == many_to_one | — |
| `INSUFFICIENT_VALIDATION_SAMPLE` | relationship_type == many_to_one | Validation had ZERO positive many-to-one examples |
| `HIGH_COMPETITION` | competing_candidate_count >= 5 | Threshold chosen because the Phase 3 false-negative case (LED-000172) had 10 competing candidates |
| `WEAK_REFERENCE_EVIDENCE` | no exact/partial reference match AND reference_similarity < 0.3 | Reference features were the single most valuable evidence type in Phase 4's ablation |
| `MISSING_REFERENCE` | both sides missing a reference | — |
| `HIGH_STRUCTURAL_AMBIGUITY` | both is_potential_one_to_many and is_potential_many_to_one set | Same condition that drove the Phase 3 false negative |

Every threshold here is a **stated project assumption**, chosen with a
documented reason — not a tuned model parameter, and not arbitrary.

## Exception categories (`classify_exception()`)

Evaluated in a fixed priority order (first match wins), not whichever
condition happens to be checked last:

1. `NO_CANDIDATE_FOUND` — zero candidates on both sides
2. `STRUCTURAL_AMBIGUITY` — both structural-potential flags set
3. `HIGH_COMPETITION` — competing_candidate_count >= 5
4. `INSUFFICIENT_EVIDENCE` — weak reference AND weak vendor similarity together
5. `LOW_MATCH_CONFIDENCE` — fallback: the calibrated probability was simply
   below the low threshold, with no other specific measurable condition
   explaining why

`LOW_MATCH_CONFIDENCE` is itself a real, measurable statement (the actual
probability and threshold are always included in the exception reason), not
a vague catch-all.

## Example (real output from a genuine held-out test candidate, not staged)

```
Candidate: LED-000172 / STL-000172-0 (Phase 3's documented false-negative case)
Relationship: one_to_one
Risk flags: [HIGH_COMPETITION, HIGH_STRUCTURAL_AMBIGUITY]
Operational note: "This record has several plausible alternative matches...
This candidate has competing structural interpretations..."
```

This is the exact case that produced Phase 3's single false negative — the
risk layer would have surfaced both contributing factors (high competition
and structural ambiguity) on this candidate even at a probability where the
model was reasonably confident, which is precisely the intended use: risk
metadata catches what a bare probability number cannot.

## What the risk layer explicitly does NOT do

- Does not modify `raw_probability` or `calibrated_probability`
- Does not override `decision` (HIGH_CONFIDENCE_MATCH / NEEDS_REVIEW / LIKELY_NO_MATCH)
- Does not silently route a flagged high-confidence match to review — per
  spec section 9, that would defeat the purpose of exposing risk
  *separately* from the measured threshold policy
