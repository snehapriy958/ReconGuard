"""
Evaluates candidate-generation recall: of all TRUE matches in the hidden
match map, what fraction survive blocking as a candidate pair?

This script is intentionally OUTSIDE ml/features/ and is never imported by
extractor.py or any training code — it reads _hidden_match_map.json, which
feature/model code must never touch. It exists purely so candidate-generation
recall is a measured number, not an assumption.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from ml.candidate_generation.blocking_v1 import generate_candidates

ROOT = Path(__file__).parent.parent
ledger_df = pd.read_csv(ROOT / "data/raw/ledger.csv")
settlement_df = pd.read_csv(ROOT / "data/raw/settlement.csv")

candidates = generate_candidates(ledger_df, settlement_df)
candidate_set = set(candidates)

match_map = json.load(open(ROOT / "data/raw/_hidden_match_map.json"))

total_true_pairs = 0
recovered = 0
lost_examples = []

for entry in match_map:
    for l in entry["ledger_ids"]:
        for s in entry["settlement_ids"]:
            total_true_pairs += 1
            if (l, s) in candidate_set:
                recovered += 1
            else:
                lost_examples.append((l, s, entry["gt_txn_id"]))

recall = recovered / total_true_pairs if total_true_pairs else 0.0

n_ledger = len(ledger_df)
n_settlement = len(settlement_df)
naive_comparisons = n_ledger * n_settlement

print(json.dumps({
    "n_ledger_records": n_ledger,
    "n_settlement_records": n_settlement,
    "naive_O(n*m)_comparisons": naive_comparisons,
    "candidate_pairs_generated": len(candidates),
    "reduction_factor": round(naive_comparisons / max(len(candidates), 1), 1),
    "avg_candidates_per_ledger_record": round(len(candidates) / n_ledger, 2),
    "true_pairs_in_hidden_match_map": total_true_pairs,
    "true_pairs_recovered_by_blocking": recovered,
    "candidate_generation_recall": round(recall, 4),
    "n_lost_pairs": len(lost_examples),
}, indent=2))

if lost_examples:
    print("\nSample of TRUE pairs lost during blocking (first 5):")
    for l, s, gt in lost_examples[:5]:
        print(f"  ledger={l} settlement={s} gt_txn_id={gt}")
