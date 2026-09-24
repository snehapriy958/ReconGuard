"""
ReconLens — batch processing pipeline. This is where the ML system (Phases
1-4, unchanged) meets the workflow engine (Phase 5). No retraining, no
threshold changes — this module only orchestrates and persists.
"""
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.audit import record_event
from backend.app.idempotency import compute_batch_hash
from backend.app.models.batch import Batch
from backend.app.models.source_record import SourceRecord
from backend.app.models.decision import ReconciliationDecision
from backend.app.models.evidence import EvidenceRecord
from backend.app.models.review import ReviewTask
from backend.app.models.exception import ExceptionRecord
from backend.app.workflow.state_machine import transition, transition_batch, InvalidTransitionError
from backend.app.workflow.risk import compute_risk_flags, classify_exception, risk_explanation
from backend.app.financials import FinancialAccumulator

from ml.candidate_generation.blocking_v1 import generate_candidates as blocking_v1
from ml.candidate_generation.blocking_v2 import generate_structural_candidates
from ml.features.group_extractor import build_all_candidate_groups, extract_group_features

ROOT = Path(__file__).parent.parent.parent
MODEL_BUNDLE_PATH = ROOT / "models" / "reconlens_phase4_final.joblib"

_bundle_cache = None


def _load_model_bundle():
    global _bundle_cache
    if _bundle_cache is None:
        _bundle_cache = joblib.load(MODEL_BUNDLE_PATH)
    return _bundle_cache


def _evidence_strength(contribution: float) -> str:
    a = abs(contribution)
    if a >= 1.5:
        return "strong"
    if a >= 0.5:
        return "moderate"
    return "weak"


def _evidence_direction(feature_name: str, contribution: float) -> str:
    if feature_name == "competing_candidate_count" and contribution < 0:
        return "creates_ambiguity"
    return "supports_match" if contribution > 0 else "weakens_match"


def _sanitize_records(records: list[dict]) -> list[dict]:
    """Replace NaN with None before these records ever reach a JSON column.
    Root cause this guards against: pandas reads an empty CSV cell (e.g. a
    genuinely missing reference_id) as float NaN, not an empty string.
    Python's json.dumps happily serializes NaN by default, but that's not
    valid JSON per RFC 8259 — Postgres' JSON column type correctly rejects
    it, which is what surfaced this while running the first real batch
    (see docs/workflow.md "Important Failures").
    """
    clean = []
    for r in records:
        clean.append({k: (None if isinstance(v, float) and v != v else v) for k, v in r.items()})
    return clean


def process_batch(db: Session, ledger_records: list[dict], settlement_records: list[dict]) -> Batch:
    """ledger_records / settlement_records: lists of dicts matching the
    public CSV schema (ledger_id/vendor_name/amount/txn_date/reference_id/
    description, and settlement_id/... respectively).
    """
    ledger_records = _sanitize_records(ledger_records)
    settlement_records = _sanitize_records(settlement_records)
    batch_hash = compute_batch_hash(ledger_records, settlement_records)

    existing = db.query(Batch).filter(Batch.batch_hash == batch_hash).first()
    if existing is not None:
        record_event(db, "BATCH", existing.id, "DUPLICATE_SUBMISSION_DETECTED", actor_type="SYSTEM",
                     payload={"batch_hash": batch_hash, "original_status": existing.status})
        db.commit()
        return existing

    batch = Batch(
        status="CREATED", batch_hash=batch_hash,
        n_ledger_records=len(ledger_records), n_settlement_records=len(settlement_records),
    )
    db.add(batch)
    db.flush()
    record_event(db, "BATCH", batch.id, "BATCH_CREATED", actor_type="SYSTEM",
                 previous_state=None, new_state="CREATED",
                 payload={"n_ledger": len(ledger_records), "n_settlement": len(settlement_records)})
    db.commit()

    t0 = time.time()

    try:
        batch.status = transition_batch(batch.status, "PROCESSING")
        db.flush()
        record_event(db, "BATCH", batch.id, "PROCESSING_STARTED", actor_type="SYSTEM",
                     previous_state="CREATED", new_state="PROCESSING")
        db.commit()

        for r in ledger_records:
            db.add(SourceRecord(id=r["ledger_id"], batch_id=batch.id, record_type="LEDGER",
                                 public_id=r["ledger_id"], raw_data=r))
        for r in settlement_records:
            db.add(SourceRecord(id=r["settlement_id"], batch_id=batch.id, record_type="SETTLEMENT",
                                 public_id=r["settlement_id"], raw_data=r))
        db.commit()

        ledger_df = pd.DataFrame(ledger_records)
        settlement_df = pd.DataFrame(settlement_records)
        ledger_idx = ledger_df.set_index("ledger_id")
        settlement_idx = settlement_df.set_index("settlement_id")

        v1_pairs = blocking_v1(ledger_df, settlement_df)
        v2_structural = generate_structural_candidates(ledger_df, settlement_df)
        groups = build_all_candidate_groups(v1_pairs, v2_structural)

        has_description = "description" in ledger_df.columns and "description" in settlement_df.columns
        feature_df, _ = extract_group_features(groups, ledger_idx, settlement_idx, has_description)

        bundle = _load_model_bundle()
        feature_cols = bundle["feature_cols"]
        for col in feature_cols:
            if col not in feature_df.columns:
                feature_df[col] = 0  # e.g. description feature absent in this batch's schema

        X = feature_df[feature_cols].to_numpy(dtype=float)
        raw_proba = bundle["model"].predict_proba(X)[:, 1]
        calibrated_proba = bundle["calibrator"].predict_proba(X)[:, 1]
        contrib_matrix = bundle["model"].booster_.predict(X, pred_contrib=True)

        policy = bundle["threshold_policy"]
        high_t, low_t = policy["high_threshold"], policy["low_threshold"]

    except Exception as e:
        db.rollback()  # MUST come before touching `batch` again — a failed flush/commit leaves
                        # the session in a "pending rollback" state; any ORM attribute access
                        # (even reading batch.status) before rollback() raises PendingRollbackError,
                        # which would mask the real error. Caught while running the first real
                        # batch through this pipeline — see docs/workflow.md "Important Failures".
        batch = db.merge(batch)  # batch may now be detached from the rolled-back session; reattach it
        batch.status = transition_batch(batch.status, "FAILED")
        batch.failure_reason = f"{type(e).__name__}: {e}"
        db.flush()
        record_event(db, "BATCH", batch.id, "PROCESSING_FAILED", actor_type="SYSTEM",
                     previous_state="PROCESSING", new_state="FAILED",
                     payload={"stage": "candidate_generation_or_inference", "error": batch.failure_reason})
        db.commit()
        return batch

    counts = {"HIGH_CONFIDENCE_MATCH": 0, "NEEDS_REVIEW": 0, "LIKELY_NO_MATCH": 0,
              "one_to_many": 0, "many_to_one": 0, "risk_flagged": 0, "failed_candidates": 0}

    accumulator = FinancialAccumulator(ledger_records, settlement_records)

    for i, group in enumerate(groups):
        row = feature_df.iloc[i]
        try:
            p_raw, p_cal = float(raw_proba[i]), float(calibrated_proba[i])
            decision_label = ("HIGH_CONFIDENCE_MATCH" if p_cal >= high_t
                               else "LIKELY_NO_MATCH" if p_cal < low_t else "NEEDS_REVIEW")
            risk_flags = compute_risk_flags(row.to_dict(), group.relationship_type_candidate)

            decision = ReconciliationDecision(
                batch_id=batch.id,
                ledger_record_ids=list(group.ledger_ids), settlement_record_ids=list(group.settlement_ids),
                relationship_type=group.relationship_type_candidate,
                model_name="lightgbm", model_version=bundle["feature_schema_version"],
                raw_probability=p_raw, calibrated_probability=p_cal,
                high_threshold=high_t, low_threshold=low_t,
                decision=decision_label, workflow_state="PROCESSING",
                risk_flags=risk_flags,
            )
            db.add(decision)
            db.flush()

            record_event(db, "DECISION", decision.id, "MODEL_EVALUATED", actor_type="MODEL",
                         actor_id=f"{decision.model_name}:{decision.model_version}",
                         payload={"raw_probability": p_raw, "calibrated_probability": p_cal,
                                   "high_threshold": high_t, "low_threshold": low_t,
                                   "decision": decision_label, "relationship_type": group.relationship_type_candidate,
                                   "risk_flags": risk_flags})

            contrib = contrib_matrix[i][:-1]
            ranked = sorted(zip(feature_cols, contrib), key=lambda x: abs(x[1]), reverse=True)[:5]
            for fname, c in ranked:
                db.add(EvidenceRecord(
                    decision_id=decision.id, feature_name=fname, feature_value=float(row[fname]),
                    evidence_direction=_evidence_direction(fname, c),
                    evidence_strength=_evidence_strength(c), contribution=float(c),
                ))

            if decision_label == "HIGH_CONFIDENCE_MATCH":
                decision.workflow_state = transition(decision.workflow_state, "AUTO_MATCHED")
                record_event(db, "DECISION", decision.id, "AUTO_MATCH_CREATED", actor_type="SYSTEM",
                             previous_state="PROCESSING", new_state="AUTO_MATCHED")
                counts["HIGH_CONFIDENCE_MATCH"] += 1

            elif decision_label == "NEEDS_REVIEW":
                decision.workflow_state = transition(decision.workflow_state, "NEEDS_REVIEW")
                review = ReviewTask(
                    decision_id=decision.id, status="OPEN", relationship_type=decision.relationship_type,
                    calibrated_probability=p_cal, risk_flags=risk_flags,
                    evidence_snapshot=[{"feature": f, "value": float(row[f]), "contribution": float(c)} for f, c in ranked],
                )
                db.add(review)
                record_event(db, "DECISION", decision.id, "REVIEW_TASK_CREATED", actor_type="SYSTEM",
                             previous_state="PROCESSING", new_state="NEEDS_REVIEW")
                counts["NEEDS_REVIEW"] += 1

            else:  # LIKELY_NO_MATCH
                decision.workflow_state = transition(decision.workflow_state, "LIKELY_NO_MATCH")
                decision.workflow_state = transition(decision.workflow_state, "EXCEPTION")
                category = classify_exception(row.to_dict())
                exc = ExceptionRecord(
                    decision_id=decision.id, category=category,
                    reason=risk_explanation(category, decision.relationship_type) if category in
                           ("HIGH_COMPETITION", "STRUCTURAL_AMBIGUITY") else
                           f"Calibrated match probability ({p_cal:.3f}) fell below the review threshold ({low_t}).",
                    evidence_snapshot=[{"feature": f, "value": float(row[f]), "contribution": float(c)} for f, c in ranked],
                )
                db.add(exc)
                record_event(db, "DECISION", decision.id, "EXCEPTION_CREATED", actor_type="SYSTEM",
                             previous_state="PROCESSING", new_state="EXCEPTION",
                             payload={"category": category})
                counts["LIKELY_NO_MATCH"] += 1

            if group.relationship_type_candidate == "one_to_many":
                counts["one_to_many"] += 1
            if group.relationship_type_candidate == "many_to_one":
                counts["many_to_one"] += 1
            if risk_flags:
                counts["risk_flagged"] += 1

            accumulator.record_candidate_outcome(
                ledger_ids=group.ledger_ids,
                settlement_ids=group.settlement_ids,
                outcome=decision_label,
            )

            db.commit()

        except (InvalidTransitionError, Exception) as e:
            db.rollback()
            record_event(db, "BATCH", batch.id, "CANDIDATE_PROCESSING_FAILED", actor_type="SYSTEM",
                         payload={"candidate_index": i, "error": f"{type(e).__name__}: {e}"})
            db.commit()
            counts["failed_candidates"] += 1

    financial_summary = accumulator.compute_summary()

    batch.status = transition_batch(batch.status, "COMPLETED")
    batch.summary = {
        "total_records": len(ledger_records) + len(settlement_records),
        "candidates_generated": len(groups),
        "high_confidence_matches": counts["HIGH_CONFIDENCE_MATCH"],
        "needs_review": counts["NEEDS_REVIEW"],
        "likely_no_match": counts["LIKELY_NO_MATCH"],
        "exceptions": counts["LIKELY_NO_MATCH"],
        "structural_matches": counts["one_to_many"] + counts["many_to_one"],
        "one_to_many_matches": counts["one_to_many"],
        "many_to_one_matches": counts["many_to_one"],
        "risk_flagged_decisions": counts["risk_flagged"],
        "failed_candidates": counts["failed_candidates"],
        "processing_time_seconds": round(time.time() - t0, 3),
        "financials": financial_summary.to_dict(),
    }
    import datetime as _dt
    batch.completed_at = _dt.datetime.now(_dt.timezone.utc)
    db.flush()
    record_event(db, "BATCH", batch.id, "BATCH_COMPLETED", actor_type="SYSTEM",
                 previous_state="PROCESSING", new_state="COMPLETED", payload=batch.summary)
    db.commit()

    return batch
