"use client";

import Link from "next/link";
import { use } from "react";
import { getDecision } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { LoadingState, ErrorState } from "@/components/dashboard/states";
import { Badge } from "@/components/ui/badge";
import {
  DECISION_LABELS,
  DECISION_TONE,
  formatProbability,
} from "@/lib/decision-display";

// Minimal scaffold only — the full Confidence Card (evidence quality,
// operational risk explanation, raw record comparison) is Phase 6.4.
// This route exists now so Phase 6.3's table can navigate somewhere real
// with the real decision ID, per that phase's explicit scope boundary.
export default function DecisionDetailPage({
  params,
}: {
  params: Promise<{ decisionId: string }>;
}) {
  const { decisionId } = use(params);
  const state = useApi(() => getDecision(decisionId), [decisionId]);

  return (
    <main className="mx-auto max-w-3xl p-8">
      {state.status === "success" && (
        <Link
          href={`/batches/${state.data.batch_id}/decisions`}
          className="text-sm text-slate-500 hover:text-slate-700"
        >
          ← Back to decisions
        </Link>
      )}

      {state.status === "loading" && (
        <div className="mt-4">
          <LoadingState label="Loading decision…" />
        </div>
      )}
      {state.status === "error" && (
        <div className="mt-4">
          <ErrorState error={state.error} onRetry={state.refetch} />
        </div>
      )}

      {state.status === "success" && (
        <div className="mt-4">
          <div className="mb-4 flex items-center gap-3">
            <h1 className="font-mono text-lg font-semibold text-slate-900">
              {state.data.decision_id}
            </h1>
            <Badge variant={DECISION_TONE[state.data.decision]}>
              {DECISION_LABELS[state.data.decision]}
            </Badge>
          </div>
          <p className="text-sm text-slate-600">
            Calibrated model confidence:{" "}
            <span className="font-medium text-slate-900">
              {formatProbability(state.data.probability.calibrated)}
            </span>
          </p>
          <p className="mt-4 text-xs text-slate-400">
            The full Confidence Card (evidence quality, risk explanation, and
            record comparison) is coming in the next iteration of this page.
          </p>
        </div>
      )}
    </main>
  );
}
