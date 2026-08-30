import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { EvidenceBreakdown } from "../evidence-breakdown";
import { RawRecordComparison, WhatChanged } from "../record-comparison";
import { OperationalRiskCard } from "../operational-risk-card";

const fullFeatures = {
  abs_amount_diff: 0.16,
  relative_amount_diff: 0.0002,
  amount_ratio: 0.9998,
  date_diff_days: 0,
  vendor_levenshtein_similarity: 0.18,
  vendor_jaro_winkler_similarity: 0.18,
  vendor_token_sort_similarity: 0.27,
  vendor_token_set_similarity: 0.27,
  vendor_exact_normalized_match: 0,
  vendor_embedding_cosine_similarity: 0.11,
  reference_exact_match: 0,
  reference_substring_overlap: 1,
  reference_similarity: 0.46,
  reference_both_missing: 0,
  candidate_count_for_ledger: 7,
  candidate_count_for_settlement: 5,
  competing_candidate_count: 10,
};

describe("EvidenceBreakdown", () => {
  it("renders real per-category strength derived from actual feature values", () => {
    render(<EvidenceBreakdown features={fullFeatures} />);
    expect(screen.getByText("Amount Evidence")).toBeInTheDocument();
    expect(screen.getByText(/Amounts differ by less than 1%/)).toBeInTheDocument();
    expect(screen.getByText(/Vendor similarity is low/)).toBeInTheDocument();
  });

  it("shows the high-competition case as weak, matching the shared threshold with risk.py", () => {
    render(<EvidenceBreakdown features={fullFeatures} />);
    expect(screen.getByText(/Multiple competing candidates increase ambiguity/)).toBeInTheDocument();
  });

  it("technical evidence is inspectable via the expandable details element", () => {
    render(<EvidenceBreakdown features={fullFeatures} />);
    const details = screen.getAllByText("Technical evidence")[0];
    expect(details.closest("details")).toBeInTheDocument();
  });
});

describe("RawRecordComparison", () => {
  it("renders one-to-one records with the ↔ connector", () => {
    render(
      <RawRecordComparison
        relationshipType="one_to_one"
        ledgerIds={["LED-001"]}
        settlementIds={["STL-001"]}
        ledgerRecords={[{ vendor_name: "Acme", amount: 100, txn_date: "2026-01-01", reference_id: "R1" }]}
        settlementRecords={[{ vendor_name: "Acme", amount: 99, txn_date: "2026-01-01", reference_id: "R1" }]}
      />
    );
    expect(screen.getByText("↔")).toBeInTheDocument();
    expect(screen.getByText("LED-001")).toBeInTheDocument();
  });

  it("renders one-to-many with every settlement record individually inspectable, not concatenated", () => {
    render(
      <RawRecordComparison
        relationshipType="one_to_many"
        ledgerIds={["LED-001"]}
        settlementIds={["STL-001", "STL-002"]}
        ledgerRecords={[{ vendor_name: "Acme", amount: 100, txn_date: "2026-01-01", reference_id: "" }]}
        settlementRecords={[
          { vendor_name: "Acme", amount: 60, txn_date: "2026-01-01", reference_id: "" },
          { vendor_name: "Acme", amount: 40, txn_date: "2026-01-01", reference_id: "" },
        ]}
      />
    );
    expect(screen.getByText("STL-001")).toBeInTheDocument();
    expect(screen.getByText("STL-002")).toBeInTheDocument();
  });

  it("clearly shows missing records rather than hiding them", () => {
    render(
      <RawRecordComparison
        relationshipType="one_to_one"
        ledgerIds={["LED-999"]}
        settlementIds={["STL-999"]}
        ledgerRecords={[null]}
        settlementRecords={[null]}
      />
    );
    expect(screen.getAllByText("Record not found").length).toBe(2);
  });

  it("displays 'Missing' for absent fields rather than blank cells", () => {
    render(
      <RawRecordComparison
        relationshipType="one_to_one"
        ledgerIds={["LED-001"]}
        settlementIds={["STL-001"]}
        ledgerRecords={[{ vendor_name: "Acme", amount: 100, txn_date: "2026-01-01", reference_id: "" }]}
        settlementRecords={[{ vendor_name: "Acme", amount: 100, txn_date: "2026-01-01", reference_id: "" }]}
      />
    );
    expect(screen.getAllByText("Missing").length).toBe(2);
  });
});

describe("WhatChanged", () => {
  it("compares individual amounts for a one-to-one match", () => {
    render(
      <WhatChanged
        ledgerRecords={[{ vendor_name: "Acme", amount: 1000, txn_date: "2026-01-01", reference_id: "R1" }]}
        settlementRecords={[{ vendor_name: "AMZN", amount: 997, txn_date: "2026-01-04", reference_id: "" }]}
      />
    );
    expect(screen.getByText("1,000")).toBeInTheDocument();
    expect(screen.getByText("997")).toBeInTheDocument();
  });

  it("compares ledger total against settlement GROUP TOTAL for a structural match, not an individual member", () => {
    render(
      <WhatChanged
        ledgerRecords={[{ vendor_name: "Acme", amount: 1000, txn_date: "2026-01-01", reference_id: "" }]}
        settlementRecords={[
          { vendor_name: "Acme", amount: 600, txn_date: "2026-01-01", reference_id: "" },
          { vendor_name: "Acme", amount: 400, txn_date: "2026-01-01", reference_id: "" },
        ]}
      />
    );
    expect(screen.getByText(/1,000 \(total\)/)).toBeInTheDocument();
    expect(screen.getByText(/1,000 \(group total\)/)).toBeInTheDocument();
  });

  it("shows an honest unavailable message when a record is missing rather than a wrong diff", () => {
    render(
      <WhatChanged
        ledgerRecords={[null]}
        settlementRecords={[{ vendor_name: "Acme", amount: 100, txn_date: "2026-01-01", reference_id: "" }]}
      />
    );
    expect(screen.getByText(/can't be shown/)).toBeInTheDocument();
  });
});

describe("OperationalRiskCard", () => {
  it("shows a clear neutral state with no risk flags", () => {
    render(<OperationalRiskCard riskFlags={[]} explanations={{}} />);
    expect(screen.getByText("No risk flags for this decision.")).toBeInTheDocument();
  });

  it("renders real flags with their real explanations, never a fabricated one", () => {
    render(
      <OperationalRiskCard
        riskFlags={["KNOWN_LOW_GENERALIZATION"]}
        explanations={{
          KNOWN_LOW_GENERALIZATION:
            "Held-out evaluation showed lower recall for this relationship type.",
        }}
      />
    );
    expect(screen.getByText("KNOWN_LOW_GENERALIZATION")).toBeInTheDocument();
    expect(
      screen.getByText(/Held-out evaluation showed lower recall/)
    ).toBeInTheDocument();
  });

  it("states explicitly that risk does not modify the calibrated probability", () => {
    render(<OperationalRiskCard riskFlags={["STRUCTURAL_MATCH"]} explanations={{ STRUCTURAL_MATCH: "x" }} />);
    expect(screen.getByText(/do not modify the model's calibrated probability/)).toBeInTheDocument();
  });
});
