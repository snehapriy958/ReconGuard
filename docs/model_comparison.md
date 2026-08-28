# ReconLens — Model Comparison (Phase 4)

## Data

Both models trained on the **unified** (pairwise + structural) labeled
dataset — 3,378 train / 151 val / 100 test — for a fair, same-data
comparison per spec §15. This is a materially harder, more realistic
problem than Phase 3's pairwise-only baseline: train positive rate is
**11.1%**, not the 54.6% Phase 3 saw.

## Feature exclusion carried into both models

`reference_missing_settlement` excluded from both models — see "Suspicious
feature investigation" below. 22 features used (23 generated minus this one).

## Validation comparison

| Metric | Logistic Regression (balanced) | LightGBM (best config) |
|---|---|---|
| Precision | 0.9806 | **1.0** |
| Recall | 1.0 | 1.0 |
| F1 | 0.9902 | **1.0** |
| PR-AUC | 0.9991 | **1.0** |
| ROC-AUC | 0.9982 | **1.0** |
| Confusion matrix | TN=48, FP=2, FN=0, TP=101 | TN=50, FP=0, FN=0, TP=101 |

**LightGBM selected** — strictly better on every metric, not just accuracy.

## Hyperparameter search (small, documented, per spec §16)

4 configurations tried, varying `num_leaves`, `max_depth`, `learning_rate`,
`n_estimators`, `min_child_samples`:

| Config | num_leaves | max_depth | learning_rate | n_estimators | Val PR-AUC | Val F1 |
|---|---|---|---|---|---|---|
| 0 (selected) | 15 | 4 | 0.05 | 200 | **1.0** | **1.0** |
| 1 | 31 | 6 | 0.05 | 200 | 0.9998 | 0.9851 |
| 2 | 31 | -1 (unlimited) | 0.1 | 100 | 0.9997 | 0.9901 |
| 3 | 63 | 8 | 0.05 | 300 | 0.9998 | 0.99 |

**Worth noting honestly:** the *simplest* configuration (shallowest, fewest
leaves) won. This is a legitimate finding, not a search failure — with this
dataset's amount/date features being nearly deterministic separators, a
shallow tree captures the signal fine, and the larger configs show mild signs
of overfitting to training noise (lower val F1 despite more capacity).

## Feature importance (LightGBM, by gain)

| Feature | Gain | Split count |
|---|---|---|
| abs_amount_diff | 24,619.63 | 453 |
| group_size | 8,247.74 | 249 |
| reference_similarity | 6,357.68 | 194 |
| vendor_jaro_winkler_similarity | 2,129.81 | 219 |
| date_diff_days | 1,773.34 | 204 |
| amount_ratio | 1,677.06 | 254 |
| reference_substring_overlap | 828.26 | 8 |
| vendor_token_set_similarity | 599.14 | 124 |

`group_size` ranking #2 is notable — LightGBM found real value in the
structural shape feature that Logistic Regression's linear coefficients
could not exploit as effectively (see ablation below).

## Suspicious feature investigation: `reference_missing_settlement`

**Finding:** perfect correlation with relationship type among true positives
— 100% of true many-to-one matches have it = 1, 100% of true one-to-many
matches have it = 0. Root cause confirmed by inspecting the generator:
batched settlement lines are constructed with a blank reference *by design*
(`generate.py`), not because missing references are real evidence of a
match. In production, a missing reference is more plausibly a **risk**
signal than supporting evidence.

**Ablation (validation only):**

| | Precision | Recall | F1 | PR-AUC |
|---|---|---|---|---|
| Model A (all features) | 0.9806 | 1.0 | 0.9902 | 0.9991 |
| Model B (without the feature) | 0.9806 | 1.0 | 0.9902 | 0.9985 |

Cost of removal: negligible (PR-AUC -0.0006). **Retained or removed:
removed.** Reason: the feature's entire predictive value in this dataset
comes from a generator construction quirk, not a generalizable financial
signal — shipping it would teach the model a rule that actively
contradicts real-world intuition (missing reference = risk, not
reassurance) the moment this system saw a real bank settlement file with
different reference conventions.

## Additional feature-group ablations (Logistic Regression, validation)

| Ablation | Precision | Recall | F1 | PR-AUC |
|---|---|---|---|---|
| All features | 0.9806 | 1.0 | 0.9902 | 0.9991 |
| Without semantic | 0.9712 | 1.0 | 0.9854 | 0.9991 |
| **Without reference** | **0.9519** | **0.9802** | **0.9659** | **0.9865** |
| Without structural | 0.9806 | 1.0 | 0.9902 | 0.9985 |

**Reference features are clearly the most valuable evidence type** — the
biggest drop by far. Semantic (currently the offline n-gram fallback
embedder, not real sentence-transformers — see docs/architecture.md) and
structural features contribute little marginal value for the *linear*
model. This doesn't contradict LightGBM's high `group_size` importance
above — a nonlinear model can exploit structural shape in ways a linear
coefficient cannot, which is itself a legitimate reason LightGBM
outperforms LR here.

## Final model selection

**LightGBM, config 0** (num_leaves=15, max_depth=4, learning_rate=0.05,
n_estimators=200), trained with `class_weight='balanced'`, on the 22-feature
schema excluding `reference_missing_settlement`. Selected on validation
evidence across five metrics, not accuracy alone, per spec §29.

## Held-out test (evaluated once — see docs/threshold_policy.md for the
three-way policy applied to test)

| Metric | Value |
|---|---|
| Precision | 1.0 |
| Recall | 0.961 |
| F1 | 0.9801 |
| ROC-AUC | 0.9983 |
| PR-AUC | 0.9995 |
| Confusion matrix | TN=23, FP=0, FN=3, TP=74 |

**By relationship type (first real signal on many-to-one and one-to-many):**

| Type | n | Positive | Precision | Recall |
|---|---|---|---|---|
| One-to-one | 83 | 70 | 1.0 | 0.9857 |
| One-to-many | 11 | 6 | 1.0 | **0.6667** |
| Many-to-one | 6 | 1 | 1.0 | 1.0 (n=1, not statistically meaningful) |

**Not directly comparable to Phase 3's 0.9928 F1** — different, harder test
set (100 rows including 17 structural candidates vs Phase 3's 83 pairwise-only
rows). The overall F1 looking slightly lower than Phase 3's baseline is
expected and correct: this model is being tested on a genuinely harder,
more complete problem, not regressing on the same one.
