"""
ReconLens — candidate generation, V2 (structural).

V1 (blocking_v1.py) only ever compares ONE ledger record against ONE
settlement record, so it cannot represent "ledger A + ledger B -> settlement
X" or "ledger A -> settlement X + settlement Y" — confirmed by
scripts/diagnose_missed_candidates.py to be the entire cause of the 80.3%
V1 recall gap (100% one-to-one recall, 0% on both structural types).

V2 adds a SEPARATE, ADDITIONAL candidate-generation pass for exactly those
two relationship shapes. It does not replace V1 — the two candidate sets are
unioned. V1 stays untouched (see blocking_v1.py's frozen-baseline docstring).

Design constraint from the spec: bounded combinations only, no unrestricted
combinatorial search. Group size and amount tolerance are both configurable
and both documented below rather than tuned silently until recall looked good.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import pandas as pd

from ml.features.normalize import normalize_vendor

MAX_GROUP_SIZE = 3          # bounded per spec section 9; matches the generator's own max batch/split size
DATE_WINDOW_DAYS = 4        # Phase 1's batch generator now clusters group members within
                            # MAX_BATCH_DATE_SPAN_DAYS=3 of each other (fixed after a real bug — see
                            # docs/architecture.md Phase 3 notes). 4 days gives a 1-day margin over
                            # that guarantee without the wide window this used to need to compensate
                            # for the old, unrealistic date spread.
RELATIVE_TOLERANCE = 0.025  # matches the generator's known fee-deduction ceiling (0.5%-2.5%) exactly,
                            # rather than padding past it. Measured on this dataset: 0.03/₹10 and
                            # 0.025/₹7 both hit 100% structural recall, but 0.025/₹7 does it with ~16%
                            # fewer candidates (9,838 vs 11,762) — see
                            # scripts/compare_blocking_v1_v2.py sweep results in docs/architecture.md.
                            # Tightening further (0.02/₹5 or below) starts losing many-to-one recall
                            # (12/14, 10/14), which is why this is the floor, not an arbitrary middle value.
ABSOLUTE_TOLERANCE_FLOOR = 7.0

# DESIGN NOTE — vendor pre-filtering was tried and dropped:
# An earlier version of this module bucketed candidates by exact-normalized-vendor
# match before searching amount combinations. Measured recall was only 27.8%
# (one-to-many) and 15.4% (many-to-one) against the >95% target. Diagnosis
# (scripts/compare_blocking_v1_v2.py output + direct inspection) showed why:
# vendor corruption is applied INDEPENDENTLY per record (see generate.py), so
# members of the SAME true group can normalize to different strings entirely
# — e.g. one true many-to-one group had settlement vendor "ADANIENT" against
# ledger vendors "Adani Enterprises" / "Adani Enteprrises" / "Adani Enterprises"
# — none of which match the settlement's normalized form. A group is only as
# strong as its weakest corrupted member, so requiring ALL members to agree
# on normalized vendor was rejecting genuine groups whenever even one member
# corrupted to a divergent abbreviation. Fix: drop the vendor gate entirely
# for structural search; amount-sum + date window are the features that
# actually constrain this problem (an exact rupee-level sum match within a
# tight date window is already a strong filter on its own), and vendor
# similarity is left as a per-candidate FEATURE for the classifier to weigh,
# not a pre-filter that can silently kill a true candidate.


@dataclass
class StructuralCandidate:
    ledger_ids: tuple
    settlement_ids: tuple
    relationship_type_candidate: str  # "many_to_one" or "one_to_many"
    group_size: int
    combined_ledger_amount: float
    combined_settlement_amount: float
    group_amount_difference: float
    group_relative_amount_difference: float


def _within_tolerance(a: float, b: float) -> bool:
    tol = max(abs(a) * RELATIVE_TOLERANCE, ABSOLUTE_TOLERANCE_FLOOR)
    return abs(a - b) <= tol


def _vendor_bucket_key(vendor_raw: str) -> str:
    # No longer used as a pre-filter gate (see design note above) — kept as a
    # small utility in case a future phase wants a soft vendor-similarity
    # feature on structural candidates without re-deriving normalization.
    return normalize_vendor(vendor_raw)


def generate_many_to_one_candidates(ledger_df: pd.DataFrame, settlement_df: pd.DataFrame) -> list[StructuralCandidate]:
    """N ledger records (2..MAX_GROUP_SIZE) -> 1 settlement record."""
    ledger_df = ledger_df.copy()
    ledger_df["date_"] = pd.to_datetime(ledger_df["txn_date"])
    settlement_df = settlement_df.copy()
    settlement_df["date_"] = pd.to_datetime(settlement_df["txn_date"])

    candidates = []
    for _, stl in settlement_df.iterrows():
        bucket = ledger_df[
            (ledger_df["date_"] <= stl["date_"]) &
            (ledger_df["date_"] >= stl["date_"] - pd.Timedelta(days=DATE_WINDOW_DAYS)) &
            (ledger_df["amount"] < stl["amount"])  # any single component must be less than the combined total
        ]
        if len(bucket) < 2:
            continue
        for group_size in range(2, MAX_GROUP_SIZE + 1):
            for combo in combinations(bucket.itertuples(), group_size):
                combined = sum(c.amount for c in combo)
                if _within_tolerance(combined, stl["amount"]):
                    ledger_ids = tuple(sorted(c.ledger_id for c in combo))
                    diff = round(abs(combined - stl["amount"]), 4)
                    candidates.append(StructuralCandidate(
                        ledger_ids=ledger_ids,
                        settlement_ids=(stl["settlement_id"],),
                        relationship_type_candidate="many_to_one",
                        group_size=group_size,
                        combined_ledger_amount=round(combined, 2),
                        combined_settlement_amount=round(stl["amount"], 2),
                        group_amount_difference=diff,
                        group_relative_amount_difference=round(diff / max(combined, 1e-9), 6),
                    ))
    return candidates


def generate_one_to_many_candidates(ledger_df: pd.DataFrame, settlement_df: pd.DataFrame) -> list[StructuralCandidate]:
    """1 ledger record -> N settlement records (2..MAX_GROUP_SIZE)."""
    ledger_df = ledger_df.copy()
    ledger_df["date_"] = pd.to_datetime(ledger_df["txn_date"])
    settlement_df = settlement_df.copy()
    settlement_df["date_"] = pd.to_datetime(settlement_df["txn_date"])

    candidates = []
    for led in ledger_df.itertuples():
        bucket = settlement_df[
            (settlement_df["date_"] >= led.date_) &
            (settlement_df["date_"] <= led.date_ + pd.Timedelta(days=DATE_WINDOW_DAYS)) &
            (settlement_df["amount"] < led.amount)
        ]
        if len(bucket) < 2:
            continue
        for group_size in range(2, MAX_GROUP_SIZE + 1):
            for combo in combinations(bucket.itertuples(), group_size):
                combined = sum(c.amount for c in combo)
                if _within_tolerance(combined, led.amount):
                    settlement_ids = tuple(sorted(c.settlement_id for c in combo))
                    diff = round(abs(combined - led.amount), 4)
                    candidates.append(StructuralCandidate(
                        ledger_ids=(led.ledger_id,),
                        settlement_ids=settlement_ids,
                        relationship_type_candidate="one_to_many",
                        group_size=group_size,
                        combined_ledger_amount=round(led.amount, 2),
                        combined_settlement_amount=round(combined, 2),
                        group_amount_difference=diff,
                        group_relative_amount_difference=round(diff / max(led.amount, 1e-9), 6),
                    ))
    return candidates


def generate_structural_candidates(ledger_df: pd.DataFrame, settlement_df: pd.DataFrame) -> list[StructuralCandidate]:
    return (generate_many_to_one_candidates(ledger_df, settlement_df) +
            generate_one_to_many_candidates(ledger_df, settlement_df))
