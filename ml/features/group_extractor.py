"""
ReconLens — unified group-level feature extraction (Phase 4).

Generalizes Phase 2's pairwise extractor to candidates of ANY shape:
one-to-one (1 ledger, 1 settlement), one-to-many (1 ledger, N settlement),
many-to-one (N ledger, 1 settlement). A (1,1) candidate is defined to reduce
EXACTLY to the original Phase 2 pairwise feature values — verified by
test_group_features_backward_compatible_with_pairwise in
backend/tests/test_phase4.py, not just claimed.

AGGREGATION RULES (documented here because §13 of the Phase 4 spec requires
every rule to be explicit, not implied):

- Amount features: computed on COMBINED amounts (sum of all ledger member
  amounts vs sum of all settlement member amounts) — this is the correct
  generalization, not an aggregation of pairwise amount diffs, because the
  business question for a batch is "does the total match", not "does any
  individual pair's amount match."

- Date features: group_date_span = (latest date - earliest date) across
  ALL member records (ledger and settlement combined). For a (1,1) candidate
  this is |settlement_date - ledger_date|, i.e. exactly date_diff_days.

- String/semantic/reference similarity features: computed on EVERY
  (ledger_member, settlement_member) pair within the group, then reduced by
  MAX. Max, not mean, because the question is "is there strong evidence
  connecting this group's ledger side to its settlement side" — a single
  strongly-matching pair is meaningful signal even if other cross-pairs
  (which aren't the "real" correspondence within a split/batch) look
  unrelated; averaging would dilute genuine evidence with irrelevant
  cross-terms. For a (1,1) candidate max over one pair is just that pair's
  value, so this reduces to the Phase 2 pairwise value exactly.

- reference_missing_ledger / reference_missing_settlement: 1 only if ALL
  members on that side are missing a reference — if even one member has a
  reference, the group has some reference evidence to work with, captured
  by the max-based reference_exact_match / reference_substring_overlap
  above. For a (1,1) candidate this is exactly the original definition.

- Structural features: group_size = max(len(ledger_ids), len(settlement_ids)).
  candidate_count_for_ledger / candidate_count_for_settlement are redefined
  at the GROUP level: the number of distinct candidate groups (pairwise or
  structural) in the full candidate pool that share at least one ledger id
  / settlement id with this group. For a (1,1) candidate restricted to the
  V1-only pool this matches Phase 2's original definition exactly; when the
  full V1+V2 pool is used (Phase 4), the count now also reflects structural
  competition, which is new information Phase 2 didn't have access to.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from ml.features.normalize import normalize_vendor
from ml.features.numeric import parse_date
from ml.features.string_similarity import (
    vendor_levenshtein_similarity, vendor_jaro_winkler_similarity,
    vendor_token_sort_similarity, vendor_token_set_similarity, vendor_exact_normalized_match,
)
from ml.features.reference import (
    reference_exact_match, reference_substring_overlap, reference_similarity,
    reference_missing_ledger as ref_missing_l, reference_missing_settlement as ref_missing_s,
)
from ml.features.embeddings import get_shared_backend, EmbeddingCache, cosine_similarity


@dataclass
class CandidateGroup:
    ledger_ids: tuple
    settlement_ids: tuple

    @property
    def group_size(self) -> int:
        return max(len(self.ledger_ids), len(self.settlement_ids))

    @property
    def relationship_type_candidate(self) -> str:
        if len(self.ledger_ids) == 1 and len(self.settlement_ids) == 1:
            return "one_to_one"
        if len(self.ledger_ids) == 1 and len(self.settlement_ids) > 1:
            return "one_to_many"
        if len(self.ledger_ids) > 1 and len(self.settlement_ids) == 1:
            return "many_to_one"
        return "other"  # not produced by V1/V2, but handled rather than silently mis-tagged


def build_all_candidate_groups(v1_pairs: list[tuple], v2_structural: list) -> list[CandidateGroup]:
    groups = [CandidateGroup(ledger_ids=(l,), settlement_ids=(s,)) for l, s in v1_pairs]
    groups += [CandidateGroup(ledger_ids=c.ledger_ids, settlement_ids=c.settlement_ids) for c in v2_structural]
    return groups


def extract_group_features(
    groups: list[CandidateGroup], ledger_idx: pd.DataFrame, settlement_idx: pd.DataFrame,
    has_description: bool,
) -> pd.DataFrame:
    backend = get_shared_backend()
    cache = EmbeddingCache(backend.backend_name)

    def embed(text: str) -> np.ndarray:
        cached = cache.get(text)
        if cached is not None:
            return cached
        v = backend.encode(text)
        cache.put(text, v)
        return v

    # Group-membership counts over the FULL candidate pool, computed once up front
    # (not per-row) for efficiency, per spec §30 performance guidance.
    ledger_group_count: dict[str, int] = {}
    settlement_group_count: dict[str, int] = {}
    for g in groups:
        for lid in g.ledger_ids:
            ledger_group_count[lid] = ledger_group_count.get(lid, 0) + 1
        for sid in g.settlement_ids:
            settlement_group_count[sid] = settlement_group_count.get(sid, 0) + 1

    rows = []
    for g in groups:
        led_rows = [ledger_idx.loc[lid] for lid in g.ledger_ids]
        stl_rows = [settlement_idx.loc[sid] for sid in g.settlement_ids]

        combined_ledger_amount = sum(r["amount"] for r in led_rows)
        combined_settlement_amount = sum(r["amount"] for r in stl_rows)
        if combined_ledger_amount <= 0:
            raise ValueError(f"Non-positive combined ledger amount for group {g}: {combined_ledger_amount}")

        group_amount_difference = abs(combined_ledger_amount - combined_settlement_amount)
        group_relative_amount_difference = group_amount_difference / combined_ledger_amount
        amount_ratio = combined_settlement_amount / combined_ledger_amount

        all_dates = [parse_date(r["txn_date"]) for r in led_rows + stl_rows]
        group_date_span = (max(all_dates) - min(all_dates)).days

        # Max-reduced pairwise evidence across every (ledger, settlement) member pair.
        best = {
            "vendor_levenshtein_similarity": 0.0, "vendor_jaro_winkler_similarity": 0.0,
            "vendor_token_sort_similarity": 0.0, "vendor_token_set_similarity": 0.0,
            "vendor_exact_normalized_match": 0, "vendor_embedding_cosine_similarity": -1.0,
            "reference_exact_match": 0, "reference_substring_overlap": 0, "reference_similarity": 0.0,
        }
        if has_description:
            best["description_embedding_cosine_similarity"] = -1.0

        for led in led_rows:
            norm_l_vendor = normalize_vendor(led["vendor_name"])
            vendor_emb_l = embed(norm_l_vendor)
            for stl in stl_rows:
                norm_s_vendor = normalize_vendor(stl["vendor_name"])
                vendor_emb_s = embed(norm_s_vendor)

                best["vendor_levenshtein_similarity"] = max(best["vendor_levenshtein_similarity"],
                    vendor_levenshtein_similarity(norm_l_vendor, norm_s_vendor))
                best["vendor_jaro_winkler_similarity"] = max(best["vendor_jaro_winkler_similarity"],
                    vendor_jaro_winkler_similarity(norm_l_vendor, norm_s_vendor))
                best["vendor_token_sort_similarity"] = max(best["vendor_token_sort_similarity"],
                    vendor_token_sort_similarity(norm_l_vendor, norm_s_vendor))
                best["vendor_token_set_similarity"] = max(best["vendor_token_set_similarity"],
                    vendor_token_set_similarity(norm_l_vendor, norm_s_vendor))
                best["vendor_exact_normalized_match"] = max(best["vendor_exact_normalized_match"],
                    vendor_exact_normalized_match(norm_l_vendor, norm_s_vendor))
                best["vendor_embedding_cosine_similarity"] = max(best["vendor_embedding_cosine_similarity"],
                    cosine_similarity(vendor_emb_l, vendor_emb_s))
                best["reference_exact_match"] = max(best["reference_exact_match"],
                    reference_exact_match(led["reference_id"], stl["reference_id"]))
                best["reference_substring_overlap"] = max(best["reference_substring_overlap"],
                    reference_substring_overlap(led["reference_id"], stl["reference_id"]))
                best["reference_similarity"] = max(best["reference_similarity"],
                    reference_similarity(led["reference_id"], stl["reference_id"]))

                if has_description:
                    desc_emb_l = embed(str(led.get("description", "")) or "")
                    desc_emb_s = embed(str(stl.get("description", "")) or "")
                    best["description_embedding_cosine_similarity"] = max(
                        best["description_embedding_cosine_similarity"], cosine_similarity(desc_emb_l, desc_emb_s))

        reference_missing_ledger = int(all(ref_missing_l(r["reference_id"]) for r in led_rows))
        reference_missing_settlement = int(all(ref_missing_s(r["reference_id"]) for r in stl_rows))
        reference_both_missing = int(reference_missing_ledger and reference_missing_settlement)

        cand_count_ledger = max(ledger_group_count[lid] for lid in g.ledger_ids)
        cand_count_settlement = max(settlement_group_count[sid] for sid in g.settlement_ids)

        row = {
            "ledger_public_id": "|".join(g.ledger_ids),
            "settlement_public_id": "|".join(g.settlement_ids),
            "group_size": g.group_size,
            "relationship_type_candidate": g.relationship_type_candidate,
            "is_potential_one_to_many": int(len(g.settlement_ids) > 1),
            "is_potential_many_to_one": int(len(g.ledger_ids) > 1),

            "abs_amount_diff": round(group_amount_difference, 4),
            "relative_amount_diff": round(group_relative_amount_difference, 6),
            "amount_ratio": round(amount_ratio, 6),
            "date_diff_days": group_date_span,

            **{k: (round(v, 6) if isinstance(v, float) else v) for k, v in best.items()},

            "reference_missing_ledger": reference_missing_ledger,
            "reference_missing_settlement": reference_missing_settlement,
            "reference_both_missing": reference_both_missing,

            "candidate_count_for_ledger": cand_count_ledger,
            "candidate_count_for_settlement": cand_count_settlement,
            "competing_candidate_count": (cand_count_ledger - 1) + (cand_count_settlement - 1),
        }
        rows.append(row)

    cache.flush()
    df = pd.DataFrame(rows)
    metadata = {"embedding_backend": backend.backend_name, "embedding_dim": backend.dim,
                "n_groups": len(groups), "has_description_feature": has_description}
    return df, metadata
