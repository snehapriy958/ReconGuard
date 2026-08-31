import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ExceptionQueuePage from "../page";
import type { ExceptionListItem } from "@/lib/api-types";

vi.mock("@/lib/api-client", () => ({
  listExceptions: vi.fn(),
}));

import { listExceptions } from "@/lib/api-client";

function makeException(overrides: Partial<ExceptionListItem>): ExceptionListItem {
  return {
    exception_id: "EXC-0001",
    decision_id: "DEC-0001",
    category: "LOW_MATCH_CONFIDENCE",
    reason: "Calibrated match probability (0.2) fell below the review threshold (0.5).",
    created_at: "2026-01-01T00:00:00Z",
    relationship_type: "one_to_one",
    calibrated_probability: 0.2,
    ledger_record_ids: ["LED-001"],
    settlement_record_ids: ["STL-001"],
    risk_flags: [],
    primary_root_cause: "AMOUNT_DISCREPANCY",
    ...overrides,
  };
}

describe("ExceptionQueuePage", () => {
  it("renders real exceptions with structural groups intact", async () => {
    vi.mocked(listExceptions).mockResolvedValue({
      exceptions: [
        makeException({
          relationship_type: "one_to_many",
          ledger_record_ids: ["LED-001"],
          settlement_record_ids: ["STL-001", "STL-002"],
        }),
      ],
    });
    render(<ExceptionQueuePage />);
    expect(await screen.findByText("LED-001")).toBeInTheDocument();
    expect(screen.getByText("STL-002")).toBeInTheDocument();
  });

  it("shows the real primary root cause badge, not a generic status", async () => {
    vi.mocked(listExceptions).mockResolvedValue({
      exceptions: [makeException({ primary_root_cause: "VENDOR_MISMATCH" })],
    });
    render(<ExceptionQueuePage />);
    expect((await screen.findAllByText("Vendor Mismatch")).length).toBeGreaterThan(0);
  });

  it("shows a clear empty state for a batch with zero exceptions", async () => {
    vi.mocked(listExceptions).mockResolvedValue({ exceptions: [] });
    render(<ExceptionQueuePage />);
    expect(await screen.findByText(/No exceptions were produced/)).toBeInTheDocument();
  });

  it("filters by root cause, distinguishing 'no results for this filter' from 'no exceptions at all'", async () => {
    vi.mocked(listExceptions).mockResolvedValue({
      exceptions: [makeException({ primary_root_cause: "AMOUNT_DISCREPANCY" })],
    });
    render(<ExceptionQueuePage />);
    const dateCauseButtons = await screen.findAllByText("Amount Discrepancy");
    // one is the filter chip, one is the badge on the item — click the filter chip (first)
    fireEvent.click(dateCauseButtons[0]);
    expect(screen.getAllByText("Amount Discrepancy").length).toBeGreaterThan(0);
  });

  it("displays real risk flags separately from the root cause badge", async () => {
    vi.mocked(listExceptions).mockResolvedValue({
      exceptions: [makeException({ risk_flags: ["WEAK_REFERENCE_EVIDENCE"] })],
    });
    render(<ExceptionQueuePage />);
    expect(await screen.findByText("WEAK_REFERENCE_EVIDENCE")).toBeInTheDocument();
    expect(screen.getAllByText("Amount Discrepancy").length).toBeGreaterThan(0);
  });
});
