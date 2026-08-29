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

Phase 6.1 (foundation) and 6.2 (batch overview) complete and verified
against real data. 6.3 onward (decision table, confidence card, review
queue, exception intelligence, audit timeline, dashboard insights) not yet
built — proceeding incrementally per the spec's explicit instruction.
