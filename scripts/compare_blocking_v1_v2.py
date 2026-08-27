"""
ReconLens — V1 vs V2 candidate-generation comparison.

EVALUATION-ONLY (reads _hidden_match_map.json). Never imported by feature,
candidate-generation, or training code.
"""
import json
import time
from pathlib import Path

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from ml.candidate_generation.blocking_v1 import generate_candidates as blocking_v1
from ml.candidate_generation.blocking_v2 import generate_structural_candidates

ROOT = Path(__file__).parent.parent
ledger_df = pd.read_csv(ROOT / "data/raw/ledger.csv")
settlement_df = pd.read_csv(ROOT / "data/raw/settlement.csv")
match_map = json.load(open(ROOT / "data/raw/_hidden_match_map.json"))


def classify(entry):
    n_led, n_stl = len(entry["ledger_ids"]), len(entry["settlement_ids"])
    if n_led == 1 and n_stl == 1:
        return "ONE_TO_ONE"
    if n_led == 1 and n_stl > 1:
        return "ONE_TO_MANY"
    if n_led > 1 and n_stl == 1:
        return "MANY_TO_ONE"
    return "OTHER"


def measure(pair_candidate_set, group_candidate_sets):
    """pair_candidate_set: set of (ledger_id, settlement_id) from V1.
    group_candidate_sets: set of (frozenset(ledger_ids), frozenset(settlement_ids)) from V2.
    A true group counts as recovered if V1 covers all its exploded pairs,
    OR V2 produced the exact matching group.
    """
    total_true_pairs, recovered_pairs = 0, 0
    per_type = {"ONE_TO_ONE": [0, 0], "ONE_TO_MANY": [0, 0], "MANY_TO_ONE": [0, 0]}

    for entry in match_map:
        rel_type = classify(entry)
        led_ids, stl_ids = frozenset(entry["ledger_ids"]), frozenset(entry["settlement_ids"])
        group_pairs = [(l, s) for l in led_ids for s in stl_ids]

        v1_full = all((l, s) in pair_candidate_set for l, s in group_pairs)
        v2_full = (led_ids, stl_ids) in group_candidate_sets
        fully_recovered = v1_full or v2_full

        for l, s in group_pairs:
            total_true_pairs += 1
            if (l, s) in pair_candidate_set or v2_full:
                recovered_pairs += 1

        if rel_type in per_type:
            per_type[rel_type][1] += 1
            if fully_recovered:
                per_type[rel_type][0] += 1

    return {
        "pair_level_recall": round(recovered_pairs / total_true_pairs, 4),
        "recovered_pairs": recovered_pairs,
        "total_true_pairs": total_true_pairs,
        "group_recall_by_type": {
            k: {"fully_recovered": v[0], "total": v[1], "recall": round(v[0] / v[1], 4) if v[1] else None}
            for k, v in per_type.items()
        },
    }


# --- V1 ---
t0 = time.time()
v1_pairs = blocking_v1(ledger_df, settlement_df)
v1_runtime = time.time() - t0
v1_pair_set = set(v1_pairs)
v1_metrics = measure(v1_pair_set, set())
v1_metrics.update({
    "candidate_count": len(v1_pairs),
    "runtime_seconds": round(v1_runtime, 4),
    "avg_candidates_per_ledger_record": round(len(v1_pairs) / len(ledger_df), 3),
})

# --- V1 + V2 (union; V2 is additive, never a replacement) ---
t0 = time.time()
v2_structural = generate_structural_candidates(ledger_df, settlement_df)
v2_runtime = time.time() - t0
v2_group_set = {(frozenset(c.ledger_ids), frozenset(c.settlement_ids)) for c in v2_structural}
combined_metrics = measure(v1_pair_set, v2_group_set)
# candidate "volume" for V1+V2: V1 pairs + V2 structural groups counted as units
combined_metrics.update({
    "candidate_count": len(v1_pairs) + len(v2_structural),
    "v1_pair_candidates": len(v1_pairs),
    "v2_structural_candidates": len(v2_structural),
    "v2_many_to_one_candidates": sum(1 for c in v2_structural if c.relationship_type_candidate == "many_to_one"),
    "v2_one_to_many_candidates": sum(1 for c in v2_structural if c.relationship_type_candidate == "one_to_many"),
    "runtime_seconds": round(v1_runtime + v2_runtime, 4),
    "v2_runtime_seconds": round(v2_runtime, 4),
})

result = {"V1": v1_metrics, "V1_plus_V2": combined_metrics}
print(json.dumps(result, indent=2))

out_dir = ROOT / "reports" / "phase3"
out_dir.mkdir(parents=True, exist_ok=True)
with open(out_dir / "v1_vs_v2_comparison.json", "w") as f:
    json.dump(result, f, indent=2)
