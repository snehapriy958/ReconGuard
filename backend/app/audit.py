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
        .order_by(AuditEvent.timestamp.asc())
        .all()
    )
