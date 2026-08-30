// ReconLens frontend — evidence interpretation policy.
//
// PRESENTATION-LAYER ONLY. These functions translate real, already-computed
// feature values into human-readable strength/direction labels. They do not
// alter, recompute, or influence the model's calibrated probability in any
// way — that number comes straight from the backend and is never touched
// here. If a threshold below matches one already used in
// backend/app/workflow/risk.py, that's deliberate reuse for consistency,
// not a coincidence — cited inline.
//
// Every threshold here is a stated interpretation choice, grounded where
// possible in documented dataset characteristics (see docs/feature_catalog.md,
// docs/architecture.md), not an arbitrary guess.

export type EvidenceStrength = "strong" | "moderate" | "weak";

// ---------------- Amount ----------------
// docs/feature_catalog.md documents relative_amount_diff's observed range
// as [0, ~0.05] for true matches (bounded by the synthetic corruption
// model's fee-deduction ceiling). 1% and 3% split that range into three
// roughly even, intuitive bands.
export function interpretAmount(relativeAmountDiff: number): {
  strength: EvidenceStrength;
  label: string;
} {
  if (relativeAmountDiff < 0.01) {
    return { strength: "strong", label: "Amounts differ by less than 1%." };
  }
  if (relativeAmountDiff < 0.03) {
    return { strength: "moderate", label: "Amounts differ by a small, plausible margin." };
  }
  return { strength: "weak", label: "Amount discrepancy is significant." };
}

// ---------------- Date ----------------
// The generator's settlement-lag cap is 5 days, and structural batch spans
// are bounded at 3 days (see docs/candidate_generation.md) — so 0 days is
// same-day, up to 3 is within a normal batch window, up to 7 covers the
// generator's realistic lag ceiling with a small margin, beyond that is
// genuinely unusual.
export function interpretDate(dateDiffDays: number): {
  strength: EvidenceStrength;
  label: string;
} {
  if (dateDiffDays <= 3) {
    return { strength: "strong", label: "Settlement timing is close to the transaction date." };
  }
  if (dateDiffDays <= 7) {
    return { strength: "moderate", label: "Settlement timing shows a modest delay." };
  }
  return { strength: "weak", label: "Date difference is larger than typical settlement lag." };
}

// ---------------- Vendor ----------------
// Primary business-facing metric is token-set similarity, not Jaro-Winkler
// — docs/feature_catalog.md documents Jaro-Winkler as prone to an inflated
// baseline on unrelated names sharing short substrings, so it's shown in
// the technical breakdown but not used to drive the headline label.
export function interpretVendor(tokenSetSimilarity: number): {
  strength: EvidenceStrength;
  label: string;
} {
  if (tokenSetSimilarity >= 0.85) {
    return { strength: "strong", label: "Vendor names remain highly similar after normalization." };
  }
  if (tokenSetSimilarity >= 0.5) {
    return { strength: "moderate", label: "Vendor names show partial similarity." };
  }
  return { strength: "weak", label: "Vendor similarity is low." };
}

// ---------------- Reference ----------------
// WEAK_REFERENCE_SIMILARITY_THRESHOLD = 0.3 is the exact constant from
// backend/app/workflow/risk.py — reused here, not reinvented, so a
// candidate's risk flag (WEAK_REFERENCE_EVIDENCE) and its evidence-card
// label always agree.
const WEAK_REFERENCE_SIMILARITY_THRESHOLD = 0.3;

export function interpretReference(
  exactMatch: number,
  substringOverlap: number,
  similarity: number,
  bothMissing: number
): { strength: EvidenceStrength; label: string } {
  if (bothMissing) {
    return { strength: "weak", label: "Reference information is missing on both sides." };
  }
  if (exactMatch) {
    return { strength: "strong", label: "Exact reference match detected." };
  }
  if (substringOverlap) {
    return { strength: "moderate", label: "Partial reference overlap detected." };
  }
  if (similarity < WEAK_REFERENCE_SIMILARITY_THRESHOLD) {
    return { strength: "weak", label: "No meaningful reference match found." };
  }
  return { strength: "moderate", label: "Some reference similarity detected, but no overlap confirmed." };
}

// ---------------- Structural ambiguity ----------------
// HIGH_COMPETITION_THRESHOLD = 5 is the exact constant from
// backend/app/workflow/risk.py — same reasoning as above.
const HIGH_COMPETITION_THRESHOLD = 5;

export function interpretCompetition(competingCandidateCount: number): {
  strength: EvidenceStrength;
  label: string;
} {
  if (competingCandidateCount === 0) {
    return { strength: "strong", label: "No competing candidates were found." };
  }
  if (competingCandidateCount < HIGH_COMPETITION_THRESHOLD) {
    return { strength: "moderate", label: "A small number of competing candidates exist." };
  }
  return { strength: "weak", label: "Multiple competing candidates increase ambiguity." };
}
