"""Model evaluation service for ReconGuard.

Reads static, precomputed held-out evaluation reports from reports/phase4/.
This service is strictly READ-ONLY:
- Does NOT trigger training
- Does NOT execute inference or modify model artifacts
- Uses fixed, controlled paths (no arbitrary file path access)
"""

import json
from pathlib import Path
from typing import Any, Optional
from fastapi import HTTPException

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports" / "phase4"


def _load_json(file_path: Path) -> Optional[Any]:
    if not file_path.exists() or not file_path.is_file():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_model_evaluation_data() -> dict[str, Any]:
    """Load and aggregate the canonical Phase 4 evaluation report artifacts."""
    test_eval_path = REPORTS_DIR / "final_held_out_test_evaluation.json"
    if not test_eval_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Model evaluation artifacts not found in reports/phase4/",
        )

    test_eval = _load_json(test_eval_path)
    if not test_eval:
        raise HTTPException(
            status_code=500,
            detail="Failed to parse final held out test evaluation artifact.",
        )

    calib_eval = _load_json(REPORTS_DIR / "calibration_report.json") or {}
    policy_eval = _load_json(REPORTS_DIR / "threshold_policy_selected.json") or {}
    importance_eval = _load_json(REPORTS_DIR / "lightgbm_feature_importance.json") or []
    label_assembly = _load_json(REPORTS_DIR / "unified_label_assembly_report.json") or {}

    def_metrics = test_eval.get("final_metrics_default_threshold", {})
    cm = def_metrics.get("confusion_matrix", {})
    tp = cm.get("tp", 0)
    tn = cm.get("tn", 0)
    fp = cm.get("fp", 0)
    fn = cm.get("fn", 0)
    total_test = tp + tn + fp + fn

    accuracy = round((tp + tn) / total_test, 4) if total_test > 0 else 0.0

    selected_policy = policy_eval.get("selected_policy", {})
    cost_assumptions = policy_eval.get("cost_assumptions", {})

    # Top features (top 8 by gain)
    top_features = []
    if isinstance(importance_eval, list):
        for item in importance_eval[:8]:
            top_features.append({
                "feature": item.get("feature", ""),
                "importance_gain": item.get("gain", 0.0),
                "split_count": item.get("split_count", 0),
            })

    dataset_info = label_assembly.get("test", {})

    return {
        "model": {
            "name": "LightGBM Classifier (Calibrated)",
            "model_type": "lightgbm",
            "version": "phase4_final",
            "features_count": len(importance_eval) if isinstance(importance_eval, list) else 22,
            "bundle_file": "models/reconlens_phase4_final.joblib",
            "threshold_policy": {
                "low_threshold": selected_policy.get("low", 0.5),
                "high_threshold": selected_policy.get("high", 0.85),
                "fp_cost": cost_assumptions.get("FP_COST", 10),
                "fn_cost": cost_assumptions.get("FN_COST", 3),
                "review_cost": cost_assumptions.get("REVIEW_COST", 1),
            },
            "top_features": top_features,
        },
        "dataset": {
            "name": "Unified Recon Dataset (Pairwise + Structural)",
            "split": "test",
            "sample_count": total_test,
            "positive_count": tp + fn,
            "negative_count": tn + fp,
            "positive_rate": round((tp + fn) / total_test, 4) if total_test > 0 else 0.0,
            "by_relationship_type": dataset_info.get("by_relationship_type", {}),
            "training_samples": label_assembly.get("train", {}).get("total", 3378),
            "validation_samples": label_assembly.get("val", {}).get("total", 151),
        },
        "metrics": {
            "accuracy": accuracy,
            "precision": def_metrics.get("precision", 0.0),
            "recall": def_metrics.get("recall", 0.0),
            "f1": def_metrics.get("f1", 0.0),
            "roc_auc": def_metrics.get("roc_auc", 0.0),
            "pr_auc": def_metrics.get("pr_auc", 0.0),
        },
        "confusion_matrix": {
            "true_positive": tp,
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
            "total": total_test,
        },
        "class_metrics": test_eval.get("by_relationship_type", {}),
        "routing_policy_results": test_eval.get("three_way_policy_applied_to_test", {}),
        "calibration": {
            "method": calib_eval.get("calibration_method", "sigmoid"),
            "val_fit_samples": calib_eval.get("val_fit_n", 75),
            "val_eval_samples": calib_eval.get("val_eval_n", 76),
            "brier_score_before": calib_eval.get("brier_score_before", 0.0),
            "brier_score_after": calib_eval.get("brier_score_after", 0.0),
            "brier_improved": calib_eval.get("brier_improved", False),
            "notes": calib_eval.get("note_on_brier_comparison", ""),
            "methodology_note": calib_eval.get("methodology_note", ""),
            "reliability_before": calib_eval.get("reliability_before_calibration", []),
            "reliability_after": calib_eval.get("reliability_after_calibration", []),
        },
        "notes": [
            "Offline test evaluation was conducted on a held-out test split of 100 candidate groups and evaluated exactly once.",
            "Small evaluation sample size: structural classes have limited test samples (n=11 for one-to-many, n=6 for many-to-one).",
            "High test precision (100%) on the test split should be interpreted alongside the small test size and offline domain conditions.",
            "Calibration: Platt/Sigmoid scaling preserves 121 continuous probability values; Brier score increases slightly (0.00355 to 0.00714) due to probability smoothing over a sharp step-function.",
            "Comparison: Phase 4 unified test set (100 rows) is not directly comparable to Phase 3 pairwise-only test set (83 rows) due to the addition of complex multi-record groups."
        ],
    }
