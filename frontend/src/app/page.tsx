"use client";

import Link from "next/link";
import { listBatches } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState, ErrorState, EmptyState } from "@/components/dashboard/states";
import { BatchStatusBadge } from "@/components/dashboard/batch-status-badge";

export default function Home() {
  const state = useApi(() => listBatches(), []);

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="mb-1 text-xl font-semibold text-slate-900">ReconLens</h1>
      <p className="mb-6 text-sm text-slate-500">
        Select a batch to see how it was reconciled, or open the{" "}
        <Link href="/reviews" className="underline hover:text-slate-700">
          review queue
        </Link>
        .
      </p>

      {state.status === "loading" && <LoadingState label="Loading batches…" />}
      {state.status === "error" && (
        <ErrorState error={state.error} onRetry={state.refetch} />
      )}
      {state.status === "success" && state.data.batches.length === 0 && (
        <EmptyState>
          No batches have been processed yet. Submit one via{" "}
          <code className="rounded bg-slate-100 px-1">POST /batches</code> to
          see it here.
        </EmptyState>
      )}

      {state.status === "success" && state.data.batches.length > 0 && (
        <div className="space-y-3">
          {state.data.batches.map((b) => (
            <Link key={b.batch_id} href={`/batches/${b.batch_id}`}>
              <Card className="transition-colors hover:border-slate-300">
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <CardTitle className="font-mono text-slate-900">
                    {b.batch_id}
                  </CardTitle>
                  <BatchStatusBadge status={b.status} />
                </CardHeader>
                <CardContent className="text-sm text-slate-600">
                  {b.n_ledger_records} ledger + {b.n_settlement_records} settlement
                  records
                  {b.summary && (
                    <span>
                      {" "}
                      · {b.summary.candidates_generated} candidates ·{" "}
                      {b.summary.high_confidence_matches} auto-matched ·{" "}
                      {b.summary.needs_review} in review
                    </span>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
