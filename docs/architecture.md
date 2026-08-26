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
