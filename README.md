# ReconGuard

**A learned, risk-aware financial reconciliation engine — with bounded
autonomy, human review, and a full audit trail — built end-to-end for a
payments/settlement reconciliation problem.**

ReconGuard takes raw ledger records (what your books say you were owed)
and settlement records (what actually landed from a payment processor or
bank), and decides — with a calibrated, measured probability, not a
hand-tuned rule — whether each pair or group of records represents the
same underlying transaction. High-confidence matches are auto-reconciled.
Genuinely uncertain ones are routed to a human. Everything the system does
is logged as an immutable event so any decision can be traced back to the
evidence that produced it.

This project was built for Razorpay's reconciliation problem statement as
a hackathon MVP. It is a real, working system — real PostgreSQL, a real
trained and calibrated model, a real Next.js frontend — but it is **not**
a production-certified financial system. See [Known limitations](#known-limitations)
for an honest account of where it currently falls short.

---

## Table of contents

1. [What problem this solves](#what-problem-this-solves)
2. [The ReconGuard approach](#the-reconguard-approach)
3. [Architecture](#architecture)
4. [Matching pipeline](#matching-pipeline)
5. [ML approach](#ml-approach)
6. [Safety and governance](#safety-and-governance)
7. [Human review](#human-review)
8. [Exceptions](#exceptions)
9. [Auditability](#auditability)
10. [Dataset and evaluation](#dataset-and-evaluation)
11. [Model metrics](#model-metrics)
12. [Tech stack](#tech-stack)
13. [Application routes](#application-routes)
14. [API](#api)
15. [Project structure](#project-structure)
16. [Setup](#setup)
17. [Testing](#testing)
18. [Demo flow](#demo-flow)
19. [Known limitations](#known-limitations)
20. [Submission materials](#submission-materials)

---

## What problem this solves

Financial reconciliation — matching a company's internal ledger against
what a payment processor or bank actually settled — sounds like it should
be a simple join. In practice it almost never is:

- **Multiple source systems** each with their own record-keeping
  conventions, so there's no shared primary key to join on.
- **Inconsistent references** — a reference ID present on the ledger side
  might be truncated, reformatted, or missing entirely by the time it
  reaches a settlement file.
- **Amount, date, and vendor-name drift** — processor fees get deducted,
  settlement lags the original transaction by days, and vendor names get
  corrupted by different upstream systems (`"Adani Enterprises"` vs
  `"ADANIENT"` vs `"Adani Enteprrises"`).
- **One-to-many and many-to-one relationships** — a single ledger
  transaction can be split across multiple settlement lines, and several
  ledger transactions can be batched into a single settlement line. A
  naive one-to-one join structurally cannot represent either case.
- **Ambiguity and operational risk** — some candidates genuinely have
  several plausible matches, and an automated system that is confidently
  wrong here doesn't just misclassify a row, it silently corrupts a
  company's financial records.

ReconGuard is for **finance and payments operations teams** who need to
reconcile ledger and settlement data at a scale where manual matching is
too slow, but where blind automation is too risky — the system needs to
know when to act on its own and when to hand off to a person.

## The ReconGuard approach

ReconGuard implements the full pipeline end to end:

```
Source ingestion
  -> Normalization
    -> Candidate generation / blocking (pairwise + structural)
      -> Feature extraction (22 features per candidate)
        -> Deterministic + fuzzy matching signals feed the model
          -> ML ranking (LightGBM)
            -> Probability calibration (sigmoid / Platt scaling)
              -> Confidence thresholds (three-way policy)
                -> Safe abstention (LIKELY_NO_MATCH / NEEDS_REVIEW)
                  -> Human review (approve / reject, ML decision preserved)
                  -> Exception creation (evidence-based root-cause category)
                    -> Evidence + audit trail (every step, immutable)
```

Nothing in this pipeline is a black box: every stage has a documented
design decision, a measured result, and (where relevant) a documented
failure that was found and fixed during development. Deep-dive
write-ups for each stage live in [`docs/`](docs/) and are linked
throughout this README.

## Architecture

```
┌─────────────────────────┐        ┌──────────────────────────────────┐
│   Next.js frontend        │  HTTP  │        FastAPI backend            │
│   (batch dashboard,        │ ─────► │   (single API surface,             │
│    decision detail,        │◄────── │    orchestration + persistence,    │
│    review queue,            │        │    no LLM agents, no RAG)          │
│    exception queue,         │        │                                    │
│    audit timeline)          │        │  ┌──────────────────────────┐      │
└─────────────────────────┘        │  │  Candidate generation      │      │
                                       │  │  (blocking V1 + V2)        │      │
                                       │  └──────────────────────────┘      │
                                       │  ┌──────────────────────────┐      │
                                       │  │  Feature extraction        │      │
                                       │  │  (group_extractor.py)      │      │
                                       │  └──────────────────────────┘      │
                                       │  ┌──────────────────────────┐      │
                                       │  │  LightGBM + calibrator     │      │
                                       │  │  (reconlens_phase4_final)  │      │
                                       │  └──────────────────────────┘      │
                                       │  ┌──────────────────────────┐      │
                                       │  │  Workflow state machines   │      │
                                       │  │  Risk layer / audit trail  │      │
                                       │  └──────────────────────────┘      │
                                       │                 │                    │
                                       │                 ▼                    │
                                       │        PostgreSQL 16                 │
                                       │  (batches, source_records,           │
                                       │   decisions, evidence_records,       │
                                       │   review_tasks, exception_records,   │
                                       │   audit_events)                      │
                                       └──────────────────────────────────┘
```

**No LLM agents, no RAG, no chatbot layer.** The learned reconciliation
model *is* the AI here; the API layer is orchestration, persistence, and
human oversight around it — deliberately, not by omission.

The backend is a single FastAPI application (`backend/app/api/main.py`)
backed by seven PostgreSQL tables via SQLAlchemy, with Alembic migrations.
SQLite is used only as an explicit, opt-in isolated-test backend
(`RECONLENS_TEST_SQLITE=1`) — never a silent fallback for real runs.

The frontend is a Next.js (App Router) + TypeScript application with a
single typed API-client module as the only place that calls `fetch()`,
and hand-built shadcn-style UI primitives (Radix + class-variance-authority
+ tailwind-merge — the same libraries shadcn/ui itself is built on).

Full write-up: [`docs/architecture.md`](docs/architecture.md).

## Matching pipeline

Candidates are generated in two passes:

- **Blocking V1** (pairwise): amount window (±5%, floor ₹50) × date window
  (0–7 days after the ledger date). Achieves 100% recall on one-to-one
  pairs, but is structurally incapable of representing split or batched
  settlements — it only ever compares one ledger record to one settlement
  record.
- **Blocking V2** (structural): a bounded combinatorial search (group size
  2–3) over the same date window, tuned via a real tolerance sweep to
  0.025 relative / ₹7 absolute floor — the tightest setting that still
  achieves 100% recall on both structural relationship types.

Every candidate is represented as a `CandidateGroup(ledger_ids, settlement_ids)`
so **one-to-one, one-ledger-to-many-settlements, and
many-ledger-to-one-settlement** are all handled through the same feature
schema — amounts are aggregated as combined sums, dates as the group's
full span, and string/reference similarity as the maximum across every
member pair (a single strongly-matching pair is real evidence even if
other cross-pairs look unrelated).

Combined, V1 + V2 generate **10,980 candidates** from 586 ledger and 607
settlement records — a large, deliberate over-generation (structural
candidates outnumber true structural groups roughly 200:1) whose cost is
paid explicitly at the candidate stage so that recall is never the
bottleneck; the ranking model's job is to separate true matches from this
wider pool. Full write-up, including the tolerance sweep and a documented
Phase 1 date-generation bug found and fixed along the way:
[`docs/candidate_generation.md`](docs/candidate_generation.md) and
[`docs/structural_matching.md`](docs/structural_matching.md).

## ML approach

Two models were trained and compared on the same unified (pairwise +
structural) labeled dataset:

- **Logistic Regression** (baseline, `class_weight='balanced'`,
  `StandardScaler` preprocessing)
- **LightGBM** (`num_leaves=15, max_depth=4, learning_rate=0.05,
  n_estimators=200, class_weight='balanced'`) — selected as the final
  ranking model, strictly outperforming Logistic Regression on every
  validation metric (see [Model metrics](#model-metrics))

LightGBM's raw output is **calibrated with sigmoid (Platt) scaling** —
isotonic regression was tried first and rejected because it collapsed the
model's output to just 3 distinct probability values on a small,
well-separated validation half, a degenerate step function rather than
genuine calibration. Sigmoid scaling preserves 121 distinct, smoothly
spread probability values at the cost of a higher (but honest) Brier
score. Full write-up: [`docs/calibration.md`](docs/calibration.md).

Calibrated probabilities feed a **three-way threshold policy**
(HIGH = 0.85, LOW = 0.50) chosen via a cost-sensitive grid search
(false positives weighted 10× a false negative's 3×, per the project's
stated financial-risk assumption), with an explicit bounded-autonomy
floor — the HIGH threshold was never allowed to drop below 0.85, even
when a pure cost-minimization on a small validation sample would have
chosen lower. Full write-up: [`docs/threshold_policy.md`](docs/threshold_policy.md).

A known, explicitly-tracked limitation: **one-to-many (split settlement)
recall drops to 66.7%** on the held-out test set (2 of 6 missed) — visible
only once, since validation had just 3 one-to-many positives to evaluate
against. This is surfaced operationally via a risk flag
(`KNOWN_LOW_GENERALIZATION`), not hidden or silently patched by lowering a
threshold with too little data to tune it safely. See
[Safety and governance](#safety-and-governance) and
[`docs/model_comparison.md`](docs/model_comparison.md) /
[`docs/structural_matching.md`](docs/structural_matching.md) for full
numbers.

## Safety and governance

ReconGuard makes a hard structural separation between **model confidence**
(the calibrated probability) and **risk** (known, measured facts about a
candidate's reliability that the probability alone doesn't communicate).
`compute_risk_flags()` in `backend/app/workflow/risk.py` returns only a
`list[str]` — there is no code path by which it can alter a probability
or a decision label. A `HIGH_CONFIDENCE_MATCH` with risk flags is still a
`HIGH_CONFIDENCE_MATCH`; the flags are metadata a human can act on, not a
silent second decision layer.

Risk flags include (grounded in measured evaluation results, not
arbitrary):

| Flag | Condition | Why |
|---|---|---|
| `STRUCTURAL_MATCH` / `ONE_TO_MANY_RELATIONSHIP` / `MANY_TO_ONE_RELATIONSHIP` | relationship type | Surfaces non-trivial structure |
| `KNOWN_LOW_GENERALIZATION` | one_to_many | Held-out test recall 66.7% for this type |
| `INSUFFICIENT_VALIDATION_SAMPLE` | many_to_one | Validation had zero positive examples of this type |
| `HIGH_COMPETITION` | ≥5 competing candidates | Grounded in a real documented false-negative case |
| `WEAK_REFERENCE_EVIDENCE` / `MISSING_REFERENCE` | reference signal absent/weak | Reference features are the single most valuable evidence type (ablation-confirmed) |
| `HIGH_STRUCTURAL_AMBIGUITY` | candidate plausible as both one-to-many and many-to-one | Same condition behind the documented false negative |

The **three-way decision** (`HIGH_CONFIDENCE_MATCH` / `NEEDS_REVIEW` /
`LIKELY_NO_MATCH`) and its thresholds are the single source of truth for
what auto-reconciles; the risk layer never silently routes a flagged
high-confidence match to review, because that would defeat the point of
exposing risk *separately* from a measured threshold policy. Full policy:
[`docs/risk_policy.md`](docs/risk_policy.md).

## Human review

Candidates that land in the `NEEDS_REVIEW` band create a `ReviewTask`
(status `OPEN`), visible in the frontend's review queue. A reviewer can
**approve** or **reject** a task (`POST /reviews/{id}/approve` /
`/reject`), each with double-submit protection and explicit 404/409
error handling.

Critically, approving or rejecting a review **never rewrites the
underlying ML decision.** `ReconciliationDecision.decision` (the model's
output) is immutable after creation; human action only ever changes
`workflow_state` (e.g. `NEEDS_REVIEW` → `APPROVED_BY_REVIEWER`) and
creates a new audit event recording the reviewer's identity, action, and
the model's original calibrated probability for comparison. This
invariant is verified directly by a test that asserts the decision field
is bit-identical before and after approval, and was confirmed against a
real approve and a real reject performed over HTTP against a live
PostgreSQL instance.

## Exceptions

Candidates that fall below the LOW threshold (or have no viable candidate
at all) become an `ExceptionRecord` with a **root-cause category**,
evaluated in a fixed priority order so the same conditions always produce
the same category:

1. `NO_CANDIDATE_FOUND` — zero candidates on either side
2. `STRUCTURAL_AMBIGUITY` — plausible as both one-to-many and many-to-one
3. `HIGH_COMPETITION` — five or more competing candidates
4. `INSUFFICIENT_EVIDENCE` — weak reference and weak vendor similarity together
5. `LOW_MATCH_CONFIDENCE` — fallback, but still a measurable statement
   (the actual probability and threshold are included in the reason text)

`GET /exceptions/{id}` returns a deeper, on-demand **root-cause analysis**
(observed evidence, interpretation, contributing factors, investigation
guidance) built by a deterministic root-cause engine
(`backend/app/workflow/exception_intelligence.py`) that refines the
persisted category with an evidence-dimension drill-down (amount / date /
vendor / reference), with precedence between simultaneously-weak
dimensions grounded in the ML model's own feature-importance findings
(amount > reference > vendor > date) rather than arbitrary ordering.
Original, immutable, persisted facts and the derived analysis are kept in
clearly separate response fields.

## Auditability

Every meaningful state change — batch creation, model evaluation, review
creation, human approval/rejection, exception creation, batch completion
— is recorded as one immutable event via `record_event()`
(`backend/app/audit.py`), which only ever `INSERT`s. There is no
`update_event()` or `delete_event()` anywhere in the codebase.

Each event captures: `event_id`, `entity_type`, `entity_id`, `event_type`,
`actor_type` (`SYSTEM` / `MODEL` / `HUMAN`), `actor_id`, `previous_state`,
`new_state`, a JSON `payload`, and a `timestamp`. A `MODEL_EVALUATED` event
carries the raw and calibrated probability, decision, relationship type,
and risk flags; a `REVIEW_APPROVED` event explicitly includes the
original model decision and probability in its payload, as a persisted,
queryable proof that nothing was overwritten.

`GET /audit/{entity_type}/{entity_id}` returns the full ordered history
for a batch, decision, or review. `GET /decisions/{id}/audit` merges
decision-level events with the human-review events that live under a
separate `REVIEW` entity namespace, so a decision's full traceable
history — from `MODEL_EVALUATED` through any human action — is available
from one endpoint. Immutability here is honestly application-level
(a single INSERT-only write function), not oversold as database-enforced
or cryptographic. Full details: [`docs/audit_trail.md`](docs/audit_trail.md).

## Dataset and evaluation

The project trains and evaluates against an internally-generated
synthetic dataset with genuine ground truth, built specifically so that
"no match" is a real, learnable outcome rather than an edge case bolted
on afterward:

| | Count |
|---|---|
| Ground-truth transactions | 600 |
| Ledger records | 586 |
| Settlement records | 607 |
| Unified candidates (V1 + V2) | 10,980 |
| Labeled candidates (post leakage-exclusion) | 3,629 |

**Structural distribution** (of the 600 ground-truth transactions):

| Relationship | Count |
|---|---|
| One-to-one | 481 |
| Batched settlement (many-to-one) | 50 |
| Split settlement (one-to-many) | 36 |
| Ledger-only (pending settlement) | 19 |
| Settlement-only (e.g. fee reversal) | 14 |

The train/val/test split is assigned at the **ground-truth transaction
level, before any corruption is applied**, so that two noisy variants of
the same underlying transaction can never land in different splits —
leakage is structurally impossible rather than something to remember to
check for. A stricter leakage rule is applied again at candidate-labeling
time: both records in a candidate pair must agree on ground-truth split,
or the pair is excluded entirely (this excluded 7,351 of 10,980 unified
candidates — a large, honestly-reported fraction, since structural
candidates freely span the date-windowed pool).

## Model metrics

**Held-out test set (evaluated exactly once, no further tuning after):**

| Metric | Value |
|---|---|
| Precision | 1.0 |
| Recall | 0.961 |
| F1 | 0.9801 |
| ROC-AUC | 0.9983 |
| PR-AUC | 0.9995 |
| Confusion matrix | TN=23, FP=0, FN=3, TP=74 |

**By relationship type (test set):**

| Type | n | Positive | Precision | Recall |
|---|---|---|---|---|
| One-to-one | 83 | 70 | 1.0 | 0.9857 |
| One-to-many | 11 | 6 | 1.0 | **0.6667** |
| Many-to-one | 6 | 1 | 1.0 | 1.0 (n=1 — not statistically meaningful) |

**Three-way policy applied to test:**

| | Count | Precision/recall or error rate |
|---|---|---|
| Auto-match | 71 | precision 1.0, recall 0.9221 |
| Needs review | 3 | review-zone positive rate 1.0 |
| Likely no match | 26 | error rate **0.1154** |

**Honestly reported limitation:** the likely-no-match error rate jumped
from 0% on validation to 11.5% on test — roughly 1 in 9 candidates routed
to "likely no match" on test were actually genuine matches. This tracks
directly with the one-to-many recall drop above, and is a real limitation
surfaced only by the one-time held-out evaluation — exactly why held-out
test exists, and exactly why the policy was not re-tuned against it
afterward. Full numbers and model-comparison detail:
[`docs/model_comparison.md`](docs/model_comparison.md),
[`docs/model_baseline.md`](docs/model_baseline.md),
[`docs/threshold_policy.md`](docs/threshold_policy.md).

## Tech stack

**Backend:** Python, FastAPI, SQLAlchemy + Alembic, PostgreSQL 16,
scikit-learn (Logistic Regression baseline, calibration), LightGBM (final
ranking model), RapidFuzz (string similarity), sentence-transformers
(`all-MiniLM-L6-v2`, with a documented deterministic n-gram-hashing
fallback when no network route to Hugging Face is available), pandas /
numpy / pyarrow, Docker.

**Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, Recharts,
hand-built shadcn-style primitives on Radix UI + class-variance-authority
+ tailwind-merge, Vitest + Testing Library for tests.

There is no Celery/Redis task queue in this project — batches are
processed synchronously within the `POST /batches` request.

## Application routes

| Route | Purpose |
|---|---|
| `/` | Batch selector — list of submitted batches |
| `/batches/[batchId]` | Batch dashboard — summary stats, outcome/confidence/root-cause charts, batch-level audit timeline |
| `/batches/[batchId]/decisions` | Full decision table for a batch (filterable/sortable by decision, relationship, risk) |
| `/decisions/[decisionId]` | Confidence card, evidence breakdown, raw record comparison, operational risk, audit timeline |
| `/reviews` | Human review queue, filterable by status (open/approved/rejected/all) |
| `/reviews/[reviewId]` | Review detail — confidence card, evidence, approve/reject actions, review history |
| `/exceptions` | Exception queue, filterable by root-cause category |
| `/exceptions/[exceptionId]` | Exception detail — root-cause analysis, record comparison, operational risk |

## API

FastAPI app: `backend/app/api/main.py`. Interactive Swagger docs are
available at `/docs` once the server is running. Full endpoint-by-endpoint
reference: [`docs/api.md`](docs/api.md).

| Method | Path | Purpose |
|---|---|---|
| GET | `/batches` | List all batches |
| POST | `/batches` | Submit ledger + settlement records; runs the full pipeline synchronously |
| GET | `/batches/{batch_id}` | Batch status and summary |
| GET | `/batches/{batch_id}/decisions` | All reconciliation decisions in a batch |
| GET | `/decisions/{decision_id}` | Full confidence-card payload — probability, decision, risk flags, evidence, raw records |
| GET | `/decisions/{decision_id}/audit` | Decision's full merged audit history, including human-review events |
| GET | `/reviews` | Review queue (filter by `status`, `batch_id`) |
| GET | `/reviews/{review_id}` | Review detail with evidence snapshot |
| POST | `/reviews/{review_id}/approve` | Human approval — preserves the original ML decision |
| POST | `/reviews/{review_id}/reject` | Human rejection — same preservation guarantee |
| GET | `/exceptions` | List exceptions (filter by `category`, `batch_id`) |
| GET | `/exceptions/{exception_id}` | Exception detail with root-cause analysis |
| GET | `/audit/{entity_type}/{entity_id}` | Full ordered audit history for a batch, decision, or review |

## Project structure

```
reconlens/
├── backend/
│   ├── app/
│   │   ├── api/main.py            # the FastAPI app — every route lives here
│   │   ├── pipeline.py            # batch processing: candidates -> features -> model -> workflow
│   │   ├── audit.py               # append-only audit event recording
│   │   ├── db.py                  # SQLAlchemy engine/session (Postgres by default)
│   │   ├── review_actions.py      # approve/reject business logic
│   │   ├── models/                # SQLAlchemy ORM models (batch, decision, review, exception, evidence, ...)
│   │   └── workflow/               # state machines, risk flags, exception root-cause engine
│   ├── alembic/                    # DB migrations
│   └── tests/                      # pytest suite (109 test functions across 6 files)
├── frontend/
│   └── src/
│       ├── app/                    # Next.js App Router pages (see Application routes)
│       ├── components/             # dashboard/, decision/, ui/ (hand-built primitives)
│       └── lib/                    # api-client.ts (sole fetch layer), api-types.ts, use-api.ts
├── ml/
│   ├── data_generation/            # synthetic ledger/settlement + ground-truth generator
│   ├── candidate_generation/       # blocking_v1.py (pairwise), blocking_v2.py (structural)
│   ├── features/                   # normalize, numeric, string_similarity, reference, embeddings,
│   │                                #   structural, group_extractor, validate, quality_report
│   ├── training/                   # baseline + LightGBM training scripts
│   └── evaluation/                 # held-out test evaluation scripts
├── models/                         # trained artifacts (LightGBM, calibrator, logreg baseline)
├── data/
│   ├── raw/                        # ledger.csv, settlement.csv (+ hidden ground truth, eval-only)
│   └── processed/                  # extracted feature parquet/csv files
├── reports/                        # phase3/, phase4/ — JSON evaluation reports backing this README
├── configs/threshold_policy.json   # the selected HIGH/LOW threshold policy
├── docs/                           # deep-dive design docs, one per subsystem (linked throughout this README)
├── docker-compose.yml              # postgres + api services
├── Dockerfile
└── requirements.txt
```

## Setup

### Backend

```bash
# from repo root
pip install -r requirements.txt

# Postgres must be running and reachable at DATABASE_URL
# (defaults to postgresql+psycopg2://postgres:reconlens@localhost:5432/reconlens)
cd backend
alembic upgrade head
uvicorn backend.app.api.main:app --reload
```

The API listens on `http://localhost:8000` by default; Swagger UI is at
`http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm install
npm run dev
```

The app listens on `http://localhost:3000` by default. CORS is
pre-configured on the backend for this origin.

### Database

The project targets **PostgreSQL 16**. `DATABASE_URL` (env var) controls
the connection string; `backend/app/db.py` defaults to
`postgresql+psycopg2://postgres:reconlens@localhost:5432/reconlens`.
SQLite is available only for isolated test runs via
`RECONLENS_TEST_SQLITE=1` — it is never a silent production fallback.

### Environment variables

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | backend | `postgresql+psycopg2://postgres:reconlens@localhost:5432/reconlens` | SQLAlchemy connection string |
| `RECONLENS_TEST_SQLITE` | backend | unset | Set to `1` to force an isolated in-memory SQLite backend for tests |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | `http://localhost:8000` | Base URL the frontend calls |

### Model / data requirements

The pipeline loads a pre-trained model bundle from
`models/reconlens_phase4_final.joblib` (LightGBM + sigmoid calibrator +
feature-column order, bundled together) — this file is included in the
repository, so no separate training step is required to run the API.
Retraining from scratch would use the scripts in `ml/training/` and
`scripts/` against `data/processed/unified_features.parquet`.

### Docker

```bash
docker compose up --build
```

This starts PostgreSQL 16 and the API together (`docker-compose.yml`),
running `alembic upgrade head` before starting `uvicorn`. The Dockerfile
also attempts a best-effort pre-cache of the `all-MiniLM-L6-v2`
sentence-transformer model at build time; if that network call isn't
available in a given build environment, it fails silently and the
documented n-gram-hashing fallback embedder takes over at runtime instead
of crashing the build. The frontend is not included in this
`docker-compose.yml` and is run separately via `npm run dev` / `npm run
build`.

## Testing

These commands assume the relevant dependencies are already installed
(`pip install -r requirements.txt` for backend, `npm install` for
frontend) — they are not run as part of preparing this documentation.

```bash
# Backend tests
pytest

# Frontend tests
cd frontend && npm run test

# Frontend production build
cd frontend && npm run build
```

## Demo flow

**Flow 1 — automated high-confidence match**
`POST /batches` → pipeline runs → a candidate scores above the HIGH
threshold → `AUTO_MATCHED` → evidence persisted → `MODEL_EVALUATED` +
`AUTO_MATCH_CREATED` audit events.

**Flow 2 — human review**
A candidate lands between thresholds → `NEEDS_REVIEW` → a `ReviewTask` is
created → a reviewer approves or rejects it via
`POST /reviews/{id}/approve` or `/reject` → `workflow_state` advances
(e.g. to `APPROVED_BY_REVIEWER`) while the original ML `decision` and
calibrated probability remain untouched → audit event recorded with the
reviewer's identity.

**Flow 3 — exception / no viable match**
A candidate scores below the LOW threshold, or no candidate exists at all
→ `LIKELY_NO_MATCH` → `ExceptionRecord` created with a root-cause category
→ `GET /exceptions/{id}` returns a full root-cause analysis (observed
evidence, interpretation, investigation guidance) → `EXCEPTION_CREATED`
audit event.

All three flows have been verified against a real batch run over live
PostgreSQL, not just unit-tested in isolation (see
[`docs/workflow.md`](docs/workflow.md) for the exact recorded run).

## Known limitations

This is a hackathon MVP, and it is documented as one rather than
oversold:

- **One-to-many (split settlement) recall is measurably worse than
  one-to-one** — 66.7% vs 98.6% on held-out test. This is surfaced via a
  risk flag (`KNOWN_LOW_GENERALIZATION`), not hidden, and not yet fixed
  with a type-aware threshold because too few structural positive
  examples exist to tune one safely.
- **Many-to-one had zero positive examples in validation** — its
  held-out test performance (n=1) is not statistically meaningful, and
  this is flagged operationally via `INSUFFICIENT_VALIDATION_SAMPLE`.
- **Semantic similarity currently runs on a deterministic n-gram-hashing
  fallback**, not real `sentence-transformers` embeddings, in any
  environment without network access to Hugging Face. Every report and
  metadata file tags which backend actually produced its numbers, so
  fallback output is never mistaken for genuine semantic similarity. The
  Dockerfile attempts to pre-bake the real model at build time to close
  this gap in deployment.
- **The dataset is synthetic**, generated with a controlled, documented
  corruption model rather than real bank/processor data. Reported metrics
  describe performance on this synthetic distribution, not a guarantee
  about real-world data with different corruption patterns.
- **Audit-trail immutability is application-level**, enforced by having
  exactly one INSERT-only write function with no corresponding
  update/delete function — it is not database-enforced (e.g. no
  append-only table constraints) or cryptographically verifiable.
- **The threshold policy is uniform across relationship types**, despite
  one-to-many's measurably worse performance, per an explicit project
  decision not to tune a second threshold against too little structural
  data.
- **No authentication or multi-tenancy** — CORS is scoped to local
  development origins only, appropriate for a local demonstration, not a
  deployed multi-tenant service.
- **No task queue** — batches are processed synchronously within the
  request; this is fine at this project's data volumes but would not
  scale to large production batches without introducing an async worker.

This project should be read as a demonstration of a *complete, honestly
evaluated* reconciliation pipeline with real bounded-autonomy and
governance mechanisms — not as a finished, production-hardened financial
system.

## Submission materials

- [`docs/submission.md`](docs/submission.md) — Razorpay Buildathon
  submission writeup (problem, solution, AI usage, architecture,
  results, limitations).
- [`docs/demo_script.md`](docs/demo_script.md) — a 5-minute demo script.
- [`docs/know_your_project.md`](docs/know_your_project.md) — a
  beginner-level walkthrough of the project, grounded in the actual
  implementation.
- [`docs/interview_prep.md`](docs/interview_prep.md) — likely judge/
  interviewer questions with honest, implementation-tied answers.
