import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RootCauseCard } from "../root-cause-card";
import type { RootCauseAnalysis } from "@/lib/api-types";

function makeAnalysis(overrides: Partial<RootCauseAnalysis>): RootCauseAnalysis {
  return {
    primary_root_cause: "AMOUNT_DISCREPANCY",
    observed: ["relative_amount_diff=0.15 (threshold: 0.03)"],
    interpretation: ["Amount evidence is the clearest weakness among this candidate's evidence."],
    contributing_factors: [],
    investigation_guidance: "Check for fees, partial settlement, refunds, or split transactions.",
    taxonomy_version: "v1",
    ...overrides,
  };
}

describe("RootCauseCard", () => {
  it("renders the real primary root cause, observed evidence, and guidance", () => {
    render(<RootCauseCard analysis={makeAnalysis({})} />);
    expect(screen.getByText("Amount Discrepancy")).toBeInTheDocument();
    expect(screen.getByText(/relative_amount_diff=0.15/)).toBeInTheDocument();
    expect(screen.getByText(/Check for fees, partial settlement/)).toBeInTheDocument();
  });

  it("keeps observed and interpretation in visually separate sections", () => {
    render(<RootCauseCard analysis={makeAnalysis({})} />);
    expect(screen.getByText("Observed")).toBeInTheDocument();
    expect(screen.getByText("Interpretation")).toBeInTheDocument();
  });

  it("shows contributing factors only when present, not an empty section", () => {
    const { rerender } = render(<RootCauseCard analysis={makeAnalysis({ contributing_factors: [] })} />);
    expect(screen.queryByText("Contributing factors")).not.toBeInTheDocument();

    rerender(
      <RootCauseCard
        analysis={makeAnalysis({ contributing_factors: ["date_diff_days=20 (threshold: 7)"] })}
      />
    );
    expect(screen.getByText("Contributing factors")).toBeInTheDocument();
    expect(screen.getByText(/date_diff_days=20/)).toBeInTheDocument();
  });

  it("never displays a fabricated confidence percentage for the root cause itself", () => {
    render(<RootCauseCard analysis={makeAnalysis({})} />);
    expect(screen.queryByText(/cause confidence/i)).not.toBeInTheDocument();
    expect(screen.getByText(/not a probability/)).toBeInTheDocument();
  });

  it("visually flags system/processing failures as distinct from reconciliation findings", () => {
    render(
      <RootCauseCard
        analysis={makeAnalysis({
          primary_root_cause: "MISSING_SOURCE_RECORD",
          observed: ["One or more records could not be found."],
        })}
      />
    );
    expect(screen.getByText(/technical processing issue, not a reconciliation-quality finding/)).toBeInTheDocument();
  });

  it("does not show the system-failure banner for ordinary reconciliation findings", () => {
    render(<RootCauseCard analysis={makeAnalysis({ primary_root_cause: "VENDOR_MISMATCH" })} />);
    expect(screen.queryByText(/technical processing issue/)).not.toBeInTheDocument();
  });

  it("handles the unknown/insufficient-evidence case honestly, without forcing a specific cause", () => {
    render(
      <RootCauseCard
        analysis={makeAnalysis({
          primary_root_cause: "UNKNOWN_OR_INSUFFICIENT_EVIDENCE",
          observed: ["Feature evidence could not be recomputed for this decision."],
          interpretation: ["Insufficient evidence to classify the root cause."],
          investigation_guidance: "Inspect the underlying records and processing context directly.",
        })}
      />
    );
    expect(screen.getByText("Unknown / Insufficient Evidence")).toBeInTheDocument();
  });
});
