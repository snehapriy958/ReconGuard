# ReconLens — Architecture Notes

Living document, updated at the end of each build phase with what was built and why.
This is what you'll draw from for the 5-minute video and for interview follow-ups.

## Phase 1 — Synthetic data generation (done)

**What:** `ml/data_generation/generate.py` produces `data/raw/ledger.csv` and
`data/raw/settlement.csv` from one internally-generated ground-truth transaction set.

**Key decisions and why:**

- **Split assigned before corruption, at the ground-truth level.** If you split after
  generating corrupted variants, two noisy versions of the same underlying transaction
  can land in different splits — the model would then be implicitly evaluated on
  transactions it has effectively already seen. Assigning `train`/`val`/`test` to the
  ground-truth transaction *first*, then deriving all corrupted variants from that
  labeled transaction, makes leakage structurally impossible rather than something
  you have to remember to check for later.

- **Batched settlements (many ledger records -> one settlement line) are grouped
  within the same split only.** A batch spanning train and test would reintroduce
  exactly the leak the split-first rule exists to prevent — one settlement line would
  effectively hand the model test-set information during training.

- **Genuine unmatched records exist by construction** (`ledger_only` = pending
  settlement, `settlement_only` = unrelated bank line such as a fee reversal), at
  roughly 5.5% combined. This means "no match" is a real, learnable outcome, not an
  edge case bolted on afterward — necessary for precision/recall on the negative
  class to mean anything.

- **Public CSVs never carry the ground-truth transaction ID.** It lives only in
  `_hidden_ledger_truth.csv`, `_hidden_settlement_truth.csv`, and
  `_hidden_match_map.json` — files that only the evaluation code should ever open.
  Phase 4 will add a test that fails the build if any feature-extraction code
  imports these.

**Current dataset (seed=42, n=600 ground-truth transactions):**
586 ledger records, 608 settlement records — 481 one-to-one, 50 batched, 36 split,
19 ledger-only exceptions, 14 settlement-only exceptions. Train/val/test = 407/109/84
ground-truth transactions.

**Open question carried into Phase 2:** the corruption severities (0.15 for ledger,
0.55 for settlement) were chosen to be "hard enough to need ML, not so hard that even
a human couldn't reconcile it." Worth revisiting once precision/recall numbers come
back from the baseline — if precision is suspiciously high, severity is too low.

## Phase 2 — Feature extraction (done)

**What:** `ml/features/{normalize,numeric,string_similarity,reference,embeddings,structural,candidate_generation,extractor,validate,quality_report}.py`
transform `ledger.csv` + `settlement.csv` into a 22-feature, leakage-free
ML-ready dataset (`data/processed/features.parquet`), plus an automated
quality report (`reports/feature_quality_report.md`) and a human-readable
catalog (`docs/feature_catalog.md`).

**Verified, not assumed:**
- Candidate generation (blocking): 1,136 candidate pairs from 586×608 records
  (313.6x reduction vs. naive O(n·m)). Recall against hidden ground truth:
  **80.3%** (502/625 true pairs) — with the entire gap isolated to
  split/batched-settlement components that fall outside a single-record
  amount window by construction (confirmed: 0 one-to-one losses).
- All 8 data-sanity checks in `validate.py` pass on the real dataset: no
  NaN/inf, binary columns strictly {0,1}, similarities in [0,1], embedding
  cosine in [-1,1], non-negative amount diffs, no duplicate pairs, valid
  identifiers, no ground-truth-derived columns present.
- 29/29 unit tests pass, covering normalization, numeric edge cases (zero/
  negative amount now raises rather than producing a 5-billion-scale
  garbage ratio — caught during testing, fixed before this became a model
  input), date parsing (including the Phase-1 timestamp-vs-date format the
  architecture notes flagged), string similarity, reference truncation/
  missing-value handling, embeddings, and an explicit leakage guard.

**Real finding, not fabricated:** this build environment has no network
route to huggingface.co, so `sentence-transformers` cannot download model
weights here. Section 9 of the build spec chose local embeddings specifically
to avoid "external dependency for demo execution" — but a vanilla
`SentenceTransformer(...)` call still needs network on first use, so as
specified it doesn't actually achieve that goal unless the weights are
pre-baked into the deployment image. Added a clearly-logged, deterministic
n-gram-hashing fallback so the pipeline still runs end-to-end here; every
report tags which backend actually produced its numbers so fallback output
is never mistaken for real semantic similarity. **Action item carried to
Phase 8:** pre-download and cache `all-MiniLM-L6-v2` at Docker build time.

**Known limitation carried forward:** Jaro-Winkler can score unrelated
vendor names above 0.6 (observed directly, e.g. two dissimilar 30+ character
names sharing common words like "company"). Documented in the feature
catalog rather than patched — it's a real property of the metric, which is
exactly why the classifier gets four independent string-similarity features
instead of relying on one.

## Phase 3 — Candidate-recall remediation + Logistic Regression baseline (done)

**Candidate generation:** V1 baseline independently re-verified (100% one-to-one,
0% structural recall — confirmed, not assumed). Root cause of the 0% structural
recall traced to a genuine **Phase 1 data-generation bug**, not a blocking
weakness: batch members had no date-proximity constraint and could be
generated months apart. Fixed at the source (synchronized batch-member dates
at generation time), regenerated the dataset, and re-verified Phase 1/2 tests
still pass on the corrected data. Built Blocking V2 (bounded structural
search, tuned via a real tolerance sweep to 0.025/₹7) achieving **100% recall
on all three relationship types** with a measured, deliberate candidate-volume
tradeoff (9,838 structural candidates against 50 true structural groups).
Full write-up: `docs/candidate_generation.md`.

**Label assembly:** evaluation-only (`scripts/assemble_labels.py`), scoped
to the V1 pairwise candidate set (structural-group classification deferred,
stated explicitly — see `docs/model_baseline.md`). Leakage rule is stricter
than transaction-group splitting: both records in a candidate pair must
agree on ground-truth split, or the pair is excluded entirely. This excluded
323 of 1,142 candidates (28%) — a real, substantial fraction.

**Logistic Regression baseline:** trained on 22 Phase 2 features, StandardScaler
preprocessing, `class_weight='balanced'` selected (tied with unweighted on
validation). Held-out test: precision 1.0, recall 0.9857, F1 0.9928. This
result was scrutinized, not just reported — probability distribution is
sharply bimodal (genuinely well-separated problem, not a leakage artifact,
confirmed via the existing leakage tests), zero false positives observed
(stated as "unverified" rather than "confirmed good" — no FP data to
characterize failure modes from), one false negative traced to vendor
corruption compounding with structural ambiguity (10 competing candidates on
a true one-to-one pair). Full write-up: `docs/model_baseline.md`.

**Tests:** 13 new Phase 3 tests, 42/42 total passing (Phase 2 + Phase 3).

**Explicit scope boundary carried to Phase 4:** structural (split/batch)
candidates are not yet classified by any model — this baseline covers
one-to-one reconciliation only.

## Phase 4 — Structural classification, LightGBM, calibration, thresholds (done)

**Structural classification gap found and fixed first, per Objective 1's
stop-and-fix requirement:** Phase 3's labeled dataset was pairwise-only;
structural (V2) candidates had recall but no feature vector or label. Built
`ml/features/group_extractor.py`, generalizing Phase 2's pairwise features to
any group shape (verified bit-identical on the 15 core features for (1,1)
candidates; 5 count-based structural features intentionally redefined over
the full V1+V2 pool, documented not hidden). Unified dataset: 10,980
candidates, 3,629 labeled after leakage exclusion (7,351 excluded for
cross-split disagreement — a real, substantial fraction, much larger than
Phase 3's 28% because structural candidates freely span the date-windowed
pool). Train positive rate 11.1% (a realistic imbalance, vs Phase 3's
54.6%); val has **zero many-to-one positives**, a real evaluation blind spot
carried forward.

**Model comparison:** LightGBM (config: num_leaves=15, max_depth=4,
learning_rate=0.05, n_estimators=200, class_weight=balanced) outperformed
Logistic Regression on every validation metric (F1 1.0 vs 0.9902, zero FP vs
2). Notably the *simplest* of 4 tried configs won — flagged as a legitimate
finding, not a search failure. `reference_missing_settlement` investigated
and removed: 100% correlated with relationship type purely due to a
generator construction quirk (batch settlements always blank), not real
financial signal; ablation showed negligible cost to removing it.

**Calibration:** isotonic regression tried first, failed — collapsed
LightGBM's output to 3 discrete values (0.0/0.995/1.0) when fit on a small,
well-separated validation half, giving a trivially "perfect" but degenerate
Brier score of 0.0. Switched to sigmoid (Platt) scaling: 121 distinct
values, smooth 0.01-0.99 range, honestly higher Brier (0.00714) that
reflects real calibration rather than a broken step function.

**Threshold policy:** cost-sensitive three-way policy (HIGH=0.85, LOW=0.50)
selected on validation; naive grid search first produced a degenerate
zero-review-band policy (traced directly to the isotonic collapse above,
fixed by the calibration fix). Final policy demonstrates genuine bounded
autonomy: on validation, all 6 review-zone candidates were true matches the
model correctly declined to auto-approve; zero false positives reached
auto-match on either validation or test.

**Held-out test (evaluated once):** precision 1.0, recall 0.961, F1 0.9801.
**Real, uncomfortable finding surfaced only here:** one-to-many recall drops
to 66.7% (2/6 missed) — invisible during validation (only 3 one-to-many
positives there). Likely-no-match error rate on test: 11.5% (vs 0% on val),
directly tracking this recall drop. Not re-tuned against — reported as a
known limitation for future work.

**Tests:** 15 new Phase 4 tests, 57/57 total passing.

**Confidence-card explanation payload:** built using LightGBM's native
`pred_contrib` (Shapley-consistent additive attributions) rather than adding
a SHAP dependency — backend contract only, no UI built yet.

**Explicit scope boundary carried to Phase 5:** threshold policy is uniform
across relationship types despite one-to-many's measurably worse
performance; a type-aware threshold is reasonable future work, not
implemented due to too few structural positives to tune against safely.
