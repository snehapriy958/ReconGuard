"""
ReconLens — Phase 4 model comparison: Logistic Regression (re-run on the
unified dataset, for a fair apples-to-apples comparison) vs LightGBM.

Held-out test is NOT touched anywhere in this file — only train/val.
"""
import json
import platform
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, confusion_matrix,
)
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).parent.parent.parent
RANDOM_SEED = 42

NON_FEATURE_COLS = {"ledger_public_id", "settlement_public_id", "split", "label", "relationship_type_candidate"}

# Excluded by a Phase 4 finding, not by default: reference_missing_settlement
# correlates perfectly with relationship_type in this dataset (100% of true
# many-to-one matches have it=1, 100% of true one-to-many matches have it=0)
# purely because the Phase 1 generator always leaves batch settlement
# references blank by construction — not because a missing reference is real
# evidence of a match (in production it would more plausibly be a risk
# signal). Ablation (scripts/investigate_reference_missing_settlement.py)
# showed negligible cost to removing it (PR-AUC 0.9994 -> 0.9991 on
# validation), so it's excluded rather than shipped as a spurious rule that
# would not generalize past this synthetic dataset's construction quirk.
EXCLUDED_ARTIFACT_FEATURES = {"reference_missing_settlement"}


def load_splits():
    df = pd.read_parquet(ROOT / "data/processed/unified_labeled_candidates.parquet")
    feature_cols = sorted([c for c in df.columns if c not in NON_FEATURE_COLS
                            and c not in EXCLUDED_ARTIFACT_FEATURES])
    train = df[df["split"] == "train"].reset_index(drop=True)
    val = df[df["split"] == "val"].reset_index(drop=True)
    test = df[df["split"] == "test"].reset_index(drop=True)
    return train, val, test, feature_cols


def metrics_from_proba(y_true, proba, threshold=0.5):
    y_pred = (proba >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    return {
        "n": len(y_true), "n_positive": int(y_true.sum()), "n_negative": int((1 - y_true).sum()),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_true, proba), 4) if len(set(y_true)) > 1 else None,
        "pr_auc": round(average_precision_score(y_true, proba), 4) if len(set(y_true)) > 1 else None,
        "confusion_matrix": {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]), "fn": int(cm[1, 0]), "tp": int(cm[1, 1])},
    }


# ---------------- Logistic Regression (re-run on unified data) ----------------

def train_logreg(train_df, val_df, feature_cols, class_weight):
    scaler = StandardScaler()
    X_train = scaler.fit_transform(train_df[feature_cols].to_numpy(dtype=float))
    model = LogisticRegression(max_iter=1000, random_state=RANDOM_SEED, class_weight=class_weight)
    model.fit(X_train, train_df["label"].to_numpy())
    X_val = scaler.transform(val_df[feature_cols].to_numpy(dtype=float))
    proba_val = model.predict_proba(X_val)[:, 1]
    return model, scaler, metrics_from_proba(val_df["label"].to_numpy(), proba_val)


# ---------------- LightGBM (small, documented hyperparameter search) ----------------

LGBM_SEARCH_SPACE = [
    {"num_leaves": 15, "max_depth": 4, "learning_rate": 0.05, "n_estimators": 200, "min_child_samples": 10},
    {"num_leaves": 31, "max_depth": 6, "learning_rate": 0.05, "n_estimators": 200, "min_child_samples": 10},
    {"num_leaves": 31, "max_depth": -1, "learning_rate": 0.1, "n_estimators": 100, "min_child_samples": 20},
    {"num_leaves": 63, "max_depth": 8, "learning_rate": 0.05, "n_estimators": 300, "min_child_samples": 5},
]


def train_lightgbm_search(train_df, val_df, feature_cols):
    X_train = train_df[feature_cols].to_numpy(dtype=float)
    y_train = train_df["label"].to_numpy()
    X_val = val_df[feature_cols].to_numpy(dtype=float)
    y_val = val_df["label"].to_numpy()

    results = []
    for i, params in enumerate(LGBM_SEARCH_SPACE):
        model = lgb.LGBMClassifier(
            **params, random_state=RANDOM_SEED, class_weight="balanced",
            verbose=-1, feature_fraction=0.9, subsample=0.9,
        )
        model.fit(X_train, y_train)
        proba_val = model.predict_proba(X_val)[:, 1]
        m = metrics_from_proba(y_val, proba_val)
        results.append({"config_index": i, "params": params, "val_metrics": m, "model": model})

    # Selection: highest val PR-AUC (more informative than F1 alone under
    # imbalance — see docs/model_comparison.md), not accuracy.
    best = max(results, key=lambda r: r["val_metrics"]["pr_auc"] or 0)
    return best, results


def main():
    train_df, val_df, test_df, feature_cols = load_splits()
    print(f"Feature columns ({len(feature_cols)}): {feature_cols}")
    print(f"Train: {len(train_df)} ({train_df['label'].mean():.1%} positive)")

    # --- Logistic Regression: unweighted vs balanced, on the UNIFIED data ---
    lr_results = {}
    lr_models = {}
    for label, cw in [("unweighted", None), ("balanced", "balanced")]:
        model, scaler, val_metrics = train_logreg(train_df, val_df, feature_cols, cw)
        lr_results[label] = val_metrics
        lr_models[label] = (model, scaler)
    lr_chosen_label = "balanced" if (lr_results["balanced"]["pr_auc"] or 0) >= (lr_results["unweighted"]["pr_auc"] or 0) else "unweighted"
    lr_model, lr_scaler = lr_models[lr_chosen_label]
    print(f"\n=== Logistic Regression (unified data) — chosen variant: {lr_chosen_label} ===")
    print(json.dumps(lr_results[lr_chosen_label], indent=2))

    # --- LightGBM ---
    best_lgbm, all_lgbm_results = train_lightgbm_search(train_df, val_df, feature_cols)
    print(f"\n=== LightGBM — best config (index {best_lgbm['config_index']}) ===")
    print(json.dumps({"params": best_lgbm["params"], "val_metrics": best_lgbm["val_metrics"]}, indent=2))
    print("\nAll LightGBM configs tried:")
    for r in all_lgbm_results:
        print(f"  config {r['config_index']}: PR-AUC={r['val_metrics']['pr_auc']} "
              f"F1={r['val_metrics']['f1']} params={r['params']}")

    # --- Comparison table ---
    comparison = {
        "logistic_regression": {"variant": lr_chosen_label, **lr_results[lr_chosen_label]},
        "lightgbm": {"config_index": best_lgbm["config_index"], "params": best_lgbm["params"], **best_lgbm["val_metrics"]},
    }
    print("\n=== VALIDATION COMPARISON ===")
    print(json.dumps(comparison, indent=2))

    reports_dir = ROOT / "reports/phase4"
    reports_dir.mkdir(parents=True, exist_ok=True)
    with open(reports_dir / "model_comparison_validation.json", "w") as f:
        json.dump(comparison, f, indent=2)
    with open(reports_dir / "lightgbm_hyperparameter_search.json", "w") as f:
        json.dump([{"config_index": r["config_index"], "params": r["params"], "val_metrics": r["val_metrics"]}
                    for r in all_lgbm_results], f, indent=2)

    # --- Feature importance (LightGBM) ---
    lgbm_model = best_lgbm["model"]
    gain_importance = dict(zip(feature_cols, lgbm_model.booster_.feature_importance(importance_type="gain")))
    split_importance = dict(zip(feature_cols, lgbm_model.booster_.feature_importance(importance_type="split")))
    importance_report = sorted(
        [{"feature": f, "gain": round(float(gain_importance[f]), 2), "split_count": int(split_importance[f])}
         for f in feature_cols],
        key=lambda x: x["gain"], reverse=True,
    )
    with open(reports_dir / "lightgbm_feature_importance.json", "w") as f:
        json.dump(importance_report, f, indent=2)
    print("\n=== LightGBM feature importance (top 8 by gain) ===")
    for row in importance_report[:8]:
        print(f"  {row['feature']:35} gain={row['gain']:>10.2f}  splits={row['split_count']}")

    # --- Save both models for downstream calibration/threshold work ---
    models_dir = ROOT / "models"
    models_dir.mkdir(exist_ok=True)
    joblib.dump({"model": lr_model, "scaler": lr_scaler, "feature_cols": feature_cols,
                 "class_weight": lr_chosen_label, "random_seed": RANDOM_SEED,
                 "sklearn_version": sklearn.__version__, "model_type": "logreg_unified_v1"},
                models_dir / "logreg_unified_v1.joblib")
    joblib.dump({"model": lgbm_model, "feature_cols": feature_cols, "params": best_lgbm["params"],
                 "random_seed": RANDOM_SEED, "lightgbm_version": lgb.__version__,
                 "model_type": "lightgbm_v1"},
                models_dir / "lightgbm_v1.joblib")

    return comparison, feature_cols


if __name__ == "__main__":
    main()
