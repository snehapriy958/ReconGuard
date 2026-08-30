"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { approveReview, rejectReview, ApiError } from "@/lib/api-client";

/**
 * Calls the real backend for every action — never simulates success
 * locally. `submitting` disables both buttons for the whole round trip,
 * which is the double-submission guard (spec Step 10): a second click
 * while a request is in flight is structurally impossible, not just
 * discouraged.
 */
export function ReviewActions({
  reviewId,
  status,
  onResolved,
}: {
  reviewId: string;
  status: string;
  onResolved: () => void;
}) {
  const [submitting, setSubmitting] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewerId, setReviewerId] = useState("");

  if (status !== "OPEN") {
    return (
      <Card>
        <CardContent className="p-4 text-sm text-slate-500">
          This review is already {status.toLowerCase()} — no further action
          is available.
        </CardContent>
      </Card>
    );
  }

  async function act(action: "approve" | "reject") {
    if (!reviewerId.trim()) {
      setError("Enter a reviewer name before submitting.");
      return;
    }
    setSubmitting(action);
    setError(null);
    try {
      if (action === "approve") {
        await approveReview(reviewId, reviewerId.trim());
      } else {
        await rejectReview(reviewId, reviewerId.trim());
      }
      onResolved();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError(
          "This review was already resolved (possibly by someone else). Refreshing…"
        );
        onResolved();
      } else if (e instanceof ApiError && e.status === 404) {
        setError("This review no longer exists.");
      } else if (e instanceof ApiError) {
        setError(e.message);
      } else {
        setError("Could not reach the backend. Please try again.");
      }
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <Card>
      <CardContent className="p-4">
        <label htmlFor="reviewer-name-input" className="block text-xs font-medium text-slate-500">
          Reviewer name
        </label>
        <input
          id="reviewer-name-input"
          type="text"
          value={reviewerId}
          onChange={(e) => setReviewerId(e.target.value)}
          placeholder="e.g. priya"
          disabled={submitting !== null}
          className="mt-1 w-full rounded-md border border-slate-200 px-3 py-1.5 text-sm disabled:bg-slate-50"
        />

        {error && <p className="mt-2 text-sm text-red-700">{error}</p>}

        <div className="mt-3 flex gap-2">
          <Button onClick={() => act("approve")} disabled={submitting !== null}>
            {submitting === "approve" ? "Approving…" : "Approve"}
          </Button>
          <Button variant="outline" onClick={() => act("reject")} disabled={submitting !== null}>
            {submitting === "reject" ? "Rejecting…" : "Reject"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
