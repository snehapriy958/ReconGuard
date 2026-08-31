export const ROOT_CAUSE_LABELS: Record<string, string> = {
  PROCESSING_FAILURE: "Processing Failure",
  MISSING_SOURCE_RECORD: "Missing Source Record",
  NO_VIABLE_CANDIDATE: "No Viable Candidate",
  STRUCTURAL_MATCH_FAILURE: "Structural Match Failure",
  WEAK_MATCH_EVIDENCE: "Weak Match Evidence",
  AMOUNT_DISCREPANCY: "Amount Discrepancy",
  DATE_DISCREPANCY: "Date Discrepancy",
  VENDOR_MISMATCH: "Vendor Mismatch",
  REFERENCE_MISMATCH: "Reference Mismatch",
  MODEL_UNCERTAINTY: "Model Uncertainty",
  UNKNOWN_OR_INSUFFICIENT_EVIDENCE: "Unknown / Insufficient Evidence",
};

// System/technical failures are visually distinct (red) from reconciliation
// -quality findings (amber) — spec Step 13's explicit requirement that
// these two categories of failure not be conflated in the UI.
const SYSTEM_FAILURE_CAUSES = new Set(["PROCESSING_FAILURE", "MISSING_SOURCE_RECORD"]);

export function rootCauseTone(cause: string): "danger" | "warning" | "neutral" {
  if (SYSTEM_FAILURE_CAUSES.has(cause)) return "danger";
  if (cause === "UNKNOWN_OR_INSUFFICIENT_EVIDENCE") return "neutral";
  return "warning";
}

export function isSystemFailure(cause: string): boolean {
  return SYSTEM_FAILURE_CAUSES.has(cause);
}

export function humanizeRootCause(cause: string): string {
  return ROOT_CAUSE_LABELS[cause] ?? cause;
}
