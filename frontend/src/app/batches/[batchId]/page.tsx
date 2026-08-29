"use client";

import Link from "next/link";
import { use } from "react";
import { getBatch } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { LoadingState, ErrorState } from "@/components/dashboard/states";
import { BatchStatusBadge } from "@/components/dashboard/batch-status-badge";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent } from "@/components/ui/card";

export default function BatchDashboard({
  params,
}: {
  params: Promise<{ batchId: string }>;
}) {
  const { batchId } = use(params);
  const state = useApi(() => getBatch(batchId), [batchId]);

  return (
    <main className="mx-auto max-w-5xl p-8">
      <Link href="/" className="text-sm text-slate-500 hover:text-slate-700">
        ← All batches
      </Link>

      {state.status === "loading" && (
        <div className="mt-4">
          <LoadingState label="Loading batch…" />
        </div>
      )}
      {state.status === "error" && (
        <div className="mt-4">
          <ErrorState error={state.error} onRetry={state.refetch} />
        </div>
      )}

      {state.status === "success" && (
        <>
          <div className="mt-2 mb-6 flex items-center gap-3">
            <h1 className="font-mono text-lg font-semibold text-slate-900">
              {state.data.batch_id}
            </h1>
            <BatchStatusBadge status={state.data.status} />
          </div>

          {state.data.status === "FAILED" && (
            <Card className="mb-6 border-red-200 bg-red-50">
              <CardContent className="py-4 text-sm text-red-800">
                Processing failed: {state.data.failure_reason ?? "no reason recorded"}
              </CardContent>
            </Card>
          )}

          {state.data.status === "PROCESSING" && (
            <Card className="mb-6 border-blue-200 bg-blue-50">
              <CardContent className="py-4 text-sm text-blue-800">
                This batch is still processing — refresh to check progress.
              </CardContent>
            </Card>
          )}

          {state.data.summary ? (
            <>
              <section className="mb-6">
                <h2 className="mb-2 text-sm font-medium text-slate-700">
                  What happened during this run
                </h2>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  <StatCard
                    label="Total records"
                    value={state.data.summary.total_records}
                  />
                  <StatCard
                    label="Candidates generated"
                    value={state.data.summary.candidates_generated}
                  />
                  <StatCard
                    label="Auto-matched"
                    value={state.data.summary.high_confidence_matches}
                    tone="success"
                  />
                  <StatCard
                    label="Needs review"
                    value={state.data.summary.needs_review}
                    tone="warning"
                  />
                  <StatCard
                    label="Likely no match"
                    value={state.data.summary.likely_no_match}
                    tone="neutral"
                  />
                  <StatCard
                    label="Exceptions"
                    value={state.data.summary.exceptions}
                    tone="danger"
                  />
                  <StatCard
                    label="Structural matches"
                    value={state.data.summary.structural_matches}
                    tone="info"
                    hint={`${state.data.summary.one_to_many_matches} one-to-many · ${state.data.summary.many_to_one_matches} many-to-one`}
                  />
                  <StatCard
                    label="Risk-flagged"
                    value={state.data.summary.risk_flagged_decisions}
                    tone="warning"
                  />
                </div>
              </section>

              {state.data.summary.failed_candidates > 0 && (
                <Card className="mb-6 border-amber-200 bg-amber-50">
                  <CardContent className="py-3 text-sm text-amber-800">
                    {state.data.summary.failed_candidates} candidate(s) failed
                    during processing and were skipped rather than silently
                    counted as reconciled — see the audit trail for details.
                  </CardContent>
                </Card>
              )}

              <p className="text-xs text-slate-400">
                Processed in {state.data.summary.processing_time_seconds}s ·
                completed{" "}
                {state.data.completed_at
                  ? new Date(state.data.completed_at).toLocaleString()
                  : "—"}
              </p>
            </>
          ) : (
            <p className="text-sm text-slate-500">
              No summary available yet — this batch hasn&apos;t finished
              processing.
            </p>
          )}
        </>
      )}
    </main>
  );
}
