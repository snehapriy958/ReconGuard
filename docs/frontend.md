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

Phase 6.1 (foundation), 6.2 (batch overview), and 6.3 (reconciliation
decision table) complete and verified against real data. 6.4 onward
(confidence card, review queue, exception intelligence, audit timeline,
dashboard insights) not yet built — proceeding incrementally per the
spec's explicit instruction.

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

