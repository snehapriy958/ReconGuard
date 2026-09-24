"""
ReconLens — FastAPI backend. Deliberately no LLM agents, no RAG, no chatbot
layer — per spec section 5, the learned reconciliation engine IS the AI
here; this layer is orchestration, persistence, and human oversight.
"""
from typing import Optional
import logging

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.app.csv_validator import validate_and_parse_csv
from backend.app.demo_datasets import (
    list_demo_datasets,
    get_demo_dataset_metadata,
    get_demo_dataset_records,
    get_demo_dataset_file_path,
)
from backend.app.model_evaluation import get_model_evaluation_data

from backend.app.db import get_db, init_db
from backend.app.pipeline import process_batch
from backend.app.review_actions import approve_review, reject_review, ReviewNotFoundError, ReviewAlreadyResolvedError
from backend.app.audit import get_audit_trail, get_decision_audit_trail
from backend.app.models.batch import Batch
from backend.app.models.decision import ReconciliationDecision
from backend.app.models.review import ReviewTask
from backend.app.models.exception import ExceptionRecord
from backend.app.models.source_record import SourceRecord
from backend.app.models.evidence import EvidenceRecord

from backend.app.workflow.risk import risk_explanation
from backend.app.workflow.exception_intelligence import analyze_exception
from ml.features.group_extractor import CandidateGroup, extract_group_features

app = FastAPI(title="ReconGuard API", version="1.0.0")
logger = logging.getLogger("reconlens")

# Frontend (Next.js dev server, typically :3000) calls this API cross-origin.
# Scoped to local dev origins only — this is a local demonstration project,
# not a deployed multi-tenant service, so a permissive-but-explicit list is
# appropriate rather than a wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()
    # Warm the embedding backend now (paying the ~75s HuggingFace-timeout-then-
    # fallback cost once, at process startup) rather than on the first real
    # request to GET /decisions/{id} — see docs/frontend.md "Important
    # Failures" for how this was discovered (a 68-75s decision-detail load).
    from ml.features.embeddings import get_shared_backend
    get_shared_backend()


# ---------------- health ----------------

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------- schemas ----------------

class LedgerRecordIn(BaseModel):
    ledger_id: str
    vendor_name: str
    amount: float
    txn_date: str
    # Optional[str], not just str="" — a submitting client (or our own
    # pipeline's NaN sanitizer) may legitimately send null for a missing
    # reference/description. Rejecting None here was a real bug caught while
    # submitting a real batch through the HTTP API (see docs/frontend.md
    # "Important Failures") — a client that already treats missing fields as
    # null shouldn't have to know this API wants "" specifically.
    reference_id: Optional[str] = ""
    description: Optional[str] = ""

    @field_validator("reference_id", "description", mode="before")
    @classmethod
    def _null_to_empty(cls, v):
        return "" if v is None else v


class SettlementRecordIn(BaseModel):
    settlement_id: str
    vendor_name: str
    amount: float
    txn_date: str
    reference_id: Optional[str] = ""
    description: Optional[str] = ""

    @field_validator("reference_id", "description", mode="before")
    @classmethod
    def _null_to_empty(cls, v):
        return "" if v is None else v


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

@app.get("/batches")
def list_batches(db: Session = Depends(get_db)):
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    return {"batches": [
        {"batch_id": b.id, "status": b.status, "n_ledger_records": b.n_ledger_records,
         "n_settlement_records": b.n_settlement_records, "created_at": b.created_at.isoformat(),
         "summary": b.summary}
        for b in batches
    ]}


@app.post("/batches")
def create_batch(payload: BatchIn, db: Session = Depends(get_db)):
    ledger_records = [r.model_dump() for r in payload.ledger_records]
    settlement_records = [r.model_dump() for r in payload.settlement_records]
    batch = process_batch(db, ledger_records, settlement_records)
    return {"batch_id": batch.id, "status": batch.status, "summary": batch.summary}


@app.post("/batches/upload")
async def upload_batch(
    ledger_file: UploadFile = File(..., description="Ledger CSV file"),
    settlement_file: UploadFile = File(..., description="Settlement CSV file"),
    db: Session = Depends(get_db),
):
    ledger_bytes = await ledger_file.read()
    settlement_bytes = await settlement_file.read()

    ledger_records, ledger_errors = validate_and_parse_csv(ledger_bytes, "ledger")
    settlement_records, settlement_errors = validate_and_parse_csv(settlement_bytes, "settlement")

    all_errors = ledger_errors + settlement_errors
    if all_errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "CSV validation failed", "errors": all_errors},
        )

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

def _recompute_full_features(d: ReconciliationDecision, db: Session) -> tuple[dict | None, bool, dict]:
    """Shared by GET /decisions/{id} and the exception endpoints — one
    recomputation path, not two copies of the same logic (spec's explicit
    instruction: reuse, don't duplicate). Returns (features_or_None,
    all_source_records_present, ledger_and_settlement_raw_by_id).
    """
    all_ids = list(d.ledger_record_ids) + list(d.settlement_record_ids)
    source_records = db.query(SourceRecord).filter(SourceRecord.id.in_(all_ids)).all()
    by_id = {r.id: r.raw_data for r in source_records}
    all_present = all(by_id.get(i) is not None for i in all_ids)

    if not all_present:
        return None, False, by_id

    try:
        import pandas as pd
        ledger_rows = [{"ledger_id": lid, **by_id[lid]} for lid in d.ledger_record_ids]
        settlement_rows = [{"settlement_id": sid, **by_id[sid]} for sid in d.settlement_record_ids]
        ledger_idx = pd.DataFrame(ledger_rows).set_index("ledger_id")
        settlement_idx = pd.DataFrame(settlement_rows).set_index("settlement_id")
        has_description = "description" in ledger_idx.columns and "description" in settlement_idx.columns
        group = CandidateGroup(ledger_ids=tuple(d.ledger_record_ids), settlement_ids=tuple(d.settlement_record_ids))
        feature_df, _ = extract_group_features([group], ledger_idx, settlement_idx, has_description)
        row = feature_df.iloc[0].to_dict()
        for k in ("ledger_public_id", "settlement_public_id", "relationship_type_candidate"):
            row.pop(k, None)
        return row, True, by_id
    except Exception:
        logger.exception(f"feature recomputation failed for decision {d.id}")
        return None, True, by_id


@app.get("/decisions/{decision_id}")
def get_decision(decision_id: str, db: Session = Depends(get_db)):
    d = db.query(ReconciliationDecision).filter(ReconciliationDecision.id == decision_id).first()
    if d is None:
        raise HTTPException(404, "Decision not found")
    evidence = db.query(EvidenceRecord).filter(EvidenceRecord.decision_id == decision_id).all()

    features, _, by_id = _recompute_full_features(d, db)

    payload = _decision_to_dict(d)
    payload["evidence"] = [_evidence_to_dict(e) for e in evidence]
    payload["ledger_records"] = [by_id.get(lid) for lid in d.ledger_record_ids]
    payload["settlement_records"] = [by_id.get(sid) for sid in d.settlement_record_ids]

    # Real explanation text, sourced from the same risk_explanation()
    # function backend/app/workflow/risk.py already uses to build exception
    # reasons — reused here rather than duplicated in the frontend, so a
    # wording change only ever needs to happen in one place.
    payload["risk_flag_explanations"] = {
        flag: risk_explanation(flag, d.relationship_type) for flag in d.risk_flags
    }
    payload["all_features"] = features

    return payload


@app.get("/decisions/{decision_id}/audit")
def get_decision_audit(decision_id: str, db: Session = Depends(get_db)):
    d = db.query(ReconciliationDecision).filter(ReconciliationDecision.id == decision_id).first()
    if d is None:
        raise HTTPException(404, "Decision not found")
    review = db.query(ReviewTask).filter(ReviewTask.decision_id == decision_id).first()
    events = get_decision_audit_trail(db, decision_id, review.id if review else None)
    return {
        "decision_id": decision_id,
        "events": [{"event_id": e.event_id, "event_type": e.event_type,
                    "actor_type": e.actor_type, "actor_id": e.actor_id,
                    "previous_state": e.previous_state, "new_state": e.new_state,
                    "payload": e.payload, "timestamp": e.timestamp.isoformat()}
                   for e in events],
    }


# ---------------- review queue ----------------

def _review_to_dict(r: ReviewTask) -> dict:
    d = r.decision
    return {
        "review_id": r.id, "decision_id": r.decision_id, "status": r.status,
        "relationship_type": r.relationship_type,
        "calibrated_probability": r.calibrated_probability,
        "risk_flags": r.risk_flags, "created_at": r.created_at.isoformat(),
        # Joined through the existing ReviewTask.decision relationship —
        # not a new query pattern, just fields the queue genuinely needs
        # (spec: batch context, ledger/settlement groups, original ML
        # decision) that weren't previously selected.
        "batch_id": d.batch_id if d else None,
        "ledger_record_ids": d.ledger_record_ids if d else None,
        "settlement_record_ids": d.settlement_record_ids if d else None,
        "original_ml_decision": d.decision if d else None,
    }


@app.get("/reviews")
def list_reviews(status: Optional[str] = None, batch_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(ReviewTask)
    if status:
        q = q.filter(ReviewTask.status == status)
    reviews = q.all()
    # Filtered in Python, not SQL: ReviewTask has no batch_id column of its
    # own (batch context only exists via the decision relationship), and
    # review volume at this project's scale doesn't justify a join just for
    # this filter — same reasoning already applied to _review_to_dict's
    # other decision-derived fields.
    if batch_id:
        reviews = [r for r in reviews if r.decision and r.decision.batch_id == batch_id]
    return {"reviews": [_review_to_dict(r) for r in reviews]}


@app.get("/reviews/{review_id}")
def get_review(review_id: str, db: Session = Depends(get_db)):
    r = db.query(ReviewTask).filter(ReviewTask.id == review_id).first()
    if r is None:
        raise HTTPException(404, "Review not found")
    payload = _review_to_dict(r)
    payload["evidence_snapshot"] = r.evidence_snapshot
    payload["assigned_reviewer"] = r.assigned_reviewer
    payload["resolved_at"] = r.resolved_at.isoformat() if r.resolved_at else None
    return payload


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
def list_exceptions(category: Optional[str] = None, batch_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(ExceptionRecord)
    if category:
        q = q.filter(ExceptionRecord.category == category)
    exceptions = q.all()
    if batch_id:
        exceptions = [e for e in exceptions if e.decision and e.decision.batch_id == batch_id]
    result = []
    for e in exceptions:
        d = e.decision
        # List view: primary_root_cause only (cheap — reuses cached
        # feature recomputation, but full observed/contributing detail is
        # reserved for the single-item detail endpoint below to keep the
        # list endpoint fast for larger exception counts).
        primary_root_cause = {
            "NO_CANDIDATE_FOUND": "NO_VIABLE_CANDIDATE",
            "STRUCTURAL_AMBIGUITY": "STRUCTURAL_MATCH_FAILURE",
            "HIGH_COMPETITION": "WEAK_MATCH_EVIDENCE",
            "INSUFFICIENT_EVIDENCE": "WEAK_MATCH_EVIDENCE",
            "LOW_MATCH_CONFIDENCE": "MODEL_UNCERTAINTY",
        }.get(e.category)
        result.append({
            "exception_id": e.id, "decision_id": e.decision_id, "category": e.category,
            "reason": e.reason, "created_at": e.created_at.isoformat(),
            "relationship_type": d.relationship_type if d else None,
            "calibrated_probability": d.calibrated_probability if d else None,
            "ledger_record_ids": d.ledger_record_ids if d else None,
            "settlement_record_ids": d.settlement_record_ids if d else None,
            "risk_flags": d.risk_flags if d else None,
            "primary_root_cause": primary_root_cause,
        })
    return {"exceptions": result}


@app.get("/exceptions/{exception_id}")
def get_exception(exception_id: str, db: Session = Depends(get_db)):
    e = db.query(ExceptionRecord).filter(ExceptionRecord.id == exception_id).first()
    if e is None:
        raise HTTPException(404, "Exception not found")
    d = e.decision

    features, all_present, _ = _recompute_full_features(d, db) if d else (None, False, {})
    analysis = analyze_exception(e.category, features, d.workflow_state if d else "FAILED", all_present)

    return {
        "exception_id": e.id, "decision_id": e.decision_id,
        "batch_id": d.batch_id if d else None,
        "original_category": e.category,   # the original classify_exception() output — never overwritten
        "original_reason": e.reason,        # the original persisted reason text — never overwritten
        "created_at": e.created_at.isoformat(),
        "relationship_type": d.relationship_type if d else None,
        "calibrated_probability": d.calibrated_probability if d else None,
        "workflow_state": d.workflow_state if d else None,
        "risk_flags": d.risk_flags if d else None,
        "ledger_record_ids": d.ledger_record_ids if d else None,
        "settlement_record_ids": d.settlement_record_ids if d else None,
        # Derived root-cause analysis — clearly separated from the fields
        # above, which are the original, immutable, persisted facts (spec
        # Step 12: "clearly distinguish original facts from derived
        # analysis").
        "root_cause_analysis": {
            "primary_root_cause": analysis.primary_root_cause,
            "observed": analysis.observed,
            "interpretation": analysis.interpretation,
            "contributing_factors": analysis.contributing_factors,
            "investigation_guidance": analysis.investigation_guidance,
            "taxonomy_version": analysis.taxonomy_version,
        },
    }


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


# ---------------- model evaluation ----------------

@app.get("/model/evaluation")
def get_model_evaluation():
    return get_model_evaluation_data()


# ---------------- demo datasets ----------------

@app.get("/demo-datasets")
def get_demo_datasets():
    """List all available preconfigured demo reconciliation scenarios."""
    return {"datasets": list_demo_datasets()}


@app.post("/demo-datasets/{dataset_id}/process")
def process_demo_dataset_batch(dataset_id: str, db: Session = Depends(get_db)):
    """Process an allowlisted demo scenario through the reconciliation pipeline."""
    meta = get_demo_dataset_metadata(dataset_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Demo dataset '{dataset_id}' not found")

    try:
        ledger_records, settlement_records = get_demo_dataset_records(dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Demo dataset '{dataset_id}' not found")
    except Exception as e:
        logger.exception("Failed to load demo dataset records for %s", dataset_id)
        raise HTTPException(status_code=500, detail=f"Failed to load demo dataset: {e}")

    batch = process_batch(db, ledger_records, settlement_records)
    return {
        "batch_id": batch.id,
        "status": batch.status,
        "summary": batch.summary,
    }


@app.get("/demo-datasets/{dataset_id}/files/{file_type}")
def download_demo_dataset_file(dataset_id: str, file_type: str):
    """Download the raw CSV file for a given demo dataset and file type (ledger or settlement)."""
    if get_demo_dataset_metadata(dataset_id) is None:
        raise HTTPException(status_code=404, detail=f"Demo dataset '{dataset_id}' not found")
    try:
        path = get_demo_dataset_file_path(dataset_id, file_type)
        return FileResponse(
            path=str(path),
            media_type="text/csv",
            filename=f"{dataset_id}_{file_type}.csv",
        )
    except (KeyError, ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Requested file not found")
