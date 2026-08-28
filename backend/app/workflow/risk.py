"""
ReconLens — relationship-aware risk layer.

CRITICAL DISTINCTION (spec section 10): this module NEVER touches or
modifies a model probability. It only reads already-computed feature values
and the already-decided relationship_type, and returns deterministic,
documented metadata. A HIGH_CONFIDENCE_MATCH with risk flags attached is
still a HIGH_CONFIDENCE_MATCH — the risk flags are a separate operational
signal for a human deciding whether to trust automation more or less on a
given case, not a hidden threshold override.

Every threshold here is a stated project assumption, not a tuned model
parameter — see docs/risk_policy.md for the reasoning behind each one.
"""

# Empirically grounded in Phase 4's held-out test results — not guessed.
KNOWN_LOW_GENERALIZATION_TYPES = {
    "one_to_many": "held-out test recall was 66.7% (2 of 6 true matches missed) for this relationship type",
}
INSUFFICIENT_VALIDATION_TYPES = {
    "many_to_one": "validation set had ZERO positive examples of this type — thresholds were never "
                   "genuinely exercised against it during tuning",
}

HIGH_COMPETITION_THRESHOLD = 5  # competing_candidate_count >= this is flagged; chosen because the
                                 # median competing_candidate_count in the labeled dataset is well
                                 # below this and the Phase 3 false-negative case had 10
WEAK_REFERENCE_SIMILARITY_THRESHOLD = 0.3


def compute_risk_flags(feature_row: dict, relationship_type: str) -> list[str]:
    flags = []

    if relationship_type != "one_to_one":
        flags.append("STRUCTURAL_MATCH")
    if relationship_type == "one_to_many":
        flags.append("ONE_TO_MANY_RELATIONSHIP")
        flags.append("KNOWN_LOW_GENERALIZATION")
    if relationship_type == "many_to_one":
        flags.append("MANY_TO_ONE_RELATIONSHIP")
        flags.append("INSUFFICIENT_VALIDATION_SAMPLE")

    competing = feature_row.get("competing_candidate_count", 0)
    if competing >= HIGH_COMPETITION_THRESHOLD:
        flags.append("HIGH_COMPETITION")

    ref_exact = feature_row.get("reference_exact_match", 0)
    ref_overlap = feature_row.get("reference_substring_overlap", 0)
    ref_sim = feature_row.get("reference_similarity", 0.0)
    ref_both_missing = feature_row.get("reference_both_missing", 0)

    if ref_both_missing:
        flags.append("MISSING_REFERENCE")
    elif not ref_exact and not ref_overlap and ref_sim < WEAK_REFERENCE_SIMILARITY_THRESHOLD:
        flags.append("WEAK_REFERENCE_EVIDENCE")

    if feature_row.get("is_potential_one_to_many") and feature_row.get("is_potential_many_to_one"):
        flags.append("HIGH_STRUCTURAL_AMBIGUITY")

    return flags


def risk_explanation(flag: str, relationship_type: str) -> str:
    """Human-readable operational note for a given flag — used in the
    confidence-card payload and exception reasoning, never fabricated per
    candidate (same fixed explanation for a given flag, by design: these are
    known, measured, structural facts, not per-case guesses).
    """
    explanations = {
        "STRUCTURAL_MATCH": "This is a structural (multi-record) reconciliation, not a simple one-to-one match.",
        "ONE_TO_MANY_RELATIONSHIP": "One ledger record reconciles against multiple settlement records.",
        "MANY_TO_ONE_RELATIONSHIP": "Multiple ledger records reconcile against one settlement record.",
        "KNOWN_LOW_GENERALIZATION": (
            f"Held-out evaluation showed lower recall ({KNOWN_LOW_GENERALIZATION_TYPES.get(relationship_type, 'this type')}) "
            f"for this relationship type. Human verification may be preferred for risk-sensitive workflows."
        ),
        "INSUFFICIENT_VALIDATION_SAMPLE": (
            f"{INSUFFICIENT_VALIDATION_TYPES.get(relationship_type, 'This relationship type')} — "
            f"treat this decision's reliability with more caution than the model's raw confidence alone suggests."
        ),
        "HIGH_COMPETITION": "This record has several plausible alternative matches, which can make the top candidate less certain than its score alone implies.",
        "WEAK_REFERENCE_EVIDENCE": "No exact or partial reference-ID match was found; the decision relies on amount, date, and vendor evidence alone.",
        "MISSING_REFERENCE": "Reference ID is absent on at least one side, removing a normally strong source of evidence.",
        "HIGH_STRUCTURAL_AMBIGUITY": "This candidate has competing structural interpretations (could plausibly be part of a split or batch), adding ambiguity beyond a simple one-to-one comparison.",
    }
    return explanations.get(flag, flag)


EXCEPTION_CATEGORIES = {
    "NO_CANDIDATE_FOUND": lambda f: f.get("candidate_count_for_ledger", 0) == 0 and f.get("candidate_count_for_settlement", 0) == 0,
    "HIGH_COMPETITION": lambda f: f.get("competing_candidate_count", 0) >= HIGH_COMPETITION_THRESHOLD,
    "STRUCTURAL_AMBIGUITY": lambda f: f.get("is_potential_one_to_many") and f.get("is_potential_many_to_one"),
    "INSUFFICIENT_EVIDENCE": lambda f: (not f.get("reference_exact_match") and not f.get("reference_substring_overlap")
                                          and f.get("reference_similarity", 0) < WEAK_REFERENCE_SIMILARITY_THRESHOLD
                                          and f.get("vendor_jaro_winkler_similarity", 1.0) < 0.5),
    # LOW_MATCH_CONFIDENCE is the fallback when no more specific measurable condition applies.
}


def classify_exception(feature_row: dict) -> str:
    """Evaluated in a fixed, documented priority order — first matching
    category wins, not whichever happens to be checked last. Falls back to
    LOW_MATCH_CONFIDENCE, which is itself a real, measurable statement (the
    calibrated probability was below the low threshold), not a vague catch-all.
    """
    for category in ["NO_CANDIDATE_FOUND", "STRUCTURAL_AMBIGUITY", "HIGH_COMPETITION", "INSUFFICIENT_EVIDENCE"]:
        if EXCEPTION_CATEGORIES[category](feature_row):
            return category
    return "LOW_MATCH_CONFIDENCE"
