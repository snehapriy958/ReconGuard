import os
os.environ["RECONLENS_TEST_SQLITE"] = "1"

import pytest
from fastapi.testclient import TestClient

from backend.app.db import Base, engine, SessionLocal
from backend.app.pipeline import process_batch


@pytest.fixture()
def db():
    from backend.app.models import batch, source_record, decision, evidence, review, exception, audit  # noqa
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _real_batch(db):
    ledger = [
        {"ledger_id": "T-LED-01", "vendor_name": "Test Vendor Ltd", "amount": 1000.0,
         "txn_date": "2026-01-01", "reference_id": "REF001", "description": "test"},
        {"ledger_id": "T-LED-02", "vendor_name": "Totally Different Co", "amount": 5000.0,
         "txn_date": "2026-01-01", "reference_id": "REFXYZ", "description": "test"},
    ]
    settlement = [
        {"settlement_id": "T-STL-01", "vendor_name": "Test Vendor Ltd", "amount": 999.5,
         "txn_date": "2026-01-01", "reference_id": "REF001", "description": "test"},
        {"settlement_id": "T-STL-02", "vendor_name": "Nothing Alike Inc", "amount": 4980.0,
         "txn_date": "2026-01-02", "reference_id": "", "description": "unrelated"},
    ]
    return process_batch(db, ledger, settlement)


def test_list_batches_endpoint_returns_real_batches(db):
    b1 = _real_batch(db)
    from backend.app.api.main import app
    from backend.app.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    resp = client.get("/batches")
    assert resp.status_code == 200
    ids = [b["batch_id"] for b in resp.json()["batches"]]
    assert b1.id in ids
    app.dependency_overrides.clear()

def test_decision_detail_includes_real_source_records(db):
    b1 = _real_batch(db)
    from backend.app.models.decision import ReconciliationDecision
    decision = db.query(ReconciliationDecision).first()
    from backend.app.api.main import app
    from backend.app.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    resp = client.get(f"/decisions/{decision.id}")
    assert resp.status_code == 200
    payload = resp.json()
    assert "ledger_records" in payload and "settlement_records" in payload
    # every record slot must be real data, never null, for an actual persisted decision
    assert all(r is not None for r in payload["ledger_records"])
    assert all(r is not None for r in payload["settlement_records"])
    assert payload["ledger_records"][0]["vendor_name"]  # real field present, not fabricated
    app.dependency_overrides.clear()

def test_decision_detail_includes_recomputed_full_feature_vector(db):
    b1 = _real_batch(db)
    from backend.app.models.decision import ReconciliationDecision
    decision = db.query(ReconciliationDecision).first()
    from backend.app.api.main import app
    from backend.app.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    resp = client.get(f"/decisions/{decision.id}")
    assert resp.status_code == 200
    payload = resp.json()
    assert "all_features" in payload
    assert payload["all_features"] is not None
    # spot-check a few features that must be present for the evidence
    # breakdown categories (amount, date, vendor, reference)
    for feature in ("abs_amount_diff", "date_diff_days",
                     "vendor_jaro_winkler_similarity", "reference_similarity"):
        assert feature in payload["all_features"]
    # identifier/categorical columns should be stripped — shown elsewhere
    # in the payload already, not duplicated here
    assert "ledger_public_id" not in payload["all_features"]
    app.dependency_overrides.clear()


def test_decision_detail_includes_real_risk_flag_explanations(db):
    b1 = _real_batch(db)
    from backend.app.models.decision import ReconciliationDecision
    # find a decision that actually has risk flags, if this batch produced one
    flagged = db.query(ReconciliationDecision).filter(
        ReconciliationDecision.risk_flags != []
    ).first()
    from backend.app.api.main import app
    from backend.app.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    if flagged is not None:
        resp = client.get(f"/decisions/{flagged.id}")
        payload = resp.json()
        assert set(payload["risk_flag_explanations"].keys()) == set(flagged.risk_flags)
        for explanation in payload["risk_flag_explanations"].values():
            assert isinstance(explanation, str) and len(explanation) > 0
    else:
        # still verify the field exists and is correctly empty for an
        # unflagged decision, rather than skipping silently
        decision = db.query(ReconciliationDecision).first()
        resp = client.get(f"/decisions/{decision.id}")
        assert resp.json()["risk_flag_explanations"] == {}
    app.dependency_overrides.clear()


def test_exceptions_endpoint_includes_relationship_type_and_probability(db):
    b1 = _real_batch(db)
    from backend.app.api.main import app
    from backend.app.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    resp = client.get("/exceptions")
    assert resp.status_code == 200
    exceptions = resp.json()["exceptions"]
    assert len(exceptions) > 0
    for e in exceptions:
        assert e["relationship_type"] is not None
        assert e["calibrated_probability"] is not None
    app.dependency_overrides.clear()
