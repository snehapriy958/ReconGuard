import type { DecisionLabel, DecisionWorkflowState, RelationshipType } from "./api-types";

// Single source of truth for how these enums are labeled/colored across the
// app — avoids each component inventing its own mapping.

export const DECISION_LABELS: Record<DecisionLabel, string> = {
  HIGH_CONFIDENCE_MATCH: "Auto Matched",
  NEEDS_REVIEW: "Needs Review",
  LIKELY_NO_MATCH: "Likely No Match",
};

export const DECISION_TONE: Record<DecisionLabel, "success" | "warning" | "neutral"> = {
  HIGH_CONFIDENCE_MATCH: "success",
  NEEDS_REVIEW: "warning",
  LIKELY_NO_MATCH: "neutral",
};

export const WORKFLOW_STATE_LABELS: Record<DecisionWorkflowState, string> = {
  PENDING: "Pending",
  PROCESSING: "Processing",
  AUTO_MATCHED: "Auto Matched",
  NEEDS_REVIEW: "Needs Review",
  APPROVED_BY_REVIEWER: "Approved",
  REJECTED_BY_REVIEWER: "Rejected",
  LIKELY_NO_MATCH: "Likely No Match",
  EXCEPTION: "Exception",
  FAILED: "Failed",
};

export const WORKFLOW_STATE_TONE: Record<
  DecisionWorkflowState,
  "success" | "warning" | "danger" | "neutral" | "info"
> = {
  PENDING: "neutral",
  PROCESSING: "info",
  AUTO_MATCHED: "success",
  NEEDS_REVIEW: "warning",
  APPROVED_BY_REVIEWER: "success",
  REJECTED_BY_REVIEWER: "danger",
  LIKELY_NO_MATCH: "neutral",
  EXCEPTION: "danger",
  FAILED: "danger",
};

export const RELATIONSHIP_LABELS: Record<RelationshipType, string> = {
  one_to_one: "One-to-One",
  one_to_many: "One-to-Many",
  many_to_one: "Many-to-One",
};

export function formatProbability(p: number): string {
  return `${Math.round(p * 100)}%`;
}
