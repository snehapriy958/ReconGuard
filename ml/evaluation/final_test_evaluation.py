"""
ReconLens — Phase 4 FINAL held-out test evaluation. Run exactly once, after
every model/calibration/threshold decision was made using train/val only.
"""
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, confusion_matrix

from ml.training.train_phase4_comparison import load_splits

ROOT = Path(__file__).parent.parent.parent

train_df, val_df, test_df, feature_cols = load_splits()

lgbm_bundle = joblib.load(ROOT / "models/lightgbm_v1.joblib")
calib_bundle = joblib.load(ROOT / "models/calibrator_v1.joblib")
with open(ROOT / "configs/threshold_policy.json") as f:
    policy = json.load(f)

X_test = test_df[feature_cols].to_numpy(dtype=float)
y_test = test_df["label"].to_numpy()

proba_calibrated = calib_bundle["calibrator"].predict_proba(X_test)[:, 1]
y_pred_default_threshold = (proba_calibrated >= 0.5).astype(int)

cm = confusion_matrix(y_test, y_pred_default_threshold, labels=[0, 1])
final_metrics = {
    "precision": round(precision_score(y_test, y_pred_default_threshold, zero_division=0), 4),
    "recall": round(recall_score(y_test, y_pred_default_threshold, zero_division=0), 4),
    "f1": round(f1_score(y_test, y_pred_default_threshold, zero_division=0), 4),
    "roc_auc": round(roc_auc_score(y_test, proba_calibrated), 4),
    "pr_auc": round(average_precision_score(y_test, proba_calibrated), 4),
    "confusion_matrix": {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]), "fn": int(cm[1, 0]), "tp": int(cm[1, 1])},
}

# Three-way policy applied to test, for reporting (not for any further tuning)
auto_match = proba_calibrated >= policy["high_threshold"]
no_match = proba_calibrated < policy["low_threshold"]
review = ~auto_match & ~no_match
policy_report = {
    "n_auto_match": int(auto_match.sum()), "n_review": int(review.sum()), "n_no_match": int(no_match.sum()),
    "auto_match_precision": round(float((y_test[auto_match] == 1).mean()), 4) if auto_match.sum() else None,
    "auto_match_recall": round(float(((y_test == 1) & auto_match).sum() / max((y_test == 1).sum(), 1)), 4),
    "review_positive_rate": round(float(y_test[review].mean()), 4) if review.sum() else None,
    "likely_no_match_error_rate": round(float(((y_test == 1) & no_match).sum() / max(no_match.sum(), 1)), 4),
}

# By relationship type, since many_to_one had zero val positives — this is
# the FIRST time many_to_one gets any real signal at all.
by_type = {}
for rel_type in ["one_to_one", "one_to_many", "many_to_one"]:
    sub = test_df[test_df["relationship_type_candidate"] == rel_type]
    if sub["label"].nunique() < 2:
        by_type[rel_type] = {"n": len(sub), "positive": int(sub["label"].sum()),
                              "note": "single class present in test for this type; precision/recall not computable"}
        continue
    idx = sub.index
    sub_proba = calib_bundle["calibrator"].predict_proba(sub[feature_cols].to_numpy(dtype=float))[:, 1]
    sub_pred = (sub_proba >= 0.5).astype(int)
    by_type[rel_type] = {
        "n": len(sub), "positive": int(sub["label"].sum()),
        "precision": round(precision_score(sub["label"], sub_pred, zero_division=0), 4),
        "recall": round(recall_score(sub["label"], sub_pred, zero_division=0), 4),
    }

result = {
    "note": "Evaluated exactly once. No further tuning follows this.",
    "final_metrics_default_threshold": final_metrics,
    "three_way_policy_applied_to_test": policy_report,
    "by_relationship_type": by_type,
    "comparison_to_phase3_pairwise_only_baseline": {
        "phase3_logreg_pairwise_only": {"precision": 1.0, "recall": 0.9857, "f1": 0.9928},
        "phase4_lightgbm_unified": final_metrics,
        "note": "Not directly comparable — Phase 3 test set was the pairwise-only labeled "
                "set (83 rows); Phase 4 test set is the unified pairwise+structural set "
                "(100 rows, including 6 many-to-one and 11 one-to-many candidates the "
                "Phase 3 model was never evaluated on at all).",
    },
}
print(json.dumps(result, indent=2))

reports_dir = ROOT / "reports/phase4"
reports_dir.mkdir(parents=True, exist_ok=True)
with open(reports_dir / "final_held_out_test_evaluation.json", "w") as f:
    json.dump(result, f, indent=2)
