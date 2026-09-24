import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FinancialSummarySection } from "../financial-summary-section";
import type { FinancialSummary } from "@/lib/api-types";
import { formatCurrency } from "@/lib/formatters";

describe("FinancialSummarySection", () => {
  const sampleFinancials: FinancialSummary = {
    ledger: {
      total_amount: 100000.0,
      matched_amount: 85000.0,
      review_amount: 10000.0,
      exception_amount: 5000.0,
      matched_rate: 0.85,
      review_rate: 0.10,
      exception_rate: 0.05,
    },
    settlement: {
      total_amount: 98000.0,
      matched_amount: 85000.0,
      review_amount: 8000.0,
      exception_amount: 5000.0,
      matched_rate: 0.8673,
      review_rate: 0.0816,
      exception_rate: 0.051,
    },
  };

  it("renders financial section headers and titles", () => {
    render(<FinancialSummarySection financials={sampleFinancials} />);

    expect(screen.getByText("Financial Accounting")).toBeInTheDocument();
    expect(screen.getByText("Financial Reconciliation Summary")).toBeInTheDocument();
    expect(screen.getByText("Internal Accounts Ledger")).toBeInTheDocument();
    expect(screen.getByText("External Settlement Records")).toBeInTheDocument();
  });

  it("renders side metrics with correct amounts and percentages", () => {
    render(<FinancialSummarySection financials={sampleFinancials} />);

    // Total amounts
    expect(screen.getByText(formatCurrency(100000.0))).toBeInTheDocument();
    expect(screen.getByText(formatCurrency(98000.0))).toBeInTheDocument();

    // Reconciled rates badges
    expect(screen.getByText("85.0% Reconciled")).toBeInTheDocument();
    expect(screen.getByText("86.7% Reconciled")).toBeInTheDocument();

    // Buckets
    expect(screen.getAllByText("Matched")).toHaveLength(2);
    expect(screen.getAllByText("In Review")).toHaveLength(2);
    expect(screen.getAllByText("Exception")).toHaveLength(2);
  });

  it("displays unique source records invariant equation", () => {
    render(<FinancialSummarySection financials={sampleFinancials} />);

    const invariantLabels = screen.getAllByText("Unique Source Records Accounting");
    expect(invariantLabels).toHaveLength(2);

    // Ledger invariant text: 85k + 10k + 5k = 100k
    const ledgerEquation = `${formatCurrency(85000)} + ${formatCurrency(10000)} + ${formatCurrency(5000)} = ${formatCurrency(100000)}`;
    expect(screen.getByText(ledgerEquation)).toBeInTheDocument();
  });

  it("renders the exposure breakdown chart container", () => {
    render(<FinancialSummarySection financials={sampleFinancials} />);

    expect(screen.getByText("Financial Exposure Breakdown")).toBeInTheDocument();
  });
});
