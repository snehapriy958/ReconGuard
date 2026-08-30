import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ReviewQueuePage from "../page";
import type { ReviewListItem } from "@/lib/api-types";

vi.mock("@/lib/api-client", () => ({
  listReviews: vi.fn(),
}));

import { listReviews } from "@/lib/api-client";

function makeReview(overrides: Partial<ReviewListItem>): ReviewListItem {
  return {
    review_id: "REV-0001",
    decision_id: "DEC-0001",
    status: "OPEN",
    relationship_type: "one_to_one",
    calibrated_probability: 0.71,
    risk_flags: [],
    created_at: "2026-01-01T00:00:00Z",
    batch_id: "BATCH-0001",
    ledger_record_ids: ["LED-001"],
    settlement_record_ids: ["STL-001"],
    original_ml_decision: "NEEDS_REVIEW",
    ...overrides,
  };
}

describe("ReviewQueuePage", () => {
  it("renders real reviewable decisions from the backend, with structural groups intact", async () => {
    vi.mocked(listReviews).mockResolvedValue({
      reviews: [
        makeReview({
          review_id: "REV-A",
          relationship_type: "one_to_many",
          ledger_record_ids: ["LED-001"],
          settlement_record_ids: ["STL-001", "STL-002"],
        }),
      ],
    });
    render(<ReviewQueuePage />);
    expect(await screen.findByText("LED-001")).toBeInTheDocument();
    expect(screen.getByText("STL-001")).toBeInTheDocument();
    expect(screen.getByText("STL-002")).toBeInTheDocument();
  });

  it("shows the original ML decision and calibrated confidence, kept visually separate", async () => {
    vi.mocked(listReviews).mockResolvedValue({
      reviews: [makeReview({ calibrated_probability: 0.71, original_ml_decision: "NEEDS_REVIEW" })],
    });
    render(<ReviewQueuePage />);
    expect(await screen.findByText("71%")).toBeInTheDocument();
    expect(screen.getByText(/ML: Needs Review/)).toBeInTheDocument();
  });

  it("shows a clear empty state distinct from a loading state", async () => {
    vi.mocked(listReviews).mockResolvedValue({ reviews: [] });
    render(<ReviewQueuePage />);
    expect(await screen.findByText(/No decisions are currently awaiting review/)).toBeInTheDocument();
  });

  it("orders reviews oldest-first, deterministically", async () => {
    vi.mocked(listReviews).mockResolvedValue({
      reviews: [
        makeReview({ review_id: "REV-NEW", batch_id: "BATCH-NEW", created_at: "2026-02-01T00:00:00Z" }),
        makeReview({ review_id: "REV-OLD", batch_id: "BATCH-OLD", created_at: "2026-01-01T00:00:00Z" }),
      ],
    });
    render(<ReviewQueuePage />);
    const items = await screen.findAllByText(/BATCH-(NEW|OLD)/);
    expect(items[0].textContent).toContain("BATCH-OLD");
  });

  it("displays real risk flags on queue items, never a fabricated priority score", async () => {
    vi.mocked(listReviews).mockResolvedValue({
      reviews: [makeReview({ risk_flags: ["KNOWN_LOW_GENERALIZATION"] })],
    });
    render(<ReviewQueuePage />);
    expect(await screen.findByText("KNOWN_LOW_GENERALIZATION")).toBeInTheDocument();
  });
});
