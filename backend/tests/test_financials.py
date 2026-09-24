"""Unit and integration tests for Phase 3 — Financial Metrics.

Verifies:
- Unique-source-record financial accounting (NEVER accumulate per candidate group)
- Precedence: HIGH_CONFIDENCE_MATCH > NEEDS_REVIEW > LIKELY_NO_MATCH
- 1:1, 1:N (one-to-many), N:1 (many-to-one)
- Zero-candidate source records as exceptions
- Independent invariant: matched + review + exception == total for ledger and settlement
- End-to-end integration with process_batch() and real data regression
"""

import os
os.environ["RECONLENS_TEST_SQLITE"] = "1"

from decimal import Decimal
import pandas as pd
import pytest
from sqlalchemy.orm import Session

from backend.app.db import Base, engine, SessionLocal
from backend.app.financials import FinancialAccumulator, FinancialSummary
from backend.app.pipeline import process_batch
from backend.app.models.batch import Batch


@pytest.fixture()
def db():
    from backend.app.models import batch, source_record, decision, evidence, review, exception, audit  # noqa
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# ---------------- Unit Tests for FinancialAccumulator ----------------

def test_a_basic_one_to_one_matching():
    ledger = [{"ledger_id": "L1", "amount": 100.0}]
    settlement = [{"settlement_id": "S1", "amount": 100.0}]

    acc = FinancialAccumulator(ledger, settlement)
    acc.record_candidate_outcome(["L1"], ["S1"], "HIGH_CONFIDENCE_MATCH")
    summary = acc.compute_summary()

    # Ledger
    assert summary.ledger.total_amount == 100.0
    assert summary.ledger.matched_amount == 100.0
    assert summary.ledger.review_amount == 0.0
    assert summary.ledger.exception_amount == 0.0
    assert summary.ledger.matched_rate == 1.0
    assert summary.ledger.review_rate == 0.0
    assert summary.ledger.exception_rate == 0.0

    # Settlement
    assert summary.settlement.total_amount == 100.0
    assert summary.settlement.matched_amount == 100.0
    assert summary.settlement.review_amount == 0.0
    assert summary.settlement.exception_amount == 0.0
    assert summary.settlement.matched_rate == 1.0
    assert summary.settlement.review_rate == 0.0
    assert summary.settlement.exception_rate == 0.0


def test_b_unmatched_ledger():
    ledger = [{"ledger_id": "L1", "amount": 100.0}]
    settlement = []

    acc = FinancialAccumulator(ledger, settlement)
    summary = acc.compute_summary()

    assert summary.ledger.total_amount == 100.0
    assert summary.ledger.matched_amount == 0.0
    assert summary.ledger.review_amount == 0.0
    assert summary.ledger.exception_amount == 100.0
    assert summary.ledger.matched_rate == 0.0
    assert summary.ledger.review_rate == 0.0
    assert summary.ledger.exception_rate == 1.0


def test_c_unmatched_settlement():
    ledger = []
    settlement = [{"settlement_id": "S1", "amount": 100.0}]

    acc = FinancialAccumulator(ledger, settlement)
    summary = acc.compute_summary()

    assert summary.settlement.total_amount == 100.0
    assert summary.settlement.matched_amount == 0.0
    assert summary.settlement.review_amount == 0.0
    assert summary.settlement.exception_amount == 100.0
    assert summary.settlement.matched_rate == 0.0
    assert summary.settlement.review_rate == 0.0
    assert summary.settlement.exception_rate == 1.0


def test_d_needs_review_record():
    ledger = [{"ledger_id": "L1", "amount": 250.75}]
    settlement = [{"settlement_id": "S1", "amount": 250.75}]

    acc = FinancialAccumulator(ledger, settlement)
    acc.record_candidate_outcome(["L1"], ["S1"], "NEEDS_REVIEW")
    summary = acc.compute_summary()

    assert summary.ledger.total_amount == 250.75
    assert summary.ledger.matched_amount == 0.0
    assert summary.ledger.review_amount == 250.75
    assert summary.ledger.exception_amount == 0.0
    assert summary.ledger.review_rate == 1.0

    assert summary.settlement.total_amount == 250.75
    assert summary.settlement.matched_amount == 0.0
    assert summary.settlement.review_amount == 250.75
    assert summary.settlement.exception_amount == 0.0
    assert summary.settlement.review_rate == 1.0


def test_e_repeated_candidate_groups_not_double_counted():
    """CRITICAL TEST: Verify a record participating in 4 groups is counted exactly once."""
    ledger = [{"ledger_id": "L1", "amount": 100.0}]
    settlement = [
        {"settlement_id": "S1", "amount": 25.0},
        {"settlement_id": "S2", "amount": 25.0},
        {"settlement_id": "S3", "amount": 25.0},
        {"settlement_id": "S4", "amount": 25.0},
    ]

    acc = FinancialAccumulator(ledger, settlement)
    # L1 appears in 4 different candidate groups
    acc.record_candidate_outcome(["L1"], ["S1"], "NEEDS_REVIEW")
    acc.record_candidate_outcome(["L1"], ["S2"], "NEEDS_REVIEW")
    acc.record_candidate_outcome(["L1"], ["S3"], "NEEDS_REVIEW")
    acc.record_candidate_outcome(["L1"], ["S4"], "HIGH_CONFIDENCE_MATCH")

    summary = acc.compute_summary()

    # Total must be 100.0, NOT 400.0
    assert summary.ledger.total_amount == 100.0
    assert summary.ledger.matched_amount == 100.0
    assert summary.ledger.review_amount == 0.0
    assert summary.ledger.exception_amount == 0.0

    # Settlement records also counted exactly once: 4 * 25 = 100.0
    assert summary.settlement.total_amount == 100.0
    # S1, S2, S3 had NEEDS_REVIEW (75.0), S4 had HIGH_CONFIDENCE_MATCH (25.0)
    assert summary.settlement.matched_amount == 25.0
    assert summary.settlement.review_amount == 75.0
    assert summary.settlement.exception_amount == 0.0


def test_f_one_to_many_matching():
    ledger = [{"ledger_id": "L1", "amount": 300.0}]
    settlement = [
        {"settlement_id": "S1", "amount": 100.0},
        {"settlement_id": "S2", "amount": 200.0},
    ]

    acc = FinancialAccumulator(ledger, settlement)
    acc.record_candidate_outcome(["L1"], ["S1", "S2"], "HIGH_CONFIDENCE_MATCH")
    summary = acc.compute_summary()

    assert summary.ledger.total_amount == 300.0
    assert summary.ledger.matched_amount == 300.0

    assert summary.settlement.total_amount == 300.0
    assert summary.settlement.matched_amount == 300.0


def test_g_many_to_one_matching():
    ledger = [
        {"ledger_id": "L1", "amount": 100.0},
        {"ledger_id": "L2", "amount": 200.0},
    ]
    settlement = [{"settlement_id": "S1", "amount": 300.0}]

    acc = FinancialAccumulator(ledger, settlement)
    acc.record_candidate_outcome(["L1", "L2"], ["S1"], "HIGH_CONFIDENCE_MATCH")
    summary = acc.compute_summary()

    assert summary.ledger.total_amount == 300.0
    assert summary.ledger.matched_amount == 300.0

    assert summary.settlement.total_amount == 300.0
    assert summary.settlement.matched_amount == 300.0


def test_h_mixed_outcomes_enter_distinct_buckets():
    ledger = [
        {"ledger_id": "L1", "amount": 500.0},
        {"ledger_id": "L2", "amount": 300.0},
        {"ledger_id": "L3", "amount": 200.0},
    ]
    settlement = [
        {"settlement_id": "S1", "amount": 500.0},
        {"settlement_id": "S2", "amount": 300.0},
        {"settlement_id": "S3", "amount": 200.0},
    ]

    acc = FinancialAccumulator(ledger, settlement)
    acc.record_candidate_outcome(["L1"], ["S1"], "HIGH_CONFIDENCE_MATCH")
    acc.record_candidate_outcome(["L2"], ["S2"], "NEEDS_REVIEW")
    acc.record_candidate_outcome(["L3"], ["S3"], "LIKELY_NO_MATCH")

    summary = acc.compute_summary()

    assert summary.ledger.total_amount == 1000.0
    assert summary.ledger.matched_amount == 500.0
    assert summary.ledger.review_amount == 300.0
    assert summary.ledger.exception_amount == 200.0

    assert summary.settlement.total_amount == 1000.0
    assert summary.settlement.matched_amount == 500.0
    assert summary.settlement.review_amount == 300.0
    assert summary.settlement.exception_amount == 200.0


def test_i_bucket_overlap_invariant_holds():
    ledger = [
        {"ledger_id": "L1", "amount": 123.45},
        {"ledger_id": "L2", "amount": 67.89},
        {"ledger_id": "L3", "amount": 210.11},
    ]
    settlement = [
        {"settlement_id": "S1", "amount": 123.45},
        {"settlement_id": "S2", "amount": 150.00},
        {"settlement_id": "S3", "amount": 128.00},
    ]

    acc = FinancialAccumulator(ledger, settlement)
    acc.record_candidate_outcome(["L1"], ["S1"], "HIGH_CONFIDENCE_MATCH")
    acc.record_candidate_outcome(["L2"], ["S2"], "NEEDS_REVIEW")
    # L3 and S3 have no candidates (zero candidate)

    summary = acc.compute_summary()

    # Invariant: matched + review + exception == total
    assert round(summary.ledger.matched_amount + summary.ledger.review_amount + summary.ledger.exception_amount, 2) == summary.ledger.total_amount
    assert round(summary.settlement.matched_amount + summary.settlement.review_amount + summary.settlement.exception_amount, 2) == summary.settlement.total_amount


def test_j_records_with_no_candidates_appear_in_exception():
    ledger = [
        {"ledger_id": "L1", "amount": 100.0},
        {"ledger_id": "L2_NO_CANDIDATE", "amount": 450.0},
    ]
    settlement = [
        {"settlement_id": "S1", "amount": 100.0},
        {"settlement_id": "S2_NO_CANDIDATE", "amount": 350.0},
    ]

    acc = FinancialAccumulator(ledger, settlement)
    acc.record_candidate_outcome(["L1"], ["S1"], "HIGH_CONFIDENCE_MATCH")
    summary = acc.compute_summary()

    assert summary.ledger.total_amount == 550.0
    assert summary.ledger.matched_amount == 100.0
    assert summary.ledger.review_amount == 0.0
    assert summary.ledger.exception_amount == 450.0

    assert summary.settlement.total_amount == 450.0
    assert summary.settlement.matched_amount == 100.0
    assert summary.settlement.review_amount == 0.0
    assert summary.settlement.exception_amount == 350.0


def test_k_outcome_precedence_strongest_wins():
    """L1 appears in groups with LIKELY_NO_MATCH, NEEDS_REVIEW, and HIGH_CONFIDENCE_MATCH.
    Expected: L1 is counted once as MATCHED."""
    ledger = [{"ledger_id": "L1", "amount": 500.0}]
    settlement = [
        {"settlement_id": "S1", "amount": 500.0},
        {"settlement_id": "S2", "amount": 500.0},
        {"settlement_id": "S3", "amount": 500.0},
    ]

    acc = FinancialAccumulator(ledger, settlement)
    acc.record_candidate_outcome(["L1"], ["S1"], "LIKELY_NO_MATCH")
    acc.record_candidate_outcome(["L1"], ["S2"], "NEEDS_REVIEW")
    acc.record_candidate_outcome(["L1"], ["S3"], "HIGH_CONFIDENCE_MATCH")

    summary = acc.compute_summary()

    assert summary.ledger.total_amount == 500.0
    assert summary.ledger.matched_amount == 500.0
    assert summary.ledger.review_amount == 0.0
    assert summary.ledger.exception_amount == 0.0


# ---------------- Integration & Pipeline Tests ----------------

def test_pipeline_includes_financials_in_batch_summary(db: Session):
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

    batch = process_batch(db, ledger, settlement)
    assert batch.summary is not None
    assert "financials" in batch.summary

    fin = batch.summary["financials"]
    assert "ledger" in fin and "settlement" in fin

    # Check ledger financials
    l_fin = fin["ledger"]
    assert l_fin["total_amount"] == 6000.0
    assert round(l_fin["matched_amount"] + l_fin["review_amount"] + l_fin["exception_amount"], 2) == l_fin["total_amount"]
    assert round(l_fin["matched_rate"] + l_fin["review_rate"] + l_fin["exception_rate"], 4) == pytest.approx(1.0, abs=1e-3)

    # Check settlement financials
    s_fin = fin["settlement"]
    assert s_fin["total_amount"] == 5979.5
    assert round(s_fin["matched_amount"] + s_fin["review_amount"] + s_fin["exception_amount"], 2) == s_fin["total_amount"]
    assert round(s_fin["matched_rate"] + s_fin["review_rate"] + s_fin["exception_rate"], 4) == pytest.approx(1.0, abs=1e-3)


def test_real_data_sample_financial_invariants(db: Session):
    """Test 11: Real data regression test using slice of repository datasets."""
    ledger_path = "data/raw/ledger.csv"
    settlement_path = "data/raw/settlement.csv"

    if not os.path.exists(ledger_path) or not os.path.exists(settlement_path):
        pytest.skip("Raw datasets not available in environment")

    # Load 30 rows from each to run a realistic end-to-end reconciliation run
    ledger_df = pd.read_csv(ledger_path).head(30)
    settlement_df = pd.read_csv(settlement_path).head(30)

    ledger_records = ledger_df.to_dict(orient="records")
    settlement_records = settlement_df.to_dict(orient="records")

    expected_ledger_total = round(float(sum(Decimal(str(r["amount"])) for r in ledger_records)), 2)
    expected_settlement_total = round(float(sum(Decimal(str(r["amount"])) for r in settlement_records)), 2)

    batch = process_batch(db, ledger_records, settlement_records)

    assert batch.status == "COMPLETED"
    fin = batch.summary["financials"]

    # 1. ledger financial total equals sum of unique ledger records
    assert fin["ledger"]["total_amount"] == expected_ledger_total

    # 2. settlement financial total equals sum of unique settlement records
    assert fin["settlement"]["total_amount"] == expected_settlement_total

    # 3. ledger matched + review + exception == ledger total
    assert round(fin["ledger"]["matched_amount"] + fin["ledger"]["review_amount"] + fin["ledger"]["exception_amount"], 2) == fin["ledger"]["total_amount"]

    # 4. settlement matched + review + exception == settlement total
    assert round(fin["settlement"]["matched_amount"] + fin["settlement"]["review_amount"] + fin["settlement"]["exception_amount"], 2) == fin["settlement"]["total_amount"]
