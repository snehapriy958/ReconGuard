"""
ReconLens — Phase 3 label assembly.

EVALUATION-ONLY. Reads _hidden_match_map.json and the hidden per-record
split truth files. Never imported by ml/features/, ml/candidate_generation/,
or any model-serving code — verified by test_no_leakage.py.

SCOPE DECISION (stated explicitly, not discovered later): this labels the
V1 pairwise candidate set only (one-to-one relationships). Structural (V2)
group candidates use a different feature shape (combined amounts across
2-3 records rather than a single amount delta) that Phase 2's extractor was
not built to produce, and unifying the two into one feature schema is
deferred to a follow-on iteration rather than rushed here. This means the
Phase 3 Logistic Regression baseline addresses one-to-one reconciliation
only; split/batch classification remains an open item, stated in
docs/model_baseline.md, not hidden.

LEAKAGE RULE (stricter than "don't split a transaction group across
splits"): a candidate pair is only assigned to a split if BOTH its ledger
record's true split AND its settlement record's true split agree. If they
disagree — which can happen for a NEGATIVE candidate pairing a ledger
record from one ground-truth transaction with a settlement record from a
different one — the pair is excluded entirely, from every split. The
reasoning: if record S (whose true home is the test split) were allowed
into a training-split negative example, the model would have already seen
S's specific feature values during training, undermining the point of
holding test out at all — even though S wasn't part of a positive label in
that training row.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent

feature_df = pd.read_parquet(ROOT / "data/processed/features.parquet")
match_map = json.load(open(ROOT / "data/raw/_hidden_match_map.json"))
ledger_truth = pd.read_csv(ROOT / "data/raw/_hidden_ledger_truth.csv").set_index("ledger_id")
settlement_truth = pd.read_csv(ROOT / "data/raw/_hidden_settlement_truth.csv").set_index("settlement_id")

# True one-to-one positive pairs.
positive_pairs = set()
# Pairs that are components of a split/batch relationship — not valid
# standalone one-to-one labels; checked for accidental overlap, not assumed absent.
ambiguous_pairs = set()

for entry in match_map:
    is_one_to_one = len(entry["ledger_ids"]) == 1 and len(entry["settlement_ids"]) == 1
    for l in entry["ledger_ids"]:
        for s in entry["settlement_ids"]:
            if is_one_to_one:
                positive_pairs.add((l, s))
            else:
                ambiguous_pairs.add((l, s))

rows = []
n_cross_split_excluded = 0
n_ambiguous_excluded = 0

for _, row in feature_df.iterrows():
    l, s = row["ledger_public_id"], row["settlement_public_id"]
    pair = (l, s)

    if pair in ambiguous_pairs:
        n_ambiguous_excluded += 1
        continue

    ledger_split = ledger_truth.loc[l, "_split"]
    settlement_split = settlement_truth.loc[s, "_split"]
    if ledger_split != settlement_split:
        n_cross_split_excluded += 1
        continue

    label = 1 if pair in positive_pairs else 0
    rows.append({**row.to_dict(), "split": ledger_split, "label": label})

labeled_df = pd.DataFrame(rows)

# --- Leakage verification, not assumed ---
gt_by_ledger = ledger_truth["_gt_txn_id"]
gt_by_settlement = settlement_truth["_gt_txn_id"]
gt_split_map = {}
for lid, gt in gt_by_ledger.items():
    gt_split_map.setdefault(gt, set()).add(ledger_truth.loc[lid, "_split"])
for sid, gt in gt_by_settlement.items():
    gt_split_map.setdefault(gt, set()).add(settlement_truth.loc[sid, "_split"])
cross_split_gt_txns = {gt: splits for gt, splits in gt_split_map.items() if len(splits) > 1}

assert len(cross_split_gt_txns) == 0, (
    f"LEAKAGE: {len(cross_split_gt_txns)} ground-truth transactions have records "
    f"in more than one split: {list(cross_split_gt_txns)[:5]}"
)

dup_check = labeled_df.duplicated(subset=["ledger_public_id", "settlement_public_id"])
assert not dup_check.any(), f"LEAKAGE: {dup_check.sum()} duplicate candidate rows in labeled dataset"

leakage_cols = [c for c in labeled_df.columns if "gt_txn" in c.lower() or "ground_truth" in c.lower()]
assert not leakage_cols, f"LEAKAGE: hidden columns present in labeled dataset: {leakage_cols}"

out_path = ROOT / "data/processed/labeled_candidates.parquet"
labeled_df.to_parquet(out_path, index=False)
labeled_df.to_csv(out_path.with_suffix(".csv"), index=False)

class_dist = {}
for split in ["train", "val", "test"]:
    sub = labeled_df[labeled_df["split"] == split]
    n_pos = int(sub["label"].sum())
    n_total = len(sub)
    class_dist[split] = {
        "total": n_total, "positive": n_pos, "negative": n_total - n_pos,
        "positive_pct": round(100 * n_pos / n_total, 2) if n_total else None,
    }

report = {
    "total_v1_candidates": len(feature_df),
    "excluded_ambiguous_structural_pairs": n_ambiguous_excluded,
    "excluded_cross_split_pairs": n_cross_split_excluded,
    "labeled_rows": len(labeled_df),
    "leakage_checks": {
        "cross_split_ground_truth_transactions": len(cross_split_gt_txns),
        "duplicate_candidate_rows": int(dup_check.sum()),
        "hidden_columns_present": len(leakage_cols),
    },
    "class_distribution": class_dist,
}
print(json.dumps(report, indent=2))

with open(ROOT / "reports/phase3/label_assembly_report.json", "w") as f:
    json.dump(report, f, indent=2)
