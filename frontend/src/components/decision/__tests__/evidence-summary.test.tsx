import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EvidenceSummary } from "../evidence-summary";
import type { EvidenceItem } from "@/lib/api-types";

describe("EvidenceSummary", () => {
  it("splits real evidence into supporting and weakening columns", () => {
    const evidence: EvidenceItem[] = [
      { feature: "abs_amount_diff", value: 0.16, direction: "supports_match", strength: "strong" },
      { feature: "vendor_jaro_winkler_similarity", value: 0.18, direction: "weakens_match", strength: "weak" },
    ];
    render(<EvidenceSummary evidence={evidence} />);
    expect(screen.getByText("Absolute amount difference")).toBeInTheDocument();
    expect(screen.getByText("Jaro-Winkler similarity")).toBeInTheDocument();
  });

  it("labels ambiguity-creating evidence distinctly from plain weakening evidence", () => {
    const evidence: EvidenceItem[] = [
      { feature: "competing_candidate_count", value: 10, direction: "creates_ambiguity", strength: "strong" },
    ];
    render(<EvidenceSummary evidence={evidence} />);
    expect(screen.getByText(/creates ambiguity/i)).toBeInTheDocument();
  });

  it("shows a clear message when no evidence was recorded, rather than an empty section", () => {
    render(<EvidenceSummary evidence={[]} />);
    expect(screen.getByText(/No evidence attribution was recorded/)).toBeInTheDocument();
  });

  it("does not fabricate evidence beyond what was passed in", () => {
    const evidence: EvidenceItem[] = [
      { feature: "reference_exact_match", value: 1, direction: "supports_match", strength: "strong" },
    ];
    render(<EvidenceSummary evidence={evidence} />);
    expect(screen.getAllByText(/Exact match|Substring overlap|Reference similarity/).length).toBe(1);
  });
});
