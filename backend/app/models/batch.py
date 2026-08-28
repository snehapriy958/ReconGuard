import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Integer, JSON
from sqlalchemy.orm import relationship

from backend.app.db import Base


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class Batch(Base):
    __tablename__ = "batches"

    id = Column(String, primary_key=True, default=lambda: _uid("BATCH"))
    status = Column(String, nullable=False, default="CREATED")  # CREATED/PROCESSING/COMPLETED/FAILED
    batch_hash = Column(String, nullable=False, unique=True, index=True)  # idempotency key
    n_ledger_records = Column(Integer, default=0)
    n_settlement_records = Column(Integer, default=0)
    summary = Column(JSON, nullable=True)  # populated after processing — see workflow/pipeline.py
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    failure_reason = Column(String, nullable=True)

    source_records = relationship("SourceRecord", back_populates="batch")
    decisions = relationship("ReconciliationDecision", back_populates="batch")
