import json
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from ml.training.train_phase4_comparison import load_splits, train_logreg

train_df, val_df, test_df, feature_cols = load_splits()

GROUPS = {
    "semantic": ["vendor_embedding_cosine_similarity", "description_embedding_cosine_similarity"],
    "reference": ["reference_exact_match", "reference_substring_overlap", "reference_similarity",
                  "reference_missing_ledger", "reference_both_missing"],
    "structural": ["group_size", "is_potential_one_to_many", "is_potential_many_to_one",
                   "candidate_count_for_ledger", "candidate_count_for_settlement", "competing_candidate_count"],
}

results = {}
_, _, full_metrics = train_logreg(train_df, val_df, feature_cols, class_weight="balanced")
results["all_features"] = full_metrics

for group_name, cols in GROUPS.items():
    remaining = [c for c in feature_cols if c not in cols]
    _, _, m = train_logreg(train_df, val_df, remaining, class_weight="balanced")
    results[f"without_{group_name}"] = m

print(json.dumps(results, indent=2))
with open(ROOT / "reports/phase4/feature_group_ablations.json", "w") as f:
    json.dump(results, f, indent=2)
