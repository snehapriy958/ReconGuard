from sqlalchemy import Column, String, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.db import Base


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(String, ForeignKey("decisions.id"), nullable=False, index=True)

    feature_name = Column(String, nullable=False)
    feature_value = Column(Float, nullable=False)
    evidence_direction = Column(String, nullable=False)  # supports_match / weakens_match / creates_ambiguity
    evidence_strength = Column(String, nullable=False)   # strong / moderate / weak
    contribution = Column(Float, nullable=False)  # raw pred_contrib value this was derived from — never fabricated

    decision = relationship("ReconciliationDecision", back_populates="evidence")
