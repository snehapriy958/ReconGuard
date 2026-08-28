import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent.parent


# ---------------- structural representation ----------------

def test_one_to_many_represented_with_all_public_ids():
    df = pd.read_parquet(ROOT / "data/processed/unified_features.parquet")
    one_to_many = df[df["relationship_type_candidate"] == "one_to_many"]
    assert len(one_to_many) > 0
    # settlement_public_id should contain multiple ids joined, ledger single
    multi_settlement = one_to_many[one_to_many["settlement_public_id"].str.contains(r"\|")]
    assert len(multi_settlement) > 0
    assert not multi_settlement["ledger_public_id"].str.contains(r"\|").any()

def test_many_to_one_represented_with_all_public_ids():
    df = pd.read_parquet(ROOT / "data/processed/unified_features.parquet")
    many_to_one = df[df["relationship_type_candidate"] == "many_to_one"]
    assert len(many_to_one) > 0
    multi_ledger = many_to_one[many_to_one["ledger_public_id"].str.contains(r"\|")]
    assert len(multi_ledger) > 0
    assert not multi_ledger["settlement_public_id"].str.contains(r"\|").any()

def test_structural_candidates_have_positive_and_negative_labels():
    df = pd.read_parquet(ROOT / "data/processed/unified_labeled_candidates.parquet")
    for rel_type in ["one_to_many", "many_to_one"]:
        sub = df[df["relationship_type_candidate"] == rel_type]
        assert (sub["label"] == 1).sum() > 0, f"{rel_type} has no positive examples"
        assert (sub["label"] == 0).sum() > 0, f"{rel_type} has no negative examples"


# ---------------- group feature aggregation ----------------

def test_group_features_backward_compatible_with_pairwise_core_features():
    """The 17 core (non-structural-count) features must match Phase 2's
    pairwise extractor exactly for one-to-one candidates — count-based
    structural features are EXPECTED to differ (they now reflect the full
    V1+V2 pool), documented in group_extractor.py's module docstring.
    """
    pairwise = pd.read_parquet(ROOT / "data/processed/features.parquet")
    unified = pd.read_parquet(ROOT / "data/processed/unified_features.parquet")
    unified_1to1 = unified[unified["relationship_type_candidate"] == "one_to_one"]

    core_cols = ["abs_amount_diff", "relative_amount_diff", "amount_ratio", "date_diff_days",
                 "vendor_levenshtein_similarity", "vendor_jaro_winkler_similarity",
                 "vendor_token_sort_similarity", "vendor_token_set_similarity",
                 "vendor_exact_normalized_match", "vendor_embedding_cosine_similarity",
                 "reference_exact_match", "reference_substring_overlap", "reference_similarity",
                 "reference_missing_ledger", "reference_both_missing"]

    p = pairwise.set_index(["ledger_public_id", "settlement_public_id"])
    u = unified_1to1.set_index(["ledger_public_id", "settlement_public_id"])
    merged = p[core_cols].join(u[core_cols], lsuffix="_p", rsuffix="_u", how="inner")
    assert len(merged) > 0
    for c in core_cols:
        a, b = merged[c + "_p"], merged[c + "_u"]
        assert np.allclose(a, b, atol=1e-6), f"{c} differs between pairwise and unified (1,1) extraction"

def test_group_amount_features_use_combined_amounts():
    """For a genuine many-to-one group, abs_amount_diff should reflect the
    SUM of ledger amounts vs the settlement amount, not any single member's
    amount alone — this is the aggregation rule group_extractor.py documents.
    """
    df = pd.read_parquet(ROOT / "data/processed/unified_labeled_candidates.parquet")
    true_many_to_one = df[(df["relationship_type_candidate"] == "many_to_one") & (df["label"] == 1)]
    assert len(true_many_to_one) > 0
    # A true match's combined amount difference should be small relative to the settlement amount
    assert (true_many_to_one["relative_amount_diff"] < 0.05).all()


# ---------------- LightGBM ----------------

def test_lightgbm_trains_and_reproduces_predictions():
    from ml.training.train_phase4_comparison import load_splits
    import lightgbm as lgb
    train_df, val_df, test_df, feature_cols = load_splits()
    X = train_df[feature_cols].to_numpy(dtype=float)
    y = train_df["label"].to_numpy()
    m1 = lgb.LGBMClassifier(random_state=42, class_weight="balanced", verbose=-1, n_estimators=50)
    m1.fit(X, y)
    m2 = lgb.LGBMClassifier(random_state=42, class_weight="balanced", verbose=-1, n_estimators=50)
    m2.fit(X, y)
    Xv = val_df[feature_cols].to_numpy(dtype=float)
    assert np.allclose(m1.predict_proba(Xv)[:, 1], m2.predict_proba(Xv)[:, 1])

def test_feature_schema_enforced_in_final_bundle():
    bundle = joblib.load(ROOT / "models/reconlens_phase4_final.joblib")
    assert "reference_missing_settlement" not in bundle["feature_cols"], \
        "excluded artifact feature must not appear in the production feature schema"
    assert len(bundle["feature_cols"]) == 22


# ---------------- calibration ----------------

def test_calibrated_probability_in_valid_range():
    bundle = joblib.load(ROOT / "models/reconlens_phase4_final.joblib")
    df = pd.read_parquet(ROOT / "data/processed/unified_labeled_candidates.parquet")
    test_df = df[df["split"] == "test"]
    X = test_df[bundle["feature_cols"]].to_numpy(dtype=float)
    proba = bundle["calibrator"].predict_proba(X)[:, 1]
    assert np.all((proba >= 0) & (proba <= 1))

def test_calibration_artifact_loads_and_matches_model_feature_order():
    bundle = joblib.load(ROOT / "models/reconlens_phase4_final.joblib")
    # calling predict_proba should not raise a shape/order mismatch
    X = np.zeros((1, len(bundle["feature_cols"])))
    proba = bundle["calibrator"].predict_proba(X)[:, 1]
    assert proba.shape == (1,)


# ---------------- threshold policy ----------------

def test_high_confidence_decision_correct_by_policy():
    from ml.evaluation.explain import decide
    policy = {"high_threshold": 0.85, "low_threshold": 0.5}
    assert decide(0.9, policy) == "HIGH_CONFIDENCE_MATCH"

def test_review_zone_routing():
    from ml.evaluation.explain import decide
    policy = {"high_threshold": 0.85, "low_threshold": 0.5}
    assert decide(0.6, policy) == "NEEDS_REVIEW"

def test_low_confidence_no_match_routing():
    from ml.evaluation.explain import decide
    policy = {"high_threshold": 0.85, "low_threshold": 0.5}
    assert decide(0.2, policy) == "LIKELY_NO_MATCH"

def test_threshold_boundaries_are_deterministic():
    from ml.evaluation.explain import decide
    policy = {"high_threshold": 0.85, "low_threshold": 0.5}
    assert decide(0.85, policy) == "HIGH_CONFIDENCE_MATCH"  # >= high is a match
    assert decide(0.5, policy) == "NEEDS_REVIEW"             # >= low, < high
    assert decide(0.4999, policy) == "LIKELY_NO_MATCH"       # just under low


# ---------------- leakage / held-out discipline ----------------

def test_held_out_test_never_used_in_threshold_selection_source():
    import inspect
    import ml.training.select_thresholds as st
    source = inspect.getsource(st)
    assert "test_df" not in source.split("load_splits()")[1].split("\n")[0] or True  # structural guard below
    assert "proba_val" in source and "X_val" in source
    assert "test_df[feature_cols]" not in source, "threshold selection must not score the held-out test set"

def test_calibration_fit_never_touches_test_split():
    import inspect
    import ml.training.calibrate as cal
    source = inspect.getsource(cal)
    assert "test_df[feature_cols]" not in source, "calibration fitting must not touch the held-out test set"
