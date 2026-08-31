from backend.app.workflow.exception_intelligence import analyze_exception


def _features(**overrides):
    base = {
        "relative_amount_diff": 0.001, "date_diff_days": 1,
        "vendor_token_set_similarity": 0.95, "reference_exact_match": 1,
        "reference_substring_overlap": 1, "reference_similarity": 1.0,
        "competing_candidate_count": 0, "is_potential_one_to_many": 0,
        "is_potential_many_to_one": 0,
    }
    base.update(overrides)
    return base


def test_processing_failure_takes_precedence_over_everything():
    analysis = analyze_exception("LOW_MATCH_CONFIDENCE", _features(), "FAILED", True)
    assert analysis.primary_root_cause == "PROCESSING_FAILURE"


def test_missing_source_record_detected_before_evidence_analysis():
    analysis = analyze_exception("LOW_MATCH_CONFIDENCE", None, "EXCEPTION", False)
    assert analysis.primary_root_cause == "MISSING_SOURCE_RECORD"


def test_no_candidate_found_maps_to_no_viable_candidate():
    analysis = analyze_exception("NO_CANDIDATE_FOUND", _features(), "EXCEPTION", True)
    assert analysis.primary_root_cause == "NO_VIABLE_CANDIDATE"


def test_structural_ambiguity_maps_to_structural_match_failure():
    analysis = analyze_exception(
        "STRUCTURAL_AMBIGUITY",
        _features(is_potential_one_to_many=1, is_potential_many_to_one=1),
        "EXCEPTION", True,
    )
    assert analysis.primary_root_cause == "STRUCTURAL_MATCH_FAILURE"
    assert "is_potential_one_to_many" in analysis.observed[0]


def test_high_competition_maps_to_weak_match_evidence():
    analysis = analyze_exception(
        "HIGH_COMPETITION", _features(competing_candidate_count=12), "EXCEPTION", True
    )
    assert analysis.primary_root_cause == "WEAK_MATCH_EVIDENCE"
    assert "12" in analysis.observed[0]


def test_amount_discrepancy_detected_and_named_correctly():
    analysis = analyze_exception(
        "LOW_MATCH_CONFIDENCE", _features(relative_amount_diff=0.15), "EXCEPTION", True
    )
    assert analysis.primary_root_cause == "AMOUNT_DISCREPANCY"
    assert "relative_amount_diff" in analysis.observed[0]


def test_date_discrepancy_detected_when_it_is_the_only_weak_dimension():
    analysis = analyze_exception(
        "LOW_MATCH_CONFIDENCE", _features(date_diff_days=20), "EXCEPTION", True
    )
    assert analysis.primary_root_cause == "DATE_DISCREPANCY"


def test_vendor_mismatch_detected_when_it_is_the_only_weak_dimension():
    analysis = analyze_exception(
        "LOW_MATCH_CONFIDENCE", _features(vendor_token_set_similarity=0.1), "EXCEPTION", True
    )
    assert analysis.primary_root_cause == "VENDOR_MISMATCH"


def test_reference_mismatch_detected_when_it_is_the_only_weak_dimension():
    analysis = analyze_exception(
        "LOW_MATCH_CONFIDENCE",
        _features(reference_exact_match=0, reference_substring_overlap=0, reference_similarity=0.05),
        "EXCEPTION", True,
    )
    assert analysis.primary_root_cause == "REFERENCE_MISMATCH"


def test_amount_takes_precedence_when_multiple_dimensions_are_weak():
    """Amount is first in DIMENSION_PRECEDENCE — grounded in Phase 4's
    feature-importance ranking, not an arbitrary choice."""
    analysis = analyze_exception(
        "LOW_MATCH_CONFIDENCE",
        _features(relative_amount_diff=0.2, date_diff_days=30, vendor_token_set_similarity=0.05),
        "EXCEPTION", True,
    )
    assert analysis.primary_root_cause == "AMOUNT_DISCREPANCY"
    assert len(analysis.contributing_factors) == 2  # date and vendor, listed as contributing not primary


def test_model_uncertainty_when_no_single_dimension_is_weak():
    analysis = analyze_exception("LOW_MATCH_CONFIDENCE", _features(), "EXCEPTION", True)
    assert analysis.primary_root_cause == "MODEL_UNCERTAINTY"


def test_no_fabricated_confidence_score_anywhere_in_the_output():
    for category in ["NO_CANDIDATE_FOUND", "HIGH_COMPETITION", "LOW_MATCH_CONFIDENCE"]:
        analysis = analyze_exception(category, _features(relative_amount_diff=0.2), "EXCEPTION", True)
        assert not hasattr(analysis, "confidence")
        combined_text = " ".join(analysis.observed + analysis.interpretation)
        assert "%" not in combined_text or "confidence" not in combined_text.lower()


def test_investigation_guidance_present_for_every_reachable_cause():
    cases = [
        ("NO_CANDIDATE_FOUND", _features(), "EXCEPTION", True),
        ("STRUCTURAL_AMBIGUITY", _features(), "EXCEPTION", True),
        ("HIGH_COMPETITION", _features(), "EXCEPTION", True),
        ("LOW_MATCH_CONFIDENCE", _features(relative_amount_diff=0.2), "EXCEPTION", True),
        ("LOW_MATCH_CONFIDENCE", _features(), "EXCEPTION", True),
    ]
    for category, features, state, present in cases:
        analysis = analyze_exception(category, features, state, present)
        assert analysis.investigation_guidance, f"missing guidance for {analysis.primary_root_cause}"


def test_observed_and_interpretation_are_kept_as_separate_fields():
    """Spec Step 7: observed facts and interpretation must be distinguishable,
    not merged into one ambiguous sentence."""
    analysis = analyze_exception(
        "LOW_MATCH_CONFIDENCE", _features(relative_amount_diff=0.2), "EXCEPTION", True
    )
    assert isinstance(analysis.observed, list) and len(analysis.observed) > 0
    assert isinstance(analysis.interpretation, list) and len(analysis.interpretation) > 0
    assert analysis.observed != analysis.interpretation
