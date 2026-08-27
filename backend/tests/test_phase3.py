import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent.parent


# ---------------- candidate generation V1/V2 ----------------

def test_v1_still_achieves_full_one_to_one_recall():
    from ml.candidate_generation.blocking_v1 import generate_candidates
    ledger_df = pd.read_csv(ROOT / "data/raw/ledger.csv")
    settlement_df = pd.read_csv(ROOT / "data/raw/settlement.csv")
    match_map = json.load(open(ROOT / "data/raw/_hidden_match_map.json"))
    v1_pairs = set(generate_candidates(ledger_df, settlement_df))
    one_to_one = [e for e in match_map if len(e["ledger_ids"]) == 1 and len(e["settlement_ids"]) == 1]
    misses = [e for e in one_to_one if (e["ledger_ids"][0], e["settlement_ids"][0]) not in v1_pairs]
    assert len(misses) == 0, f"V1 should recover 100% of one-to-one matches; missed {len(misses)}"


def test_v2_recovers_split_settlements():
    from ml.candidate_generation.blocking_v2 import generate_structural_candidates
    ledger_df = pd.read_csv(ROOT / "data/raw/ledger.csv")
    settlement_df = pd.read_csv(ROOT / "data/raw/settlement.csv")
    match_map = json.load(open(ROOT / "data/raw/_hidden_match_map.json"))
    structural = generate_structural_candidates(ledger_df, settlement_df)
    group_set = {(frozenset(c.ledger_ids), frozenset(c.settlement_ids)) for c in structural}
    one_to_many = [e for e in match_map if len(e["ledger_ids"]) == 1 and len(e["settlement_ids"]) > 1]
    for e in one_to_many:
        key = (frozenset(e["ledger_ids"]), frozenset(e["settlement_ids"]))
        assert key in group_set, f"V2 failed to recover a true split settlement: {e}"


def test_v2_recovers_batched_settlements():
    from ml.candidate_generation.blocking_v2 import generate_structural_candidates
    ledger_df = pd.read_csv(ROOT / "data/raw/ledger.csv")
    settlement_df = pd.read_csv(ROOT / "data/raw/settlement.csv")
    match_map = json.load(open(ROOT / "data/raw/_hidden_match_map.json"))
    structural = generate_structural_candidates(ledger_df, settlement_df)
    group_set = {(frozenset(c.ledger_ids), frozenset(c.settlement_ids)) for c in structural}
    many_to_one = [e for e in match_map if len(e["ledger_ids"]) > 1 and len(e["settlement_ids"]) == 1]
    for e in many_to_one:
        key = (frozenset(e["ledger_ids"]), frozenset(e["settlement_ids"]))
        assert key in group_set, f"V2 failed to recover a true batched settlement: {e}"


def test_batch_members_are_temporally_close():
    """Regression test for the Phase 1 bug: batch members must be generated
    within MAX_BATCH_DATE_SPAN_DAYS of each other, not scattered arbitrarily.
    """
    match_map = json.load(open(ROOT / "data/raw/_hidden_match_map.json"))
    ledger_df = pd.read_csv(ROOT / "data/raw/ledger.csv").set_index("ledger_id")
    many_to_one = [e for e in match_map if len(e["ledger_ids"]) > 1]
    assert len(many_to_one) > 0, "expected at least one many-to-one group in this dataset"
    for e in many_to_one:
        dates = pd.to_datetime([ledger_df.loc[lid, "txn_date"] for lid in e["ledger_ids"]])
        span_days = (dates.max() - dates.min()).days
        assert span_days <= 3, f"batch {e['gt_txn_id']} spans {span_days} days — regression of the Phase 1 date-clustering fix"


# ---------------- label assembly / leakage ----------------

def test_labeled_dataset_has_no_cross_split_ground_truth():
    labeled = pd.read_parquet(ROOT / "data/processed/labeled_candidates.parquet")
    ledger_truth = pd.read_csv(ROOT / "data/raw/_hidden_ledger_truth.csv").set_index("ledger_id")
    settlement_truth = pd.read_csv(ROOT / "data/raw/_hidden_settlement_truth.csv").set_index("settlement_id")
    for _, row in labeled.iterrows():
        l_split = ledger_truth.loc[row["ledger_public_id"], "_split"]
        s_split = settlement_truth.loc[row["settlement_public_id"], "_split"]
        assert l_split == s_split == row["split"], (
            f"split mismatch for {row['ledger_public_id']}/{row['settlement_public_id']}: "
            f"ledger={l_split} settlement={s_split} assigned={row['split']}"
        )

def test_labeled_dataset_has_no_hidden_columns():
    labeled = pd.read_parquet(ROOT / "data/processed/labeled_candidates.parquet")
    forbidden = [c for c in labeled.columns if "gt_txn" in c.lower() or "ground_truth" in c.lower()]
    assert not forbidden, f"hidden columns leaked into labeled dataset: {forbidden}"

def test_no_duplicate_candidate_rows_in_labeled_dataset():
    labeled = pd.read_parquet(ROOT / "data/processed/labeled_candidates.parquet")
    dup = labeled.duplicated(subset=["ledger_public_id", "settlement_public_id"])
    assert not dup.any()

def test_class_distribution_reported_and_nontrivial():
    labeled = pd.read_parquet(ROOT / "data/processed/labeled_candidates.parquet")
    for split in ["train", "val", "test"]:
        sub = labeled[labeled["split"] == split]
        assert sub["label"].nunique() == 2, f"{split} split should contain both classes"


# ---------------- model ----------------

def test_model_trains_and_produces_probabilities():
    from ml.training.train_baseline import load_splits, fit_scaler_and_model, evaluate
    train_df, val_df, test_df, feature_cols = load_splits()
    model, scaler = fit_scaler_and_model(train_df, feature_cols, class_weight="balanced")
    X_val = scaler.transform(val_df[feature_cols].to_numpy(dtype=float))
    proba = model.predict_proba(X_val)[:, 1]
    assert proba.shape[0] == len(val_df)
    assert np.all((proba >= 0) & (proba <= 1)), "predict_proba output must be a valid probability"

def test_model_expects_documented_feature_count():
    from ml.training.train_baseline import load_splits
    _, _, _, feature_cols = load_splits()
    assert len(feature_cols) == 22, f"expected 22 features, got {len(feature_cols)}: {feature_cols}"

def test_model_predictions_reproducible_with_fixed_seed():
    from ml.training.train_baseline import load_splits, fit_scaler_and_model
    train_df, val_df, _, feature_cols = load_splits()
    model1, scaler1 = fit_scaler_and_model(train_df, feature_cols, class_weight="balanced")
    model2, scaler2 = fit_scaler_and_model(train_df, feature_cols, class_weight="balanced")
    X_val = scaler1.transform(val_df[feature_cols].to_numpy(dtype=float))
    p1 = model1.predict_proba(X_val)[:, 1]
    p2 = model2.predict_proba(X_val)[:, 1]
    assert np.allclose(p1, p2), "same seed/config should produce identical predictions"


# ---------------- evaluation metrics correctness ----------------

def test_metrics_calculation_matches_manual_confusion_matrix():
    from sklearn.metrics import precision_score, recall_score
    y_true = np.array([1, 1, 1, 0, 0])
    y_pred = np.array([1, 1, 0, 0, 1])
    # TP=2, FN=1, FP=1, TN=1 -> precision=2/3, recall=2/3
    assert precision_score(y_true, y_pred) == pytest.approx(2 / 3)
    assert recall_score(y_true, y_pred) == pytest.approx(2 / 3)

def test_test_set_not_used_for_threshold_tuning():
    """Static check: train_baseline.py's threshold_sweep call must run against
    val_df, never test_df — a regression here would mean thresholds are being
    silently tuned against the set reserved for final reporting only.
    """
    import inspect
    import ml.training.train_baseline as tb
    source = inspect.getsource(tb.main)
    assert "threshold_sweep(chosen_model, chosen_scaler, val_df" in source
    assert "threshold_sweep(chosen_model, chosen_scaler, test_df" not in source
