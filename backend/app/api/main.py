"""
ReconLens — FastAPI backend. Deliberately no LLM agents, no RAG, no chatbot
layer — per spec section 5, the learned reconciliation engine IS the AI
here; this layer is orchestration, persistence, and human oversight.
"""
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.db import get_db, init_db
from backend.app.pipeline import process_batch
from backend.app.review_actions import approve_review, reject_review, ReviewNotFoundError, ReviewAlreadyResolvedError
from backend.app.audit import get_audit_trail
from backend.app.models.batch import Batch
from backend.app.models.decision import ReconciliationDecision
from backend.app.models.review import ReviewTask
from backend.app.models.exception import ExceptionRecord
from backend.app.models.evidence import EvidenceRecord

app = FastAPI(title="ReconLens API", version="phase5")


@app.on_event("startup")
def _startup():
    init_db()


# ---------------- schemas ----------------

class LedgerRecordIn(BaseModel):
    ledger_id: str
    vendor_name: str
    amount: float
    txn_date: str
    reference_id: str = ""
    description: str = ""


class SettlementRecordIn(BaseModel):
    settlement_id: str
    vendor_name: str
    amount: float
    txn_date: str
    reference_id: str = ""
    description: str = ""


class BatchIn(BaseModel):
    ledger_records: list[LedgerRecordIn]
    settlement_records: list[SettlementRecordIn]


class ReviewActionIn(BaseModel):
    reviewer_id: str
    comment: Optional[str] = None


# ---------------- helpers ----------------

def _decision_to_dict(d: ReconciliationDecision) -> dict:
    return {
        "decision_id": d.id, "batch_id": d.batch_id,
        "ledger_record_ids": d.ledger_record_ids, "settlement_record_ids": d.settlement_record_ids,
        "relationship_type": d.relationship_type,
        "model_name": d.model_name, "model_version": d.model_version,
        "probability": {"raw": d.raw_probability, "calibrated": d.calibrated_probability},
        "thresholds": {"high": d.high_threshold, "low": d.low_threshold},
        "decision": d.decision, "workflow_state": d.workflow_state,
        "risk_flags": d.risk_flags, "created_at": d.created_at.isoformat(),
    }


def _evidence_to_dict(e: EvidenceRecord) -> dict:
    return {"feature": e.feature_name, "value": e.feature_value,
            "direction": e.evidence_direction, "strength": e.evidence_strength}


# ---------------- batches ----------------

@app.post("/batches")
def create_batch(payload: BatchIn, db: Session = Depends(get_db)):
    ledger_records = [r.model_dump() for r in payload.ledger_records]
    settlement_records = [r.model_dump() for r in payload.settlement_records]
    batch = process_batch(db, ledger_records, settlement_records)
    return {"batch_id": batch.id, "status": batch.status, "summary": batch.summary}


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch is None:
        raise HTTPException(404, "Batch not found")
    return {"batch_id": batch.id, "status": batch.status, "summary": batch.summary,
            "created_at": batch.created_at.isoformat(),
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            "failure_reason": batch.failure_reason}


@app.get("/batches/{batch_id}/decisions")
def get_batch_decisions(batch_id: str, db: Session = Depends(get_db)):
    decisions = db.query(ReconciliationDecision).filter(ReconciliationDecision.batch_id == batch_id).all()
    return {"batch_id": batch_id, "decisions": [_decision_to_dict(d) for d in decisions]}


# ---------------- decisions (confidence card) ----------------

@app.get("/decisions/{decision_id}")
def get_decision(decision_id: str, db: Session = Depends(get_db)):
    d = db.query(ReconciliationDecision).filter(ReconciliationDecision.id == decision_id).first()
    if d is None:
        raise HTTPException(404, "Decision not found")
    evidence = db.query(EvidenceRecord).filter(EvidenceRecord.decision_id == decision_id).all()
    payload = _decision_to_dict(d)
    payload["evidence"] = [_evidence_to_dict(e) for e in evidence]
    return payload


# ---------------- review queue ----------------

@app.get("/reviews")
def list_reviews(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(ReviewTask)
    if status:
        q = q.filter(ReviewTask.status == status)
    reviews = q.all()
    return {"reviews": [{"review_id": r.id, "decision_id": r.decision_id, "status": r.status,
                          "relationship_type": r.relationship_type,
                          "calibrated_probability": r.calibrated_probability,
                          "risk_flags": r.risk_flags, "created_at": r.created_at.isoformat()}
                         for r in reviews]}


@app.get("/reviews/{review_id}")
def get_review(review_id: str, db: Session = Depends(get_db)):
    r = db.query(ReviewTask).filter(ReviewTask.id == review_id).first()
    if r is None:
        raise HTTPException(404, "Review not found")
    return {"review_id": r.id, "decision_id": r.decision_id, "status": r.status,
            "relationship_type": r.relationship_type, "calibrated_probability": r.calibrated_probability,
            "risk_flags": r.risk_flags, "evidence_snapshot": r.evidence_snapshot,
            "assigned_reviewer": r.assigned_reviewer, "created_at": r.created_at.isoformat(),
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None}


@app.post("/reviews/{review_id}/approve")
def approve(review_id: str, payload: ReviewActionIn, db: Session = Depends(get_db)):
    try:
        review = approve_review(db, review_id, payload.reviewer_id, payload.comment)
    except ReviewNotFoundError:
        raise HTTPException(404, "Review not found")
    except ReviewAlreadyResolvedError as e:
        raise HTTPException(409, str(e))
    return {"review_id": review.id, "status": review.status}


@app.post("/reviews/{review_id}/reject")
def reject(review_id: str, payload: ReviewActionIn, db: Session = Depends(get_db)):
    try:
        review = reject_review(db, review_id, payload.reviewer_id, payload.comment)
    except ReviewNotFoundError:
        raise HTTPException(404, "Review not found")
    except ReviewAlreadyResolvedError as e:
        raise HTTPException(409, str(e))
    return {"review_id": review.id, "status": review.status}


# ---------------- exceptions ----------------

@app.get("/exceptions")
def list_exceptions(category: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(ExceptionRecord)
    if category:
        q = q.filter(ExceptionRecord.category == category)
    exceptions = q.all()
    return {"exceptions": [{"exception_id": e.id, "decision_id": e.decision_id, "category": e.category,
                             "reason": e.reason, "created_at": e.created_at.isoformat()}
                            for e in exceptions]}


# ---------------- audit ----------------

@app.get("/audit/{entity_type}/{entity_id}")
def audit_trail(entity_type: str, entity_id: str, db: Session = Depends(get_db)):
    events = get_audit_trail(db, entity_type.upper(), entity_id)
    return {"entity_type": entity_type, "entity_id": entity_id,
            "events": [{"event_id": e.event_id, "event_type": e.event_type,
                        "actor_type": e.actor_type, "actor_id": e.actor_id,
                        "previous_state": e.previous_state, "new_state": e.new_state,
                        "payload": e.payload, "timestamp": e.timestamp.isoformat()}
                       for e in events]}
