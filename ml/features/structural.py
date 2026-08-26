"""
ReconLens — structural features.

These describe the shape of the *candidate set* around a pair, not the true
underlying relationship (one-to-one/split/batched) — that ground truth is
hidden by design (see Phase 1). A ledger record that has 3 settlement
candidates within the blocking window doesn't tell us whether it's genuinely
a split settlement or just an ambiguous coincidence; it tells the classifier
"this pair is competing against N alternatives," which is real, observable
signal it can legitimately use.
"""

from __future__ import annotations

from collections import Counter


def compute_structural_features(candidate_pairs: list[tuple[str, str]]) -> dict[tuple[str, str], dict]:
    """candidate_pairs: list of (ledger_public_id, settlement_public_id) tuples
    surviving candidate generation (blocking). Returns a dict keyed by the
    same tuple with structural features for that pair.
    """
    ledger_counts = Counter(l for l, s in candidate_pairs)
    settlement_counts = Counter(s for l, s in candidate_pairs)

    out = {}
    for l, s in candidate_pairs:
        cand_count_ledger = ledger_counts[l]
        cand_count_settlement = settlement_counts[s]
        out[(l, s)] = {
            "candidate_count_for_ledger": cand_count_ledger,
            "candidate_count_for_settlement": cand_count_settlement,
            # total distinct alternative records this pair is competing against
            "competing_candidate_count": (cand_count_ledger - 1) + (cand_count_settlement - 1),
            # observable hint, NOT ground truth: this ledger record has multiple
            # settlement candidates, consistent with (but not proof of) a split
            "is_potential_one_to_many": int(cand_count_ledger > 1),
            # observable hint: this settlement record has multiple ledger
            # candidates, consistent with (but not proof of) a batch
            "is_potential_many_to_one": int(cand_count_settlement > 1),
        }
    return out
