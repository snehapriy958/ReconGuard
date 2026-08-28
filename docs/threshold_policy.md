# ReconLens — Threshold Policy (Phase 4)

## Cost assumptions (project assumptions, NOT real Razorpay production costs)

```
FP_COST = 10      # an incorrect auto-reconciliation silently corrupts records
FN_COST = 3        # a missed auto-match just costs human review time
REVIEW_COST = 1    # baseline cost of a human reviewing one candidate
```

The 10:3 ratio encodes the project's stated principle (spec section 25):
false positives are materially more costly than false negatives in
financial reconciliation.

## A finding worth reporting honestly: the naive cost-optimal policy was degenerate

Grid search over (low, high) threshold pairs on validation initially
selected **LOW=0.05, HIGH=0.85 with zero review cases** — every single one
of 51 threshold pairs tied at zero total cost. This traced back to the
isotonic calibration collapse documented in `docs/calibration.md`: with
probabilities compressed to {0.0, 0.995, 1.0}, there were no genuinely
ambiguous cases anywhere in validation for a review band to catch. A policy
with literally no review zone contradicts the bounded-autonomy principle
this whole objective exists to demonstrate (spec section 28) — not because
the search was wrong, but because the calibration feeding it was broken.
Switching to sigmoid calibration (see docs/calibration.md) restored a real
probability gradient and produced a genuine, non-degenerate policy.

## Selected policy (validation, sigmoid-calibrated probabilities)

```
HIGH_THRESHOLD = 0.85   ->  HIGH_CONFIDENCE_MATCH
LOW_THRESHOLD  = 0.50   ->  LIKELY_NO_MATCH (below this)
                        ->  NEEDS_REVIEW (between the two)
```

**Validation results under this policy:**

| | Count | |
|---|---|---|
| Auto-match | 95 | precision 1.0, recall 0.9406 |
| Needs review | 6 | review-zone positive rate: 1.0 |
| Likely no match | 50 | error rate: 0.0 |
| Total expected cost | 6 | (all from review cost; zero FP/FN) |

**What this demonstrates:** all 6 review-zone candidates were genuinely
true matches that the model wasn't confident enough to auto-approve — the
system correctly chose caution over false confidence, exactly the
bounded-autonomy behavior the spec asks for. Zero false positives reached
auto-match.

## Held-out test (evaluated once, same fixed policy — no re-tuning)

| | Count | |
|---|---|---|
| Auto-match | 71 | precision 1.0, recall 0.9221 |
| Needs review | 3 | review-zone positive rate: 1.0 |
| Likely no match | 26 | **error rate: 0.1154** |

**Worth flagging honestly:** the likely-no-match error rate jumped from 0%
on validation to **11.5%** on test — meaning roughly 1 in 9 candidates
routed to "likely no match" on test were actually genuine matches. This
tracks directly with the one-to-many recall drop documented in
`docs/structural_matching.md` (66.7% on test vs the model never being
meaningfully tested on this relationship type during validation, which had
only 3 one-to-many positives). This is a real limitation surfaced only by
the one-time held-out evaluation — exactly why held-out test exists, and
exactly why it should not be re-tuned against now that this is known.

## Bounded autonomy principle (stated per spec section 28)

The policy is built to prefer **uncertain → human review** over
**uncertain → automatic action**. Concretely: the HIGH threshold (0.85) was
never allowed to drop below a floor of 0.85 during grid search, regardless
of what a pure cost-minimization would have chosen on a small, easily-fit
validation set — auto-match should always require genuine, demonstrated
confidence, not just "cheapest on this sample."

## Known limitation carried forward

The current single threshold pair is applied uniformly across all
relationship types, despite one-to-many performing measurably worse than
one-to-one. A relationship-type-aware threshold (e.g. a more conservative
HIGH threshold specifically for one-to-many/many-to-one candidates) is a
reasonable next step, not implemented here due to the very small number of
structural positive examples available to tune it against.
