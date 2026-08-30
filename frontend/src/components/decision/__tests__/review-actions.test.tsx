import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ReviewActions } from "../review-actions";
import { ApiError } from "@/lib/api-client";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, approveReview: vi.fn(), rejectReview: vi.fn() };
});

import { approveReview, rejectReview } from "@/lib/api-client";

describe("ReviewActions", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows a clear resolved message and no buttons when status is not OPEN", () => {
    render(<ReviewActions reviewId="REV-1" status="APPROVED" onResolved={vi.fn()} />);
    expect(screen.getByText(/already approved/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("requires a reviewer name before submitting", () => {
    render(<ReviewActions reviewId="REV-1" status="OPEN" onResolved={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(screen.getByText(/Enter a reviewer name/)).toBeInTheDocument();
    expect(approveReview).not.toHaveBeenCalled();
  });

  it("calls the real approve API with the entered reviewer name", async () => {
    vi.mocked(approveReview).mockResolvedValue({ review_id: "REV-1", status: "APPROVED" });
    const onResolved = vi.fn();
    render(<ReviewActions reviewId="REV-1" status="OPEN" onResolved={onResolved} />);
    fireEvent.change(screen.getByLabelText(/Reviewer name/i), {
      target: { value: "priya" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(approveReview).toHaveBeenCalledWith("REV-1", "priya"));
    await waitFor(() => expect(onResolved).toHaveBeenCalled());
  });

  it("calls the real reject API, not a simulated local result", async () => {
    vi.mocked(rejectReview).mockResolvedValue({ review_id: "REV-1", status: "REJECTED" });
    render(<ReviewActions reviewId="REV-1" status="OPEN" onResolved={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText("e.g. priya"), { target: { value: "priya" } });
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    await waitFor(() => expect(rejectReview).toHaveBeenCalledWith("REV-1", "priya"));
  });

  it("disables both buttons while a request is in flight — the double-submit guard", async () => {
    let resolvePromise: (v: { review_id: string; status: string }) => void;
    vi.mocked(approveReview).mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve;
      })
    );
    render(<ReviewActions reviewId="REV-1" status="OPEN" onResolved={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText("e.g. priya"), { target: { value: "priya" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Approving…" })).toBeDisabled());
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();

    const { act } = await import("@testing-library/react");
    await act(async () => {
      resolvePromise!({ review_id: "REV-1", status: "APPROVED" });
    });
  });

  it("shows an honest message and refreshes when the review was already resolved elsewhere (409)", async () => {
    vi.mocked(approveReview).mockRejectedValue(new ApiError("already resolved", 409));
    const onResolved = vi.fn();
    render(<ReviewActions reviewId="REV-1" status="OPEN" onResolved={onResolved} />);
    fireEvent.change(screen.getByPlaceholderText("e.g. priya"), { target: { value: "priya" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(screen.getByText(/already resolved/)).toBeInTheDocument());
    expect(onResolved).toHaveBeenCalled();
  });

  it("shows a not-found message on 404, without pretending the action succeeded", async () => {
    vi.mocked(approveReview).mockRejectedValue(new ApiError("not found", 404));
    render(<ReviewActions reviewId="REV-1" status="OPEN" onResolved={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText("e.g. priya"), { target: { value: "priya" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(screen.getByText(/no longer exists/)).toBeInTheDocument());
  });

  it("shows a network-failure message distinct from a backend rejection", async () => {
    vi.mocked(approveReview).mockRejectedValue(new ApiError("Could not reach the ReconLens API", 0));
    render(<ReviewActions reviewId="REV-1" status="OPEN" onResolved={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText("e.g. priya"), { target: { value: "priya" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(screen.getByText(/Could not reach/)).toBeInTheDocument());
  });
});
