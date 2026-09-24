"use client";

import Link from "next/link";
import { use, useState } from "react";
import { Download } from "lucide-react";
import {
  getBatch,
  getAuditTrail,
  getBatchDecisions,
  listExceptions,
} from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { LoadingState, ErrorState } from "@/components/dashboard/states";
import { BatchStatusBadge } from "@/components/dashboard/batch-status-badge";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent } from "@/components/ui/card";
import { AuditTimeline } from "@/components/decision/audit-timeline";
import { OutcomeDistributionChart } from "@/components/dashboard/charts/outcome-distribution-chart";
import { ConfidenceDistributionChart } from "@/components/dashboard/charts/confidence-distribution-chart";
import { RootCauseDistributionChart } from "@/components/dashboard/charts/root-cause-distribution-chart";
import { FinancialSummarySection } from "@/components/dashboard/financial-summary-section";
import { ExportDialog } from "@/components/dashboard/export-dialog";

const BATCH_LIFECYCLE_EVENT_TYPES = new Set([
  "BATCH_CREATED",
  "PROCESSING_STARTED",
  "PROCESSING_FAILED",
  "BATCH_COMPLETED",
  "DUPLICATE_SUBMISSION_DETECTED",
]);

export default function BatchDashboard({
  params,
}: {
  params: Promise<{ batchId: string }>;
}) {
  const { batchId } = use(params);
  const [isExportOpen, setIsExportOpen] = useState(false);

  const state = useApi(() => getBatch(batchId), [batchId]);

  const auditState = useApi(
    () => getAuditTrail("BATCH", batchId),
    [batchId]
  );

  const decisionsState = useApi(
    () => getBatchDecisions(batchId),
    [batchId]
  );

  const exceptionsState = useApi(
    () => listExceptions(undefined, batchId),
    [batchId]
  );

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8 lg:px-10">

        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-slate-900"
        >
          <span aria-hidden="true">←</span>
          All batches
        </Link>

        {state.status === "loading" && (
          <div className="mt-8">
            <LoadingState label="Loading batch…" />
          </div>
        )}

        {state.status === "error" && (
          <div className="mt-8">
            <ErrorState error={state.error} onRetry={state.refetch} />
          </div>
        )}

        {state.status === "success" && (
          <>
            {/* Header */}
            <header className="mt-6 mb-8 rounded-2xl border border-slate-200 bg-white px-6 py-6 shadow-sm sm:px-7">
              <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="mb-3 flex flex-wrap items-center gap-3">
                    <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      Reconciliation run
                    </span>

                    <BatchStatusBadge status={state.data.status} />
                  </div>

                  <h1 className="font-mono text-xl font-bold tracking-tight text-slate-950 sm:text-2xl">
                    {state.data.batch_id}
                  </h1>

                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                    Review how ReconGuard evaluated this run, where confidence
                    was high, and which candidates require human attention.
                  </p>
                </div>

                {state.data.status === "COMPLETED" && (
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setIsExportOpen(true)}
                      className="inline-flex shrink-0 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 hover:text-slate-900"
                    >
                      <Download className="mr-2 h-4 w-4" />
                      Export Results
                    </button>
                    <Link
                      href={`/batches/${state.data.batch_id}/decisions`}
                      className="inline-flex shrink-0 items-center justify-center rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
                    >
                      Review decisions
                      <span className="ml-2" aria-hidden="true">
                        →
                      </span>
                    </Link>
                  </div>
                )}
              </div>
            </header>

            {state.data.status === "FAILED" && (
              <Card className="mb-8 border-red-200 bg-red-50">
                <CardContent className="py-4 text-sm text-red-800">
                  Processing failed:{" "}
                  {state.data.failure_reason ?? "no reason recorded"}
                </CardContent>
              </Card>
            )}

            {state.data.status === "PROCESSING" && (
              <Card className="mb-8 border-blue-200 bg-blue-50">
                <CardContent className="py-4 text-sm text-blue-800">
                  This batch is still processing — refresh to check progress.
                </CardContent>
              </Card>
            )}

            {state.data.summary ? (
              <>
                {/* KPI section */}
                <section className="mb-8">
                  <div className="mb-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      Run overview
                    </p>

                    <div className="mt-1 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                      <div>
                        <h2 className="text-lg font-semibold tracking-tight text-slate-900">
                          Reconciliation results
                        </h2>

                        <p className="mt-1 text-sm text-slate-500">
                          {state.data.summary.total_records.toLocaleString()}{" "}
                          source records evaluated across{" "}
                          {state.data.summary.candidates_generated.toLocaleString()}{" "}
                          candidate relationships.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
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
                      hint={`${state.data.summary.one_to_many_matches.toLocaleString()} one-to-many · ${state.data.summary.many_to_one_matches.toLocaleString()} many-to-one`}
                    />

                    <StatCard
                      label="Risk-flagged"
                      value={state.data.summary.risk_flagged_decisions}
                      tone="warning"
                    />
                  </div>

                  {/* Human review callout */}
                  {state.data.summary.needs_review > 0 && (
                    <div className="mt-4 flex flex-col gap-4 rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 text-sm font-bold text-amber-700">
                          !
                        </div>

                        <div>
                          <p className="text-sm font-semibold text-amber-950">
                            {state.data.summary.needs_review.toLocaleString()}{" "}
                            cases require human review
                          </p>

                          <p className="mt-1 text-sm leading-5 text-amber-800">
                            ReconGuard could not safely automate these
                            decisions. Review the evidence before approving or
                            rejecting them.
                          </p>
                        </div>
                      </div>

                      <Link
                        href="/reviews"
                        className="inline-flex shrink-0 items-center justify-center rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-700"
                      >
                        Open review queue
                        <span className="ml-2" aria-hidden="true">
                          →
                        </span>
                      </Link>
                    </div>
                  )}
                </section>

                {/* Financial Accounting & Exposure */}
                {state.data.summary.financials && (
                  <FinancialSummarySection financials={state.data.summary.financials} />
                )}

                {/* Intelligence */}
                <section className="mb-8">
                  <div className="mb-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      Decision intelligence
                    </p>

                    <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">
                      Where the model landed
                    </h2>

                    <p className="mt-1 text-sm text-slate-500">
                      Outcome mix, calibrated confidence and exception causes
                      for this reconciliation run.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                    <OutcomeDistributionChart
                      summary={state.data.summary}
                    />

                    {decisionsState.status === "success" && (
                      <ConfidenceDistributionChart
                        decisions={decisionsState.data.decisions}
                      />
                    )}

                    {exceptionsState.status === "success" && (
                      <RootCauseDistributionChart
                        exceptions={exceptionsState.data.exceptions}
                      />
                    )}
                  </div>
                </section>

                {state.data.summary.failed_candidates > 0 && (
                  <Card className="mb-8 border-amber-200 bg-amber-50">
                    <CardContent className="py-3 text-sm text-amber-800">
                      {state.data.summary.failed_candidates} candidate(s)
                      failed during processing and were skipped rather than
                      silently counted as reconciled — see the audit trail for
                      details.
                    </CardContent>
                  </Card>
                )}

                <div className="mb-8 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-4">
                  <p className="text-xs text-slate-400">
                    Processing time:{" "}
                    {state.data.summary.processing_time_seconds}s
                  </p>

                  <p className="text-xs text-slate-400">
                    Completed{" "}
                    {state.data.completed_at
                      ? new Date(
                          state.data.completed_at
                        ).toLocaleString()
                      : "—"}
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-500">
                No summary available yet — this batch hasn&apos;t finished
                processing.
              </p>
            )}

            {/* Audit */}
            {auditState.status === "success" && (
              <section className="border-t border-slate-200 pt-8">
                <div className="mb-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                    Traceability
                  </p>

                  <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">
                    Audit timeline
                  </h2>

                  <p className="mt-1 text-sm text-slate-500">
                    A chronological record of the batch lifecycle and state
                    transitions.
                  </p>
                </div>

                <AuditTimeline
                  events={auditState.data.events.filter((e) =>
                    BATCH_LIFECYCLE_EVENT_TYPES.has(e.event_type)
                  )}
                />
              </section>
            )}

            <ExportDialog
              isOpen={isExportOpen}
              onClose={() => setIsExportOpen(false)}
              batchId={state.data.batch_id}
            />
          </>
        )}
      </div>
    </main>
  );
}