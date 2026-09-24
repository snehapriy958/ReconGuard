"""
ReconGuard — Reconciliation Export, Reporting & Financial Close Package.

Provides read-only extraction and reporting for completed reconciliation batches:
1. Reconciled Matched Export (CSV) — auto-matched & reviewer-approved pairs with structural groups.
2. Exception Export (CSV) — unresolved exceptions with root-cause categorization.
3. Reconciliation Closing Statement (JSON) — application-verified financial summary and invariant status.

Constraints:
- Strictly read-only: no database mutations or audit event emissions.
- Reuses Phase 3 financial summary as single source of accounting truth.
- Preserves 1:1, 1:N, and N:1 structural relationships without ID loss or amount duplication.
- Retains persisted calibrated probabilities without recalculation.
"""

from __future__ import annotations

import csv
import io
from typing import Any
from sqlalchemy.orm import Session

from backend.app.models.batch import Batch
from backend.app.models.decision import ReconciliationDecision
from backend.app.models.exception import ExceptionRecord
from backend.app.models.review import ReviewTask
from backend.app.models.source_record import SourceRecord

TAXONOMY_MAP = {
    "NO_CANDIDATE_FOUND": "NO_VIABLE_CANDIDATE",
    "STRUCTURAL_AMBIGUITY": "STRUCTURAL_MATCH_FAILURE",
    "HIGH_COMPETITION": "WEAK_MATCH_EVIDENCE",
    "INSUFFICIENT_EVIDENCE": "WEAK_MATCH_EVIDENCE",
    "LOW_MATCH_CONFIDENCE": "MODEL_UNCERTAINTY",
}


class BatchNotFoundError(Exception):
    """Raised when the specified batch does not exist."""
    pass


class BatchNotCompletedError(Exception):
    """Raised when an export is attempted on a batch that is not COMPLETED."""
    pass


def _get_completed_batch(db: Session, batch_id: str) -> Batch:
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch is None:
        raise BatchNotFoundError(f"Batch '{batch_id}' not found")
    if batch.status != "COMPLETED":
        raise BatchNotCompletedError(
            f"Cannot export batch in '{batch.status}' status. Batch must be COMPLETED."
        )
    return batch


def generate_matched_export_csv(db: Session, batch_id: str) -> str:
    """
    Generate CSV of reconciled source relationships for a completed batch.

    Inclusion rules:
    - Decisions where decision == 'HIGH_CONFIDENCE_MATCH'
    - Reviewer-approved decisions (workflow_state in ('APPROVED', 'APPROVED_BY_REVIEWER')
      or review_task.status == 'APPROVED')
    - Excludes rejected decisions or unresolved review items.

    Structural relationships (1:N, N:1):
    - Multiple record IDs are joined with pipe (|) delimiters.
    - Amount is the group total amount without artificial duplication.
    """
    batch = _get_completed_batch(db, batch_id)

    decisions = (
        db.query(ReconciliationDecision)
        .filter(ReconciliationDecision.batch_id == batch_id)
        .all()
    )

    reconciled_decisions: list[ReconciliationDecision] = []
    for d in decisions:
        is_rejected = (
            d.workflow_state in ("REJECTED", "REJECTED_BY_REVIEWER")
            or (d.review_task and d.review_task.status == "REJECTED")
        )
        if is_rejected:
            continue

        is_auto_matched = d.decision == "HIGH_CONFIDENCE_MATCH"
        is_approved = (
            d.workflow_state in ("APPROVED", "APPROVED_BY_REVIEWER")
            or (d.review_task and d.review_task.status == "APPROVED")
        )

        if is_auto_matched or is_approved:
            reconciled_decisions.append(d)

    # Fetch source records to resolve amounts and vendor names
    all_record_ids: set[str] = set()
    for d in reconciled_decisions:
        all_record_ids.update(d.ledger_record_ids or [])
        all_record_ids.update(d.settlement_record_ids or [])

    source_records = (
        db.query(SourceRecord)
        .filter(SourceRecord.batch_id == batch_id, SourceRecord.id.in_(all_record_ids))
        .all()
        if all_record_ids
        else []
    )
    source_map: dict[str, dict[str, Any]] = {r.id: r.raw_data for r in source_records}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ledger_id",
        "settlement_id",
        "relationship_type",
        "amount",
        "vendor_name",
        "calibrated_probability",
        "workflow_state",
    ])

    for d in reconciled_decisions:
        ledger_ids = d.ledger_record_ids or []
        settlement_ids = d.settlement_record_ids or []

        ledger_id_str = "|".join(ledger_ids)
        settlement_id_str = "|".join(settlement_ids)

        # Resolve total amount (sum ledger side, or settlement side fallback)
        ledger_amounts = [
            float(source_map.get(lid, {}).get("amount", 0.0) or 0.0)
            for lid in ledger_ids
        ]
        settlement_amounts = [
            float(source_map.get(sid, {}).get("amount", 0.0) or 0.0)
            for sid in settlement_ids
        ]

        if sum(ledger_amounts) > 0:
            total_amount = sum(ledger_amounts)
        else:
            total_amount = sum(settlement_amounts)

        # Resolve vendor name
        vendors = [
            str(source_map.get(lid, {}).get("vendor_name", "")).strip()
            for lid in ledger_ids
            if source_map.get(lid, {}).get("vendor_name")
        ]
        if not vendors:
            vendors = [
                str(source_map.get(sid, {}).get("vendor_name", "")).strip()
                for sid in settlement_ids
                if source_map.get(sid, {}).get("vendor_name")
            ]
        unique_vendors = list(dict.fromkeys(v for v in vendors if v))
        vendor_name_str = " | ".join(unique_vendors) if unique_vendors else ""

        prob_str = f"{d.calibrated_probability:.4f}"

        writer.writerow([
            ledger_id_str,
            settlement_id_str,
            d.relationship_type,
            f"{total_amount:.2f}",
            vendor_name_str,
            prob_str,
            d.workflow_state,
        ])

    return output.getvalue()


def generate_exceptions_export_csv(db: Session, batch_id: str) -> str:
    """
    Generate CSV of unresolved exception records associated with a completed batch.

    Columns:
    - exception_id
    - decision_id
    - record_ids (pipe-delimited list of source IDs involved)
    - category (persisted coarse category)
    - primary_root_cause (standardized taxonomy code)
    - reason (explanatory reason text)
    """
    _get_completed_batch(db, batch_id)

    exceptions = (
        db.query(ExceptionRecord)
        .join(ReconciliationDecision, ExceptionRecord.decision_id == ReconciliationDecision.id)
        .filter(ReconciliationDecision.batch_id == batch_id)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "exception_id",
        "decision_id",
        "record_ids",
        "category",
        "primary_root_cause",
        "reason",
    ])

    for exc in exceptions:
        d = exc.decision
        record_ids: list[str] = []
        if d:
            record_ids.extend(d.ledger_record_ids or [])
            record_ids.extend(d.settlement_record_ids or [])

        record_ids_str = "|".join(record_ids)
        category_str = exc.category
        root_cause_str = TAXONOMY_MAP.get(exc.category, exc.category)
        reason_str = exc.reason

        writer.writerow([
            exc.id,
            exc.decision_id,
            record_ids_str,
            category_str,
            root_cause_str,
            reason_str,
        ])

    return output.getvalue()


def generate_reconciliation_statement(db: Session, batch_id: str) -> dict[str, Any]:
    """
    Generate structured closing statement for a completed batch.
    Reuses existing Phase 3 financial summary and verifies mathematical invariants.
    """
    batch = _get_completed_batch(db, batch_id)
    summary = batch.summary or {}
    financials = summary.get("financials", {})

    ledger_fin = financials.get("ledger", {})
    settlement_fin = financials.get("settlement", {})

    # Verify invariants from the persisted financial metrics
    l_total = float(ledger_fin.get("total_amount", 0.0) or 0.0)
    l_sum = (
        float(ledger_fin.get("matched_amount", 0.0) or 0.0)
        + float(ledger_fin.get("review_amount", 0.0) or 0.0)
        + float(ledger_fin.get("exception_amount", 0.0) or 0.0)
    )
    ledger_amount_conservation = abs(l_total - l_sum) < 0.01

    s_total = float(settlement_fin.get("total_amount", 0.0) or 0.0)
    s_sum = (
        float(settlement_fin.get("matched_amount", 0.0) or 0.0)
        + float(settlement_fin.get("review_amount", 0.0) or 0.0)
        + float(settlement_fin.get("exception_amount", 0.0) or 0.0)
    )
    settlement_amount_conservation = abs(s_total - s_sum) < 0.01

    l_rate_sum = (
        float(ledger_fin.get("matched_rate", 0.0) or 0.0)
        + float(ledger_fin.get("review_rate", 0.0) or 0.0)
        + float(ledger_fin.get("exception_rate", 0.0) or 0.0)
    )
    # If total is 0, rate sum is 0, which is technically consistent
    ledger_rate_unity = abs(1.0 - l_rate_sum) < 0.001 if l_total > 0 else True

    s_rate_sum = (
        float(settlement_fin.get("matched_rate", 0.0) or 0.0)
        + float(settlement_fin.get("review_rate", 0.0) or 0.0)
        + float(settlement_fin.get("exception_rate", 0.0) or 0.0)
    )
    settlement_rate_unity = abs(1.0 - s_rate_sum) < 0.001 if s_total > 0 else True

    all_invariants_hold = bool(
        ledger_amount_conservation
        and settlement_amount_conservation
        and ledger_rate_unity
        and settlement_rate_unity
    )

    return {
        "batch_id": batch.id,
        "status": batch.status,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "ledger_record_count": batch.n_ledger_records,
        "settlement_record_count": batch.n_settlement_records,
        "ledger": {
            "total_amount": l_total,
            "matched_amount": float(ledger_fin.get("matched_amount", 0.0) or 0.0),
            "review_amount": float(ledger_fin.get("review_amount", 0.0) or 0.0),
            "exception_amount": float(ledger_fin.get("exception_amount", 0.0) or 0.0),
            "matched_rate": float(ledger_fin.get("matched_rate", 0.0) or 0.0),
            "review_rate": float(ledger_fin.get("review_rate", 0.0) or 0.0),
            "exception_rate": float(ledger_fin.get("exception_rate", 0.0) or 0.0),
        },
        "settlement": {
            "total_amount": s_total,
            "matched_amount": float(settlement_fin.get("matched_amount", 0.0) or 0.0),
            "review_amount": float(settlement_fin.get("review_amount", 0.0) or 0.0),
            "exception_amount": float(settlement_fin.get("exception_amount", 0.0) or 0.0),
            "matched_rate": float(settlement_fin.get("matched_rate", 0.0) or 0.0),
            "review_rate": float(settlement_fin.get("review_rate", 0.0) or 0.0),
            "exception_rate": float(settlement_fin.get("exception_rate", 0.0) or 0.0),
        },
        "invariants": {
            "ledger_amount_conservation": ledger_amount_conservation,
            "settlement_amount_conservation": settlement_amount_conservation,
            "ledger_rate_unity": ledger_rate_unity,
            "settlement_rate_unity": settlement_rate_unity,
            "all_invariants_hold": all_invariants_hold,
        },
        "summary": {
            "high_confidence_matches": int(summary.get("high_confidence_matches", 0) or 0),
            "needs_review": int(summary.get("needs_review", 0) or 0),
            "exceptions": int(summary.get("exceptions", 0) or 0),
            "structural_matches": int(summary.get("structural_matches", 0) or 0),
        },
    }
