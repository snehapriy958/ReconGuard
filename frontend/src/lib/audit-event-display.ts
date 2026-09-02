import type { AuditEventItem } from "./api-types";

export type EventCategory = "SYSTEM" | "MODEL" | "WORKFLOW" | "HUMAN" | "EXCEPTION";

// Derived directly from the real event_type strings emitted in
// backend/app/pipeline.py and backend/app/review_actions.py — not guessed.
// See docs/frontend.md "Phase 6.7" for the full taxonomy this was built from.
const EVENT_CATEGORY: Record<string, EventCategory> = {
  BATCH_CREATED: "SYSTEM",
  PROCESSING_STARTED: "SYSTEM",
  PROCESSING_FAILED: "SYSTEM",
  CANDIDATE_PROCESSING_FAILED: "SYSTEM",
  BATCH_COMPLETED: "SYSTEM",
  DUPLICATE_SUBMISSION_DETECTED: "SYSTEM",
  MODEL_EVALUATED: "MODEL",
  AUTO_MATCH_CREATED: "WORKFLOW",
  REVIEW_TASK_CREATED: "WORKFLOW",
  EXCEPTION_CREATED: "EXCEPTION",
  REVIEW_APPROVED: "HUMAN",
  REVIEW_REJECTED: "HUMAN",
};

const EVENT_TITLES: Record<string, string> = {
  BATCH_CREATED: "Batch created",
  PROCESSING_STARTED: "Processing started",
  PROCESSING_FAILED: "Processing failed",
  CANDIDATE_PROCESSING_FAILED: "A candidate failed to process",
  BATCH_COMPLETED: "Batch completed",
  DUPLICATE_SUBMISSION_DETECTED: "Duplicate submission detected",
  MODEL_EVALUATED: "Model evaluated reconciliation candidate",
  AUTO_MATCH_CREATED: "Automatically matched",
  REVIEW_TASK_CREATED: "Sent for human review",
  EXCEPTION_CREATED: "Exception created",
  REVIEW_APPROVED: "Reviewer approved",
  REVIEW_REJECTED: "Reviewer rejected",
};

export function eventCategory(eventType: string): EventCategory | "UNKNOWN" {
  return EVENT_CATEGORY[eventType] ?? "UNKNOWN";
}

export function eventTitle(eventType: string): string {
  // Honest fallback for an event type this presentation layer doesn't
  // recognize — never guesses a plausible-sounding title for it.
  return EVENT_TITLES[eventType] ?? `Unrecognized event: ${eventType}`;
}

export const CATEGORY_TONE: Record<EventCategory | "UNKNOWN", "neutral" | "info" | "success" | "warning" | "danger"> = {
  SYSTEM: "neutral",
  MODEL: "info",
  WORKFLOW: "success",
  HUMAN: "warning",
  EXCEPTION: "danger",
  UNKNOWN: "neutral",
};

/**
 * Builds a one-line summary from the event's REAL payload fields only.
 * Every branch checks for the field's actual presence before using it —
 * an event whose payload lacks an expected field gets a shorter, honest
 * summary rather than a fabricated placeholder value.
 */
export function eventSummary(event: AuditEventItem): string {
  const p = event.payload ?? {};
  switch (event.event_type) {
    case "MODEL_EVALUATED": {
      const parts: string[] = [];
      if (typeof p.decision === "string") parts.push(`decision: ${p.decision}`);
      if (typeof p.calibrated_probability === "number") {
        parts.push(`confidence: ${Math.round(p.calibrated_probability * 100)}%`);
      }
      if (typeof p.relationship_type === "string") parts.push(p.relationship_type);
      return parts.length > 0 ? parts.join(" · ") : "Model evaluation recorded.";
    }
    case "REVIEW_APPROVED":
    case "REVIEW_REJECTED": {
      const parts: string[] = [];
      if (event.actor_id) parts.push(`by ${event.actor_id}`);
      if (typeof p.comment === "string" && p.comment) parts.push(`"${p.comment}"`);
      return parts.length > 0 ? parts.join(" — ") : "Reviewer action recorded.";
    }
    case "EXCEPTION_CREATED": {
      if (typeof p.category === "string") return `Category: ${p.category}`;
      return "Exception recorded.";
    }
    case "PROCESSING_FAILED": {
      if (typeof p.error === "string") return p.error;
      return "Processing failed.";
    }
    case "CANDIDATE_PROCESSING_FAILED": {
      if (typeof p.error === "string") return p.error;
      return "A candidate could not be processed.";
    }
    default:
      return "";
  }
}
