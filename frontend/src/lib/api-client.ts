// ReconLens frontend — API client.
//
// This is the ONLY module that calls fetch() directly. Every component
// imports typed functions from here rather than constructing requests
// itself, per Phase 6.1's explicit requirement ("do not scatter raw fetch
// calls throughout components").

import type {
  BatchListItem,
  BatchDetail,
  Decision,
  DecisionDetail,
  ReviewListItem,
  ReviewDetail,
  ExceptionListItem,
  ExceptionDetail,
  AuditEventItem,
} from "./api-types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    // Network-level failure (backend unreachable) — distinguished from an
    // HTTP error status so the UI can show "can't reach the backend"
    // rather than a generic error.
    throw new ApiError(
      `Could not reach the ReconLens API at ${API_BASE_URL}. Is the backend running?`,
      0
    );
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // body wasn't JSON — fall back to statusText, already set
    }
    throw new ApiError(detail, res.status);
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

// ---------------- decisions ----------------

export function getDecision(decisionId: string): Promise<DecisionDetail> {
  return request(`/decisions/${decisionId}`);
}

// ---------------- reviews ----------------

export function listReviews(
  status?: string
): Promise<{ reviews: ReviewListItem[] }> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return request(`/reviews${qs}`);
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
  category?: string
): Promise<{ exceptions: ExceptionListItem[] }> {
  const qs = category ? `?category=${encodeURIComponent(category)}` : "";
  return request(`/exceptions${qs}`);
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
