// ReconLens frontend — API client.
//
// This is the ONLY module that calls fetch() directly. Every component
// imports typed functions from here rather than constructing requests
// itself, per Phase 6.1's explicit requirement ("do not scatter raw fetch
// calls throughout components").

import type {
  BatchListItem,
  BatchDetail,
  BatchCreateResponse,
  Decision,
  DecisionDetail,
  ReviewListItem,
  ReviewDetail,
  ExceptionListItem,
  ExceptionDetail,
  AuditEventItem,
  ModelEvaluationResponse,
  DemoDatasetsResponse,
} from "./api-types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail?: unknown;
  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const defaultHeaders: Record<string, string> = isFormData
    ? {}
    : { "Content-Type": "application/json" };

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...defaultHeaders,
        ...(init?.headers as Record<string, string>),
      },
    });
  } catch {
    // Network-level failure (backend unreachable) — distinguished from an
    // HTTP error status so the UI can show "can't reach the backend"
    // rather than a generic error.
    throw new ApiError(
      `Could not reach the ReconGuard API at ${API_BASE_URL}. Is the backend running?`,
      0
    );
  }

  if (!res.ok) {
    let detailText = res.statusText;
    let detailPayload: unknown = undefined;
    try {
      const body = await res.json();
      detailPayload = body.detail;
      if (typeof body.detail === "string") {
        detailText = body.detail;
      } else if (body.detail?.message) {
        detailText = body.detail.message;
      } else if (body.detail) {
        detailText = JSON.stringify(body.detail);
      }
    } catch {
      // body wasn't JSON — fall back to statusText, already set
    }
    throw new ApiError(detailText, res.status, detailPayload);
  }

  return res.json() as Promise<T>;
}

// ---------------- batches ----------------

export function listBatches(): Promise<{ batches: BatchListItem[] }> {
  return request("/batches");
}

export function getBatch(batchId: string): Promise<BatchDetail> {
  return request(`/batches/${batchId}`);
}

export function getBatchDecisions(
  batchId: string
): Promise<{ batch_id: string; decisions: Decision[] }> {
  return request(`/batches/${batchId}/decisions`);
}

export function uploadBatch(
  ledgerFile: File,
  settlementFile: File
): Promise<BatchCreateResponse> {
  const formData = new FormData();
  formData.append("ledger_file", ledgerFile);
  formData.append("settlement_file", settlementFile);

  return request<BatchCreateResponse>("/batches/upload", {
    method: "POST",
    body: formData,
  });
}

// ---------------- decisions ----------------

export function getDecision(decisionId: string): Promise<DecisionDetail> {
  return request(`/decisions/${decisionId}`);
}

// ---------------- reviews ----------------

export function listReviews(
  status?: string,
  batchId?: string
): Promise<{ reviews: ReviewListItem[] }> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (batchId) params.set("batch_id", batchId);
  const qs = params.toString();
  return request(`/reviews${qs ? `?${qs}` : ""}`);
}

export function getReview(reviewId: string): Promise<ReviewDetail> {
  return request(`/reviews/${reviewId}`);
}

export function approveReview(
  reviewId: string,
  reviewerId: string,
  comment?: string
): Promise<{ review_id: string; status: string }> {
  return request(`/reviews/${reviewId}/approve`, {
    method: "POST",
    body: JSON.stringify({ reviewer_id: reviewerId, comment }),
  });
}

export function rejectReview(
  reviewId: string,
  reviewerId: string,
  comment?: string
): Promise<{ review_id: string; status: string }> {
  return request(`/reviews/${reviewId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reviewer_id: reviewerId, comment }),
  });
}

// ---------------- exceptions ----------------

export function listExceptions(
  category?: string,
  batchId?: string
): Promise<{ exceptions: ExceptionListItem[] }> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (batchId) params.set("batch_id", batchId);
  const qs = params.toString();
  return request(`/exceptions${qs ? `?${qs}` : ""}`);
}

export function getException(exceptionId: string): Promise<ExceptionDetail> {
  return request(`/exceptions/${exceptionId}`);
}

// ---------------- audit ----------------

export function getDecisionAudit(
  decisionId: string
): Promise<{ decision_id: string; events: AuditEventItem[] }> {
  return request(`/decisions/${decisionId}/audit`);
}

export function getAuditTrail(
  entityType: string,
  entityId: string
): Promise<{ entity_type: string; entity_id: string; events: AuditEventItem[] }> {
  return request(`/audit/${entityType}/${entityId}`);
}

// ---------------- model evaluation ----------------

export function getModelEvaluation(): Promise<ModelEvaluationResponse> {
  return request("/model/evaluation");
}

// ---------------- demo datasets ----------------

export function getDemoDatasets(): Promise<DemoDatasetsResponse> {
  return request("/demo-datasets");
}

export function processDemoDataset(
  datasetId: string
): Promise<BatchCreateResponse> {
  return request(`/demo-datasets/${encodeURIComponent(datasetId)}/process`, {
    method: "POST",
  });
}

export function getDemoDatasetFileUrl(
  datasetId: string,
  fileType: "ledger" | "settlement"
): string {
  return `${API_BASE_URL}/demo-datasets/${encodeURIComponent(datasetId)}/files/${fileType}`;
}
