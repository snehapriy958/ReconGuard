"""
ReconLens — audit trail. This module's record_event() is the ONLY function
anywhere in the codebase that writes to the audit_events table. There is no
update_event() or delete_event() — append-only by construction, not just
convention.
"""
from sqlalchemy.orm import Session

from backend.app.models.audit import AuditEvent


def record_event(
    db: Session, entity_type: str, entity_id: str, event_type: str,
    actor_type: str, actor_id: str | None = None,
    previous_state: str | None = None, new_state: str | None = None,
    payload: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        entity_type=entity_type, entity_id=entity_id, event_type=event_type,
        actor_type=actor_type, actor_id=actor_id,
        previous_state=previous_state, new_state=new_state, payload=payload,
    )
    db.add(event)
    db.flush()  # assign id without committing — caller controls the transaction boundary
    return event


def get_audit_trail(db: Session, entity_type: str, entity_id: str) -> list[AuditEvent]:
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
        # Secondary sort by the autoincrement id: timestamps alone aren't a
        # guaranteed-unique ordering key (two events in the same request
        # could share a timestamp at datetime resolution), and `id` is
        # monotonic with insertion order, giving a genuinely deterministic
        # tie-break rather than relying on undefined SQL ordering.
        .order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
        .all()
    )


def get_decision_audit_trail(db: Session, decision_id: str, review_id: str | None) -> list[AuditEvent]:
    """A decision's full lifecycle spans TWO audit entity namespaces:
    entity_type="DECISION" (MODEL_EVALUATED, AUTO_MATCH_CREATED/
    REVIEW_TASK_CREATED/EXCEPTION_CREATED — all emitted by pipeline.py
    against decision.id) and entity_type="REVIEW" (REVIEW_APPROVED/
    REVIEW_REJECTED — emitted by review_actions.py against review.id, a
    DIFFERENT id). The generic GET /audit/{type}/{id} endpoint only ever
    queries one namespace, so calling it with DECISION/{decision_id} alone
    would silently omit the human review outcome — a real gap found while
    inspecting the existing architecture for Phase 6.7, not a redesign of
    it. This function does the merge server-side, once, so the frontend
    never has to guess which namespace an event belongs to.
    """
    events = get_audit_trail(db, "DECISION", decision_id)
    if review_id:
        events += get_audit_trail(db, "REVIEW", review_id)
    events.sort(key=lambda e: (e.timestamp, e.id))
    return events
