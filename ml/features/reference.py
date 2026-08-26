"""
ReconLens — reference-ID features.

The one rule this module exists to enforce: missing reference evidence is
NOT evidence of a match. "" == "" must never become reference_exact_match=1.
"""

from __future__ import annotations

from ml.features.normalize import normalize_reference, is_missing_reference


def reference_missing_ledger(raw_ledger_ref) -> int:
    return int(is_missing_reference(raw_ledger_ref))


def reference_missing_settlement(raw_settlement_ref) -> int:
    return int(is_missing_reference(raw_settlement_ref))


def reference_both_missing(raw_ledger_ref, raw_settlement_ref) -> int:
    return int(is_missing_reference(raw_ledger_ref) and is_missing_reference(raw_settlement_ref))


def reference_exact_match(raw_ledger_ref, raw_settlement_ref) -> int:
    if is_missing_reference(raw_ledger_ref) or is_missing_reference(raw_settlement_ref):
        return 0
    return int(normalize_reference(raw_ledger_ref) == normalize_reference(raw_settlement_ref))


def reference_substring_overlap(raw_ledger_ref, raw_settlement_ref) -> int:
    """Handles truncation: 'RZP839291' vs '839291' should register overlap
    even though they aren't equal length. Checks both directions since we
    don't know a priori which side truncates.
    """
    if is_missing_reference(raw_ledger_ref) or is_missing_reference(raw_settlement_ref):
        return 0
    a = normalize_reference(raw_ledger_ref)
    b = normalize_reference(raw_settlement_ref)
    if not a or not b:
        return 0
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return int(shorter in longer)


def reference_similarity(raw_ledger_ref, raw_settlement_ref) -> float:
    """A continuous companion to the binary overlap feature: longest common
    substring length / length of the longer reference. Robust to truncation
    from either end (unlike a plain prefix/suffix check), and to partial
    corruption in the middle.
    """
    if is_missing_reference(raw_ledger_ref) or is_missing_reference(raw_settlement_ref):
        return 0.0
    a = normalize_reference(raw_ledger_ref)
    b = normalize_reference(raw_settlement_ref)
    if not a or not b:
        return 0.0
    lcs_len = _longest_common_substring_len(a, b)
    return round(lcs_len / max(len(a), len(b)), 6)


def _longest_common_substring_len(a: str, b: str) -> int:
    # Standard DP longest-common-substring; reference IDs are short (<=20
    # chars in this dataset) so O(len(a)*len(b)) is trivially fast.
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    best = 0
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                best = max(best, dp[i][j])
    return best
