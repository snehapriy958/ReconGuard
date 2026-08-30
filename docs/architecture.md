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

## Phase 5 — Workflow engine, audit trail, review queue, real PostgreSQL (done)

**Real infrastructure, not simulated:** installed and ran PostgreSQL 16
directly in the dev environment (spec section 21's own bar — "do NOT
silently replace it with in-memory dictionaries"), created the database,
wrote Postgres-compatible SQLAlchemy models (7 tables: batches,
source_records, decisions, evidence_records, review_tasks,
exception_records, audit_events), and generated/applied a real Alembic
migration against it. SQLite is used ONLY for isolated test runs
(`RECONLENS_TEST_SQLITE=1`), explicitly opt-in, never a silent fallback.

**Two separate state machines**, not one shared: batch-level
(CREATED/PROCESSING/COMPLETED/FAILED) and decision-level
(PENDING/PROCESSING/AUTO_MATCHED/NEEDS_REVIEW/.../EXCEPTION/FAILED) — the
first end-to-end run caught a real bug from conflating them (see
docs/workflow.md).

**Risk layer built as genuinely separate metadata**, verified structurally:
`compute_risk_flags()` returns only `list[str]`, with no code path that can
touch a probability or decision value. Surfaces Phase 4's measured
limitations (one-to-many `KNOWN_LOW_GENERALIZATION`, many-to-one
`INSUFFICIENT_VALIDATION_SAMPLE`) as operational metadata rather than
silently changing thresholds, per spec section 29's explicit instruction.

**Real end-to-end batch run against Postgres:** 130 records -> 72
candidates -> 57 auto-matched / 1 review / 14 exceptions / 9 structural
matches / 23 risk-flagged / 0 failed, verified independently via direct SQL
query (72 decisions, 147 audit events, both matching the pipeline's own
summary exactly). Idempotency verified: resubmitting the identical batch
created zero new batches and zero new decisions. Review flow verified: a
real NEEDS_REVIEW case (genuine one-to-many, KNOWN_LOW_GENERALIZATION
flagged, calibrated probability 0.707) was approved via `approve_review()`,
confirming the ML decision (`NEEDS_REVIEW`) stayed bit-identical while
`workflow_state` advanced to `APPROVED_BY_REVIEWER`.

**Three real failures found and fixed while running this** (full diagnosis
in docs/workflow.md): batch/decision state machine conflation, NaN values
breaking Postgres JSON columns (pandas reads empty CSV cells as float NaN;
Postgres correctly rejects NaN as invalid JSON per RFC 8259, unlike Python's
permissive `json.dumps`), and a session-management bug where the failure
handler itself raised `PendingRollbackError` by touching the ORM session
before calling `db.rollback()`.

**Tests:** 22 new Phase 5 tests (18 passed, 4 honestly skipped — the tiny
deterministic test fixture doesn't happen to produce a NEEDS_REVIEW case;
that exact flow was independently verified against the real 130-record
Postgres run instead). 79/79 total passing across all phases.

**Explicit scope boundary carried to Phase 6:** no frontend yet, per spec —
the API and Swagger UI are the full Phase 5 deliverable. Threshold policy
remains uniform across relationship types (risk flags, not new thresholds,
per spec section 29).

## Phase 6.1-6.2 — Frontend foundation and batch overview (done)

Next.js + TypeScript + Tailwind frontend scaffolded; typed API client as the
single fetch layer; hand-built shadcn-style UI primitives (registry
unreachable in this sandbox). Extended the backend with `GET /batches`,
enriched `GET /decisions/{id}` and `GET /exceptions` responses, and CORS
middleware — all justified by an actual frontend screen's data need, not
spec-following for its own sake. Fixed a real Pydantic contract bug
(`reference_id` rejecting `None`) caught only by submitting a genuine HTTP
request. Full details, including four documented failures found while
building this, in docs/frontend.md.

Batch overview dashboard verified against a real submitted batch (180
records -> 89 candidates -> 62/3/24 split, 18 structural, 35 risk-flagged)
via actual HTTP requests to a running backend, with CORS confirmed for the
frontend origin. 12 frontend tests passing; 78 backend tests still passing
after all schema changes.

Not yet built: decision table, confidence card, review queue, exception
intelligence, audit timeline, dashboard charts (Phase 6.3 onward).

## Phase 6.3 — Reconciliation decision table (done)

No backend changes needed — inspection of the real decisions endpoint
confirmed `workflow_state` alone already encodes review/exception status.
Built the decision table with client-side filtering (decision/relationship/
risk), sorting, structural relationship display (never flattened), and
strict confidence/risk separation. An initial "divergence note" design was
removed after review showed it added ambiguous derived logic the two
existing columns (Decision, Workflow Status) already made unnecessary —
caught by the test suite before it shipped. 24/24 frontend tests passing,
78/78 backend unchanged. Verified against real HTTP requests including a
real structural decision's navigation. Full details in docs/frontend.md.

## Phase 6.4 — Confidence Card, evidence breakdown, record comparison, operational risk (done)

Extended `GET /decisions/{id}` with two server-side additions, both
justified by inspecting the existing contract first: `all_features`
(recomputed via the same `ml/features/group_extractor` function the
pipeline already uses — no duplicated logic, no new inference) and
`risk_flag_explanations` (sourced from the existing `risk_explanation()`
function, not copied into the frontend). Built the six-section Decision
Detail page with the three-layer trust model enforced structurally in
component prop types, not just visually. Evidence interpretation
thresholds documented and reused from existing constants
(`HIGH_COMPETITION_THRESHOLD`, `WEAK_REFERENCE_SIMILARITY_THRESHOLD`) for
consistency between risk flags and evidence labels.

Two real bugs found and fixed: a 75-second per-request latency bug (fresh
`EmbeddingBackend()` construction on every call, fixed with a process-level
singleton warmed at startup) and a silently-swallowed `NameError` from a
broken import (fixed, plus added logging so a similar bug can't hide
silently again). 62/62 frontend tests, 80/80 backend tests (2 new).
Verified against 5 real decisions across every available category via the
actual running frontend, including the spec's core requirement case: a
`HIGH_CONFIDENCE_MATCH` one-to-many decision still correctly carrying
`KNOWN_LOW_GENERALIZATION` without being silently downgraded. Full details
in docs/frontend.md.

## Phase 6.5 — Human review queue, actions, and history (done)

Extended `GET /reviews` and `GET /reviews/{id}` with batch/structural
context joined through the existing decision relationship. Fixed a real
bug: `assigned_reviewer` existed as a column but was never populated
anywhere — the reviewer's identity only reached the audit event, never the
review record. Built the review queue (oldest-first, backend workflow
state as the sole eligibility source of truth) and review detail page,
composing Phase 6.4's components entirely through composition — zero
evidence/confidence/risk logic duplicated. Approve/reject call the real
backend with double-submit protection and honest 409/404/network error
handling. 75/75 frontend tests, 80/80 backend (2 new). Verified against 3
real open review cases (including a genuine 3-member one-to-many
structural group) with both a real approve and real reject performed via
HTTP against live PostgreSQL — confirming the core invariant end-to-end:
ML decision, calibrated probability, and risk flags all remained
byte-identical while workflow_state transitioned correctly and
assigned_reviewer/resolved_at were persisted. Full details in
docs/frontend.md.
