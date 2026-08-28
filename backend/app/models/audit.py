import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, JSON, Integer

from backend.app.db import Base


def _uid() -> str:
    return f"EVT-{uuid.uuid4().hex[:12]}"


class AuditEvent(Base):
    """Append-only by convention AND by code path: this module exposes no
    update/delete function anywhere in the codebase — only `record_event()`
    in backend/app/audit.py, which always INSERTs. Verified by
    test_audit_events_cannot_be_modified.
    """
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=False, unique=True, default=_uid)

    entity_type = Column(String, nullable=False)  # BATCH / DECISION / REVIEW / EXCEPTION
    entity_id = Column(String, nullable=False, index=True)

    event_type = Column(String, nullable=False)  # BATCH_CREATED, MODEL_EVALUATED, REVIEW_APPROVED, ...

    actor_type = Column(String, nullable=False)  # SYSTEM / MODEL / HUMAN
    actor_id = Column(String, nullable=True)

    previous_state = Column(String, nullable=True)
    new_state = Column(String, nullable=True)

    payload = Column(JSON, nullable=True)

    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
