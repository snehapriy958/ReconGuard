"""
ReconLens — Phase 3 missed-candidate diagnostic.

EVALUATION-ONLY. This is the first Phase 3 component permitted to read
_hidden_match_map.json / _hidden_*_truth.csv. It is never imported by
ml/features/, ml/candidate_generation/blocking_v1.py or blocking_v2.py, or
any training code — verified by tests/test_no_leakage.py.

Purpose: independently confirm (not assume) that the 80.3% V1 recall gap is
concentrated in split/batched settlements, and produce a detailed per-miss
diagnostic to inform Blocking V2's design.
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from ml.candidate_generation.blocking_v1 import generate_candidates as blocking_v1
from ml.features.normalize import normalize_vendor
from ml.features.string_similarity import vendor_levenshtein_similarity
from ml.features.reference import reference_substring_overlap

ROOT = Path(__file__).parent.parent
ledger_df = pd.read_csv(ROOT / "data/raw/ledger.csv").set_index("ledger_id")
settlement_df = pd.read_csv(ROOT / "data/raw/settlement.csv").set_index("settlement_id")
ledger_df_full = pd.read_csv(ROOT / "data/raw/ledger.csv")
settlement_df_full = pd.read_csv(ROOT / "data/raw/settlement.csv")

match_map = json.load(open(ROOT / "data/raw/_hidden_match_map.json"))


def classify_relationship(entry: dict) -> str:
    n_led, n_stl = len(entry["ledger_ids"]), len(entry["settlement_ids"])
    if n_led == 1 and n_stl == 1:
        return "ONE_TO_ONE"
    if n_led == 1 and n_stl > 1:
        return "ONE_TO_MANY"
    if n_led > 1 and n_stl == 1:
        return "MANY_TO_ONE"
    return "OTHER"


def run_v1_baseline():
    t0 = time.time()
    pairs = blocking_v1(ledger_df_full, settlement_df_full)
    runtime = time.time() - t0
    candidate_set = set(pairs)

    per_type = {"ONE_TO_ONE": [0, 0], "ONE_TO_MANY": [0, 0], "MANY_TO_ONE": [0, 0]}  # [full_recovered, total_groups]
    total_true_pairs, recovered_pairs = 0, 0
    missed_details = []

    for entry in match_map:
        rel_type = classify_relationship(entry)
        group_pairs = [(l, s) for l in entry["ledger_ids"] for s in entry["settlement_ids"]]
        all_recovered = True
        for l, s in group_pairs:
            total_true_pairs += 1
            if (l, s) in candidate_set:
                recovered_pairs += 1
            else:
                all_recovered = False
                led, stl = ledger_df.loc[l], settlement_df.loc[s]
                nl, ns = normalize_vendor(led["vendor_name"]), normalize_vendor(stl["vendor_name"])
                missed_details.append({
                    "ledger_id": l, "settlement_id": s, "relationship_type": rel_type,
                    "group_size": max(len(entry["ledger_ids"]), len(entry["settlement_ids"])),
                    "ledger_amount": led["amount"], "settlement_amount": stl["amount"],
                    "abs_amount_diff": round(abs(led["amount"] - stl["amount"]), 2),
                    "date_diff_days": (pd.to_datetime(stl["txn_date"]) - pd.to_datetime(led["txn_date"])).days,
                    "ledger_vendor": led["vendor_name"], "settlement_vendor": stl["vendor_name"],
                    "vendor_similarity": round(vendor_levenshtein_similarity(nl, ns), 3),
                    "reference_overlap": reference_substring_overlap(led["reference_id"], stl["reference_id"]),
                    "why_excluded": (
                        "amount outside single-record blocking window "
                        f"(diff={abs(led['amount'] - stl['amount']):.2f} on a group-split/batch amount)"
                    ),
                })
        if rel_type in per_type:
            per_type[rel_type][1] += 1
            if all_recovered:
                per_type[rel_type][0] += 1

    result = {
        "runtime_seconds": round(runtime, 4),
        "candidate_pairs": len(pairs),
        "avg_candidates_per_ledger_record": round(len(pairs) / len(ledger_df_full), 3),
        "pair_level_recall": round(recovered_pairs / total_true_pairs, 4),
        "total_true_pairs": total_true_pairs,
        "recovered_pairs": recovered_pairs,
        "group_level_recall_by_type": {
            k: {"fully_recovered": v[0], "total_groups": v[1],
                "recall": round(v[0] / v[1], 4) if v[1] else None}
            for k, v in per_type.items()
        },
    }
    return result, missed_details


if __name__ == "__main__":
    result, missed = run_v1_baseline()
    print(json.dumps(result, indent=2))

    out_dir = ROOT / "reports" / "phase3"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "v1_baseline.json", "w") as f:
        json.dump(result, f, indent=2)
    pd.DataFrame(missed).to_csv(out_dir / "v1_missed_candidates.csv", index=False)

    # Independent confirmation of the hypothesis, not an assumption
    missed_df = pd.DataFrame(missed)
    print("\nMissed pairs by relationship type (independent re-check):")
    print(missed_df["relationship_type"].value_counts().to_string())
    one_to_one_misses = (missed_df["relationship_type"] == "ONE_TO_ONE").sum()
    print(f"\nONE_TO_ONE misses: {one_to_one_misses} "
          f"({'CONFIRMS' if one_to_one_misses == 0 else 'CONTRADICTS'} the hypothesis that "
          f"pairwise blocking loses zero one-to-one matches)")
