# ReconLens — Logistic Regression Baseline (Phase 3)

## Scope, stated explicitly

This baseline classifies **one-to-one pairwise candidates only** (the V1
candidate set). Structural (V2) group candidates use a different feature
shape — combined amounts across 2-3 records instead of a single amount
delta — that Phase 2's extractor was not built to produce. Unifying the two
into one feature schema is a real design problem (how does a classifier
compare a pairwise candidate's `abs_amount_diff` against a structural
candidate's `group_amount_difference` on the same footing?) deferred to a
follow-on iteration rather than rushed to hit a deadline. **Split/batch
classification is an open item**, not a hidden gap — it's stated here and in
the Phase 3 final report.

## Data

Labels assembled by `scripts/assemble_labels.py` (evaluation-only, reads
hidden ground truth once to assign labels — never touched again downstream).

**Leakage rule stricter than transaction-group-level splitting:** a candidate
pair is only assigned to a split if *both* its ledger record's true split
and its settlement record's true split agree; disagreement excludes the pair
entirely rather than picking one side arbitrarily. Reasoning: a negative
example pairing a train-split ledger record with a test-split settlement
record would let the model see that settlement record's specific values
during training — undermining held-out evaluation for that record even
though it wasn't a positive label in that row. **323 of 1,142 V1 candidates
(28%) were excluded** on this basis — a substantial fraction, worth knowing
about rather than discovering later that "leakage-free" only meant the
looser check.

**Class distribution** (positives dominate — the reverse of typical
imbalance, because tight blocking mostly returns true matches):

| Split | Total | Positive | Negative | Positive % |
|---|---|---|---|---|
| Train | 612 | 334 | 278 | 54.6% |
| Val | 123 | 98 | 25 | 79.7% |
| Test | 83 | 70 | 13 | 84.3% |

The rising positive rate from train→val→test is explained by split size, not
a bug: negative candidates arise from coincidental amount/date collisions
between *unrelated* transactions, and smaller splits have proportionally
fewer opportunities for such collisions. Verified directly: negative-candidate
density per record is 0.698 (train, 398 records) vs 0.238 (val, 105) vs 0.157
(test, 83) — falling with split size, consistent with the explanation.

## Preprocessing

`StandardScaler` fit on train only, applied to val/test. All 22 Phase 2
features used; none excluded (this baseline treats feature selection as a
later, evaluation-driven decision, per Phase 2's rule against selecting
features by peeking at labels prematurely — this is the first phase where
labels exist at all, and no post-hoc feature pruning was done based on this
run's results).

## Class imbalance handling

Compared `class_weight=None` vs `class_weight='balanced'` **on validation
only**, before ever touching test:

| Variant | Val precision | Val recall | Val F1 |
|---|---|---|---|
| Unweighted | 1.0 | 1.0 | 1.0 |
| Balanced | 1.0 | 1.0 | 1.0 |

Both variants tied on validation. Selection rule (stated before comparing,
not chosen after seeing which looked better): prefer `balanced` on ties,
since it's the variant designed not to under-predict the class whose errors
matter more here.

## Held-out test results (reported once, not used for any tuning)

| Metric | Value |
|---|---|
| Precision | 1.0 |
| Recall | 0.9857 |
| F1 | 0.9928 |
| ROC-AUC | 1.0 |
| PR-AUC | 1.0 |
| Confusion matrix | TP=69, FP=0, FN=1, TN=13 |

**This is a strong result and it deserves scrutiny, not just reporting.**
The probability distribution on test is sharply bimodal (median 0.998, only
3 of 83 predictions fall between 5% and 95% probability) — the classification
problem is genuinely well-separated given these features, not artificially
perfect from a leakage bug (verified: no hidden columns in the feature set,
per `validate.py`'s leakage check and the dedicated leakage tests). The
caveat worth stating plainly: this is measured on synthetic corruption with
bounded severity (max 2.5% fee drift, max 5-day lag) over only 83 test
examples. Zero false positives is a genuinely good sign, but it also means
**false-positive failure modes cannot be characterized from this dataset** —
a harsher, more adversarial synthetic corruption model would be needed to
find them, which is a natural next step if time allows.

## Feature importance (Logistic Regression coefficients, by |magnitude|)

| Feature | Coefficient | Direction |
|---|---|---|
| reference_substring_overlap | +2.26 | increases match likelihood |
| reference_missing_settlement | +1.63 | increases match likelihood |
| relative_amount_diff | -1.22 | decreases match likelihood |
| reference_exact_match | +0.97 | increases match likelihood |
| date_diff_days | -0.92 | decreases match likelihood |
| abs_amount_diff | -0.90 | decreases match likelihood |
| vendor_jaro_winkler_similarity | +0.77 | increases match likelihood |

(Full list in `reports/phase3/baseline_coefficients.json`.) These are
associations the model learned, not causal claims. One point worth flagging:
`reference_missing_settlement` has a *positive* coefficient, which looks
counterintuitive until you recall the reference features' own design — a
missing reference contributes no matching evidence either way, so this
coefficient is likely absorbing correlation with *other* evidence (e.g.
batched/split settlement lines legitimately carry no reference by
construction, and those happen more often to be genuine one-to-one matches
in this specific dataset draw) rather than saying "missing references predict
matches" as a general rule. Worth re-checking if the dataset composition changes.

## Error analysis

**False positives: none observed.** Precision is 1.0 on both validation and
test. This can't be characterized further without a harder dataset — stated
as a limitation, not silently treated as "nothing to analyze."

**False negative (1, on test):** `LED-000172` / `STL-000172-0` — a true
one-to-one match with near-perfect amount agreement (diff=₹0.16) and same-day
dates, but heavily corrupted vendor naming (Levenshtein similarity 0.18,
zero exact-normalized match) **combined with** high structural ambiguity
(10 competing candidates; both `is_potential_one_to_many` and
`is_potential_many_to_one` flags set, even though the true relationship is
one-to-one). Predicted probability: 0.31. This is a genuine, informative
failure mode: strong numeric evidence undermined by vendor corruption *and*
an unlucky structural coincidence that made the pair look like it might be
part of a larger group — not a data-quality bug or a trivial case the model
should obviously have gotten right.

## Threshold behavior (validation set — see `reports/phase3/baseline_threshold_sweep_val.json` for full table)

Precision and recall are both saturated near 1.0 from threshold 0.1 through
0.9 on this validation set — a direct consequence of the same sharp
separation discussed above. **This means threshold selection on this
dataset alone would not surface a meaningful precision/recall tradeoff** —
the real tradeoff will only become visible once evaluated against harder,
more adversarial synthetic data or, eventually, real reconciliation data.
Final threshold selection (τ_high/τ_low, cost-weighted) is deferred to the
calibration phase as planned — not skipped here because it looked
unnecessary, but because this dataset can't yet exercise it meaningfully.

## Model artifact

`models/logreg_baseline_v1.joblib` — bundles the fitted model, scaler,
feature column order, class_weight choice, random seed (42), and library
versions (scikit-learn, Python). Retraining via `python -m
ml.training.train_baseline` reproduces bit-identical predictions given the
same input data (verified by `test_model_predictions_reproducible_with_fixed_seed`).

## Known limitations, stated plainly

- One-to-one only; split/batch classification is not yet part of this model.
- Test set is small (83 rows); precision/recall estimates on 13 negatives
  should be read as directional, not tightly confident.
- No false positives observed means false-positive behavior is unverified,
  not "confirmed good."
- Synthetic corruption severity is bounded (max 2.5% amount drift, 5-day
  lag) — real-world reconciliation data will likely be messier.
