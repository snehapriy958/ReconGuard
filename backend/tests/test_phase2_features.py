import numpy as np
import pandas as pd
import pytest

from ml.features.normalize import normalize_vendor, normalize_reference, is_missing_reference
from ml.features.numeric import abs_amount_diff, relative_amount_diff, amount_ratio, date_diff_days
from ml.features.string_similarity import (
    vendor_levenshtein_similarity, vendor_jaro_winkler_similarity,
    vendor_token_sort_similarity, vendor_exact_normalized_match,
)
from ml.features.reference import (
    reference_exact_match, reference_substring_overlap, reference_both_missing,
)
from ml.features.embeddings import EmbeddingBackend, cosine_similarity

_backend = EmbeddingBackend()  # instantiate once per test session, not once per test —
                                # each instantiation attempts (and, offline, times out on)
                                # a network call before falling back; see embeddings.py


# ---------------- normalization ----------------

def test_normalize_case():
    assert normalize_vendor("HDFC BANK") == normalize_vendor("hdfc bank")

def test_normalize_whitespace():
    assert normalize_vendor("HDFC   Bank   Limited") == normalize_vendor("HDFC Bank Limited")

def test_normalize_punctuation():
    assert normalize_vendor("Reliance Industries, Ltd.") == normalize_vendor("Reliance Industries Ltd")

def test_normalize_legal_suffix():
    assert normalize_vendor("Reliance Industries Limited") == normalize_vendor("Reliance Industries Pvt Ltd") \
        or normalize_vendor("Reliance Industries Limited") == "reliance industries"

def test_normalize_unicode():
    assert normalize_vendor("Café Vendor") == normalize_vendor("Cafe\u0301 Vendor")  # NFKC should equalize combining accent


# ---------------- amount features ----------------

def test_amount_equal():
    assert abs_amount_diff(1000, 1000) == 0.0
    assert relative_amount_diff(1000, 1000) == 0.0
    assert amount_ratio(1000, 1000) == 1.0

def test_amount_small_drift():
    assert abs_amount_diff(1000, 998.5) == 1.5

def test_amount_large_drift():
    assert relative_amount_diff(1000, 800) == pytest.approx(0.2)

def test_amount_zero_raises():
    with pytest.raises(ValueError):
        relative_amount_diff(0, 100)
    with pytest.raises(ValueError):
        amount_ratio(-5, 100)


# ---------------- date features ----------------

def test_date_same_day():
    assert date_diff_days("2026-03-12", "2026-03-12") == 0

def test_date_one_day():
    assert date_diff_days("2026-03-12", "2026-03-13") == 1

def test_date_multi_day():
    assert date_diff_days("2026-03-12", "2026-03-17") == 5

def test_date_timestamp_vs_date_format():
    assert date_diff_days("2026-03-12T00:00:00", "2026-03-15") == 3

def test_date_invalid_raises():
    with pytest.raises(ValueError):
        date_diff_days("not-a-date", "2026-03-15")

def test_date_missing_raises():
    with pytest.raises(ValueError):
        date_diff_days("2026-03-12", None)


# ---------------- string similarity ----------------

def test_string_identical():
    n = normalize_vendor("Reliance Industries Limited")
    assert vendor_levenshtein_similarity(n, n) == 1.0
    assert vendor_exact_normalized_match(n, n) == 1

def test_string_typo():
    a = normalize_vendor("Reliance Industries Limited")
    b = normalize_vendor("Reliance Indutsries Limited")  # transposed letters
    sim = vendor_levenshtein_similarity(a, b)
    assert 0.8 < sim < 1.0

def test_string_abbreviation():
    a = normalize_vendor("Tata Consultancy Services")
    b = normalize_vendor("TCS")
    sim = vendor_jaro_winkler_similarity(a, b)
    assert 0.0 <= sim <= 1.0  # abbreviations score low on edit-distance metrics; this documents that, doesn't assert high similarity

def test_string_completely_different():
    a = normalize_vendor("Reliance Industries Limited")
    b = normalize_vendor("Zomato Limited")
    assert vendor_exact_normalized_match(a, b) == 0

def test_string_empty():
    assert vendor_levenshtein_similarity("", "") == 1.0
    assert vendor_levenshtein_similarity("something", "") == 0.0


# ---------------- reference features ----------------

def test_reference_exact():
    assert reference_exact_match("RZP123456", "RZP123456") == 1

def test_reference_truncated_overlap_but_not_exact():
    assert reference_exact_match("RZP123456", "123456") == 0
    assert reference_substring_overlap("RZP123456", "123456") == 1

def test_reference_formatting_difference():
    assert reference_exact_match("RZP-123-456", "rzp123456") == 1

def test_reference_missing_never_counts_as_exact_match():
    assert reference_exact_match("", "") == 0
    assert reference_both_missing("", "") == 1
    assert reference_exact_match(None, None) == 0


# ---------------- embeddings ----------------

def test_embedding_same_text_deterministic():
    v1 = _backend.encode("Reliance Industries")
    v2 = _backend.encode("Reliance Industries")
    assert np.allclose(v1, v2)

def test_embedding_missing_text_is_zero_vector():
    v = _backend.encode("")
    assert np.allclose(v, np.zeros_like(v))

def test_cosine_similarity_range():
    v1 = _backend.encode("Reliance Industries Limited")
    v2 = _backend.encode("Completely Different Vendor")
    sim = cosine_similarity(v1, v2)
    assert -1.0001 <= sim <= 1.0001


# ---------------- leakage guard ----------------

def test_extractor_source_never_references_hidden_files():
    import ml.features.extractor as extractor_module
    import inspect
    source = inspect.getsource(extractor_module)
    # allow the word only inside the explicit refusal check / comments, never
    # as part of an actual file path being opened
    assert "pd.read_csv(RAW_DIR / \"_hidden" not in source
    assert "open(RAW_DIR / \"_hidden" not in source

def test_feature_dataset_has_no_ground_truth_columns():
    from ml.features.validate import validate
    df = pd.read_parquet("data/processed/features.parquet")
    results = validate(df)
    assert results["no_leakage_columns"] is True
