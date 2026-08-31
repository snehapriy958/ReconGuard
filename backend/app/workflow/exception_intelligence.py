"""
ReconLens — Exception Intelligence engine.

Builds ON TOP of the existing classify_exception() taxonomy in risk.py
(NO_CANDIDATE_FOUND / STRUCTURAL_AMBIGUITY / HIGH_COMPETITION /
INSUFFICIENT_EVIDENCE / LOW_MATCH_CONFIDENCE) rather than replacing it —
those categories are already real, deterministic, and used to create the
persisted ExceptionRecord.category. This module adds a second, more
granular layer of analysis for cases that already fell into
INSUFFICIENT_EVIDENCE/LOW_MATCH_CONFIDENCE, where "low confidence" alone
doesn't tell an operator WHICH evidence dimension was actually weak.

DESIGN PRINCIPLE (spec Step 7): no fabricated "root-cause confidence"
score. Every value shown is either an OBSERVED number (a real feature
value) or a DETERMINISTIC INTERPRETATION of it (a strength label from a
documented threshold) — never a probability that a cause is "correct."

Thresholds mirror src/lib/evidence-interpretation.ts on the frontend
exactly, and are documented with the same justification — this
intentionally duplicates the numeric constants (not the decision of WHERE
the authoritative classification happens, which is here, server-side, per
spec Step 11: "the backend should remain the source of truth"). The
frontend's copy is presentation-only (used for Phase 6.4's evidence
breakdown cards); this copy is the actual root-cause determination.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.workflow.risk import (
    HIGH_COMPETITION_THRESHOLD,
    WEAK_REFERENCE_SIMILARITY_THRESHOLD,
    classify_exception,
)

# Same bands as src/lib/evidence-interpretation.ts — see that file's
# comments for the dataset-grounded justification of each threshold.
AMOUNT_WEAK_THRESHOLD = 0.03
DATE_WEAK_THRESHOLD_DAYS = 7
VENDOR_WEAK_THRESHOLD = 0.5

# Precedence when multiple dimensions are simultaneously weak: amount first
# because Phase 4's LightGBM feature importance ranked abs_amount_diff far
# above every other feature (see docs/model_comparison.md); reference
# second because Phase 4's ablation showed removing reference features cost
# the most accuracy of any feature group; vendor and date follow.
DIMENSION_PRECEDENCE = ["amount", "reference", "vendor", "date"]

INVESTIGATION_GUIDANCE = {
    "PROCESSING_FAILURE": "Inspect the processing error and retry only after the underlying failure is resolved.",
    "MISSING_SOURCE_RECORD": "Check whether a corresponding source record is missing or was ingested from a different batch or settlement period.",
    "NO_VIABLE_CANDIDATE": "Check whether a corresponding source record is missing or was ingested from a different settlement period.",
    "STRUCTURAL_MATCH_FAILURE": "Review whether this record is genuinely part of a split or batched settlement, and whether the grouping logic correctly identified all members.",
    "WEAK_MATCH_EVIDENCE": "Review the competing candidates directly — no single candidate stood out clearly enough for automatic resolution.",
    "AMOUNT_DISCREPANCY": "Check for fees, partial settlement, refunds, or split transactions.",
    "DATE_DISCREPANCY": "Check for delayed settlement or posting-date differences.",
    "VENDOR_MISMATCH": "Check alternate vendor names, abbreviations, or transliterations.",
    "REFERENCE_MISMATCH": "Check alternate payment or reference identifiers.",
    "MODEL_UNCERTAINTY": "Evidence looks reasonable on each individual dimension, but the combined calibrated probability did not clear the auto-match threshold — manual comparison is recommended.",
    "UNKNOWN_OR_INSUFFICIENT_EVIDENCE": "Inspect the underlying records and processing context directly; the available signals did not clearly point to one cause.",
}


@dataclass
class RootCauseAnalysis:
    primary_root_cause: str
    observed: list[str] = field(default_factory=list)       # objective, real values
    interpretation: list[str] = field(default_factory=list)  # deterministic labels derived from them
    contributing_factors: list[str] = field(default_factory=list)
    investigation_guidance: str = ""
    taxonomy_version: str = "v1"


def _strength(value: float, weak_threshold: float, higher_is_weaker: bool) -> str:
    if higher_is_weaker:
        return "weak" if value >= weak_threshold else "strong"
    return "weak" if value <= weak_threshold else "strong"


def analyze_exception(
    persisted_category: str,
    features: dict | None,
    workflow_state: str,
    all_source_records_present: bool,
) -> RootCauseAnalysis:
    """persisted_category: the ExceptionRecord.category already stored (from
    classify_exception() at decision time — never recomputed differently
    here, only refined further when it's the generic fallback).
    features: the recomputed all_features dict (None if unavailable).
    """
    # 1. Processing failure — checked first, but see module docstring: this
    # is currently unreachable given how the pipeline handles candidate
    # failures (they're skipped before any decision/exception is created).
    # Included for correctness, not because a real example exists yet.
    if workflow_state == "FAILED":
        return RootCauseAnalysis(
            primary_root_cause="PROCESSING_FAILURE",
            observed=["The decision's workflow state is FAILED."],
            interpretation=["This is a technical processing failure, not a reconciliation-quality issue."],
            investigation_guidance=INVESTIGATION_GUIDANCE["PROCESSING_FAILURE"],
        )

    # 2. Missing source record — a real, checkable condition.
    if not all_source_records_present:
        return RootCauseAnalysis(
            primary_root_cause="MISSING_SOURCE_RECORD",
            observed=["One or more ledger or settlement records referenced by this decision could not be found."],
            interpretation=["The comparison cannot be fully evaluated without the missing record."],
            investigation_guidance=INVESTIGATION_GUIDANCE["MISSING_SOURCE_RECORD"],
        )

    if features is None:
        return RootCauseAnalysis(
            primary_root_cause="UNKNOWN_OR_INSUFFICIENT_EVIDENCE",
            observed=["Feature evidence could not be recomputed for this decision."],
            interpretation=["Insufficient evidence to classify the root cause."],
            investigation_guidance=INVESTIGATION_GUIDANCE["UNKNOWN_OR_INSUFFICIENT_EVIDENCE"],
        )

    # 3-5. Map the existing, already-persisted coarse category directly —
    # these were already deterministic and evidence-based at decision time.
    if persisted_category == "NO_CANDIDATE_FOUND":
        return RootCauseAnalysis(
            primary_root_cause="NO_VIABLE_CANDIDATE",
            observed=["No candidate records were found on either side during candidate generation."],
            interpretation=["No viable reconciliation candidate was found."],
            investigation_guidance=INVESTIGATION_GUIDANCE["NO_VIABLE_CANDIDATE"],
        )
    if persisted_category == "STRUCTURAL_AMBIGUITY":
        return RootCauseAnalysis(
            primary_root_cause="STRUCTURAL_MATCH_FAILURE",
            observed=[f"is_potential_one_to_many={bool(features.get('is_potential_one_to_many'))}, "
                      f"is_potential_many_to_one={bool(features.get('is_potential_many_to_one'))}"],
            interpretation=["This candidate has competing structural interpretations (could plausibly be part of a split or batch)."],
            investigation_guidance=INVESTIGATION_GUIDANCE["STRUCTURAL_MATCH_FAILURE"],
        )
    if persisted_category == "HIGH_COMPETITION":
        competing = features.get("competing_candidate_count", 0)
        return RootCauseAnalysis(
            primary_root_cause="WEAK_MATCH_EVIDENCE",
            observed=[f"competing_candidate_count={competing} (threshold: {HIGH_COMPETITION_THRESHOLD})"],
            interpretation=["Multiple plausible candidates exist, and no single one stood out clearly enough."],
            investigation_guidance=INVESTIGATION_GUIDANCE["WEAK_MATCH_EVIDENCE"],
        )

    # 6. INSUFFICIENT_EVIDENCE / LOW_MATCH_CONFIDENCE — drill into which
    # specific evidence dimension is actually weak, rather than leaving
    # "low confidence" unexplained.
    amount_weak = _strength(features.get("relative_amount_diff", 0), AMOUNT_WEAK_THRESHOLD, higher_is_weaker=True) == "weak"
    date_weak = _strength(features.get("date_diff_days", 0), DATE_WEAK_THRESHOLD_DAYS, higher_is_weaker=True) == "weak"
    vendor_weak = _strength(features.get("vendor_token_set_similarity", 1.0), VENDOR_WEAK_THRESHOLD, higher_is_weaker=False) == "weak"
    ref_weak = (not features.get("reference_exact_match") and not features.get("reference_substring_overlap")
                and features.get("reference_similarity", 1.0) < WEAK_REFERENCE_SIMILARITY_THRESHOLD)

    weak_dims = {"amount": amount_weak, "reference": ref_weak, "vendor": vendor_weak, "date": date_weak}
    weak_list = [d for d in DIMENSION_PRECEDENCE if weak_dims[d]]

    dim_labels = {
        "amount": ("AMOUNT_DISCREPANCY", f"relative_amount_diff={features.get('relative_amount_diff', 0):.4f} (threshold: {AMOUNT_WEAK_THRESHOLD})"),
        "reference": ("REFERENCE_MISMATCH", f"reference_similarity={features.get('reference_similarity', 0):.4f}, exact_match={bool(features.get('reference_exact_match'))}, substring_overlap={bool(features.get('reference_substring_overlap'))}"),
        "vendor": ("VENDOR_MISMATCH", f"vendor_token_set_similarity={features.get('vendor_token_set_similarity', 0):.4f} (threshold: {VENDOR_WEAK_THRESHOLD})"),
        "date": ("DATE_DISCREPANCY", f"date_diff_days={features.get('date_diff_days', 0)} (threshold: {DATE_WEAK_THRESHOLD_DAYS})"),
    }

    if weak_list:
        primary_dim = weak_list[0]
        primary_cause, primary_observed = dim_labels[primary_dim]
        contributing = [dim_labels[d][1] for d in weak_list[1:]]
        return RootCauseAnalysis(
            primary_root_cause=primary_cause,
            observed=[primary_observed],
            interpretation=[f"{primary_dim.capitalize()} evidence is the clearest weakness among this candidate's evidence."],
            contributing_factors=contributing,
            investigation_guidance=INVESTIGATION_GUIDANCE[primary_cause],
        )

    # No single dimension is individually weak, yet the model still didn't
    # clear the threshold — a genuine model-uncertainty case, not a
    # data-quality issue.
    return RootCauseAnalysis(
        primary_root_cause="MODEL_UNCERTAINTY",
        observed=[f"amount, date, vendor, and reference evidence are each within normal ranges, "
                  f"but the calibrated probability did not exceed the review threshold"],
        interpretation=["The model is uncertain despite no single dimension being clearly weak."],
        investigation_guidance=INVESTIGATION_GUIDANCE["MODEL_UNCERTAINTY"],
    )
