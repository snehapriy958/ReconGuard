"""
ReconGuard — Backend tests for Phase 5 Demo Scenarios.

Verifies:
- Registry contains exactly four intended scenarios
- Every registered dataset has valid files on disk with valid schemas
- Globally unique IDs across all demo scenarios
- GET /demo-datasets endpoint metadata and record counts
- POST /demo-datasets/{dataset_id}/process executes through the real pipeline
- Idempotency is preserved on repeated submission
- Financial metrics are computed for each scenario
- Structural matching behavior in structural-splits
- 404 on unknown scenario IDs and prevention of path traversal
"""

import os
os.environ["RECONLENS_TEST_SQLITE"] = "1"

import pytest
from fastapi.testclient import TestClient

from backend.app.db import Base, engine, SessionLocal, get_db
from backend.app.api.main import app
from backend.app.demo_datasets import (
    DEMO_DATASETS,
    list_demo_datasets,
    get_demo_dataset_metadata,
    get_demo_dataset_records,
    get_demo_dataset_file_path,
)
from backend.app.models.batch import Batch
from backend.app.models.source_record import SourceRecord
from backend.app.models.decision import ReconciliationDecision


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


# ---------------- Registry & File Integrity Tests ----------------

def test_a_registry_contains_four_scenarios():
    assert len(DEMO_DATASETS) == 4
    expected_ids = {"clean-settlement", "structural-splits", "discrepancies-exceptions", "balanced-portfolio"}
    assert set(DEMO_DATASETS.keys()) == expected_ids


def test_b_every_registered_dataset_has_valid_files():
    for dataset_id in DEMO_DATASETS:
        l_path = get_demo_dataset_file_path(dataset_id, "ledger")
        s_path = get_demo_dataset_file_path(dataset_id, "settlement")
        assert l_path.is_file(), f"Missing ledger file for {dataset_id}"
        assert s_path.is_file(), f"Missing settlement file for {dataset_id}"


def test_c_csv_schemas_are_strictly_valid():
    for dataset_id in DEMO_DATASETS:
        l_records, s_records = get_demo_dataset_records(dataset_id)
        assert len(l_records) > 0
        assert len(s_records) > 0

        # Validate ledger fields
        for r in l_records:
            assert "ledger_id" in r and r["ledger_id"]
            assert "vendor_name" in r and r["vendor_name"]
            assert "amount" in r and isinstance(r["amount"], float)
            assert "txn_date" in r and len(r["txn_date"]) == 10  # YYYY-MM-DD

        # Validate settlement fields
        for r in s_records:
            assert "settlement_id" in r and r["settlement_id"]
            assert "vendor_name" in r and r["vendor_name"]
            assert "amount" in r and isinstance(r["amount"], float)
            assert "txn_date" in r and len(r["txn_date"]) == 10


def test_d_ids_are_globally_unique_across_all_demo_scenarios():
    all_ledger_ids = set()
    all_settlement_ids = set()

    for dataset_id in DEMO_DATASETS:
        l_records, s_records = get_demo_dataset_records(dataset_id)
        for r in l_records:
            lid = r["ledger_id"]
            assert lid not in all_ledger_ids, f"Duplicate ledger_id '{lid}' found in scenario {dataset_id}"
            all_ledger_ids.add(lid)

        for r in s_records:
            sid = r["settlement_id"]
            assert sid not in all_settlement_ids, f"Duplicate settlement_id '{sid}' found in scenario {dataset_id}"
            all_settlement_ids.add(sid)


def test_e_get_demo_datasets_endpoint_returns_metadata(client):
    res = client.get("/demo-datasets")
    assert res.status_code == 200
    data = res.json()
    assert "datasets" in data
    assert len(data["datasets"]) == 4

    returned_ids = {d["id"] for d in data["datasets"]}
    assert returned_ids == {"clean-settlement", "structural-splits", "discrepancies-exceptions", "balanced-portfolio"}


def test_f_metadata_matches_actual_record_counts():
    for dataset_id, meta in DEMO_DATASETS.items():
        l_records, s_records = get_demo_dataset_records(dataset_id)
        assert len(l_records) == meta.ledger_record_count, f"Mismatch in {dataset_id} ledger count"
        assert len(s_records) == meta.settlement_record_count, f"Mismatch in {dataset_id} settlement count"


# ---------------- Execution & Pipeline Integration Tests ----------------

def test_g_process_clean_settlement_scenario(client, db):
    res = client.post("/demo-datasets/clean-settlement/process")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "COMPLETED"
    assert "batch_id" in body
    summary = body["summary"]
    assert summary is not None
    assert summary["high_confidence_matches"] >= 15
    assert "financials" in summary


def test_h_process_structural_splits_scenario(client, db):
    res = client.post("/demo-datasets/structural-splits/process")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "COMPLETED"
    summary = body["summary"]
    assert summary is not None
    # Structural matches must be present
    assert summary.get("structural_matches", 0) > 0
    assert summary.get("one_to_many_matches", 0) > 0 or summary.get("many_to_one_matches", 0) > 0


def test_i_process_discrepancies_exceptions_scenario(client, db):
    res = client.post("/demo-datasets/discrepancies-exceptions/process")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "COMPLETED"
    summary = body["summary"]
    assert summary is not None
    # Exceptions and/or review items must exist
    assert summary["exceptions"] > 0
    assert summary["financials"]["ledger"]["exception_amount"] > 0


def test_j_process_balanced_portfolio_scenario(client, db):
    res = client.post("/demo-datasets/balanced-portfolio/process")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "COMPLETED"
    summary = body["summary"]
    assert summary is not None
    assert summary["candidates_generated"] > 50
    assert summary["high_confidence_matches"] > 0
    assert summary["exceptions"] > 0


def test_k_unknown_dataset_id_returns_404(client):
    res = client.post("/demo-datasets/non-existent-scenario/process")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_l_arbitrary_path_traversal_is_blocked(client):
    traversal_attempts = [
        "../../data/raw",
        "../clean-settlement",
        "..%2F..%2Fdata",
        "etc/passwd",
    ]
    for attempt in traversal_attempts:
        res = client.post(f"/demo-datasets/{attempt}/process")
        assert res.status_code in (404, 422)


def test_m_process_endpoint_persists_source_records_and_decisions(client, db):
    res = client.post("/demo-datasets/clean-settlement/process")
    assert res.status_code == 200
    batch_id = res.json()["batch_id"]

    db_batch = db.query(Batch).filter(Batch.id == batch_id).first()
    assert db_batch is not None
    assert db_batch.status == "COMPLETED"

    # Confirm SourceRecord rows were persisted
    records_count = db.query(SourceRecord).filter(SourceRecord.batch_id == batch_id).count()
    assert records_count == 40  # 20 ledger + 20 settlement

    # Confirm ReconciliationDecision rows were persisted
    decisions_count = db.query(ReconciliationDecision).filter(ReconciliationDecision.batch_id == batch_id).count()
    assert decisions_count > 0


def test_n_idempotency_preserved_on_repeated_submission(client, db):
    res1 = client.post("/demo-datasets/clean-settlement/process")
    assert res1.status_code == 200
    batch_id_1 = res1.json()["batch_id"]

    # Post same scenario again
    res2 = client.post("/demo-datasets/clean-settlement/process")
    assert res2.status_code == 200
    batch_id_2 = res2.json()["batch_id"]

    # Must return identical existing batch
    assert batch_id_1 == batch_id_2

    # Total batch count in database should be 1
    total_batches = db.query(Batch).count()
    assert total_batches == 1


def test_o_financial_summary_invariants_hold_in_demo_batch(client, db):
    res = client.post("/demo-datasets/balanced-portfolio/process")
    assert res.status_code == 200
    fin = res.json()["summary"]["financials"]

    l_fin = fin["ledger"]
    s_fin = fin["settlement"]

    assert round(l_fin["matched_amount"] + l_fin["review_amount"] + l_fin["exception_amount"], 2) == l_fin["total_amount"]
    assert round(s_fin["matched_amount"] + s_fin["review_amount"] + s_fin["exception_amount"], 2) == s_fin["total_amount"]


def test_p_structural_scenario_produces_structural_matches(client, db):
    res = client.post("/demo-datasets/structural-splits/process")
    assert res.status_code == 200
    summary = res.json()["summary"]

    assert summary.get("structural_matches", 0) > 0
    batch_id = res.json()["batch_id"]

    decisions = db.query(ReconciliationDecision).filter(ReconciliationDecision.batch_id == batch_id).all()
    relationship_types = {d.relationship_type for d in decisions}
    assert "one_to_many" in relationship_types or "many_to_one" in relationship_types


def test_q_demo_file_download_endpoint(client):
    res_l = client.get("/demo-datasets/clean-settlement/files/ledger")
    assert res_l.status_code == 200
    assert "text/csv" in res_l.headers.get("content-type", "")
    assert "CLN-LED-001" in res_l.text

    res_s = client.get("/demo-datasets/clean-settlement/files/settlement")
    assert res_s.status_code == 200
    assert "CLN-STL-001" in res_s.text

    # Invalid file type
    res_bad = client.get("/demo-datasets/clean-settlement/files/invalid_type")
    assert res_bad.status_code == 404
