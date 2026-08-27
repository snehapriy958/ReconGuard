"""
ReconLens — Phase 3 Logistic Regression baseline.

Trains on the labeled V1 pairwise candidate set (data/processed/labeled_candidates.parquet).
Reads NO hidden files directly — labels/split were already assigned by the
evaluation-only scripts/assemble_labels.py and baked into that parquet file.
This script only ever sees ledger_public_id/settlement_public_id, feature
columns, split, and label — never a ground-truth transaction ID.
"""
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score, average_precision_score,
    confusion_matrix, precision_recall_curve,
)
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).parent.parent.parent
RANDOM_SEED = 42

ID_COLS = {"ledger_public_id", "settlement_public_id", "split", "label"}


def load_splits():
    df = pd.read_parquet(ROOT / "data/processed/labeled_candidates.parquet")
    feature_cols = [c for c in df.columns if c not in ID_COLS]
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    test = df[df["split"] == "test"]
    return train, val, test, feature_cols


def fit_scaler_and_model(train_df, feature_cols, class_weight):
    scaler = StandardScaler()
    X_train = scaler.fit_transform(train_df[feature_cols].to_numpy(dtype=float))
    y_train = train_df["label"].to_numpy()
    model = LogisticRegression(
        max_iter=1000, random_state=RANDOM_SEED, class_weight=class_weight,
    )
    model.fit(X_train, y_train)
    return model, scaler


def evaluate(model, scaler, df, feature_cols, threshold=0.5):
    X = scaler.transform(df[feature_cols].to_numpy(dtype=float))
    y_true = df["label"].to_numpy()
    proba = model.predict_proba(X)[:, 1]
    y_pred = (proba >= threshold).astype(int)

    metrics = {
        "n": len(df),
        "n_positive": int(y_true.sum()),
        "n_negative": int((1 - y_true).sum()),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_true, proba), 4) if len(set(y_true)) > 1 else None,
        "pr_auc": round(average_precision_score(y_true, proba), 4) if len(set(y_true)) > 1 else None,
    }
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    metrics["confusion_matrix"] = {
        "tn": int(cm[0, 0]), "fp": int(cm[0, 1]), "fn": int(cm[1, 0]), "tp": int(cm[1, 1]),
    }
    return metrics, proba, y_pred


def threshold_sweep(model, scaler, df, feature_cols):
    X = scaler.transform(df[feature_cols].to_numpy(dtype=float))
    y_true = df["label"].to_numpy()
    proba = model.predict_proba(X)[:, 1]
    rows = []
    for t in [round(x, 1) for x in np.arange(0.1, 1.0, 0.1)]:
        y_pred = (proba >= t).astype(int)
        rows.append({
            "threshold": t,
            "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
            "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
            "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
            "n_predicted_positive": int(y_pred.sum()),
            "n_predicted_negative": int((1 - y_pred).sum()),
        })
    return rows


def main():
    train_df, val_df, test_df, feature_cols = load_splits()

    # --- Compare unweighted vs class_weight='balanced' on VALIDATION only ---
    results = {}
    models = {}
    for label, cw in [("unweighted", None), ("balanced", "balanced")]:
        model, scaler = fit_scaler_and_model(train_df, feature_cols, cw)
        val_metrics, _, _ = evaluate(model, scaler, val_df, feature_cols)
        results[label] = val_metrics
        models[label] = (model, scaler)

    print("=== Validation comparison: unweighted vs balanced ===")
    print(json.dumps(results, indent=2))

    # Selection rule stated before looking at test: prefer the variant with
    # higher validation F1; ties broken toward 'balanced' since false positives
    # (see docs/model_baseline.md) are the costlier error class in this domain,
    # and class_weight='balanced' is the variant designed to not under-predict
    # the minority class.
    chosen_label = "balanced" if results["balanced"]["f1"] >= results["unweighted"]["f1"] else "unweighted"
    chosen_model, chosen_scaler = models[chosen_label]
    print(f"\nSelected variant: {chosen_label} (val F1 {results[chosen_label]['f1']} "
          f"vs {results['unweighted' if chosen_label=='balanced' else 'balanced']['f1']})")

    # --- Final, one-time evaluation on held-out test ---
    test_metrics, test_proba, test_pred = evaluate(chosen_model, chosen_scaler, test_df, feature_cols)
    print("\n=== HELD-OUT TEST (final report only) ===")
    print(json.dumps(test_metrics, indent=2))

    # --- Coefficients ---
    coefs = sorted(
        zip(feature_cols, chosen_model.coef_[0]),
        key=lambda x: abs(x[1]), reverse=True,
    )
    coef_report = [{"feature": f, "coefficient": round(float(c), 4),
                     "direction": "increases match likelihood" if c > 0 else "decreases match likelihood"}
                    for f, c in coefs]
    print("\n=== Feature coefficients (sorted by |magnitude|) ===")
    for row in coef_report:
        print(f"  {row['feature']:45} {row['coefficient']:+.4f}  ({row['direction']})")

    # --- Threshold sweep on validation (not test) ---
    thresh_table = threshold_sweep(chosen_model, chosen_scaler, val_df, feature_cols)

    # --- Save artifacts ---
    models_dir = ROOT / "models"
    models_dir.mkdir(exist_ok=True)
    joblib.dump({
        "model": chosen_model,
        "scaler": chosen_scaler,
        "feature_cols": feature_cols,
        "class_weight": chosen_label,
        "random_seed": RANDOM_SEED,
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "model_type": "logistic_regression_baseline_v1",
    }, models_dir / "logreg_baseline_v1.joblib")

    reports_dir = ROOT / "reports/phase3"
    reports_dir.mkdir(parents=True, exist_ok=True)
    with open(reports_dir / "baseline_validation_comparison.json", "w") as f:
        json.dump(results, f, indent=2)
    with open(reports_dir / "baseline_test_metrics.json", "w") as f:
        json.dump({"chosen_variant": chosen_label, "test_metrics": test_metrics}, f, indent=2)
    with open(reports_dir / "baseline_coefficients.json", "w") as f:
        json.dump(coef_report, f, indent=2)
    with open(reports_dir / "baseline_threshold_sweep_val.json", "w") as f:
        json.dump(thresh_table, f, indent=2)

    # Save test predictions for error analysis (separate script, still no hidden files)
    test_out = test_df[["ledger_public_id", "settlement_public_id", "label"]].copy()
    test_out["predicted_proba"] = test_proba
    test_out["predicted_label"] = test_pred
    test_out.to_csv(reports_dir / "test_predictions.csv", index=False)

    return chosen_label, results, test_metrics, coef_report, thresh_table


if __name__ == "__main__":
    main()
