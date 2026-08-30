import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { DECISION_LABELS } from "@/lib/decision-display";
import type { DecisionLabel } from "@/lib/api-types";

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

/**
 * A concise, review-specific timeline — NOT the full audit trail (that's
 * Phase 6.7). Only two real, persisted moments: when the model decided,
 * and when (if at all) a reviewer resolved it. No fabricated timestamps.
 */
export function ReviewHistory({
  modelDecision,
  modelDecisionAt,
  reviewStatus,
  resolvedAt,
  assignedReviewer,
}: {
  modelDecision: DecisionLabel;
  modelDecisionAt: string;
  reviewStatus: string;
  resolvedAt: string | null;
  assignedReviewer: string | null;
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-4 text-sm font-medium text-slate-700">
          Review history
        </CardTitle>
        <ol className="space-y-4">
          <li className="flex gap-3">
            <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-slate-400" />
            <div>
              <p className="text-xs text-slate-400">{formatTime(modelDecisionAt)}</p>
              <p className="text-sm text-slate-700">
                <span className="font-medium">Model decision:</span>{" "}
                {DECISION_LABELS[modelDecision]}
              </p>
            </div>
          </li>
          {resolvedAt ? (
            <li className="flex gap-3">
              <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-emerald-500" />
              <div>
                <p className="text-xs text-slate-400">{formatTime(resolvedAt)}</p>
                <p className="text-sm text-slate-700">
                  <span className="font-medium">Reviewer action:</span> {reviewStatus}
                  {assignedReviewer && ` by ${assignedReviewer}`}
                </p>
              </div>
            </li>
          ) : (
            <li className="flex gap-3">
              <div className="mt-1 h-2 w-2 shrink-0 rounded-full border border-slate-300" />
              <p className="text-sm text-slate-400">Awaiting reviewer action</p>
            </li>
          )}
        </ol>
      </CardContent>
    </Card>
  );
}
