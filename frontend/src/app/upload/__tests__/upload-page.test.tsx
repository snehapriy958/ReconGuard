import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import UploadPage from "../page";
import * as apiClient from "@/lib/api-client";
import type { BatchCreateResponse } from "@/lib/api-types";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/upload",
}));

vi.mock("@/lib/api-client", () => {
  class MockApiError extends Error {
    status: number;
    detail?: unknown;
    constructor(message: string, status: number, detail?: unknown) {
      super(message);
      this.status = status;
      this.detail = detail;
      this.name = "ApiError";
    }
  }

  return {
    uploadBatch: vi.fn(),
    ApiError: MockApiError,
  };
});

describe("UploadPage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const validLedgerCsv = `ledger_id,vendor_name,amount,txn_date
L001,Acme Corp,150.00,2026-03-01
L002,Beta LLC,250.50,2026-03-02`;

  const validSettlementCsv = `settlement_id,vendor_name,amount,txn_date
S001,Acme Corp,150.00,2026-03-01
S002,Beta LLC,250.50,2026-03-02`;

  const invalidHeaderCsv = `id,name,val,date
1,Acme Corp,150.00,2026-03-01`;

  it("1. upload page renders title and descriptions", () => {
    render(<UploadPage />);

    expect(screen.getByRole("heading", { name: "Upload Reconciliation Batch" })).toBeInTheDocument();
    expect(screen.getByText(/Submit your internal accounts ledger and external settlement files/i)).toBeInTheDocument();
    expect(screen.getByText(/Processing Note/i)).toBeInTheDocument();
  });

  it("2. both file drop zones render with distinct labels (Ledger vs Settlement)", () => {
    render(<UploadPage />);

    expect(screen.getByText("1. Internal Ledger CSV")).toBeInTheDocument();
    expect(screen.getByText("2. Settlement CSV")).toBeInTheDocument();
    expect(screen.getByText("Select or drag ledger CSV")).toBeInTheDocument();
    expect(screen.getByText("Select or drag settlement CSV")).toBeInTheDocument();
  });

  it("3. submit button initially disabled", () => {
    render(<UploadPage />);

    const submitBtn = screen.getByRole("button", { name: /Reconcile Batch/i });
    expect(submitBtn).toBeDisabled();
    expect(screen.getByText(/Please select valid Ledger and Settlement CSV files to proceed/i)).toBeInTheDocument();
  });

  it("4. selecting valid ledger CSV updates UI (file name, row count preview)", async () => {
    render(<UploadPage />);

    const file = new File([validLedgerCsv], "ledger_sample.csv", { type: "text/csv" });
    const input = screen.getByTestId("ledger-file-input");

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText("ledger_sample.csv")).toBeInTheDocument();
    });

    expect(screen.getByText("2")).toBeInTheDocument(); // 2 records detected
    expect(screen.getByText("Valid")).toBeInTheDocument();
  });

  it("5. selecting valid settlement CSV updates UI", async () => {
    render(<UploadPage />);

    const file = new File([validSettlementCsv], "settlement_sample.csv", { type: "text/csv" });
    const input = screen.getByTestId("settlement-file-input");

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText("settlement_sample.csv")).toBeInTheDocument();
    });

    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Valid")).toBeInTheDocument();
  });

  it("6. selecting CSV with missing required columns shows client-side validation error", async () => {
    render(<UploadPage />);

    const file = new File([invalidHeaderCsv], "bad_ledger.csv", { type: "text/csv" });
    const input = screen.getByTestId("ledger-file-input");

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText("Invalid Schema")).toBeInTheDocument();
    });

    expect(screen.getByText(/Missing required columns: ledger_id, vendor_name, amount, txn_date/i)).toBeInTheDocument();
  });

  it("7. selecting empty / no-row CSV shows client-side error", async () => {
    render(<UploadPage />);

    const file = new File(["ledger_id,vendor_name,amount,txn_date\n"], "empty.csv", { type: "text/csv" });
    const input = screen.getByTestId("ledger-file-input");

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText("Invalid Schema")).toBeInTheDocument();
    });

    expect(screen.getByText(/File has no data rows/i)).toBeInTheDocument();
  });

  it("8. submitting valid files triggers uploadBatch() with FormData", async () => {
    const mockUpload = vi.mocked(apiClient.uploadBatch).mockResolvedValueOnce({
      batch_id: "BATCH-TEST-001",
      status: "COMPLETED",
      summary: null,
    });

    render(<UploadPage />);

    const ledgerFile = new File([validLedgerCsv], "ledger.csv", { type: "text/csv" });
    const settlementFile = new File([validSettlementCsv], "settlement.csv", { type: "text/csv" });

    fireEvent.change(screen.getByTestId("ledger-file-input"), { target: { files: [ledgerFile] } });
    fireEvent.change(screen.getByTestId("settlement-file-input"), { target: { files: [settlementFile] } });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Reconcile Batch/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: /Reconcile Batch/i }));

    await waitFor(() => {
      expect(mockUpload).toHaveBeenCalledTimes(1);
    });

    expect(mockUpload).toHaveBeenCalledWith(ledgerFile, settlementFile);
  });

  it("9. submit button shows loading state and disables re-submission", async () => {
    let resolveUpload!: (val: BatchCreateResponse) => void;
    const uploadPromise = new Promise<BatchCreateResponse>((resolve) => {
      resolveUpload = resolve;
    });

    vi.mocked(apiClient.uploadBatch).mockReturnValueOnce(uploadPromise);

    render(<UploadPage />);

    const ledgerFile = new File([validLedgerCsv], "ledger.csv", { type: "text/csv" });
    const settlementFile = new File([validSettlementCsv], "settlement.csv", { type: "text/csv" });

    fireEvent.change(screen.getByTestId("ledger-file-input"), { target: { files: [ledgerFile] } });
    fireEvent.change(screen.getByTestId("settlement-file-input"), { target: { files: [settlementFile] } });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Reconcile Batch/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: /Reconcile Batch/i }));

    await waitFor(() => {
      expect(screen.getByText(/Reconciling Batch…/i)).toBeInTheDocument();
    });

    const submitBtn = screen.getByRole("button", { name: /Reconciling Batch…/i });
    expect(submitBtn).toBeDisabled();

    // Resolve upload to clean up
    resolveUpload!({
      batch_id: "BATCH-123",
      status: "COMPLETED",
      summary: null,
    });
  });

  it("10. successful upload redirects to /batches/{batch_id}", async () => {
    vi.mocked(apiClient.uploadBatch).mockResolvedValueOnce({
      batch_id: "BATCH-NEW-999",
      status: "COMPLETED",
      summary: null,
    });

    render(<UploadPage />);

    const ledgerFile = new File([validLedgerCsv], "ledger.csv", { type: "text/csv" });
    const settlementFile = new File([validSettlementCsv], "settlement.csv", { type: "text/csv" });

    fireEvent.change(screen.getByTestId("ledger-file-input"), { target: { files: [ledgerFile] } });
    fireEvent.change(screen.getByTestId("settlement-file-input"), { target: { files: [settlementFile] } });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Reconcile Batch/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: /Reconcile Batch/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/batches/BATCH-NEW-999");
    });
  });

  it("11. API 400 validation error renders error table with row/column/message", async () => {
    const errorPayload = {
      message: "CSV validation failed",
      errors: [
        { file: "ledger", row: 4, field: "amount", message: "Invalid amount value: 'invalid'" },
        { file: "settlement", row: 2, field: "settlement_id", message: "Duplicate ID" },
      ],
    };

    const apiErr = new apiClient.ApiError("CSV validation failed", 400, errorPayload);
    vi.mocked(apiClient.uploadBatch).mockRejectedValueOnce(apiErr);

    render(<UploadPage />);

    const ledgerFile = new File([validLedgerCsv], "ledger.csv", { type: "text/csv" });
    const settlementFile = new File([validSettlementCsv], "settlement.csv", { type: "text/csv" });

    fireEvent.change(screen.getByTestId("ledger-file-input"), { target: { files: [ledgerFile] } });
    fireEvent.change(screen.getByTestId("settlement-file-input"), { target: { files: [settlementFile] } });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Reconcile Batch/i })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: /Reconcile Batch/i }));

    await waitFor(() => {
      expect(screen.getByText("CSV validation failed")).toBeInTheDocument();
    });

    expect(screen.getByText("Invalid amount value: 'invalid'")).toBeInTheDocument();
    expect(screen.getByText("Duplicate ID")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("settlement")).toBeInTheDocument();
  });

  it("12. remove/clear file button resets state", async () => {
    render(<UploadPage />);

    const ledgerFile = new File([validLedgerCsv], "ledger.csv", { type: "text/csv" });
    fireEvent.change(screen.getByTestId("ledger-file-input"), { target: { files: [ledgerFile] } });

    await waitFor(() => {
      expect(screen.getByText("ledger.csv")).toBeInTheDocument();
    });

    const clearBtn = screen.getByRole("button", { name: "Remove ledger file" });
    fireEvent.click(clearBtn);

    expect(screen.queryByText("ledger.csv")).not.toBeInTheDocument();
    expect(screen.getByText("Select or drag ledger CSV")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reconcile Batch/i })).toBeDisabled();
  });
});
