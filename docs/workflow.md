# ReconLens — Workflow Engine (Phase 5)

## Two separate state machines, deliberately

**Batch-level** (`backend/app/workflow/state_machine.py: BATCH_VALID_TRANSITIONS`):
```
CREATED -> PROCESSING -> COMPLETED
                       -> FAILED
```

**Decision-level** (`VALID_TRANSITIONS`):
```
PENDING -> PROCESSING -> AUTO_MATCHED                       (terminal)
                       -> NEEDS_REVIEW -> APPROVED_BY_REVIEWER   (terminal)
                                       -> REJECTED_BY_REVIEWER   (terminal)
                       -> LIKELY_NO_MATCH -> EXCEPTION            (terminal)
                       -> FAILED                                 (terminal)
```

These were originally one shared machine — a real bug (see "Important
Failures" below) forced splitting them, and in hindsight it's the correct
design: a batch doesn't become `AUTO_MATCHED`, and a decision doesn't have a
`COMPLETED` state. Conflating them was the mistake, not the fix.

Invalid transitions raise `InvalidTransitionError` rather than silently
succeeding — verified by `test_invalid_transition_raises` and
`test_terminal_states_have_no_outgoing_transitions`.

## End-to-end flow

```
Batch submitted (ledger + settlement records)
  -> idempotency check (content hash) - duplicate submission returns the
     existing batch unchanged, creates nothing new
  -> BATCH_CREATED audit event
  -> transition to PROCESSING
  -> source records persisted
  -> candidate generation (V1 + V2, unchanged from Phase 3/4)
  -> unified feature extraction (unchanged from Phase 4)
  -> LightGBM prediction + sigmoid calibration (unchanged from Phase 4 -
     Phase 5 does not retrain or retune anything)
  -> per candidate:
       risk flags computed (separate from probability - see docs/risk_policy.md)
       decision persisted with ALL public IDs (never a collapsed fake ID)
       evidence persisted (real pred_contrib attributions, not fabricated)
       MODEL_EVALUATED audit event
       routed by decision:
         HIGH_CONFIDENCE_MATCH -> AUTO_MATCHED, AUTO_MATCH_CREATED event
         NEEDS_REVIEW -> ReviewTask created (OPEN), REVIEW_TASK_CREATED event
         LIKELY_NO_MATCH -> EXCEPTION, ExceptionRecord created (evidence-based
                             category via classify_exception()), EXCEPTION_CREATED event
  -> batch summary computed, BATCH_COMPLETED audit event, status COMPLETED
```

## Real end-to-end run (not simulated)

130 records (60 ledger + 70 settlement, sampled from the actual dataset) ->
72 candidates -> 57 auto-matched, 1 review, 14 exceptions, 9 structural
matches, 23 risk-flagged decisions, 0 failed candidates, against a real
PostgreSQL 16 instance. Verified independently via direct SQL query
(`SELECT count(*) FROM decisions` = 72, matching the summary exactly) -
not just trusted from the pipeline's own return value.

## Important Failures (preserved, not smoothed over)

**1. Batch/decision state conflation**
*Observed:* first pipeline run failed immediately with
`InvalidTransitionError: Unknown current state: 'CREATED'`.
*Root cause:* the pipeline reused the decision-level `transition()` function
for `Batch.status`, but `Batch` uses `CREATED`/`COMPLETED` - states that
don't exist in the decision-level machine at all.
*Fix:* added a genuinely separate `transition_batch()` / `BATCH_VALID_TRANSITIONS`.
*Verification:* `test_batch_transitions_separate_from_decision_transitions` passes;
the real batch run completed successfully afterward.

**2. NaN in a JSON column**
*Observed:* the same real batch run then failed with
`psycopg2.errors.InvalidTextRepresentation: invalid input syntax for type json ... Token "NaN" is invalid`.
*Root cause:* pandas reads an empty `reference_id` CSV cell as float `NaN`;
Python's `json.dumps` serializes `NaN` by default (non-standard, but
allowed), while PostgreSQL's JSON column correctly enforces the actual JSON
spec (RFC 8259), which has no `NaN` literal.
*Fix:* `_sanitize_records()` replaces any float NaN with `None` before
records reach a JSON column.
*Verification:* `test_nan_reference_id_does_not_crash_ingestion` passes; the
real batch completed successfully on retry.

**3. Session left in "pending rollback" state after the NaN failure**
*Observed:* the exception handler meant to record `PROCESSING_FAILED` itself
raised `PendingRollbackError`, masking the real error above.
*Root cause:* after a failed `db.commit()`, SQLAlchemy requires an explicit
`db.rollback()` before the session can be touched again - my handler read
`batch.status` (triggering a lazy reload) before rolling back.
*Fix:* `db.rollback()` and `db.merge(batch)` now happen first in the
exception handler, before any further ORM attribute access.
*Verification:* the failure-injection test
(`test_processing_failure_creates_failed_state_and_audit_event`) correctly
reaches and persists the `FAILED` state with a real audit event, instead of
raising a second, unrelated exception.

## Known limitation this workflow layer inherits from Phase 4

The uniform threshold policy (HIGH=0.85, LOW=0.50) applies to every
relationship type equally, despite one-to-many's measured 66.7% held-out
recall. Phase 5's answer to this - per spec section 29's explicit
instruction NOT to add type-aware thresholds yet - is the risk-flag layer
(`docs/risk_policy.md`), not a silent threshold change.
