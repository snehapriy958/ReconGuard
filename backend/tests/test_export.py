"""
ReconGuard — Backend tests for Phase 6 Export, Reporting & Financial Close Package.

Verifies:
- 404 on unknown batch ID across all three export endpoints
- 400 on non-COMPLETED batch status across all three export endpoints
- Correct headers, media types, and Content-Disposition attachments for CSV exports
- Inclusion of HIGH_CONFIDENCE_MATCH and approved reviews in matched export
- Exclusion of rejected and pending reviews in matched export
- Correct 1:N and N:1 structural formatting (pipe-delimited IDs, amount non-duplication)
- Correct exception CSV columns, taxonomy mapping, and record preservation
- Statement structure, financial metrics, and mathematical invariants
- Strictly read-only operation: no database mutations or audit events emitted
- End-to-end integration with pipeline-processed batches
"""

import os
os.environ["RECONLENS_TEST_SQLITE"] = "1"

import csv
import io
import datetime
import pytest
from fastapi.testclient import TestClient

from backend.app.db import Base, engine, SessionLocal, get_db
from backend.app.api.main import app
from backend.app.models.batch import Batch
from backend.app.models.source_record import SourceRecord
from backend.app.models.decision import ReconciliationDecision
from backend.app.models.review import ReviewTask
from backend.app.models.exception import ExceptionRecord
from backend.app.models.audit import AuditEvent
from backend.app.export import (
    generate_matched_export_csv,
    generate_exceptions_export_csv,
    generate_reconciliation_statement,
    BatchNotFoundError,
    BatchNotCompletedError,
)
from backend.app.pipeline import process_batch


@pytest.fixture()
def db():
    from backend.app.models import batch, source_record, decision, evidence, review, exception, audit  # noqa
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _create_test_batch(db, status="COMPLETED", summary=None) -> Batch:
    now = datetime.datetime.now(datetime.timezone.utc)
    b = Batch(
        id="batch-test-123",
        batch_hash="hash-test-123",
        status=status,
        created_at=now,
        completed_at=now if status == "COMPLETED" else None,
        n_ledger_records=2,
        n_settlement_records=2,
        summary=summary or {
            "high_confidence_matches": 1,
            "needs_review": 1,
            "exceptions": 1,
            "structural_matches": 0,
            "financials": {
                "ledger": {
                    "total_amount": 1000.0,
                    "matched_amount": 600.0,
                    "review_amount": 300.0,
                    "exception_amount": 100.0,
                    "matched_rate": 0.60,
                    "review_rate": 0.30,
                    "exception_rate": 0.10,
                },
                "settlement": {
                    "total_amount": 1000.0,
                    "matched_amount": 600.0,
                    "review_amount": 300.0,
                    "exception_amount": 100.0,
                    "matched_rate": 0.60,
                    "review_rate": 0.30,
                    "exception_rate": 0.10,
                },
            },
        },
    )
    db.add(b)
    db.commit()
    return b


def _create_source_record(db, batch_id: str, record_id: str, record_type: str, raw_data: dict) -> SourceRecord:
    r = SourceRecord(
        id=record_id,
        batch_id=batch_id,
        record_type=record_type,
        public_id=record_id,
        raw_data=raw_data,
    )
    db.add(r)
    return r


def _create_review_task(
    db,
    decision_id: str,
    id: str,
    status: str = "OPEN",
    relationship_type: str = "ONE_TO_ONE",
    calibrated_probability: float = 0.75,
    assigned_reviewer: str = None,
) -> ReviewTask:
    rev = ReviewTask(
        id=id,
        decision_id=decision_id,
        status=status,
        relationship_type=relationship_type,
        calibrated_probability=calibrated_probability,
        assigned_reviewer=assigned_reviewer,
        risk_flags=[],
    )
    db.add(rev)
    return rev


def _create_decision(
    db,
    batch_id: str,
    id: str,
    decision: str = "HIGH_CONFIDENCE_MATCH",
    relationship_type: str = "ONE_TO_ONE",
    ledger_record_ids: list = None,
    settlement_record_ids: list = None,
    calibrated_probability: float = 0.95,
    raw_probability: float = 0.95,
    high_threshold: float = 0.85,
    low_threshold: float = 0.50,
    workflow_state: str = "MATCHED",
) -> ReconciliationDecision:
    d = ReconciliationDecision(
        id=id,
        batch_id=batch_id,
        decision=decision,
        relationship_type=relationship_type,
        ledger_record_ids=ledger_record_ids or [],
        settlement_record_ids=settlement_record_ids or [],
        calibrated_probability=calibrated_probability,
        raw_probability=raw_probability,
        high_threshold=high_threshold,
        low_threshold=low_threshold,
        workflow_state=workflow_state,
        risk_flags=[],
    )
    db.add(d)
    return d


# ---------------- 1-6: Status & Not Found Validation ----------------

def test_matched_export_unknown_batch_404(client):
    res = client.get("/batches/nonexistent-batch/export/matched")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_exceptions_export_unknown_batch_404(client):
    res = client.get("/batches/nonexistent-batch/export/exceptions")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_statement_export_unknown_batch_404(client):
    res = client.get("/batches/nonexistent-batch/export/statement")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_matched_export_non_completed_batch_400(client, db):
    _create_test_batch(db, status="PROCESSING")
    res = client.get("/batches/batch-test-123/export/matched")
    assert res.status_code == 400
    assert "COMPLETED" in res.json()["detail"]


def test_exceptions_export_non_completed_batch_400(client, db):
    _create_test_batch(db, status="PENDING")
    res = client.get("/batches/batch-test-123/export/exceptions")
    assert res.status_code == 400
    assert "COMPLETED" in res.json()["detail"]


def test_statement_export_non_completed_batch_400(client, db):
    _create_test_batch(db, status="FAILED")
    res = client.get("/batches/batch-test-123/export/statement")
    assert res.status_code == 400
    assert "COMPLETED" in res.json()["detail"]


# ---------------- 7-9: Headers, Content Types & Attachments ----------------

def test_matched_export_csv_headers_and_content_type(client, db):
    _create_test_batch(db, status="COMPLETED")
    res = client.get("/batches/batch-test-123/export/matched")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert 'attachment; filename="reconguard_batch-test-123_matched.csv"' in res.headers["content-disposition"]
    reader = csv.reader(io.StringIO(res.text))
    header = next(reader)
    assert header == [
        "ledger_id",
        "settlement_id",
        "relationship_type",
        "amount",
        "vendor_name",
        "calibrated_probability",
        "workflow_state",
    ]


def test_exceptions_export_csv_headers_and_content_type(client, db):
    _create_test_batch(db, status="COMPLETED")
    res = client.get("/batches/batch-test-123/export/exceptions")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert 'attachment; filename="reconguard_batch-test-123_exceptions.csv"' in res.headers["content-disposition"]
    reader = csv.reader(io.StringIO(res.text))
    header = next(reader)
    assert header == [
        "exception_id",
        "decision_id",
        "record_ids",
        "category",
        "primary_root_cause",
        "reason",
    ]


def test_statement_export_json_structure(client, db):
    _create_test_batch(db, status="COMPLETED")
    res = client.get("/batches/batch-test-123/export/statement")
    assert res.status_code == 200
    data = res.json()
    assert data["batch_id"] == "batch-test-123"
    assert data["status"] == "COMPLETED"
    assert "ledger" in data
    assert "settlement" in data
    assert "invariants" in data
    assert "summary" in data
    assert data["invariants"]["all_invariants_hold"] is True


# ---------------- 10-13: Matched Export Filtering ----------------

def test_matched_export_includes_auto_match(db):
    b = _create_test_batch(db)
    rec_l = _create_source_record(db, b.id, "L1", "LEDGER", {"amount": 150.0, "vendor_name": "Acme Corp"})
    rec_s = _create_source_record(db, b.id, "S1", "SETTLEMENT", {"amount": 150.0, "vendor_name": "Acme Corp"})
    d = _create_decision(
        db,
        batch_id=b.id,
        id="d1",
        decision="HIGH_CONFIDENCE_MATCH",
        relationship_type="ONE_TO_ONE",
        ledger_record_ids=["L1"],
        settlement_record_ids=["S1"],
        calibrated_probability=0.985,
        workflow_state="MATCHED",
    )
    db.commit()

    csv_text = generate_matched_export_csv(db, b.id)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 1
    assert rows[0]["ledger_id"] == "L1"
    assert rows[0]["settlement_id"] == "S1"
    assert rows[0]["relationship_type"] == "ONE_TO_ONE"
    assert rows[0]["amount"] == "150.00"
    assert rows[0]["vendor_name"] == "Acme Corp"
    assert rows[0]["calibrated_probability"] == "0.9850"
    assert rows[0]["workflow_state"] == "MATCHED"


def test_matched_export_includes_approved_review(db):
    b = _create_test_batch(db)
    rec_l = _create_source_record(db, b.id, "L2", "LEDGER", {"amount": 250.0, "vendor_name": "Beta Inc"})
    rec_s = _create_source_record(db, b.id, "S2", "SETTLEMENT", {"amount": 250.0, "vendor_name": "Beta Inc"})
    d = _create_decision(
        db,
        batch_id=b.id,
        id="d2",
        decision="NEEDS_REVIEW",
        relationship_type="ONE_TO_ONE",
        ledger_record_ids=["L2"],
        settlement_record_ids=["S2"],
        calibrated_probability=0.74,
        workflow_state="APPROVED",
    )
    rev = _create_review_task(
        db,
        decision_id=d.id,
        id="rev2",
        status="APPROVED",
        relationship_type="ONE_TO_ONE",
        calibrated_probability=0.74,
        assigned_reviewer="reviewer@example.com",
    )
    db.commit()

    csv_text = generate_matched_export_csv(db, b.id)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 1
    assert rows[0]["ledger_id"] == "L2"
    assert rows[0]["workflow_state"] == "APPROVED"


def test_matched_export_excludes_rejected_review(db):
    b = _create_test_batch(db)
    rec_l = _create_source_record(db, b.id, "L3", "LEDGER", {"amount": 300.0, "vendor_name": "Gamma LLC"})
    rec_s = _create_source_record(db, b.id, "S3", "SETTLEMENT", {"amount": 300.0, "vendor_name": "Gamma LLC"})
    d = _create_decision(
        db,
        batch_id=b.id,
        id="d3",
        decision="NEEDS_REVIEW",
        relationship_type="ONE_TO_ONE",
        ledger_record_ids=["L3"],
        settlement_record_ids=["S3"],
        calibrated_probability=0.62,
        workflow_state="REJECTED",
    )
    rev = _create_review_task(
        db,
        decision_id=d.id,
        id="rev3",
        status="REJECTED",
        relationship_type="ONE_TO_ONE",
        calibrated_probability=0.62,
    )
    db.commit()

    csv_text = generate_matched_export_csv(db, b.id)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 0


def test_matched_export_excludes_pending_review(db):
    b = _create_test_batch(db)
    rec_l = _create_source_record(db, b.id, "L4", "LEDGER", {"amount": 400.0, "vendor_name": "Delta Co"})
    rec_s = _create_source_record(db, b.id, "S4", "SETTLEMENT", {"amount": 400.0, "vendor_name": "Delta Co"})
    d = _create_decision(
        db,
        batch_id=b.id,
        id="d4",
        decision="NEEDS_REVIEW",
        relationship_type="ONE_TO_ONE",
        ledger_record_ids=["L4"],
        settlement_record_ids=["S4"],
        calibrated_probability=0.65,
        workflow_state="NEEDS_REVIEW",
    )
    rev = _create_review_task(
        db,
        decision_id=d.id,
        id="rev4",
        status="PENDING",
        relationship_type="ONE_TO_ONE",
        calibrated_probability=0.65,
    )
    db.commit()

    csv_text = generate_matched_export_csv(db, b.id)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 0


# ---------------- 14-17: Structural Relationships & Formatting ----------------

def test_matched_export_structural_one_to_many(db):
    b = _create_test_batch(db)
    l1 = _create_source_record(db, b.id, "L10", "LEDGER", {"amount": 100.0, "vendor_name": "Split Corp"})
    s1 = _create_source_record(db, b.id, "S10A", "SETTLEMENT", {"amount": 40.0, "vendor_name": "Split Corp"})
    s2 = _create_source_record(db, b.id, "S10B", "SETTLEMENT", {"amount": 60.0, "vendor_name": "Split Corp"})
    d = _create_decision(
        db,
        batch_id=b.id,
        id="d-split-1",
        decision="HIGH_CONFIDENCE_MATCH",
        relationship_type="ONE_TO_MANY",
        ledger_record_ids=["L10"],
        settlement_record_ids=["S10A", "S10B"],
        calibrated_probability=0.96,
        workflow_state="MATCHED",
    )
    db.commit()

    csv_text = generate_matched_export_csv(db, b.id)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 1
    assert rows[0]["ledger_id"] == "L10"
    assert rows[0]["settlement_id"] == "S10A|S10B"
    assert rows[0]["relationship_type"] == "ONE_TO_MANY"
    assert rows[0]["amount"] == "100.00"


def test_matched_export_structural_many_to_one(db):
    b = _create_test_batch(db)
    l1 = _create_source_record(db, b.id, "L20A", "LEDGER", {"amount": 50.0, "vendor_name": "Consolidated LLC"})
    l2 = _create_source_record(db, b.id, "L20B", "LEDGER", {"amount": 50.0, "vendor_name": "Consolidated LLC"})
    s1 = _create_source_record(db, b.id, "S20", "SETTLEMENT", {"amount": 100.0, "vendor_name": "Consolidated LLC"})
    d = _create_decision(
        db,
        batch_id=b.id,
        id="d-split-2",
        decision="HIGH_CONFIDENCE_MATCH",
        relationship_type="MANY_TO_ONE",
        ledger_record_ids=["L20A", "L20B"],
        settlement_record_ids=["S20"],
        calibrated_probability=0.955,
        workflow_state="MATCHED",
    )
    db.commit()

    csv_text = generate_matched_export_csv(db, b.id)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 1
    assert rows[0]["ledger_id"] == "L20A|L20B"
    assert rows[0]["settlement_id"] == "S20"
    assert rows[0]["relationship_type"] == "MANY_TO_ONE"
    assert rows[0]["amount"] == "100.00"


def test_matched_export_amounts_not_duplicated(db):
    b = _create_test_batch(db)
    l1 = _create_source_record(db, b.id, "L30", "LEDGER", {"amount": 200.0, "vendor_name": "Vendor A"})
    s1 = _create_source_record(db, b.id, "S30A", "SETTLEMENT", {"amount": 100.0, "vendor_name": "Vendor A"})
    s2 = _create_source_record(db, b.id, "S30B", "SETTLEMENT", {"amount": 100.0, "vendor_name": "Vendor A"})
    d = _create_decision(
        db,
        batch_id=b.id,
        id="d-single-entry",
        decision="HIGH_CONFIDENCE_MATCH",
        relationship_type="ONE_TO_MANY",
        ledger_record_ids=["L30"],
        settlement_record_ids=["S30A", "S30B"],
        calibrated_probability=0.97,
        workflow_state="MATCHED",
    )
    db.commit()

    csv_text = generate_matched_export_csv(db, b.id)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    # Output must have exactly 1 row for the match, not split into 2 duplicate rows
    assert len(rows) == 1
    assert float(rows[0]["amount"]) == 200.0


def test_matched_export_calibrated_probabilities_persisted(db):
    b = _create_test_batch(db)
    rec_l = _create_source_record(db, b.id, "LP", "LEDGER", {"amount": 75.0, "vendor_name": "Prob Test"})
    rec_s = _create_source_record(db, b.id, "SP", "SETTLEMENT", {"amount": 75.0, "vendor_name": "Prob Test"})
    d = _create_decision(
        db,
        batch_id=b.id,
        id="dp",
        decision="HIGH_CONFIDENCE_MATCH",
        relationship_type="ONE_TO_ONE",
        ledger_record_ids=["LP"],
        settlement_record_ids=["SP"],
        calibrated_probability=0.912345,
        workflow_state="MATCHED",
    )
    db.commit()
    db.commit()

    csv_text = generate_matched_export_csv(db, b.id)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert rows[0]["calibrated_probability"] == "0.9123"


# ---------------- 18-19: Exceptions Export & Taxonomy ----------------

def test_exceptions_export_columns_and_taxonomy(db):
    b = _create_test_batch(db)
    d = _create_decision(
        db,
        batch_id=b.id,
        id="d-exc-1",
        decision="EXCEPTION",
        relationship_type="ONE_TO_ZERO",
        ledger_record_ids=["L_EXC_1"],
        settlement_record_ids=[],
        calibrated_probability=0.12,
        workflow_state="EXCEPTION",
    )
    exc = ExceptionRecord(
        id="exc-001",
        decision_id="d-exc-1",
        category="NO_CANDIDATE_FOUND",
        reason="No matching candidate settlement record exists within amount threshold",
    )
    db.add_all([d, exc])
    db.commit()

    csv_text = generate_exceptions_export_csv(db, b.id)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 1
    assert rows[0]["exception_id"] == "exc-001"
    assert rows[0]["decision_id"] == "d-exc-1"
    assert rows[0]["record_ids"] == "L_EXC_1"
    assert rows[0]["category"] == "NO_CANDIDATE_FOUND"
    assert rows[0]["primary_root_cause"] == "NO_VIABLE_CANDIDATE"
    assert "threshold" in rows[0]["reason"]


def test_exceptions_export_includes_all_unresolved(db):
    b = _create_test_batch(db)
    d1 = _create_decision(
        db,
        batch_id=b.id,
        id="de1",
        decision="EXCEPTION",
        relationship_type="ONE_TO_ZERO",
        ledger_record_ids=["L101"],
        settlement_record_ids=[],
        calibrated_probability=0.10,
        workflow_state="EXCEPTION",
    )
    exc1 = ExceptionRecord(id="e1", decision_id="de1", category="STRUCTURAL_AMBIGUITY", reason="Ambiguous candidate options")

    d2 = _create_decision(
        db,
        batch_id=b.id,
        id="de2",
        decision="EXCEPTION",
        relationship_type="ZERO_TO_ONE",
        ledger_record_ids=[],
        settlement_record_ids=["S101"],
        calibrated_probability=0.10,
        workflow_state="EXCEPTION",
    )
    exc2 = ExceptionRecord(id="e2", decision_id="de2", category="LOW_MATCH_CONFIDENCE", reason="Confidence below review threshold")

    db.add_all([d1, exc1, d2, exc2])
    db.commit()

    csv_text = generate_exceptions_export_csv(db, b.id)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 2
    root_causes = {r["primary_root_cause"] for r in rows}
    assert root_causes == {"STRUCTURAL_MATCH_FAILURE", "MODEL_UNCERTAINTY"}


# ---------------- 20-21: Closing Statement & Invariants ----------------

def test_reconciliation_statement_financial_invariants(db):
    b = _create_test_batch(
        db,
        summary={
            "high_confidence_matches": 5,
            "needs_review": 2,
            "exceptions": 1,
            "structural_matches": 1,
            "financials": {
                "ledger": {
                    "total_amount": 5000.0,
                    "matched_amount": 3500.0,
                    "review_amount": 1000.0,
                    "exception_amount": 500.0,
                    "matched_rate": 0.70,
                    "review_rate": 0.20,
                    "exception_rate": 0.10,
                },
                "settlement": {
                    "total_amount": 5000.0,
                    "matched_amount": 3500.0,
                    "review_amount": 1000.0,
                    "exception_amount": 500.0,
                    "matched_rate": 0.70,
                    "review_rate": 0.20,
                    "exception_rate": 0.10,
                },
            },
        },
    )

    statement = generate_reconciliation_statement(db, b.id)
    invariants = statement["invariants"]
    assert invariants["ledger_amount_conservation"] is True
    assert invariants["settlement_amount_conservation"] is True
    assert invariants["ledger_rate_unity"] is True
    assert invariants["settlement_rate_unity"] is True
    assert invariants["all_invariants_hold"] is True


def test_reconciliation_statement_conserved_totals(db):
    b = _create_test_batch(db)
    stmt = generate_reconciliation_statement(db, b.id)
    assert stmt["batch_id"] == b.id
    assert stmt["ledger"]["total_amount"] == 1000.0
    assert stmt["settlement"]["total_amount"] == 1000.0
    assert stmt["summary"]["high_confidence_matches"] == 1
    assert stmt["summary"]["needs_review"] == 1


# ---------------- 22-23: Read-Only Property & Integration Test ----------------

def test_exports_are_strictly_read_only_no_mutations(client, db):
    b = _create_test_batch(db)
    batch_count_before = db.query(Batch).count()
    decision_count_before = db.query(ReconciliationDecision).count()
    audit_count_before = db.query(AuditEvent).count()

    # Trigger all three exports
    res_m = client.get(f"/batches/{b.id}/export/matched")
    res_e = client.get(f"/batches/{b.id}/export/exceptions")
    res_s = client.get(f"/batches/{b.id}/export/statement")

    assert res_m.status_code == 200
    assert res_e.status_code == 200
    assert res_s.status_code == 200

    assert db.query(Batch).count() == batch_count_before
    assert db.query(ReconciliationDecision).count() == decision_count_before
    assert db.query(AuditEvent).count() == audit_count_before


def test_exports_on_pipeline_processed_batch(client, db):
    ledger = [
        {"ledger_id": "T-LED-01", "vendor_name": "Test Vendor Ltd", "amount": 1000.0,
         "txn_date": "2026-01-01", "reference_id": "REF001", "description": "test"},
        {"ledger_id": "T-LED-02", "vendor_name": "Totally Different Co", "amount": 5000.0,
         "txn_date": "2026-01-01", "reference_id": "REFXYZ", "description": "test"},
    ]
    settlement = [
        {"settlement_id": "T-STL-01", "vendor_name": "Test Vendor Ltd", "amount": 999.5,
         "txn_date": "2026-01-01", "reference_id": "REF001", "description": "test"},
        {"settlement_id": "T-STL-02", "vendor_name": "Totally Different Co", "amount": 4980.0,
         "txn_date": "2026-01-02", "reference_id": "", "description": "unrelated"},
    ]

    batch = process_batch(db, ledger, settlement)
    assert batch.status == "COMPLETED"

    # Verify statement
    stmt_res = client.get(f"/batches/{batch.id}/export/statement")
    assert stmt_res.status_code == 200
    stmt = stmt_res.json()
    assert stmt["batch_id"] == batch.id
    assert stmt["invariants"]["all_invariants_hold"] is True

    # Verify matched CSV
    matched_res = client.get(f"/batches/{batch.id}/export/matched")
    assert matched_res.status_code == 200
    reader = csv.DictReader(io.StringIO(matched_res.text))
    rows = list(reader)
    assert len(rows) >= 1

    # Verify exceptions CSV
    exc_res = client.get(f"/batches/{batch.id}/export/exceptions")
    assert exc_res.status_code == 200
