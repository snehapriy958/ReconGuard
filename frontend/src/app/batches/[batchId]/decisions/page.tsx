"use client";

import Link from "next/link";
import { use } from "react";
import { getBatchDecisions } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { LoadingState, ErrorState } from "@/components/dashboard/states";
import { DecisionTable } from "@/components/dashboard/decision-table";

export default function BatchDecisionsPage({
  params,
}: {
  params: Promise<{ batchId: string }>;
}) {
  const { batchId } = use(params);
  const state = useApi(() => getBatchDecisions(batchId), [batchId]);

  return (
    <main className="mx-auto max-w-6xl p-8">
      <Link
        href={`/batches/${batchId}`}
        className="text-sm text-slate-500 hover:text-slate-700"
      >
        ← Batch overview
      </Link>

      <h1 className="mt-2 mb-1 font-mono text-lg font-semibold text-slate-900">
        Decisions for {batchId}
      </h1>
      <p className="mb-6 text-sm text-slate-500">
        What ReconLens decided for each reconciliation candidate, and why it
        should (or shouldn&apos;t) be trusted at face value.
      </p>

      {state.status === "loading" && <LoadingState label="Loading decisions…" />}
      {state.status === "error" && (
        <ErrorState error={state.error} onRetry={state.refetch} />
      )}
      {state.status === "success" && (
        <DecisionTable decisions={state.data.decisions} />
      )}
    </main>
  );
}
