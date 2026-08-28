"""
ReconLens — Phase 4: build the unified (pairwise + structural) feature dataset.

Reads ONLY public ledger.csv / settlement.csv, same as Phase 2's extractor.
No hidden files touched here.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from ml.candidate_generation.blocking_v1 import generate_candidates as blocking_v1
from ml.candidate_generation.blocking_v2 import generate_structural_candidates
from ml.features.group_extractor import build_all_candidate_groups, extract_group_features

ledger_df = pd.read_csv(ROOT / "data/raw/ledger.csv")
settlement_df = pd.read_csv(ROOT / "data/raw/settlement.csv")
ledger_idx = ledger_df.set_index("ledger_id")
settlement_idx = settlement_df.set_index("settlement_id")

v1_pairs = blocking_v1(ledger_df, settlement_df)
v2_structural = generate_structural_candidates(ledger_df, settlement_df)
groups = build_all_candidate_groups(v1_pairs, v2_structural)

has_description = "description" in ledger_df.columns and "description" in settlement_df.columns
feature_df, metadata = extract_group_features(groups, ledger_idx, settlement_idx, has_description)

out_path = ROOT / "data/processed/unified_features.parquet"
feature_df.to_parquet(out_path, index=False)
feature_df.to_csv(out_path.with_suffix(".csv"), index=False)

import json
metadata.update({"n_v1_pairwise": len(v1_pairs), "n_v2_structural": len(v2_structural)})
with open(out_path.with_suffix(".metadata.json"), "w") as f:
    json.dump(metadata, f, indent=2)

print(f"Wrote {len(feature_df)} unified candidate rows.")
print(metadata)
print(feature_df["relationship_type_candidate"].value_counts())
