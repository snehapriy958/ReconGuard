import { Suspense } from "react";
import { describe, it, expect, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import BatchDashboard from "../page";
import type { BatchDetail, Decision, ExceptionListItem } from "@/lib/api-types";

vi.mock("@/lib/api-client", () => ({
  getBatch: vi.fn(),
  getAuditTrail: vi.fn(),
  getBatchDecisions: vi.fn(),
  listExceptions: vi.fn(),
}));

import {
  getBatch,
  getAuditTrail,
  getBatchDecisions,
  listExceptions,
} from "@/lib/api-client";

const BATCH_ID = "BATCH-0001";

function makeBatch(overrides: Partial<BatchDetail> = {}): BatchDetail {
  return {
    batch_id: BATCH_ID,
    status: "COMPLETED",
    summary: {
      total_records: 100,
      candidates_generated: 40,
      high_confidence_matches: 25,
      needs_review: 10,
      likely_no_match: 5,
      exceptions: 5,
      structural_matches: 8,
      one_to_many_matches: 5,
      many_to_one_matches: 3,
      risk_flagged_decisions: 4,
      failed_candidates: 0,
      processing_time_seconds: 12.5,
    },
    created_at: "2026-01-01T00:00:00Z",
    completed_at: "2026-01-01T00:05:00Z",
    failure_reason: null,
    ...overrides,
  };
}

function makeDecision(overrides: Partial<Decision> = {}): Decision {
  return {
    decision_id: "DEC-0001",
    batch_id: BATCH_ID,
    ledger_record_ids: ["LED-001"],
    settlement_record_ids: ["STL-001"],
    relationship_type: "one_to_one",
    model_name: "lightgbm_v1",
    model_version: "v1",
    probability: { raw: 0.9, calibrated: 0.92 },
    thresholds: { high: 0.85, low: 0.5 },
    decision: "HIGH_CONFIDENCE_MATCH",
    workflow_state: "AUTO_MATCHED",
    risk_flags: [],
    created_at: "2026-01-01T00:01:00Z",
    ...overrides,
  };
}

function makeException(overrides: Partial<ExceptionListItem> = {}): ExceptionListItem {
  return {
    exception_id: "EXC-0001",
    decision_id: "DEC-0002",
    category: "LOW_MATCH_CONFIDENCE",
    reason: "Calibrated match probability (0.2) fell below the review threshold (0.5).",
    created_at: "2026-01-01T00:02:00Z",
    relationship_type: "one_to_one",
    calibrated_probability: 0.2,
    ledger_record_ids: ["LED-002"],
    settlement_record_ids: ["STL-002"],
    risk_flags: [],
    primary_root_cause: "AMOUNT_DISCREPANCY",
    ...overrides,
  };
}

async function renderPage() {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <BatchDashboard params={Promise.resolve({ batchId: BATCH_ID })} />
      </Suspense>
    );
  });
}

describe("BatchDashboard charts", () => {
  it("renders the outcome distribution chart from the batch summary", async () => {
    vi.mocked(getBatch).mockResolvedValue(makeBatch());
    vi.mocked(getAuditTrail).mockResolvedValue({
      entity_type: "BATCH",
      entity_id: BATCH_ID,
      events: [],
    });
    vi.mocked(getBatchDecisions).mockResolvedValue({
      batch_id: BATCH_ID,
      decisions: [makeDecision()],
    });
    vi.mocked(listExceptions).mockResolvedValue({
      exceptions: [makeException()],
    });

    await renderPage();

    // Outcome chart is derived directly from BatchSummary and doesn't
    // depend on the decisions/exceptions fetches, so it renders as soon
    // as the batch itself loads.
    expect(await screen.findByText("Reconciliation outcomes")).toBeInTheDocument();
  });

  it("renders the confidence distribution chart once getBatchDecisions succeeds", async () => {
    vi.mocked(getBatch).mockResolvedValue(makeBatch());
    vi.mocked(getAuditTrail).mockResolvedValue({
      entity_type: "BATCH",
      entity_id: BATCH_ID,
      events: [],
    });
    vi.mocked(getBatchDecisions).mockResolvedValue({
      batch_id: BATCH_ID,
      decisions: [makeDecision({ probability: { raw: 0.6, calibrated: 0.55 } })],
    });
    vi.mocked(listExceptions).mockResolvedValue({ exceptions: [] });

    await renderPage();

    expect(await screen.findByText("Confidence distribution")).toBeInTheDocument();
    expect(getBatchDecisions).toHaveBeenCalledWith(BATCH_ID);
  });

  it("renders the root cause distribution chart once listExceptions succeeds", async () => {
    vi.mocked(getBatch).mockResolvedValue(makeBatch());
    vi.mocked(getAuditTrail).mockResolvedValue({
      entity_type: "BATCH",
      entity_id: BATCH_ID,
      events: [],
    });
    vi.mocked(getBatchDecisions).mockResolvedValue({
      batch_id: BATCH_ID,
      decisions: [],
    });
    vi.mocked(listExceptions).mockResolvedValue({
      exceptions: [makeException({ primary_root_cause: "VENDOR_MISMATCH" })],
    });

    await renderPage();

    expect(await screen.findByText("Why reconciliation failed")).toBeInTheDocument();
    expect(listExceptions).toHaveBeenCalledWith(undefined, BATCH_ID);
  });

  it("does not render the decisions/exceptions charts while their batch-scoped requests are still pending", async () => {
    vi.mocked(getBatch).mockResolvedValue(makeBatch());
    vi.mocked(getAuditTrail).mockResolvedValue({
      entity_type: "BATCH",
      entity_id: BATCH_ID,
      events: [],
    });
    // Never resolves within this test, simulating an in-flight request.
    vi.mocked(getBatchDecisions).mockReturnValue(new Promise(() => {}));
    vi.mocked(listExceptions).mockReturnValue(new Promise(() => {}));

    await renderPage();

    // The summary-derived chart still renders immediately...
    expect(await screen.findByText("Reconciliation outcomes")).toBeInTheDocument();
    // ...but the two data-dependent charts must not render before their
    // fetches succeed (this is what the success-state gating in page.tsx
    // is responsible for).
    expect(screen.queryByText("Confidence distribution")).not.toBeInTheDocument();
    expect(screen.queryByText("Why reconciliation failed")).not.toBeInTheDocument();
  });
});
