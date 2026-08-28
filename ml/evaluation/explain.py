"""
ReconLens — Phase 4 confidence-card explanation payload (backend contract only, no UI).

Uses LightGBM's built-in pred_contrib (additive per-feature contributions to
the raw log-odds output) instead of adding a SHAP dependency — LightGBM's
own contributions ARE Shapley-consistent additive attributions for tree
ensembles, so a separate library adds dependency weight without adding
accuracy here (per spec §17: "do not make SHAP mandatory if it creates
unnecessary dependency... priority is trustworthy explanations").
"""
import json
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).parent.parent.parent


def load_inference_bundle():
    lgbm_bundle = joblib.load(ROOT / "models/lightgbm_v1.joblib")
    calib_bundle = joblib.load(ROOT / "models/calibrator_v1.joblib")
    with open(ROOT / "configs/threshold_policy.json") as f:
        policy = json.load(f)
    # Enforce a single shared feature order across model, calibrator, and
    # inference — a mismatch here would silently corrupt every prediction.
    assert lgbm_bundle["feature_cols"] == calib_bundle["feature_cols"], (
        "Feature schema mismatch between model and calibrator artifacts."
    )
    return lgbm_bundle, calib_bundle, policy


def decide(proba_calibrated: float, policy: dict) -> str:
    if proba_calibrated >= policy["high_threshold"]:
        return "HIGH_CONFIDENCE_MATCH"
    if proba_calibrated < policy["low_threshold"]:
        return "LIKELY_NO_MATCH"
    return "NEEDS_REVIEW"


def explain_candidate(candidate_id: str, feature_row: dict, lgbm_bundle: dict, calib_bundle: dict, policy: dict) -> dict:
    feature_cols = lgbm_bundle["feature_cols"]
    x = np.array([[feature_row[c] for c in feature_cols]], dtype=float)

    model = lgbm_bundle["model"]
    proba_raw = float(model.predict_proba(x)[:, 1][0])
    proba_calibrated = float(calib_bundle["calibrator"].predict_proba(x)[:, 1][0])
    decision = decide(proba_calibrated, policy)

    # pred_contrib: one row, columns = [contrib_feature_0, ..., contrib_feature_n, base_value]
    contrib = model.booster_.predict(x, pred_contrib=True)[0]
    feature_contribs = contrib[:-1]

    ranked = sorted(zip(feature_cols, feature_contribs), key=lambda x: abs(x[1]), reverse=True)
    top_evidence = [
        {"feature": f, "direction": "supports_match" if c > 0 else "weakens_match",
         "value": feature_row[f], "contribution": round(float(c), 4)}
        for f, c in ranked[:5]
    ]

    return {
        "candidate_id": candidate_id,
        "match_probability_raw": round(proba_raw, 4),
        "match_probability_calibrated": round(proba_calibrated, 4),
        "decision": decision,
        "thresholds": {"high": policy["high_threshold"], "low": policy["low_threshold"]},
        "top_evidence": top_evidence,
    }


if __name__ == "__main__":
    import pandas as pd
    lgbm_bundle, calib_bundle, policy = load_inference_bundle()
    df = pd.read_parquet(ROOT / "data/processed/unified_labeled_candidates.parquet")
    test_df = df[df["split"] == "test"].reset_index(drop=True)

    examples = []
    for _, row in test_df.head(3).iterrows():
        payload = explain_candidate(
            f"{row['ledger_public_id']}::{row['settlement_public_id']}",
            row.to_dict(), lgbm_bundle, calib_bundle, policy,
        )
        examples.append(payload)
        print(json.dumps(payload, indent=2, default=str))
