import { describe, it, expect } from "vitest";
import { render, screen, within, fireEvent } from "@testing-library/react";
import { vi } from "vitest";
import { DecisionTable } from "../decision-table";
import type { Decision } from "@/lib/api-types";

// The router is required by the table (row click navigation) but not under
// test here — mocked so tests focus on rendering/filtering behavior.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function makeDecision(overrides: Partial<Decision>): Decision {
  return {
    decision_id: "DEC-0001",
    batch_id: "BATCH-0001",
    ledger_record_ids: ["LED-001"],
    settlement_record_ids: ["STL-001"],
    relationship_type: "one_to_one",
    model_name: "lightgbm",
    model_version: "phase4_unified_v1",
    probability: { raw: 0.99, calibrated: 0.91 },
    thresholds: { high: 0.85, low: 0.5 },
    decision: "HIGH_CONFIDENCE_MATCH",
    workflow_state: "AUTO_MATCHED",
    risk_flags: [],
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("DecisionTable — real data rendering", () => {
  it("renders the actual calibrated probability, not a placeholder", () => {
    render(<DecisionTable decisions={[makeDecision({ probability: { raw: 0.99, calibrated: 0.7068 } })]} />);
    expect(screen.getByText("71%")).toBeInTheDocument();
  });

  it("renders risk flags independently from confidence — both visible, not merged", () => {
    const d = makeDecision({
      relationship_type: "one_to_many",
      settlement_record_ids: ["STL-001", "STL-002"],
      probability: { raw: 0.95, calibrated: 0.91 },
      risk_flags: ["STRUCTURAL_MATCH", "KNOWN_LOW_GENERALIZATION"],
    });
    render(<DecisionTable decisions={[d]} />);
    expect(screen.getByText("91%")).toBeInTheDocument();
    expect(screen.getByText("STRUCTURAL_MATCH")).toBeInTheDocument();
    expect(screen.getByText("KNOWN_LOW_GENERALIZATION")).toBeInTheDocument();
  });

  it("shows a clear neutral state when there are no risk flags, not a blank cell", () => {
    render(<DecisionTable decisions={[makeDecision({ risk_flags: [] })]} />);
    expect(screen.getByText("No risk flags")).toBeInTheDocument();
  });

  it("renders one-to-many structural relationships without flattening them", () => {
    const d = makeDecision({
      relationship_type: "one_to_many",
      ledger_record_ids: ["LED-001"],
      settlement_record_ids: ["STL-001", "STL-002"],
    });
    render(<DecisionTable decisions={[d]} />);
    expect(screen.getByText("LED-001")).toBeInTheDocument();
    expect(screen.getByText("STL-001")).toBeInTheDocument();
    expect(screen.getByText("STL-002")).toBeInTheDocument();
    // "One-to-Many" appears both as a filter chip and a table cell — scope
    // to the table body to check the cell specifically.
    const table = screen.getByRole("table");
    expect(within(table).getByText("One-to-Many")).toBeInTheDocument();
  });

  it("renders many-to-one structural relationships with both ledger ids visible", () => {
    const d = makeDecision({
      relationship_type: "many_to_one",
      ledger_record_ids: ["LED-001", "LED-002"],
      settlement_record_ids: ["STL-001"],
    });
    render(<DecisionTable decisions={[d]} />);
    expect(screen.getByText("LED-001")).toBeInTheDocument();
    expect(screen.getByText("LED-002")).toBeInTheDocument();
  });

  it("shows both the original ML decision and the current workflow status when they differ, side by side", () => {
    const d = makeDecision({
      decision: "NEEDS_REVIEW",
      workflow_state: "APPROVED_BY_REVIEWER",
    });
    render(<DecisionTable decisions={[d]} />);
    const table = screen.getByRole("table");
    // Both values must be visible in their own columns — this IS how the
    // table preserves the distinction, without needing extra derived logic.
    expect(within(table).getByText("Needs Review")).toBeInTheDocument();
    expect(within(table).getByText("Approved")).toBeInTheDocument();
  });

  it("shows a matching decision and workflow status when they agree", () => {
    render(<DecisionTable decisions={[makeDecision({})]} />);
    const table = screen.getByRole("table");
    expect(within(table).getAllByText("Auto Matched").length).toBeGreaterThan(0);
  });
});

describe("DecisionTable — empty and filter states", () => {
  it("shows an empty state for a batch with zero decisions", () => {
    render(<DecisionTable decisions={[]} />);
    expect(screen.getByText(/No decisions were produced/)).toBeInTheDocument();
  });

  it("shows a distinct no-results state when filters exclude everything, not a blank table", () => {
    render(<DecisionTable decisions={[makeDecision({ decision: "HIGH_CONFIDENCE_MATCH" })]} />);
    fireEvent.click(screen.getByText("Needs Review"));
    expect(screen.getByText(/No decisions match the current filters/)).toBeInTheDocument();
  });

  it("filters by decision type correctly", () => {
    const decisions = [
      makeDecision({ decision_id: "DEC-A", decision: "HIGH_CONFIDENCE_MATCH" }),
      makeDecision({ decision_id: "DEC-B", decision: "NEEDS_REVIEW", workflow_state: "NEEDS_REVIEW" }),
    ];
    render(<DecisionTable decisions={decisions} />);
    fireEvent.click(screen.getByRole("button", { name: "Needs Review" }));
    expect(screen.queryByText("DEC-A")).not.toBeInTheDocument();
  });

  it("filters by relationship type correctly", () => {
    const decisions = [
      makeDecision({ decision_id: "DEC-A", relationship_type: "one_to_one" }),
      makeDecision({
        decision_id: "DEC-B",
        relationship_type: "many_to_one",
        ledger_record_ids: ["LED-010", "LED-011"],
      }),
    ];
    render(<DecisionTable decisions={decisions} />);
    fireEvent.click(screen.getByRole("button", { name: "Many-to-One" }));
    expect(screen.getByText("LED-010")).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).queryByText("One-to-One")).not.toBeInTheDocument();
  });

  it("filters by risk-flagged status correctly", () => {
    const decisions = [
      makeDecision({ decision_id: "DEC-A", risk_flags: [] }),
      makeDecision({ decision_id: "DEC-B", risk_flags: ["HIGH_COMPETITION"] }),
    ];
    render(<DecisionTable decisions={decisions} />);
    fireEvent.click(screen.getByText("Risk Flagged"));
    expect(screen.getByText("HIGH_COMPETITION")).toBeInTheDocument();
    expect(screen.queryByText("No risk flags")).not.toBeInTheDocument();
  });
});
