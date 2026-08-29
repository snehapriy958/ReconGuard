import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCard } from "../stat-card";
import { BatchStatusBadge } from "../batch-status-badge";

describe("StatCard", () => {
  it("renders the exact numeric value passed in, not a placeholder", () => {
    render(<StatCard label="Auto-matched" value={62} tone="success" />);
    expect(screen.getByText("62")).toBeInTheDocument();
    expect(screen.getByText("Auto-matched")).toBeInTheDocument();
  });

  it("renders zero explicitly rather than hiding the card", () => {
    render(<StatCard label="Exceptions" value={0} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("shows the optional hint when provided", () => {
    render(
      <StatCard
        label="Structural matches"
        value={18}
        hint="18 one-to-many · 0 many-to-one"
      />
    );
    expect(screen.getByText("18 one-to-many · 0 many-to-one")).toBeInTheDocument();
  });
});

describe("BatchStatusBadge", () => {
  it("renders the real status text for every known status", () => {
    const statuses = ["CREATED", "PROCESSING", "COMPLETED", "FAILED"] as const;
    for (const status of statuses) {
      const { unmount } = render(<BatchStatusBadge status={status} />);
      expect(screen.getByText(status)).toBeInTheDocument();
      unmount();
    }
  });
});
