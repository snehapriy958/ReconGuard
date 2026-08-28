"""
ReconLens — investigate reference_missing_settlement (Phase 4 objective: is
this a legitimate signal, a synthetic artifact, or a leakage-adjacent effect?)

Runs on VALIDATION only, per spec — held-out test is not touched here.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from ml.training.train_phase4_comparison import load_splits, train_logreg

train_df, val_df, test_df, feature_cols = load_splits()

# --- Step 1: is it a synthetic-data artifact of WHICH transactions get a
# missing settlement reference? Check correlation with relationship type
# directly, since batched/split settlements are constructed with a blank
# reference by design (see generate.py: batch lines get reference_id=""). ---
combined = pd.concat([train_df, val_df, test_df], ignore_index=True)
crosstab = pd.crosstab(combined["relationship_type_candidate"], combined["reference_missing_settlement"])
print("=== reference_missing_settlement vs relationship_type_candidate (all labeled data) ===")
print(crosstab)
print()
crosstab_given_positive = pd.crosstab(
    combined[combined["label"] == 1]["relationship_type_candidate"],
    combined[combined["label"] == 1]["reference_missing_settlement"],
)
print("=== same, restricted to TRUE POSITIVE candidates only ===")
print(crosstab_given_positive)

# --- Step 2: ablation — Model A (all features) vs Model B (without the feature) ---
feature_cols_ablated = [c for c in feature_cols if c != "reference_missing_settlement"]

_, _, metrics_a = train_logreg(train_df, val_df, feature_cols, class_weight="balanced")
_, _, metrics_b = train_logreg(train_df, val_df, feature_cols_ablated, class_weight="balanced")

result = {
    "crosstab_all_labeled_data": crosstab.to_dict(),
    "crosstab_true_positives_only": crosstab_given_positive.to_dict(),
    "model_A_all_features": metrics_a,
    "model_B_without_reference_missing_settlement": metrics_b,
}
print("\n=== Ablation result ===")
print(json.dumps({"model_A": metrics_a, "model_B_ablated": metrics_b}, indent=2))

reports_dir = ROOT / "reports/phase4"
reports_dir.mkdir(parents=True, exist_ok=True)
with open(reports_dir / "feature_investigation_reference_missing_settlement.json", "w") as f:
    json.dump(result, f, indent=2, default=str)
