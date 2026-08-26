"""
ReconLens — string similarity features on normalized vendor names.

All similarities are normalized into [0, 1], 1.0 = identical. Computed on
*normalized* vendor names (see normalize.py) — comparing raw strings would
conflate "different casing" with "different entity," which is exactly what
normalization exists to separate out before we measure genuine similarity.
"""

from __future__ import annotations

from rapidfuzz import fuzz


def vendor_levenshtein_similarity(norm_a: str, norm_b: str) -> float:
    """RapidFuzz's ratio() is Indel-distance-based, normalized to [0,100];
    rescaled to [0,1] here for consistency with the other similarity features.
    """
    if not norm_a and not norm_b:
        return 1.0  # both empty after normalization: treat as trivially equal,
                    # but this should be rare — normalize_vendor only returns
                    # "" for a genuinely empty/NaN raw name, which is itself
                    # a data-quality issue the row-level validator should flag.
    if not norm_a or not norm_b:
        return 0.0
    return round(fuzz.ratio(norm_a, norm_b) / 100.0, 6)


def vendor_jaro_winkler_similarity(norm_a: str, norm_b: str) -> float:
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0
    from rapidfuzz.distance import JaroWinkler
    return round(JaroWinkler.normalized_similarity(norm_a, norm_b), 6)


def vendor_token_sort_similarity(norm_a: str, norm_b: str) -> float:
    """Handles word-order differences ("Industries Reliance" vs "Reliance
    Industries") that plain Levenshtein penalizes heavily but that are
    common artifacts of how different systems concatenate name fields.
    """
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0
    return round(fuzz.token_sort_ratio(norm_a, norm_b) / 100.0, 6)


def vendor_token_set_similarity(norm_a: str, norm_b: str) -> float:
    """Handles subset relationships ("Reliance Industries" contained within
    "Reliance Industries Retail Division") where token_sort would still
    penalize the extra tokens.
    """
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0
    return round(fuzz.token_set_ratio(norm_a, norm_b) / 100.0, 6)


def vendor_exact_normalized_match(norm_a: str, norm_b: str) -> int:
    """Binary input feature only — never the reconciliation decision itself.
    Two records can have identical normalized vendor names and still be
    different transactions (same vendor, different invoice); this feature
    exists so the classifier can weigh it alongside amount/date/reference
    evidence, not decide on it alone.
    """
    if not norm_a or not norm_b:
        return 0
    return int(norm_a == norm_b)
