# Know Your Project — ReconGuard, from the ground up

This document explains ReconGuard assuming no prior background, using
the actual implementation as the example throughout rather than
generic textbook definitions.

### 1. What is financial reconciliation?

It's the process of confirming that two independent records of money
movement agree with each other. A business keeps its own internal
record of what it's owed (the ledger); a payment processor or bank
keeps its own record of what it actually paid out (the settlement).
Reconciliation is checking that every entry on one side has a matching
entry on the other, and flagging the ones that don't.

### 2. What is a ledger?

In ReconGuard, a ledger record (`ledger_id`, `vendor_name`, `amount`,
`txn_date`, `reference_id`, `description`) is the business's own record
of an expected transaction — "what we think we're owed."

### 3. What is a settlement?

A settlement record (`settlement_id`, `vendor_name`, `amount`,
`txn_date`, `reference_id`, `description`) is what a payment processor
or bank actually reports as paid — "what actually landed."

### 4. Why don't records match directly?

Because the two sides are produced by different systems with no shared
key. Reference IDs get truncated or dropped. Amounts drift (processor
fees). Dates lag (settlement happens days after the transaction).
Vendor names get corrupted differently by each system (`"Adani
Enterprises"` vs `"ADANIENT"`). And the relationship isn't always
one-to-one — see item 18.

### 5. What is normalization?

Before anything is compared, raw records are cleaned into a consistent
internal shape — for example, `NaN` values from a CSV read (a genuinely
missing reference) are turned into `None` before they ever reach a JSON
database column, because Postgres' JSON type correctly rejects `NaN`
(not valid JSON per RFC 8259) — a real bug this project found and fixed
(`_sanitize_records()` in `backend/app/pipeline.py`).

### 6. What is candidate generation?

Instead of trying to score every possible ledger/settlement pair (which
would be computationally wasteful and mostly irrelevant), ReconGuard
first generates a much smaller pool of *plausible* pairs or groups —
"candidates" — that are worth scoring at all. Only this pool goes on to
feature extraction and ML ranking.

### 7. What is blocking?

Blocking is the technique used to generate that candidate pool cheaply:
instead of comparing every record to every other record, you only
compare records that fall within some cheap, coarse filter — in this
project, an amount window and a date window. ReconGuard runs two
blocking passes: **V1** (pairwise: amount ±5%/₹50 floor, date 0–7 days
after) for one-to-one candidates, and **V2** (structural: a bounded
combinatorial search over the same date window, group size 2–3) for
one-to-many and many-to-one candidates that V1 structurally cannot
represent (V1 only ever compares one record to one record).

### 8. What features are compared?

22 engineered features per candidate: amount similarity, date
proximity, vendor-string similarity (via RapidFuzz), reference-string
similarity, an embedding-based semantic similarity, and structural-group
aggregates (combined amounts, full date span, max similarity across
member pairs) for one-to-many/many-to-one groups. Full list:
[`docs/feature_catalog.md`](feature_catalog.md).

### 9. What does the ML model predict?

A single number: the probability that a given candidate (pair or group)
represents the same real underlying transaction.

### 10. Why Logistic Regression?

As a **baseline** — a simple, well-understood, interpretable linear
model (`class_weight='balanced'`, `StandardScaler`-preprocessed) to
compare against before committing to something more complex. On
validation it scored precision 0.9806 / recall 1.0 / F1 0.9902 — strong,
but LightGBM strictly outperformed it.

### 11. Why LightGBM?

It's a gradient-boosted tree model that can capture non-linear
interactions between features (e.g. "weak vendor similarity matters a
lot more when reference similarity is *also* weak") that a linear model
can't. On the same validation set it scored precision 1.0 / recall 1.0 /
F1 1.0 — strictly better than the Logistic Regression baseline — so it
was selected as the final ranking model
(`num_leaves=15, max_depth=4, learning_rate=0.05, n_estimators=200`).

### 12. Why calibration?

A raw model score isn't necessarily an honest probability — a model can
be systematically over- or under-confident. Calibration (sigmoid /
Platt scaling here) adjusts the raw score so that "0.85" actually means
roughly an 85% chance of being correct. This matters because the entire
downstream safety policy (item 14) is a fixed probability threshold —
if the number feeding it isn't honestly calibrated, the threshold is
meaningless. Isotonic regression was tried first and rejected because
it collapsed output to just 3 distinct values on a small validation
split — a degenerate step function, not real calibration.

### 13. What are confidence bands?

The calibrated probability is split into three bands: above HIGH (0.85)
is `HIGH_CONFIDENCE_MATCH` (auto-reconciled), below LOW (0.50) is
`LIKELY_NO_MATCH` (becomes an exception), and between the two is
`NEEDS_REVIEW` (goes to a human).

### 14. Why HIGH/LOW thresholds?

Because a single cutoff can't simultaneously minimize false positives
(wrongly auto-matching two unrelated transactions — expensive, corrupts
books) and false negatives (missing a real match — recoverable, a human
can catch it later). The two thresholds were chosen by a cost-sensitive
grid search (false positive cost 10, false negative cost 3, review cost
1) with an explicit floor: HIGH was never allowed below 0.85, even when
raw cost-minimization on the small validation sample would have
suggested lower.

### 15. What is abstention?

Choosing *not* to make an automatic decision when the evidence isn't
strong enough — instead of forcing every candidate into "match" or "no
match," the middle band (`NEEDS_REVIEW`) is a deliberate, safe
non-decision that hands the case to a human rather than guessing.

### 16. Why is ML ranking alone unsafe?

Because a probability is a statistical estimate on the *training
distribution*, and this project's own held-out test proves the point:
one-to-many recall measured 66.7%, versus 98.6% for one-to-one — a real
gap that only became visible on data the model had never been scored
against. If the raw probability directly drove irreversible
auto-matching with no other safeguard, that gap would silently misfile
split-settlement transactions in production.

### 17. What does the deterministic safety layer do?

Two things, kept structurally separate from the model:

- The **three-way threshold policy** is the single source of truth for
  what auto-reconciles — fixed numbers, not learned, not adjustable by
  the model itself.
- The **risk-flag layer** (`compute_risk_flags()` in
  `backend/app/workflow/risk.py`) returns only a `list[str]` of known
  caveats (e.g. `KNOWN_LOW_GENERALIZATION` for one-to-many candidates,
  `HIGH_COMPETITION` when ≥5 plausible candidates compete) — it has no
  code path to alter a probability or decision label. A flagged
  `HIGH_CONFIDENCE_MATCH` is still a `HIGH_CONFIDENCE_MATCH`; the flag
  is information for a human, not a silent second decision.

### 18. How are one-to-many cases handled?

Every candidate is represented as a `CandidateGroup(ledger_ids,
settlement_ids)` — both fields are lists, even for the common
one-to-one case (a 1-element list each). This means one ledger
transaction split across several settlement lines (`one_to_many`), or
several ledger transactions batched into one settlement line
(`many_to_one`), are handled through the exact same schema and feature
pipeline as one-to-one — amounts are combined sums, dates are the
group's full span, and string similarity is the maximum across every
member pair, rather than collapsing the group into a fake single ID.

### 19. How are exceptions generated?

Any candidate that falls below the LOW threshold (or has no viable
candidate at all) becomes an `ExceptionRecord` with a root-cause
category, chosen in a fixed priority order so the same conditions always
produce the same category: `NO_CANDIDATE_FOUND` → `STRUCTURAL_AMBIGUITY`
→ `HIGH_COMPETITION` → `INSUFFICIENT_EVIDENCE` → `LOW_MATCH_CONFIDENCE`
(fallback). `GET /exceptions/{id}` additionally computes a deeper,
on-demand root-cause analysis (which evidence dimension was weak, and
in what priority — amount > reference > vendor > date, grounded in the
model's own feature-importance results).

### 20. How does reviewer approval work?

A candidate in `NEEDS_REVIEW` creates an open `ReviewTask`. A human
approves or rejects it via `POST /reviews/{id}/approve` or `/reject`.
Critically, this action **never rewrites the ML decision or
probability** — those fields are immutable after creation. Only
`workflow_state` changes (e.g. to `APPROVED_BY_REVIEWER`), and a new
audit event records the reviewer's identity alongside the model's
original probability, so the two can always be directly compared. A
second attempt to resolve an already-resolved review correctly returns
HTTP 409, not a silent overwrite.

### 21. How does auditability work?

Every meaningful state change — batch creation, model evaluation,
auto-match, review-task creation, human approval/rejection, exception
creation, batch completion — is written as one immutable event via
`record_event()` (`backend/app/audit.py`), which only ever `INSERT`s.
There is no update or delete function for audit events anywhere in the
codebase. `GET /decisions/{id}/audit` merges two separate event
namespaces (`DECISION` events from the model, `REVIEW` events from a
human) into one chronological history.

### 22. Why PostgreSQL?

A real relational database with genuine ACID transactions and JSON
column support (for feature/evidence payloads) — the project's stated
production target, not a toy substitute. SQLite exists only as an
explicit, opt-in isolated-test backend (`RECONLENS_TEST_SQLITE=1`), never
a silent fallback for real runs.

### 23. Why FastAPI?

A modern, typed Python web framework with automatic request validation
(Pydantic models) and auto-generated interactive API docs (`/docs`) —
matches the rest of the stack (the ML pipeline is Python/pandas/
LightGBM), so there's no serialization boundary between the ML code and
the API layer.

### 24. Why Next.js?

A React framework with built-in routing (the App Router directly maps
to the application's routes — `/batches/[batchId]`,
`/decisions/[decisionId]`, etc.) and TypeScript support, paired here
with a single typed API-client module (`api-client.ts`) as the only
place that calls `fetch()`, so route/schema drift between frontend and
backend has one place to be caught.

### 25. How does Docker Compose fit in?

`docker-compose.yml` defines two services: `postgres` (with a
healthcheck via `pg_isready`) and `api` (depends on postgres being
healthy, runs `alembic upgrade head` then starts `uvicorn`, with its own
healthcheck hitting `/health`). The frontend isn't included in this
compose file and is run separately (`npm run dev` / `npm run build`) —
a deliberate scope decision, not an oversight.

### 26. What happens from upload → final decision?

`POST /batches` → records are sanitized and persisted as
`SourceRecord`s → blocking V1 + V2 generate candidates → 22 features
extracted per candidate → the LightGBM bundle scores + calibrates each
one → the three-way policy assigns a decision label → a
`ReconciliationDecision` (with top-5 evidence features) is persisted →
depending on the label, either the workflow state advances to
`AUTO_MATCHED`, a `ReviewTask` is created, or an `ExceptionRecord` is
created with a root-cause category — every step recording an immutable
audit event.

### 27. How was the model evaluated?

Ground-truth transactions were split into train/val/test **before** any
noise/corruption was applied, so two noisy variants of the same
underlying transaction can never land in different splits. A second,
stricter leakage rule at candidate-labeling time excludes any candidate
whose member records disagree on ground-truth split (this excluded
7,351 of 10,980 unified candidates). LightGBM was compared against
Logistic Regression on validation, selected, and then evaluated
**exactly once** on the held-out test set with no further tuning
afterward — the standard discipline that makes a held-out number
trustworthy.

### 28. What are the known limitations?

See [Known limitations](../README.md#known-limitations) in the README —
in short: measurably worse one-to-many recall (66.7% vs 98.6%),
statistically insufficient many-to-one validation data, a synthetic
(not real-world) dataset, an n-gram-hashing fallback when the real
embedding model's network dependency isn't available, application-level
(not database-enforced) audit immutability, no auth/multi-tenancy, and
synchronous (not queued) batch processing.

### 29. What would be improved in production?

Type-aware thresholds once enough structural labeled data exists; async
batch processing via a task queue; authentication and multi-tenant
scoping; guaranteed availability of the real embedding model;
stronger (database-level or cryptographic) audit-trail guarantees; and
validation against real bank/processor data to test whether the
measured metrics hold outside the synthetic distribution.
