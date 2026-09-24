# ReconLens — Frontend (Phase 6)

## Stack

Next.js (App Router) + TypeScript + Tailwind CSS, hand-built UI primitives
(Button/Card/Badge) on the same underlying libraries shadcn/ui itself uses
(class-variance-authority, Radix, tailwind-merge) — shadcn's own CLI
couldn't run in this sandbox (`ui.shadcn.com` isn't in the allowed network
list), so the primitives were written directly rather than faked or skipped.

## Architecture

```
src/lib/api-types.ts    - TypeScript interfaces written directly from the
                          backend's actual response construction, not a
                          guessed/idealized schema
src/lib/api-client.ts   - the ONLY module that calls fetch(); every
                          component imports typed functions from here
src/lib/use-api.ts      - shared loading/error/success state hook, used by
                          every data-fetching screen
src/components/ui/      - hand-built shadcn-style primitives
src/components/dashboard/ - ReconLens-specific components (StatCard,
                          BatchStatusBadge, shared Loading/Error/Empty states)
src/app/page.tsx         - batch selector (home page)
src/app/batches/[batchId]/page.tsx - the real batch dashboard
```

## Backend contract changes made to support the frontend (not faked)

Per the explicit instruction to extend the backend rather than substitute
mock data when a screen needs something the API doesn't provide yet:

- **Added `GET /batches`** (list) — didn't exist before Phase 6; needed for
  batch selection when multiple batches exist.
- **Extended `GET /decisions/{id}`** to include real `ledger_records` /
  `settlement_records` content (not just IDs) — needed for the record-
  comparison view planned for the confidence card and exception explanations.
- **Extended `GET /exceptions`** with `relationship_type` and
  `calibrated_probability` — needed so the exception list doesn't require a
  second round-trip per row just to show basic context.
- **Added CORS middleware**, scoped to local dev origins
  (`localhost:3000`/`127.0.0.1:3000`) — a local demonstration project, not a
  deployed multi-tenant service, so an explicit origin list is appropriate
  rather than a wildcard.
- **Fixed a real Pydantic contract bug**: `reference_id: str = ""` rejected
  `None`, even though the pipeline's own NaN-sanitizer produces `None` for
  missing values — caught only by submitting an actual HTTP request, not by
  reading the code. Now `Optional[str]` with a validator normalizing `None`
  to `""`.

All four backend test files still pass after these changes (78 passed, 4
skipped — see docs/architecture.md).

## The Three-Layer Trust Model, in the UI (Phase 6.4+, not yet built)

The dashboard so far (6.1-6.2) only shows aggregate batch numbers. The
decision-detail screen, still to come, is where the three-layer separation
matters most:

- **Model confidence** = calibrated probability, shown on its own
- **Evidence quality** = the actual `EvidenceRecord` rows (real
  `pred_contrib` attributions from Phase 4/5, never fabricated)
- **Operational risk** = `risk_flags`, displayed with the explicit statement
  that they don't modify the probability (per `docs/risk_policy.md`)

## Real data verification performed for 6.1-6.2

A batch was submitted through the actual running HTTP API (not called
directly in Python) — 180 records → 89 candidates → 62 auto-matched, 3
needs review, 24 exceptions, 18 structural matches, 35 risk-flagged — and
both the batch list page and the batch dashboard page were confirmed to
return HTTP 200 with CORS headers present for `localhost:3000`, using this
real batch's ID. No hardcoded numbers appear anywhere in the two pages
built so far; every value renders from `BatchSummary` fields returned by
`GET /batches/{id}`.

## Important failures found while building this (preserved, not smoothed over)

**1. SQLite in-memory tests silently split across two databases**
*Observed:* a new FastAPI TestClient test failed to see rows the test
fixture had just created.
*Root cause:* SQLite's `:memory:` creates a separate database per
connection by default; the fixture's `create_all()` and the API's own
session were hitting different databases.
*Fix:* `StaticPool` added to the SQLite engine config.
*Verification:* `test_list_batches_endpoint_returns_real_batches` and
related API tests now pass.

**2. Backgrounded dev servers don't survive between separate tool
invocations in this sandbox**
*Observed:* a `uvicorn` process started with `nohup ... &` in one command
was gone by the next command — not merely stopped, absent from `ps`.
*Root cause:* only genuinely system-managed services (like the Postgres
cluster started via `pg_ctlcluster`) persist between separate sandbox
commands; a plain backgrounded shell job does not.
*Fix:* every verification step that needs the server running performs the
start-and-test sequence within one single command.

**3. `next/font/google` requires build-time network access to
fonts.googleapis.com**
*Observed:* `npm run build` failed outright — this sandbox can't reach
Google Fonts, the same category of issue as the sentence-transformers /
HuggingFace dependency in Phase 2.
*Fix:* removed the Google Fonts import, using a system font stack instead
— zero external dependency, same reasoning as the ML pipeline's documented
embedding fallback.
*Verification:* `npm run build` completes cleanly.

**4. `SourceRecord.id` collision on resubmitted, overlapping test data**
*Observed:* submitting a batch that reused a row range already ingested by
an earlier test batch raised a Postgres unique-constraint violation.
*Assessment:* not a bug — `SourceRecord.id` is intentionally globally
unique, correctly modeling that real Razorpay ledger/settlement IDs are
globally unique in production. This only surfaced because manual testing
reused overlapping synthetic data ranges across separate submissions.
*Resolution:* used a fresh, non-overlapping data slice for subsequent test
batches; noted here so a future contributor doesn't mistake this
constraint for a defect.

## Running locally

```
# Backend (from repo root)
cd backend && alembic upgrade head
uvicorn backend.app.api.main:app --reload

# Frontend
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm install
npm run dev
```

No API keys required for local demonstration.

## Status

Phase 6.1-6.7 complete and verified against real data. 6.8 (dashboard
charts, polish, full Docker integration test) and submission packaging
remain — proceeding incrementally per the spec's explicit instruction.

## Phase 6.7 — Immutable Audit Timeline and Decision Traceability

**Real gap found during inspection, fixed — not a redesign:**
`REVIEW_APPROVED`/`REVIEW_REJECTED` events are persisted under
`entity_type="REVIEW"`, keyed by `review.id` — a *different* id namespace
than `entity_type="DECISION"` events (`MODEL_EVALUATED`,
`AUTO_MATCH_CREATED`, `REVIEW_TASK_CREATED`, `EXCEPTION_CREATED`), which
are keyed by `decision.id`. The pre-existing generic
`GET /audit/{entity_type}/{entity_id}` endpoint only ever queries one
namespace at a time — calling it with `DECISION/{decision_id}` alone would
have **completely omitted the human review outcome** from a decision's
timeline, directly contradicting this phase's core requirement. Fixed with
a new, server-side merge (`get_decision_audit_trail()` in
`backend/app/audit.py`) that looks up the decision's associated
`ReviewTask` (if any) and merges both namespaces, sorted chronologically —
exposed via the new `GET /decisions/{id}/audit` endpoint.

**Actual event taxonomy discovered** (12 real event types, all
already-emitted by Phase 5's pipeline and review-action code — none
invented for this phase):

| event_type | entity_type | actor_type | Category |
|---|---|---|---|
| `BATCH_CREATED`, `PROCESSING_STARTED`, `PROCESSING_FAILED`, `BATCH_COMPLETED`, `DUPLICATE_SUBMISSION_DETECTED` | BATCH | SYSTEM | SYSTEM |
| `CANDIDATE_PROCESSING_FAILED` | BATCH | SYSTEM | SYSTEM |
| `MODEL_EVALUATED` | DECISION | MODEL | MODEL |
| `AUTO_MATCH_CREATED`, `REVIEW_TASK_CREATED` | DECISION | SYSTEM | WORKFLOW |
| `EXCEPTION_CREATED` | DECISION | SYSTEM | EXCEPTION |
| `REVIEW_APPROVED`, `REVIEW_REJECTED` | REVIEW | HUMAN | HUMAN |

**Immutability — verified, not just claimed:** `backend/app/audit.py`
exposes exactly one write function, `record_event()`, which only ever
`INSERT`s (verified since Phase 5 by
`test_audit_events_append_only_no_update_function_exists`, which asserts
no `update_event()`/`delete_event()` exist on the module at all). This is
**application-level, conventional append-only behavior** — there is no
database-level immutability constraint (no `REVOKE UPDATE`, no trigger).
Stated honestly rather than described as cryptographic or tamper-proof,
per the spec's explicit instruction not to overclaim.

**Ordering fix:** `get_audit_trail()` previously sorted by `timestamp`
only; added a secondary sort by the autoincrement `id` (monotonic with
insertion order) for genuine determinism when timestamps could collide at
datetime resolution — verified by a dedicated repeated-request test.

**Decision-centric timeline:** scoped correctly to one decision's real
lifecycle only — verified directly that an unrelated batch's
`CANDIDATE_PROCESSING_FAILED` events never leak into a decision's audit
view (structurally impossible, since those events carry no `decision.id`
at all).

**Batch-centric timeline:** deliberately concise — filtered client-side to
5 real lifecycle event types
(`BATCH_CREATED`/`PROCESSING_STARTED`/`PROCESSING_FAILED`/
`BATCH_COMPLETED`/`DUPLICATE_SUBMISSION_DETECTED`), excluding individual
`CANDIDATE_PROCESSING_FAILED` rows (already surfaced as a count via
`summary.failed_candidates`). Verified against the real populated batch:
exactly 3 real lifecycle events, zero noise.

**Invariant visualization (Step 9), using data that already existed:**
`review_actions.py` has recorded `model_decision_preserved` and
`model_calibrated_probability` in the `REVIEW_APPROVED`/`REVIEW_REJECTED`
payload since Phase 5 — this phase's `AuditEventCard` renders a banner
from those exact fields when present, and only then (verified by a
dedicated test that the banner does NOT appear for a
similarly-shaped-but-different event type, and does NOT appear when those
specific fields are absent).

**Technical payload safety (Step 13):** hidden by default behind a
`<details>` disclosure on every event card — verified by a test asserting
the element has no `open` attribute initially.

**Real end-to-end verification**, all three required cases, against live
PostgreSQL:
- **CASE 1 (automated):** `MODEL_EVALUATED → AUTO_MATCH_CREATED`, correct order, correct actor types.
- **CASE 2 (human review, both directions):** approved case —
  `MODEL_EVALUATED → REVIEW_TASK_CREATED → REVIEW_APPROVED`, spanning a
  real one-day gap between review creation and human action, correctly
  ordered; invariant payload confirmed
  `model_decision_preserved=NEEDS_REVIEW`,
  `model_calibrated_probability=0.8226` (untouched by the approval).
  Rejected case verified identically:
  `model_decision_preserved=NEEDS_REVIEW`,
  `model_calibrated_probability=0.7106` (untouched by the rejection).
- **CASE 3 (exception):** `MODEL_EVALUATED → EXCEPTION_CREATED`, correct
  order, real `category` payload.
- All four decision/batch pages confirmed rendering at HTTP 200 through
  the actual running Next.js server, with CORS confirmed for the new
  `/decisions/{id}/audit` endpoint.

**Tests:** 100/100 frontend (13 new: event categorization/summarization
from real payload fields, state-transition honest-nulling, invariant
banner shown/not-shown correctly, technical details hidden by default,
timeline ordering and empty state). Backend: 100 passed, 7 skipped (6 new:
3 pure endpoint tests plus the regression test that specifically proves
the review-merge gap is fixed, 1 of which skips on the tiny deterministic
fixture and is covered instead by the real verification above).

**Remaining limitations:** the batch-level timeline's noise-reduction
(collapsing `CANDIDATE_PROCESSING_FAILED`) has only been verified against
a batch with zero such failures — the real populated batch never
generated one, so the "avoid dumping every candidate-level event" behavior
is implemented and unit-testable but not demonstrated at real volume.
No database-level immutability enforcement exists (append-only is
enforced by the application's code surface only, stated honestly above,
not oversold).

## Phase 6.6 — Exception Intelligence

**Backend additions, each justified by inspecting the existing contract first:**

Inspection found that `classify_exception()` (in `risk.py`) already exists
as a real, deterministic, priority-ordered taxonomy
(`NO_CANDIDATE_FOUND` → `STRUCTURAL_AMBIGUITY` → `HIGH_COMPETITION` →
`INSUFFICIENT_EVIDENCE` → fallback `LOW_MATCH_CONFIDENCE`), already used
to create every persisted `ExceptionRecord`. Phase 6.6 does not replace
this — it builds a second, more granular layer on top
(`backend/app/workflow/exception_intelligence.py`) that refines the
generic `LOW_MATCH_CONFIDENCE`/`INSUFFICIENT_EVIDENCE` fallback into a
specific evidence dimension (amount/date/vendor/reference), since "low
confidence" alone doesn't tell an operator *which* evidence was weak.

1. **New module `exception_intelligence.py`** — `analyze_exception()`
   takes the already-persisted category, the recomputed feature vector
   (reusing the exact same `_recompute_full_features()` helper factored
   out of `GET /decisions/{id}` — no duplicated feature logic), workflow
   state, and source-record presence, and returns a primary root cause,
   observed facts, interpretation, contributing factors, and investigation
   guidance.
2. **`GET /exceptions` extended** with `primary_root_cause` (cheap — one
   recomputation per row, using the shared cached embedding backend).
3. **New `GET /exceptions/{id}` endpoint** (didn't exist before — only the
   list endpoint did) — returns the full root-cause analysis, with
   `original_category`/`original_reason` (the immutable, already-persisted
   facts) kept in clearly separate fields from `root_cause_analysis` (the
   derived analysis), per the spec's explicit "clearly distinguish
   original facts from derived analysis."

**Root-cause taxonomy** (`taxonomy_version: "v1"`, documented for future
versioning):

| Cause | Trigger | System failure? |
|---|---|---|
| `PROCESSING_FAILURE` | `workflow_state == "FAILED"` | Yes |
| `MISSING_SOURCE_RECORD` | A referenced ledger/settlement record can't be found | Yes |
| `NO_VIABLE_CANDIDATE` | Existing category `NO_CANDIDATE_FOUND` | No |
| `STRUCTURAL_MATCH_FAILURE` | Existing category `STRUCTURAL_AMBIGUITY` | No |
| `WEAK_MATCH_EVIDENCE` | Existing category `HIGH_COMPETITION` | No |
| `AMOUNT_DISCREPANCY` / `DATE_DISCREPANCY` / `VENDOR_MISMATCH` / `REFERENCE_MISMATCH` | Drill-down within the fallback categories — whichever evidence dimension is "weak" per the shared thresholds | No |
| `MODEL_UNCERTAINTY` | Fallback categories, but no single dimension is individually weak | No |
| `UNKNOWN_OR_INSUFFICIENT_EVIDENCE` | Features couldn't be recomputed at all | No |

**Honest finding, not glossed over:** `PROCESSING_FAILURE` is included in
the taxonomy for correctness, but inspection confirmed it is currently
**structurally unreachable** — a candidate that fails during pipeline
processing is logged as a batch-level audit event and simply skipped;
no `ReconciliationDecision` or `ExceptionRecord` is ever created for it,
and no decision has ever reached `workflow_state=FAILED` in practice. This
is documented in the module docstring rather than worked around by
fabricating a decision-level failure that doesn't reflect real backend
behavior.

**Precedence when multiple dimensions are weak** (amount > reference >
vendor > date): grounded in real, already-established Phase 4 findings —
`abs_amount_diff` ranked far above every other feature in LightGBM's gain
importance, and removing reference features cost the most accuracy of any
group in the Phase 4 ablation. Not an arbitrary choice.

**No fabricated confidence score** (spec Step 7): every root cause is
accompanied by real `observed` values (actual feature numbers) and a
separate `interpretation` (the deterministic label derived from them) —
never a percentage claiming the cause itself is "87% likely."

**System failures vs. reconciliation failures, visually distinct:** the
frontend's `RootCauseCard` shows an explicit red banner
("This is a technical processing issue, not a reconciliation-quality
finding") for `PROCESSING_FAILURE`/`MISSING_SOURCE_RECORD`, and uses a
different badge color (red vs. amber) — verified by a dedicated test that
the banner does NOT appear for ordinary reconciliation findings.

**Root cause vs. operational risk, kept structurally separate:**
`RootCauseCard` takes no `risk_flags` prop at all — the two concepts
can never be accidentally merged, the same pattern already established
for confidence vs. risk in Phase 6.4.

**Real data verification** against the actual populated batch (24 real
exceptions): confirmed root causes across **5 of the 9 reachable
categories** — `REFERENCE_MISMATCH` (11), `VENDOR_MISMATCH` (5),
`AMOUNT_DISCREPANCY` (3), `MODEL_UNCERTAINTY` (3), `WEAK_MATCH_EVIDENCE`
(2). Two specific cases spot-checked in full: a `REFERENCE_MISMATCH` case
where `reference_similarity=0.23` correctly triggered the cause with
vendor weakness correctly listed as contributing, and an
`AMOUNT_DISCREPANCY` case where `relative_amount_diff=0.0427` correctly
took precedence over two other simultaneously-weak dimensions (reference,
vendor), confirming the documented precedence rule works on real data, not
just in unit tests. **Not verified against real data** (none existed in
this batch): `NO_VIABLE_CANDIDATE`, `STRUCTURAL_MATCH_FAILURE`,
`DATE_DISCREPANCY`, `MISSING_SOURCE_RECORD`, `PROCESSING_FAILURE`,
`UNKNOWN_OR_INSUFFICIENT_EVIDENCE` — these are covered by the 14 backend
unit tests in `test_exception_intelligence.py` (which exercise the
deterministic engine directly, independent of any specific dataset) but
not claimed as end-to-end verified, per the spec's explicit instruction
not to claim verification a category didn't actually receive.

**Tests:** 87/87 frontend (24 new: root-cause card rendering, system-
failure distinction, contributing-factors conditional display, no-
fabricated-confidence check, exception queue rendering/filtering/empty
states). Backend: 97 passed, 6 skipped (17 new: 14 pure unit tests on the
deterministic engine covering every reachable category and precedence
rule, 3 API-level tests for the enriched endpoints).

**Remaining limitations:** `PROCESSING_FAILURE` and several other taxonomy
branches remain real but unverified against production-shaped data (see
above); the list endpoint recomputes features per exception row (fast
after the shared embedding-backend warmup, but would need pagination or a
persisted cache for a much larger exception volume than this demo scale).

## Phase 6.5 — Human Review Queue, Actions, and History

**Backend additions, each justified by inspecting the existing contract first:**

1. **`batch_id`, `ledger_record_ids`, `settlement_record_ids`,
   `original_ml_decision` added to `GET /reviews` and `GET /reviews/{id}`**
   — joined through the existing `ReviewTask.decision` relationship, not a
   new query pattern. Without these, the queue would have had to either
   flatten structural relationships or make a second round-trip per row.
2. **Real bug fixed: `assigned_reviewer` was a column that was never
   actually set anywhere.** The reviewer's identity only ever reached the
   audit event's `actor_id`, never the `ReviewTask` record itself — meaning
   `GET /reviews/{id}` could never say who resolved a case. Fixed in
   `review_actions.py`'s `_resolve()` to persist `review.assigned_reviewer
   = reviewer_id` on approval/rejection. Verified with a dedicated
   regression test and confirmed against a real approval
   (`assigned_reviewer: "priya_reviewer"` came back correctly).

**Review eligibility source of truth:** the backend's `ReviewTask.status`
field (`OPEN`/`APPROVED`/`REJECTED`), never inferred from confidence in the
frontend — the queue calls `GET /reviews?status=OPEN` and trusts that
entirely.

**Review prioritization:** oldest-first, stated plainly as the only
transparent option available — no backend priority field exists, and the
spec explicitly forbids inventing a fake "AI priority score." Sorting
happens client-side on `created_at`.

**Architecture — composition, not duplication:** `ReviewDetailPage`
fetches `getReview(reviewId)` for review-specific status/resolution, then
`getDecision(decision_id)` for the full Phase 6.4 payload, and composes
the *exact same* `ConfidenceCard`, `EvidenceSummary`, `EvidenceBreakdown`,
`RawRecordComparison`, `WhatChanged`, and `OperationalRiskCard` components
Phase 6.4 already built — zero evidence/confidence/risk logic was
reimplemented for review screens.

**Approve/reject workflow:** `ReviewActions` calls the real backend
(`approveReview`/`rejectReview`) and never simulates success locally.
Both buttons disable for the full round-trip (structural double-submit
protection, not just a UI convention). On success, both the review and
decision are refetched from the real backend — the UI never assumes its
optimistic view matches what persisted.

**Original ML decision preservation — the core invariant — verified with
real data, not just asserted:**
```
BEFORE:  decision=NEEDS_REVIEW  workflow_state=NEEDS_REVIEW  calibrated=0.8226
[real POST /reviews/{id}/approve, reviewer_id=priya_reviewer]
AFTER:   decision=NEEDS_REVIEW  workflow_state=APPROVED_BY_REVIEWER  calibrated=0.8226 (unchanged)
         assigned_reviewer=priya_reviewer, resolved_at=<real timestamp>
```
Reject verified identically on a second real case
(`DEC-8c44a513908f`, a one-to-many decision with `KNOWN_LOW_GENERALIZATION`):
`decision` stayed `NEEDS_REVIEW`, `workflow_state` became
`REJECTED_BY_REVIEWER`, and `risk_flags` were completely untouched by the
review action.

**Error handling, verified with real HTTP responses, not mocked:**
- Re-approving an already-rejected review → real `409` with message
  `"Review 'REV-...' is already resolved (REJECTED); the original
  resolution is preserved, not overwritten."` — the frontend shows this
  and refetches rather than trusting its stale local state.
- Approving a nonexistent review ID → real `404`.

**Review history (concise, not the full audit trail — that's Phase 6.7):**
shows exactly two real, persisted moments — the model's decision timestamp
(`decision.created_at`) and the reviewer's resolution timestamp
(`review.resolved_at`), with `assigned_reviewer` when present. No
fabricated intermediate steps.

**Tests:** 75/75 frontend tests passing (18 new: review actions including
double-submit disable, 409/404/network-failure handling; review queue
rendering, structural relationship display, oldest-first ordering, empty
states). Backend: 80 passed, 6 skipped (2 new tests skip on the tiny
deterministic fixture that doesn't happen to produce a review case —
fully covered instead by the real end-to-end verification above, exactly
as the Phase 5 precedent established).

**Real end-to-end verification performed:** against the actual populated
batch (`BATCH-b4f076fca9a5`) with 3 real `OPEN` review cases spanning
`one_to_one` and `one_to_many` (3-member settlement group), a real approve
and a real reject were both performed via actual HTTP POST requests
against live PostgreSQL, with every invariant (ML decision preservation,
workflow state transition, unchanged probability, unchanged risk flags,
queue count updates, assigned_reviewer persistence) confirmed against the
database — not asserted from memory. All four review-related frontend
routes (`/reviews`, and three individual review detail pages covering
open/approved/rejected states) verified at HTTP 200 through the real
running Next.js server, with CORS confirmed for the queue endpoint.

**Remaining limitations:** the reviewer-name field is a plain text input
with no authentication (out of scope per spec — "do not add authentication
unless required"); review prioritization is a simple oldest-first sort
with no backend-driven priority signal yet.

## Phase 6.4 — Confidence Card, Evidence Breakdown, Record Comparison, Operational Risk

**Backend additions, each justified by inspecting the real data contract first:**

1. **`all_features` field on `GET /decisions/{id}`** — `EvidenceRecord`
   only ever persisted the top-5 features by `pred_contrib` magnitude
   (Phase 5's design, sized for the confidence-card "top evidence" list),
   which isn't enough for a full category-by-category technical breakdown
   (e.g. every vendor-similarity metric, not just whichever ranked top-5).
   Rather than duplicate feature-extraction logic in the frontend, the
   endpoint now recomputes the full feature vector deterministically from
   the same persisted source records, using the identical
   `ml/features/group_extractor.extract_group_features` function the ML
   pipeline itself uses. No new inference, no new model call — pure
   recomputation of already-derivable values.
2. **`risk_flag_explanations` field** — sourced server-side from
   `backend/app/workflow/risk.py`'s existing `risk_explanation()` function,
   not duplicated as a second copy of that text in the frontend.

**Data flow:**
```
Persisted decision + source records (Postgres)
        ↓
GET /decisions/{id} — recomputes full features via the real ML pipeline
        code, fetches real risk explanations, real evidence, real records
        ↓
Typed API client (DecisionDetail)
        ↓
Decision Detail page — assembles 6 components, each reading only its
        own real, typed slice of the payload
```

**Three-Layer Trust Model, structurally enforced in the component API, not just visually:**
- `ConfidenceCard` — its props type is `Pick<Decision, "probability" | "decision" | "thresholds">`; it has no code path that could accept a risk flag
- `EvidenceSummary` / `EvidenceBreakdown` — read only `evidence` / `all_features`; render real attribution and real recomputed feature values through a documented, deterministic interpretation policy (`src/lib/evidence-interpretation.ts`) — never an LLM, never a per-case invention
- `OperationalRiskCard` — takes no probability prop at all; explicitly states in its own copy that risk flags don't modify the calibrated probability shown elsewhere on the page

**Evidence interpretation policy** (`src/lib/evidence-interpretation.ts`),
every threshold documented and justified:
- Amount: <1% strong, 1-3% moderate, >3% weak — grounded in the dataset's
  documented `relative_amount_diff` range (`docs/feature_catalog.md`)
- Date: ≤3 days strong, ≤7 moderate, beyond weak — grounded in the
  generator's documented settlement-lag cap and batch-span limit
- Vendor: uses `vendor_token_set_similarity` as the headline metric, not
  Jaro-Winkler, because `docs/feature_catalog.md` documents Jaro-Winkler's
  inflated-baseline quirk (still shown in the technical breakdown, just not
  driving the business-facing label)
- Competition and weak-reference thresholds are the **exact same constants**
  (`HIGH_COMPETITION_THRESHOLD = 5`, `WEAK_REFERENCE_SIMILARITY_THRESHOLD = 0.3`)
  already defined in `backend/app/workflow/risk.py` — reused, not reinvented,
  so a decision's risk flag and its evidence-card label always agree

**Raw record comparison and "What Changed":** structural groups are never
flattened — every member ID gets its own inspectable card. For "What
Changed," a structural group compares the **ledger total against the
settlement group total**, never an individual member's amount against a
multi-record group (the spec's explicit warning) — verified by a dedicated
test asserting `"1,000 (total)"` vs `"1,000 (group total)"` render
correctly for a true one-to-many case.

**Real data verification** across 5 real decisions spanning every
available category (no `many_to_one` existed in this particular batch):
`one_to_one` auto-matched with no risk, `one_to_one` likely-no-match with
`WEAK_REFERENCE_EVIDENCE`, `one_to_one` auto-matched *with* a risk flag
(proving risk doesn't gate auto-match), `one_to_many` needs-review with
full structural risk flags, and — the cleanest confirmation of the
spec's core requirement — `one_to_many` **HIGH_CONFIDENCE_MATCH still
carrying `KNOWN_LOW_GENERALIZATION`**, verified through the real running
frontend at `/decisions/DEC-cc85d1911f31` (HTTP 200, correct CORS).

**Tests:** 62/62 frontend tests passing (38 new for Phase 6.4: evidence
interpretation thresholds, confidence/risk separation, evidence summary
and breakdown rendering, record comparison including the structural-total
calculation, missing-data handling, and operational risk rendering).
Backend: 80 passed, 4 skipped (2 new tests for `all_features` and
`risk_flag_explanations`).

**Important failures found while building this:**
1. *Observed:* first `all_features` request took 75 seconds. *Root cause:*
   `extract_group_features` constructs a fresh `EmbeddingBackend()` on
   every call, which retries (and times out on) an unreachable HuggingFace
   connection each time — fine when called once per batch (the existing
   pipeline path), broken when called once per API request (the new path
   this phase added). *Fix:* added a process-level singleton
   (`get_shared_backend()` in `ml/features/embeddings.py`) and warmed it at
   app startup so no real user request ever pays the cost.
   *Verification:* repeat requests measured at 0.18s; the first real
   request after startup measured at 0.25s.
2. *Observed:* `all_features` came back `null` in a test, silently.
   *Root cause:* an unrelated import edit had accidentally deleted the
   `CandidateGroup` import, causing a `NameError` inside a broad
   `except Exception` block that swallowed it without a trace.
   *Fix:* corrected the import; also added `logger.exception(...)` inside
   that except block so a future bug of this shape shows up in server logs
   instead of only manifesting as a quietly-null field.
   *Verification:* the dedicated `all_features` test now passes, and
   the failure mode itself is now visible if it recurs.

**Remaining limitations:** no `many_to_one` decision existed in the
verification batch to visually confirm that specific grouping (the logic
is identical to `one_to_many`'s and covered by a dedicated unit test, but
not yet seen live against the real running app); the technical evidence
`<details>` disclosure is a plain HTML element rather than an animated
accordion (a deliberate simplicity choice, not a gap).


## Phase 6.3 — Reconciliation Decision Table

**No backend changes were needed.** Inspection of the real
`GET /batches/{batch_id}/decisions` response (verified via actual HTTP
request, not just reading the code) showed every field the table needs is
already present — critically, `workflow_state` alone fully encodes both
"review status" and "exception status" (`EXCEPTION`, `NEEDS_REVIEW`,
`APPROVED_BY_REVIEWER`, `REJECTED_BY_REVIEWER`, `AUTO_MATCHED`), so no new
endpoint or field was justified.

**Architecture:**
- `src/lib/decision-display.ts` — single source of truth for how
  `DecisionLabel`/`DecisionWorkflowState`/`RelationshipType` enums are
  labeled and colored, so no component invents its own mapping
- `src/components/dashboard/relationship-display.tsx` — renders
  one-to-one as `LED-001 ↔ STL-001`, one-to-many/many-to-one as
  `X → Y` with every member ID visible, never flattened into a
  misleading single-record view
- `src/components/dashboard/risk-flags.tsx` — real `risk_flags` array
  rendered as badges, with an explicit "No risk flags" state (never a
  blank cell)
- `src/components/dashboard/decision-table.tsx` — the table itself:
  client-side filtering (decision / relationship type / risk-flagged),
  sorting (confidence / decision / relationship type), empty and
  no-filter-results states kept visually distinct
- `src/app/batches/[batchId]/decisions/page.tsx` — the page, fetching via
  `getBatchDecisions()`
- `src/app/decisions/[decisionId]/page.tsx` — a **minimal scaffold only**,
  per the explicit Phase 6.3 scope boundary: shows the decision ID and
  calibrated confidence, with a note that the full Confidence Card
  (evidence quality, risk explanation, record comparison) is Phase 6.4

**Confidence vs. risk, kept structurally separate:** the Model Confidence
column renders only `probability.calibrated`; risk flags render in their
own column from the unmodified `risk_flags` array. Nothing in the table
code path combines these into a derived score.

**ML decision vs. workflow state:** both are shown in their own columns
(Decision, Workflow Status) using their own real values — a
`NEEDS_REVIEW` decision that was later `APPROVED_BY_REVIEWER` shows
"Needs Review" and "Approved" side by side. An earlier design added a
derived "diverges" note on top of this; removed after review showed the
two columns already satisfy "preserve the distinction" without needing
extra business logic with its own debatable edge cases (see Important
Failures below).

**Real data verification:** against the real batch (`BATCH-b4f076fca9a5`,
89 decisions: 62 auto-matched, 3 needs review, 24 exceptions, 18
one-to-many), confirmed via actual HTTP requests:
- `GET /batches/{id}/decisions` returns the full real distribution
- The decisions table page and decision-detail scaffold both return
  HTTP 200 with correct CORS headers for `localhost:3000`
- A real structural (`one_to_many`) decision ID was pulled directly from
  the live API and used to verify the detail route navigates correctly

**Tests:** 24/24 frontend tests passing (12 new for the decision table:
real-data rendering, confidence/risk separation, one-to-many and
many-to-one structural rendering, empty/no-results states, and all three
filter types). Backend: 78 passed, 4 skipped, unchanged since no backend
code was modified this phase.

**Important failures found while building this:**
1. *Observed:* an early "divergence note" feature (flagging when
   `workflow_state` differs from `decision`) had debatable logic — is
   `APPROVED_BY_REVIEWER` a "divergence" from `NEEDS_REVIEW`, or an
   expected progression? *Root cause:* invented a business rule the table
   didn't actually need. *Fix:* removed it — the Decision and Workflow
   Status columns already show both real values side by side, which
   satisfies the spec's actual requirement without introducing an
   ambiguous derived concept. *Verification:* dedicated test confirms
   both values render correctly when they differ.
2. *Observed:* several new tests failed with "multiple elements found."
   *Root cause:* filter chip labels (e.g. "Many-to-One") and table cell
   values use identical text, which is correct product behavior, not a
   bug — but ambiguous for `getByText`. *Fix:* scoped queries with
   `within(table)` or `getByRole("button", {name})` instead of loosening
   the actual UI.

**Remaining limitations:** the decision-detail route is intentionally a
placeholder; no pagination (client-side filtering only, acceptable at
this data scale per spec); sorting resets on filter change rather than
persisting (a minor UX polish item, not a correctness issue).

---

## Phase 2 — CSV Upload & Validation (`/upload`)

The `/upload` route allows users to upload Ledger and Settlement CSV files directly to ReconGuard, inspect client-side schema previews and validation status, submit the files for synchronous end-to-end reconciliation, and be automatically redirected to the resulting batch detail page (`/batches/{batchId}`).

### Key Capabilities:
- **Dual Dropzones & File Selectors:** Separate upload zones for Internal Ledger CSV and Settlement CSV with clear visual boundaries and drag-and-drop support.
- **Client-Side Validation & Previews:**
  - Powered by PapaParse in-browser parsing.
  - Column schema verification:
    - Ledger requires: `ledger_id`, `vendor_name`, `amount`, `txn_date`
    - Settlement requires: `settlement_id`, `vendor_name`, `amount`, `txn_date`
  - Record count detection and file size formatting.
  - Total amount summation for financial sanity check before submission.
  - Instant status badges (`Valid` / `Invalid Schema`) and error callouts.
  - Individual "Clear" buttons to remove and re-select files.
- **Form Submission & State Handling:**
  - Submit button disabled until both files are selected and schema-valid.
  - Submission packages files into `FormData` and posts to `/batches/upload`.
  - Disables double submission and shows loading spinner (`Reconciling Batch...`).
  - Clear user guidance explaining that reconciliation executes synchronously.
  - Automatic redirect to `/batches/{batchId}` on completion.
- **Error Display:**
  - Structured error notification card displaying server-side 400 validation failures.
  - Detailed error table breaking down each failure by File, Row, Field, and Reason.

---

## Phase 3 — Financial Metrics (`/batches/{batchId}`)

The batch dashboard surfaces full financial exposure metrics computed by unique source record:

### Key Capabilities:
- **Centralized Formatters (`frontend/src/lib/formatters.ts`):**
  - `formatCurrency()`: Formats amounts with locale grouping and 2 decimal places using configurable currency symbol (defaults to ₹ matching source datasets).
  - `formatPercent()`: Formats 0-1 ratios as percentages (e.g. 85.2%).
- **Financial Summary Section (`FinancialSummarySection`):**
  - Displays distinct cards for Internal Accounts Ledger and External Settlement Records.
  - Shows Total Value, Reconciled rate badges, and breakdown buckets:
    - Matched Amount + Rate
    - In Review Amount + Rate
    - Exception Amount + Rate
  - Displays explicit mathematical invariant equation ensuring transparency.
- **Financial Breakdown Chart (`FinancialBreakdownChart`):**
  - Recharts horizontal stacked bar chart visualizing Matched, Review, and Exception exposure across both Ledger and Settlement sides.
  - Interactive tooltips formatted with `formatCurrency()`.
