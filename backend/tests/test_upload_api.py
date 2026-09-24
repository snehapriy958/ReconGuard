import io
import csv
import os
os.environ["RECONLENS_TEST_SQLITE"] = "1"

import pytest
from fastapi.testclient import TestClient

from backend.app.db import Base, engine, SessionLocal, get_db
from backend.app.api.main import app
from backend.app.models.batch import Batch
from backend.app.models.decision import ReconciliationDecision
from backend.app.csv_validator import validate_and_parse_csv


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


def _make_csv(headers: list[str], rows: list[list[str]]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)
    return out.getvalue().encode("utf-8")


def _valid_ledger_csv() -> bytes:
    return _make_csv(
        ["ledger_id", "vendor_name", "amount", "txn_date", "reference_id", "description"],
        [
            ["LED-01", "Test Vendor Ltd", "1000.0", "2026-01-01", "REF001", "payment 1"],
            ["LED-02", "Totally Different Co", "5000.0", "2026-01-01", "REFXYZ", "payment 2"],
        ],
    )


def _valid_settlement_csv() -> bytes:
    return _make_csv(
        ["settlement_id", "vendor_name", "amount", "txn_date", "reference_id", "description"],
        [
            ["STL-01", "Test Vendor Ltd", "999.5", "2026-01-01", "REF001", "settle 1"],
            ["STL-02", "Nothing Alike Inc", "4980.0", "2026-01-02", "", "settle 2"],
        ],
    )


# 1. Valid ledger + settlement CSV upload succeeds
def test_valid_csv_upload_succeeds(client):
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", _valid_ledger_csv(), "text/csv"),
            "settlement_file": ("settlement.csv", _valid_settlement_csv(), "text/csv"),
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "batch_id" in data
    assert data["status"] == "COMPLETED"
    assert data["summary"] is not None
    assert data["summary"]["total_records"] == 4


# 2. Missing ledger file rejected
def test_missing_ledger_file_rejected(client):
    resp = client.post(
        "/batches/upload",
        files={"settlement_file": ("settlement.csv", _valid_settlement_csv(), "text/csv")},
    )
    assert resp.status_code == 422  # FastAPI validation


# 3. Missing settlement file rejected
def test_missing_settlement_file_rejected(client):
    resp = client.post(
        "/batches/upload",
        files={"ledger_file": ("ledger.csv", _valid_ledger_csv(), "text/csv")},
    )
    assert resp.status_code == 422


# 4. Empty ledger CSV rejected
def test_empty_ledger_csv_rejected(client):
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", b"", "text/csv"),
            "settlement_file": ("settlement.csv", _valid_settlement_csv(), "text/csv"),
        },
    )
    assert resp.status_code == 400
    errs = resp.json()["detail"]["errors"]
    assert any(e["file"] == "ledger" and "empty" in e["message"].lower() for e in errs)


# 5. Empty settlement CSV rejected
def test_empty_settlement_csv_rejected(client):
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", _valid_ledger_csv(), "text/csv"),
            "settlement_file": ("settlement.csv", b"   \n", "text/csv"),
        },
    )
    assert resp.status_code == 400
    errs = resp.json()["detail"]["errors"]
    assert any(e["file"] == "settlement" and "empty" in e["message"].lower() for e in errs)


# 6. Missing required ledger column rejected
def test_missing_required_ledger_column_rejected(client):
    bad_ledger = _make_csv(
        ["ledger_id", "amount", "txn_date"],  # missing vendor_name
        [["LED-01", "100.0", "2026-01-01"]],
    )
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", bad_ledger, "text/csv"),
            "settlement_file": ("settlement.csv", _valid_settlement_csv(), "text/csv"),
        },
    )
    assert resp.status_code == 400
    errs = resp.json()["detail"]["errors"]
    assert any(e["file"] == "ledger" and e["field"] == "vendor_name" for e in errs)


# 7. Missing required settlement column rejected
def test_missing_required_settlement_column_rejected(client):
    bad_settlement = _make_csv(
        ["settlement_id", "vendor_name", "txn_date"],  # missing amount
        [["STL-01", "Vendor X", "2026-01-01"]],
    )
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", _valid_ledger_csv(), "text/csv"),
            "settlement_file": ("settlement.csv", bad_settlement, "text/csv"),
        },
    )
    assert resp.status_code == 400
    errs = resp.json()["detail"]["errors"]
    assert any(e["file"] == "settlement" and e["field"] == "amount" for e in errs)


# 8. Duplicate ledger IDs rejected
def test_duplicate_ledger_ids_rejected(client):
    dup_ledger = _make_csv(
        ["ledger_id", "vendor_name", "amount", "txn_date"],
        [
            ["LED-01", "Vendor A", "100.0", "2026-01-01"],
            ["LED-01", "Vendor B", "200.0", "2026-01-02"],
        ],
    )
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", dup_ledger, "text/csv"),
            "settlement_file": ("settlement.csv", _valid_settlement_csv(), "text/csv"),
        },
    )
    assert resp.status_code == 400
    errs = resp.json()["detail"]["errors"]
    assert any(e["file"] == "ledger" and "duplicate" in e["message"].lower() for e in errs)


# 9. Duplicate settlement IDs rejected
def test_duplicate_settlement_ids_rejected(client):
    dup_settlement = _make_csv(
        ["settlement_id", "vendor_name", "amount", "txn_date"],
        [
            ["STL-01", "Vendor A", "100.0", "2026-01-01"],
            ["STL-01", "Vendor B", "200.0", "2026-01-02"],
        ],
    )
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", _valid_ledger_csv(), "text/csv"),
            "settlement_file": ("settlement.csv", dup_settlement, "text/csv"),
        },
    )
    assert resp.status_code == 400
    errs = resp.json()["detail"]["errors"]
    assert any(e["file"] == "settlement" and "duplicate" in e["message"].lower() for e in errs)


# 10. Invalid amount rejected
def test_invalid_amount_rejected(client):
    bad_amount = _make_csv(
        ["ledger_id", "vendor_name", "amount", "txn_date"],
        [["LED-01", "Vendor A", "not_a_number", "2026-01-01"]],
    )
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", bad_amount, "text/csv"),
            "settlement_file": ("settlement.csv", _valid_settlement_csv(), "text/csv"),
        },
    )
    assert resp.status_code == 400
    errs = resp.json()["detail"]["errors"]
    assert any(e["file"] == "ledger" and e["field"] == "amount" and e["row"] == 2 for e in errs)


# 11. Invalid date rejected
def test_invalid_date_rejected(client):
    bad_date = _make_csv(
        ["settlement_id", "vendor_name", "amount", "txn_date"],
        [["STL-01", "Vendor A", "50.0", "32-13-2026"]],
    )
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", _valid_ledger_csv(), "text/csv"),
            "settlement_file": ("settlement.csv", bad_date, "text/csv"),
        },
    )
    assert resp.status_code == 400
    errs = resp.json()["detail"]["errors"]
    assert any(e["file"] == "settlement" and e["field"] == "txn_date" and e["row"] == 2 for e in errs)


# 12. Empty required vendor rejected
def test_empty_required_vendor_rejected(client):
    bad_vendor = _make_csv(
        ["ledger_id", "vendor_name", "amount", "txn_date"],
        [["LED-01", "   ", "100.0", "2026-01-01"]],
    )
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", bad_vendor, "text/csv"),
            "settlement_file": ("settlement.csv", _valid_settlement_csv(), "text/csv"),
        },
    )
    assert resp.status_code == 400
    errs = resp.json()["detail"]["errors"]
    assert any(e["file"] == "ledger" and e["field"] == "vendor_name" and e["row"] == 2 for e in errs)


# 13. Malformed CSV rejected
def test_malformed_csv_rejected():
    records, errors = validate_and_parse_csv(b"", "ledger")
    assert len(errors) > 0


# 14. Optional reference_id/description may be absent
def test_optional_reference_id_and_description_may_be_absent(client):
    minimal_ledger = _make_csv(
        ["ledger_id", "vendor_name", "amount", "txn_date"],
        [["MIN-LED-01", "Vendor Min", "100.0", "2026-01-01"]],
    )
    minimal_settlement = _make_csv(
        ["settlement_id", "vendor_name", "amount", "txn_date"],
        [["MIN-STL-01", "Vendor Min", "99.5", "2026-01-01"]],
    )
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", minimal_ledger, "text/csv"),
            "settlement_file": ("settlement.csv", minimal_settlement, "text/csv"),
        },
    )
    assert resp.status_code == 200


# 15. Valid optional fields are preserved
def test_valid_optional_fields_are_preserved():
    csv_bytes = _make_csv(
        ["ledger_id", "vendor_name", "amount", "txn_date", "reference_id", "description"],
        [["L1", "V1", "10.0", "2026-01-01", "REF-XYZ", "Invoice 123"]],
    )
    records, errors = validate_and_parse_csv(csv_bytes, "ledger")
    assert errors == []
    assert records[0]["reference_id"] == "REF-XYZ"
    assert records[0]["description"] == "Invoice 123"


# 16. Error response identifies file/row/field where applicable
def test_error_response_identifies_file_row_field(client):
    bad_ledger = _make_csv(
        ["ledger_id", "vendor_name", "amount", "txn_date"],
        [
            ["LED-01", "Vendor A", "100.0", "2026-01-01"],
            ["LED-02", "Vendor B", "bad_num", "2026-01-02"],
        ],
    )
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", bad_ledger, "text/csv"),
            "settlement_file": ("settlement.csv", _valid_settlement_csv(), "text/csv"),
        },
    )
    assert resp.status_code == 400
    err = next(e for e in resp.json()["detail"]["errors"] if e["field"] == "amount")
    assert err["file"] == "ledger"
    assert err["row"] == 3
    assert err["field"] == "amount"


# 17. Valid upload reaches the existing process_batch() and creates decisions
def test_valid_upload_reaches_pipeline_and_persists(client, db):
    resp = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", _valid_ledger_csv(), "text/csv"),
            "settlement_file": ("settlement.csv", _valid_settlement_csv(), "text/csv"),
        },
    )
    assert resp.status_code == 200
    batch_id = resp.json()["batch_id"]

    batch_row = db.query(Batch).filter(Batch.id == batch_id).first()
    assert batch_row is not None
    assert batch_row.status == "COMPLETED"

    decisions = db.query(ReconciliationDecision).filter(ReconciliationDecision.batch_id == batch_id).all()
    assert len(decisions) > 0


# 18. Existing POST /batches behavior remains unchanged
def test_existing_post_batches_remains_unchanged(client):
    payload = {
        "ledger_records": [
            {"ledger_id": "T-LED-OLD", "vendor_name": "Old API Vendor", "amount": 100.0, "txn_date": "2026-01-01"}
        ],
        "settlement_records": [
            {"settlement_id": "T-STL-OLD", "vendor_name": "Old API Vendor", "amount": 100.0, "txn_date": "2026-01-01"}
        ],
    }
    resp = client.post("/batches", json=payload)
    assert resp.status_code == 200
    assert "batch_id" in resp.json()
    assert resp.json()["status"] == "COMPLETED"


# 19 & 20. Existing idempotency behavior remains intact for uploads
def test_duplicate_csv_upload_is_idempotent(client, db):
    l_bytes = _valid_ledger_csv()
    s_bytes = _valid_settlement_csv()

    resp1 = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", l_bytes, "text/csv"),
            "settlement_file": ("settlement.csv", s_bytes, "text/csv"),
        },
    )
    assert resp1.status_code == 200
    batch_id_1 = resp1.json()["batch_id"]

    count_batches_1 = db.query(Batch).count()
    count_decisions_1 = db.query(ReconciliationDecision).count()

    # Resubmit identical CSV data
    resp2 = client.post(
        "/batches/upload",
        files={
            "ledger_file": ("ledger.csv", l_bytes, "text/csv"),
            "settlement_file": ("settlement.csv", s_bytes, "text/csv"),
        },
    )
    assert resp2.status_code == 200
    batch_id_2 = resp2.json()["batch_id"]

    count_batches_2 = db.query(Batch).count()
    count_decisions_2 = db.query(ReconciliationDecision).count()

    assert batch_id_1 == batch_id_2
    assert count_batches_1 == count_batches_2
    assert count_decisions_1 == count_decisions_2
