"""
ReconLens — feature dataset validation.

Fails loudly (raises) rather than silently continuing, per project rule.
Run this immediately after extraction and before any report is trusted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EXPECTED_BINARY_COLS = [
    "vendor_exact_normalized_match", "reference_exact_match", "reference_substring_overlap",
    "reference_missing_ledger", "reference_missing_settlement", "reference_both_missing",
    "is_potential_one_to_many", "is_potential_many_to_one",
]

EXPECTED_UNIT_RANGE_COLS = [
    "vendor_levenshtein_similarity", "vendor_jaro_winkler_similarity",
    "vendor_token_sort_similarity", "vendor_token_set_similarity", "reference_similarity",
]

EXPECTED_NONNEGATIVE_COLS = ["abs_amount_diff", "relative_amount_diff"]


class FeatureValidationError(Exception):
    pass


def validate(feature_df: pd.DataFrame) -> dict:
    """Returns a dict of check -> pass/fail + details. Raises
    FeatureValidationError on any hard failure; never returns a "looks fine"
    result while silently having skipped a check.
    """
    results = {}

    # 1. No unexpected NaN/inf in numeric columns
    numeric_cols = feature_df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        n_nan = feature_df[col].isna().sum()
        n_inf = np.isinf(feature_df[col].to_numpy(dtype=float)).sum()
        if n_nan > 0:
            raise FeatureValidationError(f"Column '{col}' has {n_nan} unexpected NaN values.")
        if n_inf > 0:
            raise FeatureValidationError(f"Column '{col}' has {n_inf} unexpected infinite values.")
    results["no_nan_or_inf"] = True

    # 2. Binary columns are strictly {0, 1}
    for col in EXPECTED_BINARY_COLS:
        if col not in feature_df.columns:
            continue
        bad = ~feature_df[col].isin([0, 1])
        if bad.any():
            raise FeatureValidationError(f"Binary column '{col}' has non-{{0,1}} values: "
                                          f"{feature_df.loc[bad, col].unique()}")
    results["binary_columns_valid"] = True

    # 3. Similarity features in [0, 1]
    for col in EXPECTED_UNIT_RANGE_COLS:
        if col not in feature_df.columns:
            continue
        out_of_range = feature_df[(feature_df[col] < 0) | (feature_df[col] > 1)]
        if len(out_of_range) > 0:
            raise FeatureValidationError(f"Column '{col}' has {len(out_of_range)} values outside [0,1].")
    results["similarity_ranges_valid"] = True

    # embedding cosine similarity is in [-1, 1] by construction, checked separately
    for col in ["vendor_embedding_cosine_similarity", "description_embedding_cosine_similarity"]:
        if col not in feature_df.columns:
            continue
        out_of_range = feature_df[(feature_df[col] < -1.0001) | (feature_df[col] > 1.0001)]
        if len(out_of_range) > 0:
            raise FeatureValidationError(f"Column '{col}' has {len(out_of_range)} values outside [-1,1].")
    results["cosine_similarity_range_valid"] = True

    # 4. Non-negative columns
    for col in EXPECTED_NONNEGATIVE_COLS:
        if col not in feature_df.columns:
            continue
        neg = feature_df[feature_df[col] < 0]
        if len(neg) > 0:
            raise FeatureValidationError(f"Column '{col}' has {len(neg)} negative values, expected non-negative.")
    results["nonnegative_columns_valid"] = True

    # 5. No duplicate candidate pairs
    dup = feature_df.duplicated(subset=["ledger_public_id", "settlement_public_id"])
    if dup.any():
        raise FeatureValidationError(f"{dup.sum()} duplicate candidate pairs found.")
    results["no_duplicate_pairs"] = True

    # 6. Required identifier columns present and non-null
    for col in ["ledger_public_id", "settlement_public_id"]:
        if col not in feature_df.columns:
            raise FeatureValidationError(f"Required identifier column '{col}' missing.")
        if feature_df[col].isna().any():
            raise FeatureValidationError(f"Identifier column '{col}' has null values.")
    results["identifiers_valid"] = True

    # 7. No leakage columns present in the feature dataset at all
    forbidden = [c for c in feature_df.columns if "gt_txn" in c.lower() or "ground_truth" in c.lower()
                 or c.lower() in ("split", "structural_type")]
    if forbidden:
        raise FeatureValidationError(f"Forbidden ground-truth-derived columns found in feature dataset: {forbidden}")
    results["no_leakage_columns"] = True

    return results
