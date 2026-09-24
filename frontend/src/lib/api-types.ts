// ReconLens frontend — API types.
//
// These interfaces are written directly from backend/app/api/main.py's
// actual response construction (_decision_to_dict, _evidence_to_dict, and
// each endpoint's return dict) — not guessed, and not a generic/idealized
// schema. If a backend field is optional or nullable in practice (e.g. a
// decision with no risk flags), the type reflects that.

export interface BatchSummary {
  total_records: number;
  candidates_generated: number;
  high_confidence_matches: number;
  needs_review: number;
  likely_no_match: number;
  exceptions: number;
  structural_matches: number;
  one_to_many_matches: number;
  many_to_one_matches: number;
  risk_flagged_decisions: number;
  failed_candidates: number;
  processing_time_seconds: number;
}

export type BatchStatus = "CREATED" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface BatchListItem {
  batch_id: string;
  status: BatchStatus;
  n_ledger_records: number;
  n_settlement_records: number;
  created_at: string;
  summary: BatchSummary | null;
}

export interface BatchDetail {
  batch_id: string;
  status: BatchStatus;
  summary: BatchSummary | null;
  created_at: string;
  completed_at: string | null;
  failure_reason: string | null;
}

export type RelationshipType = "one_to_one" | "one_to_many" | "many_to_one";

export type DecisionLabel = "HIGH_CONFIDENCE_MATCH" | "NEEDS_REVIEW" | "LIKELY_NO_MATCH";

export type DecisionWorkflowState =
  | "PENDING"
  | "PROCESSING"
  | "AUTO_MATCHED"
  | "NEEDS_REVIEW"
  | "APPROVED_BY_REVIEWER"
  | "REJECTED_BY_REVIEWER"
  | "LIKELY_NO_MATCH"
  | "EXCEPTION"
  | "FAILED";

export interface Decision {
  decision_id: string;
  batch_id: string;
  ledger_record_ids: string[];
  settlement_record_ids: string[];
  relationship_type: RelationshipType;
  model_name: string;
  model_version: string;
  probability: { raw: number; calibrated: number };
  thresholds: { high: number; low: number };
  decision: DecisionLabel;
  workflow_state: DecisionWorkflowState;
  risk_flags: string[];
  created_at: string;
}

export interface EvidenceItem {
  feature: string;
  value: number;
  direction: "supports_match" | "weakens_match" | "creates_ambiguity";
  strength: "strong" | "moderate" | "weak";
}

// Raw source record content — shape matches SourceRecord.raw_data exactly
// (vendor_name/amount/txn_date/reference_id/description), so a field is
// only shown in the UI if the backend actually stored it.
export interface SourceRecordData {
  vendor_name?: string;
  amount?: number;
  txn_date?: string;
  reference_id?: string;
  description?: string;
  [key: string]: unknown;
}

export interface DecisionDetail extends Decision {
  evidence: EvidenceItem[];
  ledger_records: (SourceRecordData | null)[];
  settlement_records: (SourceRecordData | null)[];
  // Full feature vector, recomputed server-side from persisted source
  // records via the same extraction function the ML pipeline uses (see
  // backend/app/api/main.py get_decision) — null if recomputation failed
  // for any reason (e.g. a source record was deleted), never fabricated.
  all_features: Record<string, number> | null;
  // Real explanation strings, sourced server-side from
  // backend/app/workflow/risk.py's risk_explanation() — one entry per flag
  // in risk_flags, never fabricated in the frontend.
  risk_flag_explanations: Record<string, string>;
}

export type ReviewStatus = "OPEN" | "IN_REVIEW" | "APPROVED" | "REJECTED";

export interface ReviewListItem {
  review_id: string;
  decision_id: string;
  status: ReviewStatus;
  relationship_type: RelationshipType;
  calibrated_probability: number;
  risk_flags: string[];
  created_at: string;
  // Joined through the decision — batch context and structural groups,
  // so the queue never has to flatten a one-to-many/many-to-one case.
  batch_id: string | null;
  ledger_record_ids: string[] | null;
  settlement_record_ids: string[] | null;
  original_ml_decision: DecisionLabel | null;
}

export interface ReviewDetail extends ReviewListItem {
  evidence_snapshot: { feature: string; value: number; contribution: number }[] | null;
  assigned_reviewer: string | null;
  resolved_at: string | null;
}

export interface ExceptionListItem {
  exception_id: string;
  decision_id: string;
  category: string;
  reason: string;
  created_at: string;
  relationship_type: RelationshipType | null;
  calibrated_probability: number | null;
  ledger_record_ids: string[] | null;
  settlement_record_ids: string[] | null;
  risk_flags: string[] | null;
  primary_root_cause: string | null;
}

export interface RootCauseAnalysis {
  primary_root_cause: string;
  observed: string[];
  interpretation: string[];
  contributing_factors: string[];
  investigation_guidance: string;
  taxonomy_version: string;
}

export interface ExceptionDetail {
  exception_id: string;
  decision_id: string;
  batch_id: string | null;
  original_category: string;
  original_reason: string;
  created_at: string;
  relationship_type: RelationshipType | null;
  calibrated_probability: number | null;
  workflow_state: DecisionWorkflowState | null;
  risk_flags: string[] | null;
  ledger_record_ids: string[] | null;
  settlement_record_ids: string[] | null;
  root_cause_analysis: RootCauseAnalysis;
}

export interface AuditEventItem {
  event_id: string;
  event_type: string;
  actor_type: "SYSTEM" | "MODEL" | "HUMAN";
  actor_id: string | null;
  previous_state: string | null;
  new_state: string | null;
  payload: Record<string, unknown> | null;
  timestamp: string;
}

// ---------------- upload & validation ----------------

export interface CsvValidationErrorDetail {
  file: "ledger" | "settlement" | string;
  row?: number;
  field?: string;
  message: string;
}

export interface CsvValidationResponseError {
  message: string;
  errors: CsvValidationErrorDetail[];
}

export interface BatchCreateResponse {
  batch_id: string;
  status: BatchStatus;
  summary: BatchSummary | null;
}
