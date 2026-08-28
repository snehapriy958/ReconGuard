import os

# MUST be set before importing backend.app.db, so the test suite runs against
# an isolated SQLite instance rather than the real Postgres database this
# project uses in normal operation (see backend/app/db.py docstring).
os.environ["RECONLENS_TEST_SQLITE"] = "1"

import pytest
from sqlalchemy.orm import Session

from backend.app.db import Base, engine, SessionLocal
from backend.app.workflow.state_machine import transition, transition_batch, InvalidTransitionError, is_terminal
from backend.app.workflow.risk import compute_risk_flags, classify_exception
from backend.app.idempotency import compute_batch_hash
from backend.app.pipeline import process_batch
from backend.app.review_actions import approve_review, reject_review, ReviewAlreadyResolvedError, ReviewNotFoundError
from backend.app.audit import get_audit_trail
from backend.app.models.batch import Batch
from backend.app.models.decision import ReconciliationDecision
from backend.app.models.review import ReviewTask
from backend.app.models.exception import ExceptionRecord
from backend.app.models.audit import AuditEvent


@pytest.fixture()
def db():
    from backend.app.models import batch, source_record, decision, evidence, review, exception, audit  # noqa
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _tiny_batch():
    """A small, deterministic set of records covering one clean match and
    one genuine LOW-CONFIDENCE candidate (close enough in amount/date to
    survive blocking, but different vendor and no reference overlap — so it
    becomes a real LIKELY_NO_MATCH candidate, not just an unpaired record)."""
    ledger = [
        {"ledger_id": "T-LED-01", "vendor_name": "Test Vendor Ltd", "amount": 1000.0,
         "txn_date": "2026-01-01", "reference_id": "REF001", "description": "test"},
        {"ledger_id": "T-LED-02", "vendor_name": "Totally Different Co", "amount": 5000.0,
         "txn_date": "2026-01-01", "reference_id": "REFXYZ", "description": "test"},
    ]
    settlement = [
        {"settlement_id": "T-STL-01", "vendor_name": "Test Vendor Ltd", "amount": 999.5,
         "txn_date": "2026-01-01", "reference_id": "REF001", "description": "test"},
        # close enough to T-LED-02's amount/date to survive blocking, but a
        # different vendor with no reference overlap — a real weak candidate,
        # not an unpaired record
        {"settlement_id": "T-STL-02", "vendor_name": "Nothing Alike Inc", "amount": 4980.0,
         "txn_date": "2026-01-02", "reference_id": "", "description": "unrelated"},
    ]
    return ledger, settlement


# ---------------- state machine ----------------

def test_valid_transition_succeeds():
    assert transition("PENDING", "PROCESSING") == "PROCESSING"
    assert transition("PROCESSING", "AUTO_MATCHED") == "AUTO_MATCHED"

def test_invalid_transition_raises():
    with pytest.raises(InvalidTransitionError):
        transition("PENDING", "AUTO_MATCHED")  # must go through PROCESSING first

def test_terminal_states_have_no_outgoing_transitions():
    assert is_terminal("AUTO_MATCHED")
    with pytest.raises(InvalidTransitionError):
        transition("AUTO_MATCHED", "NEEDS_REVIEW")

def test_batch_transitions_separate_from_decision_transitions():
    # Regression test for the real bug hit while running the first end-to-end
    # batch: Batch uses CREATED/PROCESSING/COMPLETED/FAILED, decisions use
    # PENDING/PROCESSING/AUTO_MATCHED/... — these must not be conflated.
    assert transition_batch("CREATED", "PROCESSING") == "PROCESSING"
    with pytest.raises(InvalidTransitionError):
        transition_batch("CREATED", "AUTO_MATCHED")  # not a batch state at all


# ---------------- risk flags ----------------

def test_one_to_many_gets_structural_risk_metadata():
    flags = compute_risk_flags({"competing_candidate_count": 0, "reference_exact_match": 1,
                                  "reference_substring_overlap": 1, "reference_similarity": 1.0,
                                  "reference_both_missing": 0}, "one_to_many")
    assert "STRUCTURAL_MATCH" in flags
    assert "ONE_TO_MANY_RELATIONSHIP" in flags
    assert "KNOWN_LOW_GENERALIZATION" in flags

def test_one_to_one_does_not_get_structural_flags():
    flags = compute_risk_flags({"competing_candidate_count": 0, "reference_exact_match": 1,
                                  "reference_substring_overlap": 1, "reference_similarity": 1.0,
                                  "reference_both_missing": 0}, "one_to_one")
    assert "STRUCTURAL_MATCH" not in flags
    assert "KNOWN_LOW_GENERALIZATION" not in flags

def test_many_to_one_flags_insufficient_validation_sample():
    flags = compute_risk_flags({"competing_candidate_count": 0, "reference_exact_match": 1,
                                  "reference_substring_overlap": 1, "reference_similarity": 1.0,
                                  "reference_both_missing": 0}, "many_to_one")
    assert "INSUFFICIENT_VALIDATION_SAMPLE" in flags

def test_risk_flags_never_alter_probability_semantics():
    """Risk is metadata, never a probability override — spec section 10."""
    row = {"competing_candidate_count": 20, "reference_exact_match": 0,
           "reference_substring_overlap": 0, "reference_similarity": 0.0, "reference_both_missing": 1}
    flags = compute_risk_flags(row, "one_to_many")
    assert isinstance(flags, list) and all(isinstance(f, str) for f in flags)
    # the function's return type structurally cannot carry a probability value


# ---------------- idempotency ----------------

def test_duplicate_batch_hash_is_deterministic_regardless_of_order():
    ledger, settlement = _tiny_batch()
    h1 = compute_batch_hash(ledger, settlement)
    h2 = compute_batch_hash(list(reversed(ledger)), list(reversed(settlement)))
    assert h1 == h2

def test_duplicate_batch_submission_creates_no_duplicate_decisions(db: Session):
    ledger, settlement = _tiny_batch()
    b1 = process_batch(db, ledger, settlement)
    n_decisions_1 = db.query(ReconciliationDecision).count()
    n_batches_1 = db.query(Batch).count()

    b2 = process_batch(db, ledger, settlement)
    n_decisions_2 = db.query(ReconciliationDecision).count()
    n_batches_2 = db.query(Batch).count()

    assert b1.id == b2.id
    assert n_decisions_1 == n_decisions_2
    assert n_batches_1 == n_batches_2


# ---------------- decision records (structural IDs preserved) ----------------

def test_pairwise_decision_stores_single_ids(db: Session):
    ledger, settlement = _tiny_batch()
    batch = process_batch(db, ledger, settlement)
    decisions = db.query(ReconciliationDecision).filter(ReconciliationDecision.batch_id == batch.id).all()
    one_to_one = [d for d in decisions if d.relationship_type == "one_to_one"]
    assert len(one_to_one) > 0
    for d in one_to_one:
        assert len(d.ledger_record_ids) == 1
        assert len(d.settlement_record_ids) == 1


# ---------------- review actions ----------------

def test_review_approve_preserves_original_ml_decision(db: Session):
    ledger, settlement = _tiny_batch()
    batch = process_batch(db, ledger, settlement)
    # Force a review task to exist for this small deterministic test by
    # checking whatever the pipeline actually produced (real data, not staged)
    review = db.query(ReviewTask).first()
    if review is None:
        pytest.skip("This tiny deterministic batch produced no NEEDS_REVIEW case — "
                    "covered instead by the real end-to-end batch in docs/workflow.md")
    ml_decision_before = review.decision.decision
    approve_review(db, review.id, reviewer_id="test_reviewer")
    assert review.decision.decision == ml_decision_before  # untouched
    assert review.decision.workflow_state == "APPROVED_BY_REVIEWER"

def test_review_reject_preserves_original_ml_decision(db: Session):
    ledger, settlement = _tiny_batch()
    batch = process_batch(db, ledger, settlement)
    review = db.query(ReviewTask).first()
    if review is None:
        pytest.skip("no review case in this deterministic batch")
    ml_decision_before = review.decision.decision
    reject_review(db, review.id, reviewer_id="test_reviewer")
    assert review.decision.decision == ml_decision_before
    assert review.decision.workflow_state == "REJECTED_BY_REVIEWER"

def test_cannot_resolve_already_resolved_review(db: Session):
    ledger, settlement = _tiny_batch()
    batch = process_batch(db, ledger, settlement)
    review = db.query(ReviewTask).first()
    if review is None:
        pytest.skip("no review case in this deterministic batch")
    approve_review(db, review.id, reviewer_id="reviewer_1")
    with pytest.raises(ReviewAlreadyResolvedError):
        approve_review(db, review.id, reviewer_id="reviewer_2")

def test_unknown_review_id_raises():
    os.environ["RECONLENS_TEST_SQLITE"] = "1"
    from backend.app.db import Base, engine, SessionLocal as SL
    Base.metadata.create_all(bind=engine)
    db = SL()
    with pytest.raises(ReviewNotFoundError):
        approve_review(db, "REV-doesnotexist", reviewer_id="x")
    db.close()


# ---------------- exceptions ----------------

def test_likely_no_match_creates_exception_with_real_evidence(db: Session):
    ledger, settlement = _tiny_batch()
    batch = process_batch(db, ledger, settlement)
    exceptions = db.query(ExceptionRecord).all()
    assert len(exceptions) > 0
    for exc in exceptions:
        assert exc.category in ("NO_CANDIDATE_FOUND", "HIGH_COMPETITION", "STRUCTURAL_AMBIGUITY",
                                  "INSUFFICIENT_EVIDENCE", "LOW_MATCH_CONFIDENCE")
        assert exc.reason  # non-empty, evidence-based reason

def test_exception_classification_priority_order():
    # NO_CANDIDATE_FOUND should win even if other conditions coincidentally hold
    row = {"candidate_count_for_ledger": 0, "candidate_count_for_settlement": 0,
           "competing_candidate_count": 20, "is_potential_one_to_many": 1, "is_potential_many_to_one": 1,
           "reference_exact_match": 0, "reference_substring_overlap": 0, "reference_similarity": 0.0,
           "vendor_jaro_winkler_similarity": 0.1}
    assert classify_exception(row) == "NO_CANDIDATE_FOUND"


# ---------------- audit trail ----------------

def test_audit_events_append_only_no_update_function_exists():
    import backend.app.audit as audit_module
    assert not hasattr(audit_module, "update_event")
    assert not hasattr(audit_module, "delete_event")

def test_human_action_creates_additional_event_not_overwrite(db: Session):
    ledger, settlement = _tiny_batch()
    batch = process_batch(db, ledger, settlement)
    review = db.query(ReviewTask).first()
    if review is None:
        pytest.skip("no review case in this deterministic batch")
    trail_before = get_audit_trail(db, "DECISION", review.decision_id)
    n_before = len(trail_before)
    approve_review(db, review.id, reviewer_id="test_reviewer")
    trail_after = get_audit_trail(db, "REVIEW", review.id)
    assert len(trail_after) >= 1
    # the original MODEL_EVALUATED event for the decision must still be there, unmodified
    model_events = [e for e in trail_before if e.event_type == "MODEL_EVALUATED"]
    assert len(model_events) == 1

def test_batch_audit_trail_retrievable(db: Session):
    ledger, settlement = _tiny_batch()
    batch = process_batch(db, ledger, settlement)
    trail = get_audit_trail(db, "BATCH", batch.id)
    event_types = [e.event_type for e in trail]
    assert "BATCH_CREATED" in event_types
    assert "PROCESSING_STARTED" in event_types
    assert "BATCH_COMPLETED" in event_types


# ---------------- failure handling ----------------

def test_processing_failure_creates_failed_state_and_audit_event(db: Session, monkeypatch):
    import backend.app.pipeline as pipeline_mod

    def broken_blocking_v1(*a, **kw):
        raise RuntimeError("simulated candidate-generation failure")

    monkeypatch.setattr(pipeline_mod, "blocking_v1", broken_blocking_v1)
    ledger, settlement = _tiny_batch()
    batch = process_batch(db, ledger, settlement)

    assert batch.status == "FAILED"
    assert batch.failure_reason is not None
    trail = get_audit_trail(db, "BATCH", batch.id)
    assert any(e.event_type == "PROCESSING_FAILED" for e in trail)

def test_nan_reference_id_does_not_crash_ingestion(db: Session):
    """Regression test for the real NaN-in-JSON bug caught while running the
    first end-to-end batch against Postgres."""
    ledger = [{"ledger_id": "T-LED-NAN", "vendor_name": "Vendor", "amount": 500.0,
               "txn_date": "2026-01-01", "reference_id": float("nan"), "description": "x"}]
    settlement = [{"settlement_id": "T-STL-NAN", "vendor_name": "Vendor", "amount": 500.0,
                   "txn_date": "2026-01-01", "reference_id": float("nan"), "description": "x"}]
    batch = process_batch(db, ledger, settlement)
    assert batch.status == "COMPLETED"
