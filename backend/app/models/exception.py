import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.db import Base


def _uid() -> str:
    return f"EXC-{uuid.uuid4().hex[:12]}"


class ExceptionRecord(Base):
    __tablename__ = "exception_records"

    id = Column(String, primary_key=True, default=_uid)
    decision_id = Column(String, ForeignKey("decisions.id"), nullable=False, unique=True, index=True)

    category = Column(String, nullable=False)  # see risk.py: EXCEPTION_CATEGORIES
    reason = Column(String, nullable=False)
    evidence_snapshot = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    decision = relationship("ReconciliationDecision", back_populates="exception_record")
