"""
ReconLens — Phase 4 cost-sensitive threshold selection.

PROJECT ASSUMPTIONS, not real Razorpay production costs (stated explicitly
per spec §27):
  FP_COST = 10   (an incorrect auto-reconciliation silently corrupts records)
  FN_COST = 3    (a missed auto-match just costs human review time)
  REVIEW_COST = 1 (baseline cost of a human reviewing one candidate)

Threshold selection uses VALIDATION calibrated probabilities only. Held-out
test is not touched here.
"""
import json
from pathlib import Path

import joblib
import numpy as np

from ml.training.train_phase4_comparison import load_splits

ROOT = Path(__file__).parent.parent.parent

FP_COST = 10
FN_COST = 3
REVIEW_COST = 1

train_df, val_df, test_df, feature_cols = load_splits()

lgbm_bundle = joblib.load(ROOT / "models/lightgbm_v1.joblib")
calib_bundle = joblib.load(ROOT / "models/calibrator_v1.joblib")
calibrator = calib_bundle["calibrator"]

X_val = val_df[feature_cols].to_numpy(dtype=float)
y_val = val_df["label"].to_numpy()
proba_val = calibrator.predict_proba(X_val)[:, 1]


def evaluate_policy(y_true, proba, low, high):
    auto_match = proba >= high
    no_match = proba < low
    review = ~auto_match & ~no_match

    n = len(y_true)
    fp_in_auto = int(((y_true == 0) & auto_match).sum())
    tp_in_auto = int(((y_true == 1) & auto_match).sum())
    fn_in_no_match = int(((y_true == 1) & no_match).sum())
    tn_in_no_match = int(((y_true == 0) & no_match).sum())
    n_review = int(review.sum())

    auto_match_precision = tp_in_auto / max(auto_match.sum(), 1)
    auto_match_recall = tp_in_auto / max((y_true == 1).sum(), 1)
    review_positive_rate = float(y_true[review].mean()) if n_review > 0 else None
    likely_no_match_error_rate = fn_in_no_match / max(no_match.sum(), 1)  # fraction of "no match" that were actually true

    total_cost = fp_in_auto * FP_COST + fn_in_no_match * FN_COST + n_review * REVIEW_COST

    return {
        "low": round(low, 2), "high": round(high, 2),
        "n_auto_match": int(auto_match.sum()), "n_review": n_review, "n_no_match": int(no_match.sum()),
        "auto_match_precision": round(auto_match_precision, 4),
        "auto_match_recall": round(auto_match_recall, 4),
        "review_positive_rate": round(review_positive_rate, 4) if review_positive_rate is not None else None,
        "likely_no_match_error_rate": round(likely_no_match_error_rate, 4),
        "fp_in_auto_match": fp_in_auto, "fn_in_no_match": fn_in_no_match,
        "total_expected_cost": total_cost,
    }


# Grid search over (low, high) pairs, respecting low < high and a floor on
# `high` (>=0.85) so auto-match always requires genuine confidence, per the
# bounded-autonomy principle (spec §28): even the cost-optimal policy should
# not be allowed to auto-match at, say, 0.55 just because it minimizes a toy
# cost function on this small dataset.
grid = [round(x, 2) for x in np.arange(0.05, 1.0, 0.05)]
results = []
for low in grid:
    for high in grid:
        if high <= low or high < 0.85:
            continue
        results.append(evaluate_policy(y_val, proba_val, low, high))

best = min(results, key=lambda r: r["total_expected_cost"])

print(f"Selected policy: LOW={best['low']}, HIGH={best['high']}")
print(json.dumps(best, indent=2))

# Also report simple full sweep at single-threshold granularity for transparency
single_threshold_sweep = []
for t in grid:
    pred = (proba_val >= t).astype(int)
    tp = int(((y_val == 1) & (pred == 1)).sum())
    fp = int(((y_val == 0) & (pred == 1)).sum())
    fn = int(((y_val == 1) & (pred == 0)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    single_threshold_sweep.append({"threshold": t, "precision": round(precision, 4), "recall": round(recall, 4),
                                    "f1": round(f1, 4), "fp": fp, "fn": fn})

reports_dir = ROOT / "reports/phase4"
reports_dir.mkdir(parents=True, exist_ok=True)
with open(reports_dir / "threshold_policy_selected.json", "w") as f:
    json.dump({"cost_assumptions": {"FP_COST": FP_COST, "FN_COST": FN_COST, "REVIEW_COST": REVIEW_COST},
                "selected_policy": best}, f, indent=2)
with open(reports_dir / "threshold_sweep_full_grid.json", "w") as f:
    json.dump(results, f, indent=2)
with open(reports_dir / "single_threshold_sweep.json", "w") as f:
    json.dump(single_threshold_sweep, f, indent=2)

policy_config = {"high_threshold": best["high"], "low_threshold": best["low"],
                  "cost_assumptions": {"FP_COST": FP_COST, "FN_COST": FN_COST, "REVIEW_COST": REVIEW_COST}}
with open(ROOT / "configs/threshold_policy.json", "w") as f:
    json.dump(policy_config, f, indent=2)
