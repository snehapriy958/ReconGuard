import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.db import Base


def _uid() -> str:
    return f"REV-{uuid.uuid4().hex[:12]}"


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id = Column(String, primary_key=True, default=_uid)
    decision_id = Column(String, ForeignKey("decisions.id"), nullable=False, unique=True, index=True)

    status = Column(String, nullable=False, default="OPEN")  # OPEN / IN_REVIEW / APPROVED / REJECTED
    relationship_type = Column(String, nullable=False)
    calibrated_probability = Column(Float, nullable=False)
    risk_flags = Column(JSON, nullable=False, default=list)
    evidence_snapshot = Column(JSON, nullable=True)  # denormalized copy of evidence for fast queue display

    assigned_reviewer = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    decision = relationship("ReconciliationDecision", back_populates="review_task")
