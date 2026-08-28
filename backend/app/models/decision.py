import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.db import Base


def _uid() -> str:
    return f"DEC-{uuid.uuid4().hex[:12]}"


class ReconciliationDecision(Base):
    __tablename__ = "decisions"

    id = Column(String, primary_key=True, default=_uid)
    batch_id = Column(String, ForeignKey("batches.id"), nullable=False, index=True)

    # Structural relationships preserve ALL member IDs — never collapsed into
    # one fake ID, per spec section 11. Stored as JSON lists even for the
    # common one-to-one case (a 1-element list) so the schema is uniform.
    ledger_record_ids = Column(JSON, nullable=False)
    settlement_record_ids = Column(JSON, nullable=False)
    relationship_type = Column(String, nullable=False)  # one_to_one / one_to_many / many_to_one

    model_name = Column(String, nullable=False, default="lightgbm_v1")
    model_version = Column(String, nullable=False, default="phase4_unified_v1")

    raw_probability = Column(Float, nullable=False)
    calibrated_probability = Column(Float, nullable=False)
    high_threshold = Column(Float, nullable=False)
    low_threshold = Column(Float, nullable=False)

    decision = Column(String, nullable=False)  # HIGH_CONFIDENCE_MATCH / NEEDS_REVIEW / LIKELY_NO_MATCH
    workflow_state = Column(String, nullable=False, default="PENDING")

    risk_flags = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    batch = relationship("Batch", back_populates="decisions")
    evidence = relationship("EvidenceRecord", back_populates="decision")
    review_task = relationship("ReviewTask", back_populates="decision", uselist=False)
    exception_record = relationship("ExceptionRecord", back_populates="decision", uselist=False)
