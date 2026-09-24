import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { ExportDialog } from "../export-dialog";
import * as apiClient from "@/lib/api-client";
import type { ReconciliationStatementResponse } from "@/lib/api-types";

vi.mock("@/lib/api-client", () => {
  return {
    getBatchExportUrl: vi.fn(
      (batchId: string, type: string) => `http://localhost:8000/batches/${batchId}/export/${type}`
    ),
    getReconciliationStatement: vi.fn(),
  };
});

const mockStatement: ReconciliationStatementResponse = {
  batch_id: "batch-123",
  status: "COMPLETED",
  created_at: "2026-09-24T12:00:00Z",
  completed_at: "2026-09-24T12:05:00Z",
  ledger_record_count: 50,
  settlement_record_count: 50,
  ledger: {
    total_amount: 10000.0,
    matched_amount: 7000.0,
    review_amount: 2000.0,
    exception_amount: 1000.0,
    matched_rate: 0.7,
    review_rate: 0.2,
    exception_rate: 0.1,
  },
  settlement: {
    total_amount: 10000.0,
    matched_amount: 7000.0,
    review_amount: 2000.0,
    exception_amount: 1000.0,
    matched_rate: 0.7,
    review_rate: 0.2,
    exception_rate: 0.1,
  },
  invariants: {
    ledger_amount_conservation: true,
    settlement_amount_conservation: true,
    ledger_rate_unity: true,
    settlement_rate_unity: true,
    all_invariants_hold: true,
  },
  summary: {
    high_confidence_matches: 35,
    needs_review: 10,
    exceptions: 5,
    structural_matches: 2,
  },
};

describe("ExportDialog", () => {
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.getReconciliationStatement).mockResolvedValue(mockStatement);
  });

  const renderOpenDialog = async () => {
    const result = render(<ExportDialog isOpen={true} onClose={onClose} batchId="batch-123" />);
    await waitFor(() => {
      expect(screen.getByTestId("invariants-verified-badge")).toBeInTheDocument();
    });
    return result;
  };

  it("1. does not render anything when isOpen is false", () => {
    const { container } = render(
      <ExportDialog isOpen={false} onClose={onClose} batchId="batch-123" />
    );
    expect(container.firstChild).toBeNull();
  });

  it("2. renders dialog with title, description, and batch ID when isOpen is true", async () => {
    await renderOpenDialog();

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Export Reconciliation Package")).toBeInTheDocument();
    expect(screen.getByText("batch-123")).toBeInTheDocument();
  });

  it("3. calls onClose when the close icon button is clicked", async () => {
    await renderOpenDialog();

    const closeBtn = screen.getByLabelText("Close export dialog");
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("4. calls onClose when clicking the backdrop", async () => {
    await renderOpenDialog();

    const backdrop = screen.getByTestId("export-dialog-backdrop");
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("5. calls onClose when pressing Escape key", async () => {
    await renderOpenDialog();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("6. calls onClose when clicking the Done button", async () => {
    await renderOpenDialog();

    const doneBtn = screen.getByRole("button", { name: "Done" });
    fireEvent.click(doneBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("7. renders Card 1 for Matched CSV with description and download button", async () => {
    await renderOpenDialog();

    expect(screen.getByText("Matched Source Records")).toBeInTheDocument();
    expect(screen.getByText(/Reconciled ledger and settlement records including auto-matches/)).toBeInTheDocument();
  });

  it("8. renders Card 2 for Exceptions CSV with description and download button", async () => {
    await renderOpenDialog();

    expect(screen.getByText("Unresolved Exceptions")).toBeInTheDocument();
    expect(screen.getByText(/All unresolved records and broken pairs mapped to standardized primary root causes/)).toBeInTheDocument();
  });

  it("9. renders Card 3 for Closing Statement with description and download button", async () => {
    await renderOpenDialog();

    expect(screen.getByText("Reconciliation Closing Statement")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download JSON/i })).toBeInTheDocument();
  });

  it("10. loads statement and displays 'Financial Invariants Verified' badge", async () => {
    await renderOpenDialog();

    expect(screen.getByTestId("invariants-verified-badge")).toBeInTheDocument();
    expect(screen.getByText("Financial Invariants Verified")).toBeInTheDocument();
    expect(screen.getByText(/Ledger: \$10,000.00/)).toBeInTheDocument();
  });

  it("11. displays error if statement fetching fails", async () => {
    vi.mocked(apiClient.getReconciliationStatement).mockRejectedValueOnce(
      new Error("Network connection error")
    );

    render(<ExportDialog isOpen={true} onClose={onClose} batchId="batch-123" />);

    await waitFor(() => {
      expect(screen.getByText("Network connection error")).toBeInTheDocument();
    });
  });

  it("12. triggers CSV download when Matched CSV button is clicked", async () => {
    await renderOpenDialog();

    const downloadSpy = vi.spyOn(document, "createElement");
    const downloadBtns = screen.getAllByRole("button", { name: /Download CSV/i });
    fireEvent.click(downloadBtns[0]); // Matched CSV

    expect(apiClient.getBatchExportUrl).toHaveBeenCalledWith("batch-123", "matched");
    expect(downloadSpy).toHaveBeenCalledWith("a");
    downloadSpy.mockRestore();
  });

  it("13. triggers CSV download when Exceptions CSV button is clicked", async () => {
    await renderOpenDialog();

    const downloadSpy = vi.spyOn(document, "createElement");
    const downloadBtns = screen.getAllByRole("button", { name: /Download CSV/i });
    fireEvent.click(downloadBtns[1]); // Exceptions CSV

    expect(apiClient.getBatchExportUrl).toHaveBeenCalledWith("batch-123", "exceptions");
    expect(downloadSpy).toHaveBeenCalledWith("a");
    downloadSpy.mockRestore();
  });

  it("14. triggers JSON download when statement download button is clicked", async () => {
    await renderOpenDialog();

    const createObjectUrlMock = vi.fn().mockReturnValue("blob:mock-url");
    const revokeObjectUrlMock = vi.fn();
    window.URL.createObjectURL = createObjectUrlMock;
    window.URL.revokeObjectURL = revokeObjectUrlMock;

    const downloadSpy = vi.spyOn(document, "createElement");
    const jsonBtn = screen.getByRole("button", { name: /Download JSON/i });
    fireEvent.click(jsonBtn);

    await waitFor(() => {
      expect(createObjectUrlMock).toHaveBeenCalled();
    });
    downloadSpy.mockRestore();
  });
});
