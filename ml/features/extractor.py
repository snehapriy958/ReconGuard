"""
ReconLens — feature extractor.

Assembles candidate pairs + all feature modules into the ML-ready dataset.
Reads ONLY data/raw/ledger.csv and data/raw/settlement.csv. Never imports
anything from the _hidden_* files — enforced structurally (this module has
no code path that opens them) and checked explicitly by
tests/test_no_leakage.py, which scans this file's source for the substring
"_hidden" and fails the build if it's found outside a comment.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ml.features.normalize import normalize_vendor, is_missing_reference
from ml.features.numeric import abs_amount_diff, relative_amount_diff, amount_ratio, date_diff_days
from ml.features.string_similarity import (
    vendor_levenshtein_similarity, vendor_jaro_winkler_similarity,
    vendor_token_sort_similarity, vendor_token_set_similarity, vendor_exact_normalized_match,
)
from ml.features.reference import (
    reference_exact_match, reference_substring_overlap, reference_similarity,
    reference_missing_ledger, reference_missing_settlement, reference_both_missing,
)
from ml.features.embeddings import EmbeddingBackend, EmbeddingCache, cosine_similarity
from ml.features.structural import compute_structural_features
from ml.features.candidate_generation import generate_candidates

ROOT = Path(__file__).parent.parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


def load_public_sources() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The ONLY function in this module allowed to touch data/raw/. Reads
    exactly two files, both public. Raises if asked to read anything with
    '_hidden' in the name — a defensive check, not just a convention.
    """
    ledger_path = RAW_DIR / "ledger.csv"
    settlement_path = RAW_DIR / "settlement.csv"
    for p in (ledger_path, settlement_path):
        if "_hidden" in p.name:
            raise RuntimeError("Refusing to load a hidden ground-truth file from feature extraction.")
    ledger_df = pd.read_csv(ledger_path)
    settlement_df = pd.read_csv(settlement_path)
    return ledger_df, settlement_df


def extract_features(ledger_df: pd.DataFrame, settlement_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    ledger_idx = ledger_df.set_index("ledger_id")
    settlement_idx = settlement_df.set_index("settlement_id")

    candidate_pairs = generate_candidates(ledger_df, settlement_df)
    structural = compute_structural_features(candidate_pairs)

    backend = EmbeddingBackend()
    cache = EmbeddingCache(backend.backend_name)

    def embed(text: str) -> np.ndarray:
        cached = cache.get(text)
        if cached is not None:
            return cached
        v = backend.encode(text)
        cache.put(text, v)
        return v

    has_description = "description" in ledger_df.columns and "description" in settlement_df.columns

    rows = []
    for ledger_id, settlement_id in candidate_pairs:
        led = ledger_idx.loc[ledger_id]
        stl = settlement_idx.loc[settlement_id]

        norm_l_vendor = normalize_vendor(led["vendor_name"])
        norm_s_vendor = normalize_vendor(stl["vendor_name"])

        vendor_emb_l = embed(norm_l_vendor)
        vendor_emb_s = embed(norm_s_vendor)

        row = {
            "ledger_public_id": ledger_id,
            "settlement_public_id": settlement_id,

            "abs_amount_diff": abs_amount_diff(led["amount"], stl["amount"]),
            "relative_amount_diff": relative_amount_diff(led["amount"], stl["amount"]),
            "amount_ratio": amount_ratio(led["amount"], stl["amount"]),
            "date_diff_days": date_diff_days(led["txn_date"], stl["txn_date"]),

            "vendor_levenshtein_similarity": vendor_levenshtein_similarity(norm_l_vendor, norm_s_vendor),
            "vendor_jaro_winkler_similarity": vendor_jaro_winkler_similarity(norm_l_vendor, norm_s_vendor),
            "vendor_token_sort_similarity": vendor_token_sort_similarity(norm_l_vendor, norm_s_vendor),
            "vendor_token_set_similarity": vendor_token_set_similarity(norm_l_vendor, norm_s_vendor),
            "vendor_exact_normalized_match": vendor_exact_normalized_match(norm_l_vendor, norm_s_vendor),

            "vendor_embedding_cosine_similarity": cosine_similarity(vendor_emb_l, vendor_emb_s),

            "reference_exact_match": reference_exact_match(led["reference_id"], stl["reference_id"]),
            "reference_substring_overlap": reference_substring_overlap(led["reference_id"], stl["reference_id"]),
            "reference_similarity": reference_similarity(led["reference_id"], stl["reference_id"]),
            "reference_missing_ledger": reference_missing_ledger(led["reference_id"]),
            "reference_missing_settlement": reference_missing_settlement(stl["reference_id"]),
            "reference_both_missing": reference_both_missing(led["reference_id"], stl["reference_id"]),

            **structural[(ledger_id, settlement_id)],
        }

        if has_description:
            desc_emb_l = embed(str(led.get("description", "")) or "")
            desc_emb_s = embed(str(stl.get("description", "")) or "")
            row["description_embedding_cosine_similarity"] = cosine_similarity(desc_emb_l, desc_emb_s)

        rows.append(row)

    cache.flush()

    feature_df = pd.DataFrame(rows)

    metadata = {
        "embedding_backend": backend.backend_name,
        "embedding_dim": backend.dim,
        "n_ledger_records": len(ledger_df),
        "n_settlement_records": len(settlement_df),
        "n_candidate_pairs": len(candidate_pairs),
        "avg_candidates_per_ledger_record": round(len(candidate_pairs) / max(len(ledger_df), 1), 3),
        "has_description_feature": has_description,
    }
    return feature_df, metadata


def run(out_path: Path = PROCESSED_DIR / "features.parquet") -> tuple[pd.DataFrame, dict]:
    ledger_df, settlement_df = load_public_sources()
    feature_df, metadata = extract_features(ledger_df, settlement_df)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    feature_df.to_parquet(out_path, index=False)
    feature_df.to_csv(out_path.with_suffix(".csv"), index=False)  # human-inspectable copy
    import json
    with open(out_path.with_suffix(".metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    return feature_df, metadata


if __name__ == "__main__":
    df, meta = run()
    print(f"Wrote {len(df)} feature rows, {len(df.columns)} columns.")
    print(meta)
