# ReconLens — Calibration (Phase 4)

## Methodology

With only train/val/test splits (no separate calibration slice), calibration
is fit on half of validation and evaluated on the other half — never on the
same data it was fit on, and never on held-out test. This costs statistical
power (~75 rows per half instead of 151) but avoids a real failure mode
encountered during development (below).

## Failure encountered and fixed: isotonic collapse

**Observed:** first attempt fit isotonic regression on the *full* validation
set and evaluated on the same set. Brier score came back exactly **0.0**.

**Why this is a red flag, not a result:** isotonic regression is a flexible,
non-parametric step function. Fit and evaluated on the same small,
near-perfectly-separated dataset, it can trivially memorize the labels —
a "perfect" score that reflects evaluation leakage internal to calibration,
not genuine calibration quality.

**Fix, attempt 1:** split validation into a fit-half and an eval-half.
Brier score *still* came back 0.0 on the eval-half. Investigation showed
why: isotonic, fit on only 75 points from an already well-separated model,
collapsed LightGBM's output to just **3 distinct probability values**
(0.0, 0.995, 1.0) — a degenerate step function, not meaningful calibration.

**Fix, attempt 2 (final):** switched to sigmoid (Platt) scaling — a smooth
2-parameter curve that can't degenerate into a step function the way
isotonic can with limited data.

| | Isotonic | Sigmoid |
|---|---|---|
| Brier score (eval-half) | 0.0 | 0.00714 |
| Distinct probability values (full val) | 3 | 121 |
| Probability range | {0.0, 0.995, 1.0} | 0.009 - 0.992 |

Sigmoid's Brier score is numerically higher, and that's the correct
tradeoff: a smooth, usable confidence gradient that a three-way policy and
per-candidate explanation payload can actually work with, instead of a
"perfect" score built on a broken 3-value output.

## Reliability (sigmoid calibration, eval-half, n=76)

| Probability bin | n | Mean predicted | Observed rate |
|---|---|---|---|
| [0.0, 0.2] | ~23 | ~0.02 | 0.0 |
| [0.2, 0.4] | 0 | - | - |
| [0.4, 0.6] | 2 | 0.517 | 0.5 |
| [0.6, 0.8] | 1 | 0.740 | 1.0 |
| [0.8, 1.0] | 49 | 0.977 | 1.0 |

**Honest reliability finding:** the extremes (near 0, near 1) are
well-supported and well-calibrated - dozens of examples each, predicted and
observed rates agree closely. **The middle range (0.2-0.8) has only 3 total
examples across the entire eval-half.** No meaningful "X% confidence
corresponds to Y% correctness" claim can be made for mid-range confidence
on this dataset - there simply isn't enough data there yet. This is stated
as a limitation per spec section 23, not glossed over: a real reliability
statement will require either a larger validation set or messier,
less-separable data than this synthetic corruption model currently produces.

## Calibration artifact

`models/calibrator_v1.joblib` bundles the fitted sigmoid calibrator,
base model type, feature column order, and fit methodology. Verified to
enforce the same feature order as the underlying LightGBM model
(`test_calibration_artifact_loads_and_matches_model_feature_order`).
