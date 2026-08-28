"""
ReconLens — Phase 4 unified label assembly.

EVALUATION-ONLY. Generalizes scripts/assemble_labels.py's leakage rule from
"both records" to "ALL records in the group must agree on ground-truth
split" — a group with 3 ledger members needs all 3 (plus the settlement
member(s)) to share one split, or the whole candidate is excluded.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent

feature_df = pd.read_parquet(ROOT / "data/processed/unified_features.parquet")
match_map = json.load(open(ROOT / "data/raw/_hidden_match_map.json"))
ledger_truth = pd.read_csv(ROOT / "data/raw/_hidden_ledger_truth.csv").set_index("ledger_id")
settlement_truth = pd.read_csv(ROOT / "data/raw/_hidden_settlement_truth.csv").set_index("settlement_id")

# True positive groups, keyed by (frozenset(ledger_ids), frozenset(settlement_ids)),
# for ALL relationship types this time (not just one-to-one).
positive_groups = {(frozenset(e["ledger_ids"]), frozenset(e["settlement_ids"])) for e in match_map}

rows = []
n_cross_split_excluded = 0

for _, row in feature_df.iterrows():
    ledger_ids = row["ledger_public_id"].split("|")
    settlement_ids = row["settlement_public_id"].split("|")

    splits = {ledger_truth.loc[lid, "_split"] for lid in ledger_ids} | \
             {settlement_truth.loc[sid, "_split"] for sid in settlement_ids}
    if len(splits) > 1:
        n_cross_split_excluded += 1
        continue
    split = next(iter(splits))

    label = 1 if (frozenset(ledger_ids), frozenset(settlement_ids)) in positive_groups else 0
    rows.append({**row.to_dict(), "split": split, "label": label})

labeled_df = pd.DataFrame(rows)

# --- Leakage verification ---
dup_check = labeled_df.duplicated(subset=["ledger_public_id", "settlement_public_id"])
assert not dup_check.any(), f"LEAKAGE: {dup_check.sum()} duplicate candidate rows"
leakage_cols = [c for c in labeled_df.columns if "gt_txn" in c.lower() or "ground_truth" in c.lower()]
assert not leakage_cols, f"LEAKAGE: hidden columns present: {leakage_cols}"

out_path = ROOT / "data/processed/unified_labeled_candidates.parquet"
labeled_df.to_parquet(out_path, index=False)
labeled_df.to_csv(out_path.with_suffix(".csv"), index=False)

report = {"total_unified_candidates": len(feature_df),
          "excluded_cross_split_pairs": n_cross_split_excluded,
          "labeled_rows": len(labeled_df)}
for split in ["train", "val", "test"]:
    sub = labeled_df[labeled_df["split"] == split]
    by_type = {}
    for rel_type in ["one_to_one", "one_to_many", "many_to_one"]:
        t = sub[sub["relationship_type_candidate"] == rel_type]
        by_type[rel_type] = {"total": len(t), "positive": int(t["label"].sum()), "negative": int((1 - t["label"]).sum())}
    n_pos, n_total = int(sub["label"].sum()), len(sub)
    report[split] = {"total": n_total, "positive": n_pos, "negative": n_total - n_pos,
                      "positive_pct": round(100 * n_pos / n_total, 3) if n_total else None,
                      "by_relationship_type": by_type}

print(json.dumps(report, indent=2))
(ROOT / "reports/phase4").mkdir(parents=True, exist_ok=True)
with open(ROOT / "reports/phase4/unified_label_assembly_report.json", "w") as f:
    json.dump(report, f, indent=2)
