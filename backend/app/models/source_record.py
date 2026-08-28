from sqlalchemy import Column, String, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.db import Base


class SourceRecord(Base):
    __tablename__ = "source_records"

    id = Column(String, primary_key=True)  # the ledger_id / settlement_id itself, unique within a batch
    batch_id = Column(String, ForeignKey("batches.id"), nullable=False, index=True)
    record_type = Column(String, nullable=False)  # "LEDGER" or "SETTLEMENT"
    public_id = Column(String, nullable=False)  # duplicated for query convenience; == id
    raw_data = Column(JSON, nullable=False)  # vendor_name, amount, txn_date, reference_id, description

    batch = relationship("Batch", back_populates="source_records")
