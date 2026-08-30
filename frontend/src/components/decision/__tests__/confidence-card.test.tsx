import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfidenceCard } from "../confidence-card";

describe("ConfidenceCard", () => {
  it("renders the real calibrated probability, not the raw score", () => {
    render(
      <ConfidenceCard
        probability={{ raw: 0.99, calibrated: 0.71 }}
        decision="NEEDS_REVIEW"
        thresholds={{ high: 0.85, low: 0.5 }}
      />
    );
    expect(screen.getByText("71%")).toBeInTheDocument();
  });

  it("shows the raw score separately in fine print, never blended into the headline number", () => {
    render(
      <ConfidenceCard
        probability={{ raw: 0.99, calibrated: 0.71 }}
        decision="NEEDS_REVIEW"
        thresholds={{ high: 0.85, low: 0.5 }}
      />
    );
    expect(screen.getByText("71%")).toBeInTheDocument();
    expect(screen.getByText(/Raw model score: 99%/)).toBeInTheDocument();
  });

  it("has no prop that could accept a risk flag — type signature enforces separation", () => {
    // Compile-time guarantee (see confidence-card.tsx's Pick<> type): the
    // component only accepts probability/decision/thresholds. The one
    // mention of "risk" that legitimately belongs here is the explicit
    // disclaimer sentence — checked separately below — not a leaked risk
    // flag or badge.
    render(
      <ConfidenceCard
        probability={{ raw: 0.5, calibrated: 0.5 }}
        decision="LIKELY_NO_MATCH"
        thresholds={{ high: 0.85, low: 0.5 }}
      />
    );
    expect(screen.queryByText(/STRUCTURAL_MATCH|ONE_TO_MANY|KNOWN_LOW/)).not.toBeInTheDocument();
  });

  it("explicitly states that operational risk never modifies this number", () => {
    render(
      <ConfidenceCard
        probability={{ raw: 0.5, calibrated: 0.5 }}
        decision="LIKELY_NO_MATCH"
        thresholds={{ high: 0.85, low: 0.5 }}
      />
    );
    expect(screen.getByText(/never modifies it/)).toBeInTheDocument();
  });

  it("displays real threshold values, not hardcoded ones", () => {
    render(
      <ConfidenceCard
        probability={{ raw: 0.9, calibrated: 0.9 }}
        decision="HIGH_CONFIDENCE_MATCH"
        thresholds={{ high: 0.7, low: 0.2 }}
      />
    );
    expect(screen.getByText(/Auto-match threshold: 70%/)).toBeInTheDocument();
    expect(screen.getByText(/Review threshold: 20%/)).toBeInTheDocument();
  });
});
