# ReconGuard — Razorpay Buildathon Submission

**Track:** Track 04 — AI Finance Controller
**Project name:** ReconGuard (internal engineering/repository name: ReconLens)

## One-line value proposition

A learned, risk-aware financial reconciliation engine that auto-matches
high-confidence ledger/settlement pairs, routes genuinely uncertain ones
to a human, and keeps an immutable audit trail of every decision —
instead of forcing a binary choice between slow manual reconciliation and
blind full automation.

## A. Project name
ReconGuard

## B. Track
Razorpay Buildathon — Track 04: AI Finance Controller

## C. One-line value proposition
See above.

## D. Problem

Financial reconciliation — matching a company's internal ledger against
what a payment processor or bank actually settled — looks like a simple
join and almost never is:

- No shared primary key across source systems.
- Reference IDs get truncated, reformatted, or dropped entirely between
  ledger and settlement.
- Amounts, dates, and vendor names drift (processor fees, settlement
  lag, corrupted vendor strings — e.g. `"Adani Enterprises"` vs
  `"ADANIENT"` vs `"Adani Enteprrises"`).
- Relationships aren't always 1:1 — a single ledger transaction can be
  split across multiple settlement lines, and several ledger
  transactions can be batched into one settlement line. A naive join
  cannot represent either case.
- Some candidates are genuinely ambiguous, and a system that is
  confidently wrong here doesn't just misclassify a row — it silently
  corrupts a company's financial records.

## E. Solution

ReconGuard implements the full pipeline end to end: ingestion →
normalization → candidate generation (two blocking passes, pairwise +
structural) → feature extraction → ML ranking → probability calibration
→ a three-way confidence policy → safe abstention → human review →
exception root-cause analysis → an immutable audit trail. Every stage
persists to PostgreSQL and is inspectable through a Next.js frontend
(batch dashboard, decision detail, review queue, exception queue, audit
timeline) and a documented FastAPI backend.

## F. How AI/ML is used

- **Candidate ranking, not candidate discovery.** Two deterministic
  blocking passes (amount/date windows for pairwise; a bounded
  combinatorial search for structural groups) generate the candidate
  pool with 100% measured recall on both relationship types. The ML
  model's job is narrower and better-suited to learning: rank candidates
  *within* that pool.
- **LightGBM** (`num_leaves=15, max_depth=4, learning_rate=0.05,
  n_estimators=200, class_weight='balanced'`) is trained on 22
  engineered features per candidate (amount similarity, date proximity,
  vendor-string similarity, reference-string similarity, embedding
  similarity, structural-group aggregates) and selected over a Logistic
  Regression baseline after both were compared on the same held-out
  validation split.
- **Calibration, not raw scores.** The model's raw probability is
  calibrated with sigmoid (Platt) scaling so the number it outputs is an
  honest probability, not an arbitrary score — this is what makes a
  fixed threshold policy meaningful in the first place.
- There are **no LLM agents, no RAG, and no chatbot layer** anywhere in
  this project. The learned reconciliation model is the AI; everything
  else is deterministic orchestration, persistence, and governance
  around it.

## G. Why deterministic safety is necessary

An ML probability is a statistical estimate, not a certainty, and this
project's own held-out evaluation demonstrates why that distinction
matters operationally: one-to-many recall measured 66.7% on held-out
test versus 98.6% on one-to-one — a real, sizeable performance gap that
only appeared once, on data the model had never seen scored against. If
the system trusted the raw probability alone, that gap would silently
misclassify split-settlement transactions in production with no
mechanism to catch it. Instead:

- The calibrated probability only ever feeds a **fixed, explicit
  three-way policy** (HIGH = 0.85, LOW = 0.50) — the model never decides
  its own threshold, and the threshold was chosen by a cost-sensitive
  grid search (false positives weighted 10× a false negative's 3×) with
  a hard floor (HIGH never below 0.85) rather than pure cost
  minimization on a small sample.
- A **separate, additive risk layer** (`compute_risk_flags()`) surfaces
  known weaknesses — e.g. `KNOWN_LOW_GENERALIZATION` on one-to-many
  candidates — as metadata a human can act on. It has no code path to
  alter a probability or a decision label; confidence and risk are
  structurally kept apart so risk information is never used to quietly
  override a threshold-based decision.
- **Human review is a first-class workflow state**, not an
  afterthought: anything landing between thresholds becomes an open
  review task, and approving/rejecting it never rewrites the original
  ML decision — only the workflow state changes, with the reviewer's
  identity and the model's original probability both preserved in the
  audit trail for direct comparison.
- **Every state change is logged as an immutable event** — model
  evaluation, auto-match, review creation, human approval/rejection,
  exception creation — so any final decision, automated or human, can
  be traced back to exactly what produced it.

## H. Architecture

```
Next.js frontend  ──HTTP──►  FastAPI backend  ──►  PostgreSQL 16
(batch dashboard,            (single API surface;      (batches, source_records,
 decision detail,             candidate generation,      decisions, evidence_records,
 review queue,                 feature extraction,        review_tasks,
 exception queue,                LightGBM + calibrator,     exception_records,
 audit timeline)                  workflow state machines,   audit_events)
                                    risk layer, audit trail)
```

No task queue — batches are processed synchronously inside `POST
/batches`, appropriate at this project's data volumes. Full write-up:
[`docs/architecture.md`](architecture.md).

## I. Key features

- Two-pass candidate generation (pairwise blocking V1 + structural
  blocking V2) with 100% measured recall on one-to-one, one-to-many, and
  many-to-one relationship types.
- 22-feature vector per candidate feeding a calibrated LightGBM ranker.
- Three-way confidence policy with a bounded-autonomy floor.
- Structural relationship handling (one-to-one / one-to-many /
  many-to-one) through a single `CandidateGroup` schema — no fake
  1:1 collapsing.
- A separate, additive risk-flag layer, grounded in measured evaluation
  results (not arbitrary rules).
- Human review workflow with double-submit protection and a proven
  invariant: the original ML decision and probability are never
  overwritten by a review action.
- Deterministic, priority-ordered exception root-cause classification,
  plus an on-demand deeper root-cause analysis endpoint.
- Fully immutable, INSERT-only audit trail covering every meaningful
  state change, queryable per-entity and merged per-decision.
- Idempotent batch submission (duplicate submissions return the
  original batch rather than reprocessing).

## J. Evaluation / results

Dataset: 600 ground-truth synthetic transactions → 586 ledger + 607
settlement records → 10,980 unified candidates (V1 + V2) → 3,629 labeled
candidates after leakage exclusion (excluded 7,351 candidates whose
member records disagreed on ground-truth split).

Structural distribution of the 600 ground-truth transactions: 481
one-to-one, 50 batched settlements (many-to-one), 36 split settlements
(one-to-many), 19 ledger-only, 14 settlement-only.

Candidate generation recall (measured): V1 (pairwise) 100% recall on
one-to-one; V1+V2 combined 100% recall on both structural types.

Validation comparison (151 candidates): Logistic Regression — precision
0.9806, recall 1.0, F1 0.9902; LightGBM — precision 1.0, recall 1.0, F1
1.0, ROC-AUC 1.0, PR-AUC 1.0.

**Held-out test (evaluated exactly once, no further tuning after):**
precision 1.000, recall 0.961, F1 0.9801, ROC-AUC 0.9983, PR-AUC 0.9995;
confusion matrix TN=23, FP=0, FN=3, TP=74.

By relationship type on test: one-to-one precision 1.0 / recall 0.9857
(n=83); one-to-many precision 1.0 / recall **0.6667** (n=11 — the known
generalization gap); many-to-one precision 1.0 / recall 1.0 (n=6, only 1
positive — not statistically meaningful on its own).

Three-way policy applied to test: 71 auto-matched (precision 1.0, recall
0.9221), 3 sent to review (100% actually positive), 26 marked likely-no-
match (11.5% error rate — up from 0% on validation, a real,
honestly-reported generalization gap).

## K. Known limitations

- One-to-many (split settlement) recall is measurably worse than
  one-to-one on held-out test (66.7% vs 98.6%) — surfaced via
  `KNOWN_LOW_GENERALIZATION`, not hidden, and not patched with a
  type-specific threshold because too few structural positive examples
  exist to tune one safely.
- Many-to-one held-out performance (n=1 positive) is not statistically
  meaningful; flagged via `INSUFFICIENT_VALIDATION_SAMPLE`.
- The likely-no-match error rate rose from 0% (validation) to 11.5%
  (test) — a real limitation the held-out evaluation exists specifically
  to catch, and the policy was deliberately not re-tuned against it
  afterward.
- Semantic similarity falls back to a deterministic n-gram-hashing
  embedder (clearly tagged in every output) in any environment without
  network access to Hugging Face; the Dockerfile attempts a best-effort
  pre-cache of the real model at build time.
- The dataset is synthetic, generated with a controlled, documented
  corruption model — reported metrics describe this synthetic
  distribution, not a guarantee about real bank/processor data.
- Audit-trail immutability is application-level (one INSERT-only write
  path), not database-enforced or cryptographically verifiable.
- No authentication or multi-tenancy; CORS is scoped to local
  development origins only.
- No task queue — batch processing is synchronous, which is fine at
  this project's data volumes but would not scale to very large
  production batches unmodified.

## L. Future production improvements

- Type-aware (or otherwise data-driven) thresholds for one-to-many once
  enough labeled structural examples exist to tune one safely, instead
  of the current uniform HIGH/LOW policy.
- Async batch processing (task queue) to decouple large-batch runtime
  from the request/response cycle.
- Authentication, authorization, and multi-tenant scoping for a
  deployed (non-local-demo) setting.
- Guaranteed network access (or a bundled model artifact) for the real
  sentence-transformer embedding backend, removing dependence on the
  n-gram-hashing fallback.
- Database-level or cryptographic append-only guarantees on the audit
  trail, beyond the current application-level INSERT-only discipline.
- Validation against real (not synthetic) ledger/settlement data to
  test whether the measured metrics generalize to real-world corruption
  patterns.
