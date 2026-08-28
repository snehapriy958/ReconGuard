# ReconLens — Audit Trail (Phase 5)

## Append-only, structurally not just by convention

`backend/app/audit.py` exposes exactly one write function: `record_event()`,
which always `INSERT`s. There is no `update_event()` or `delete_event()`
anywhere in the codebase - verified by
`test_audit_events_append_only_no_update_function_exists`, which asserts
those functions don't exist on the module at all, not just that they're
unused.

## Event structure

```
event_id, entity_type, entity_id, event_type,
actor_type (SYSTEM / MODEL / HUMAN), actor_id,
previous_state, new_state, payload (JSON), timestamp
```

## Example real sequence (from the actual Postgres-backed run)

```
BATCH_CREATED       (SYSTEM)  -> new_state=CREATED
PROCESSING_STARTED  (SYSTEM)  CREATED -> PROCESSING
MODEL_EVALUATED     (MODEL, lightgbm:phase4_unified_v1)  payload: {raw_probability, calibrated_probability, decision, relationship_type, risk_flags, ...}
REVIEW_TASK_CREATED (SYSTEM)  PROCESSING -> NEEDS_REVIEW
REVIEW_APPROVED     (HUMAN, priya_reviewer)  NEEDS_REVIEW -> APPROVED_BY_REVIEWER
                     payload includes model_decision_preserved=NEEDS_REVIEW,
                     model_calibrated_probability=0.7068 - explicit proof
                     the ML decision was never rewritten, only superseded by
                     a separate final resolution
BATCH_COMPLETED     (SYSTEM)  PROCESSING -> COMPLETED
```

This exact sequence was produced by a real batch run and a real
`approve_review()` call against Postgres, not constructed by hand for this
document.

## Model decision vs. final resolution (spec section 16)

`ReconciliationDecision.decision` (the ML output: HIGH_CONFIDENCE_MATCH /
NEEDS_REVIEW / LIKELY_NO_MATCH) is **never modified** after creation. Human
review actions only ever change `ReconciliationDecision.workflow_state`
(PROCESSING -> NEEDS_REVIEW -> APPROVED_BY_REVIEWER, for example) and create
a new `ReviewTask` state + audit event. Verified directly:
`test_review_approve_preserves_original_ml_decision` asserts
`decision.decision` is bit-identical before and after approval.

## Retrieval

`GET /audit/{entity_type}/{entity_id}` returns the full ordered event
history for any batch, decision, or review - `get_audit_trail()` in
`backend/app/audit.py`, ordered by timestamp ascending.
