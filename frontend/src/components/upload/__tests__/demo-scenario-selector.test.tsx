import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DemoScenarioSelector } from "../demo-scenario-selector";
import * as apiClient from "@/lib/api-client";
import type { DemoDatasetsResponse } from "@/lib/api-types";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lib/api-client", () => {
  class MockApiError extends Error {
    status: number;
    constructor(message: string, status = 500) {
      super(message);
      this.status = status;
      this.name = "ApiError";
    }
  }

  return {
    getDemoDatasets: vi.fn(),
    processDemoDataset: vi.fn(),
    getDemoDatasetFileUrl: vi.fn(
      (id: string, type: string) => `http://localhost:8000/demo-datasets/${id}/files/${type}`
    ),
    ApiError: MockApiError,
  };
});

const mockDatasets: DemoDatasetsResponse = {
  datasets: [
    {
      id: "clean-settlement",
      name: "Clean Daily Settlement",
      description: "Routine 1:1 matching with clean reference IDs.",
      ledger_record_count: 20,
      settlement_record_count: 20,
      tags: ["1:1", "high-confidence", "routine"],
    },
    {
      id: "structural-splits",
      name: "Structural 1:N & N:1 Batches",
      description: "Complex many-to-one batch settlements.",
      ledger_record_count: 25,
      settlement_record_count: 25,
      tags: ["structural", "1:N", "N:1"],
    },
    {
      id: "discrepancies-exceptions",
      name: "Discrepancy & Exception Queue",
      description: "Amount discrepancies and missing IDs.",
      ledger_record_count: 20,
      settlement_record_count: 20,
      tags: ["exceptions", "drift", "unmatched"],
    },
    {
      id: "balanced-portfolio",
      name: "Balanced Real-World Batch",
      description: "Realistic cross-section of enterprise operations.",
      ledger_record_count: 40,
      settlement_record_count: 45,
      tags: ["balanced", "portfolio", "real-world"],
    },
  ],
};

describe("DemoScenarioSelector Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. renders loading state while fetching scenarios", () => {
    vi.mocked(apiClient.getDemoDatasets).mockImplementation(
      () => new Promise(() => {}) // never resolves
    );

    render(<DemoScenarioSelector />);
    expect(screen.getByText("Loading demonstration scenarios…")).toBeInTheDocument();
  });

  it("2. renders all scenario cards with title, description, tags, and record counts", async () => {
    vi.mocked(apiClient.getDemoDatasets).mockResolvedValue(mockDatasets);

    render(<DemoScenarioSelector />);

    await waitFor(() => {
      expect(screen.getByText("Clean Daily Settlement")).toBeInTheDocument();
    });

    expect(screen.getByText("Structural 1:N & N:1 Batches")).toBeInTheDocument();
    expect(screen.getByText("Discrepancy & Exception Queue")).toBeInTheDocument();
    expect(screen.getByText("Balanced Real-World Batch")).toBeInTheDocument();

    // Descriptions
    expect(screen.getByText("Routine 1:1 matching with clean reference IDs.")).toBeInTheDocument();
    expect(screen.getByText("Complex many-to-one batch settlements.")).toBeInTheDocument();

    // Tags
    expect(screen.getByText("high-confidence")).toBeInTheDocument();
    expect(screen.getByText("structural")).toBeInTheDocument();
    expect(screen.getByText("exceptions")).toBeInTheDocument();

    // Record counts
    expect(screen.getAllByText(/20 ledger/i)).toHaveLength(2);
    expect(screen.getByText(/40 ledger/i)).toBeInTheDocument();
    expect(screen.getByText(/45 settlement/i)).toBeInTheDocument();
  });

  it("3. renders raw CSV inspection download links", async () => {
    vi.mocked(apiClient.getDemoDatasets).mockResolvedValue(mockDatasets);

    render(<DemoScenarioSelector />);

    await waitFor(() => {
      expect(screen.getByText("Clean Daily Settlement")).toBeInTheDocument();
    });

    const ledgerLinks = screen.getAllByRole("link", { name: /Inspect ledger CSV/i });
    expect(ledgerLinks.length).toBe(4);
    expect(ledgerLinks[0]).toHaveAttribute(
      "href",
      "http://localhost:8000/demo-datasets/clean-settlement/files/ledger"
    );

    const settlementLinks = screen.getAllByRole("link", { name: /Inspect settlement CSV/i });
    expect(settlementLinks.length).toBe(4);
    expect(settlementLinks[1]).toHaveAttribute(
      "href",
      "http://localhost:8000/demo-datasets/structural-splits/files/settlement"
    );
  });

  it("4. clicking 'Run Scenario' calls processDemoDataset and navigates to the batch", async () => {
    vi.mocked(apiClient.getDemoDatasets).mockResolvedValue(mockDatasets);
    vi.mocked(apiClient.processDemoDataset).mockResolvedValue({
      batch_id: "batch-clean-1234",
      status: "COMPLETED",
      summary: null,
    });

    render(<DemoScenarioSelector />);

    await waitFor(() => {
      expect(screen.getByText("Clean Daily Settlement")).toBeInTheDocument();
    });

    const runButtons = screen.getAllByRole("button", { name: /Run .* scenario/i });
    fireEvent.click(runButtons[0]);

    expect(apiClient.processDemoDataset).toHaveBeenCalledWith("clean-settlement");

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/batches/batch-clean-1234");
    });
  });

  it("5. calls onScenarioProcessed callback if provided", async () => {
    vi.mocked(apiClient.getDemoDatasets).mockResolvedValue(mockDatasets);
    vi.mocked(apiClient.processDemoDataset).mockResolvedValue({
      batch_id: "batch-cb-5678",
      status: "COMPLETED",
      summary: null,
    });

    const mockCallback = vi.fn();
    render(<DemoScenarioSelector onScenarioProcessed={mockCallback} />);

    await waitFor(() => {
      expect(screen.getByText("Structural 1:N & N:1 Batches")).toBeInTheDocument();
    });

    const runButtons = screen.getAllByRole("button", { name: /Run .* scenario/i });
    fireEvent.click(runButtons[1]);

    await waitFor(() => {
      expect(mockCallback).toHaveBeenCalledWith("batch-cb-5678");
      expect(mockPush).not.toHaveBeenCalled();
    });
  });

  it("6. displays friendly error alert banner when processing fails", async () => {
    vi.mocked(apiClient.getDemoDatasets).mockResolvedValue(mockDatasets);
    vi.mocked(apiClient.processDemoDataset).mockRejectedValue(
      new Error("Demo scenario files missing on disk")
    );

    render(<DemoScenarioSelector />);

    await waitFor(() => {
      expect(screen.getByText("Discrepancy & Exception Queue")).toBeInTheDocument();
    });

    const runButtons = screen.getAllByRole("button", { name: /Run .* scenario/i });
    fireEvent.click(runButtons[2]);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(
        screen.getByText(/Demo scenario files missing on disk/i)
      ).toBeInTheDocument();
    });
  });

  it("7. renders error state when getDemoDatasets fails with retry", async () => {
    vi.mocked(apiClient.getDemoDatasets).mockRejectedValue(
      new Error("Network connection lost")
    );

    render(<DemoScenarioSelector />);

    await waitFor(() => {
      expect(screen.getByText(/Network connection lost/i)).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
  });
});
