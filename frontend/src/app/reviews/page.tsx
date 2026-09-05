"use client";

import { useState } from "react";
import Link from "next/link";
import { listReviews } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import {
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/dashboard/states";
import { Badge } from "@/components/ui/badge";
import { RelationshipDisplay } from "@/components/dashboard/relationship-display";
import { RiskFlags } from "@/components/dashboard/risk-flags";
import {
  DECISION_LABELS,
  DECISION_TONE,
  formatProbability,
} from "@/lib/decision-display";
import type { ReviewStatus } from "@/lib/api-types";

const STATUS_TABS: {
  key: ReviewStatus | "ALL";
  label: string;
}[] = [
  { key: "OPEN", label: "Open" },
  { key: "APPROVED", label: "Approved" },
  { key: "REJECTED", label: "Rejected" },
  { key: "ALL", label: "All" },
];

export default function ReviewQueuePage() {
  const [tab, setTab] = useState<ReviewStatus | "ALL">("OPEN");

  const state = useApi(
    () => listReviews(tab === "ALL" ? undefined : tab),
    [tab]
  );

  const sorted =
    state.status === "success"
      ? [...state.data.reviews].sort(
          (a, b) =>
            new Date(a.created_at).getTime() -
            new Date(b.created_at).getTime()
        )
      : [];

  const openCount =
    tab === "OPEN" && state.status === "success"
      ? sorted.length
      : null;

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8 lg:px-10">

        {/* Back navigation */}
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-slate-900"
        >
          <span aria-hidden="true">←</span>
          All batches
        </Link>

        {/* Page header */}
        <header className="mt-6 mb-7 rounded-2xl border border-slate-200 bg-white px-6 py-6 shadow-sm sm:px-7">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-3">
                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-600">
                  Human oversight
                </span>

                {openCount !== null && (
                  <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">
                    {openCount} open
                  </span>
                )}
              </div>

              <h1 className="text-2xl font-bold tracking-tight text-slate-950">
                Review queue
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                Cases ReconGuard deliberately withheld from automatic
                approval. Review the evidence and make the final operational
                decision.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                Review policy
              </p>

              <p className="mt-1 text-sm font-medium text-slate-700">
                Oldest cases first
              </p>
            </div>
          </div>
        </header>

        {/* Status filters */}
        <div className="mb-5 flex flex-wrap items-center gap-2">
          {STATUS_TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                tab === t.key
                  ? "bg-slate-950 text-white shadow-sm"
                  : "border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Loading */}
        {state.status === "loading" && (
          <LoadingState label="Loading review queue…" />
        )}

        {/* Error */}
        {state.status === "error" && (
          <ErrorState
            error={state.error}
            onRetry={state.refetch}
          />
        )}

        {/* Empty */}
        {state.status === "success" && sorted.length === 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white px-6 py-12 text-center shadow-sm">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-xl text-emerald-600">
              ✓
            </div>

            <h2 className="mt-4 text-base font-semibold text-slate-900">
              {tab === "OPEN"
                ? "No decisions are currently awaiting review."
                : `No ${tab.toLowerCase()} reviews found.`}
            </h2>

            {tab === "OPEN" && (
              <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
                ReconGuard has no outstanding cases requiring human
                intervention.
              </p>
            )}
          </div>
        )}

        {/* Review cases */}
        {state.status === "success" && sorted.length > 0 && (
          <section>
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Cases
                </p>

                <p className="mt-1 text-sm text-slate-500">
                  {sorted.length}{" "}
                  {sorted.length === 1 ? "case" : "cases"} in this queue
                </p>
              </div>
            </div>

            <ul className="space-y-3">
              {sorted.map((r) => (
                <li key={r.review_id}>
                  <Link
                    href={`/reviews/${r.review_id}`}
                    className="group block rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-slate-300 hover:shadow-md"
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">

                      {/* Case identity */}
                      <div className="min-w-0">
                        {r.ledger_record_ids &&
                          r.settlement_record_ids && (
                            <RelationshipDisplay
                              relationshipType={r.relationship_type}
                              ledgerIds={r.ledger_record_ids}
                              settlementIds={r.settlement_record_ids}
                            />
                          )}

                        {r.batch_id && (
                          <p className="mt-2 font-mono text-xs text-slate-400">
                            {r.batch_id}
                          </p>
                        )}
                      </div>

                      {/* Confidence */}
                      <div className="shrink-0 rounded-lg bg-slate-50 px-4 py-3 text-left lg:min-w-[150px] lg:text-right">
                        <p className="text-2xl font-bold tabular-nums tracking-tight text-slate-950">
                          {formatProbability(
                            r.calibrated_probability
                          )}
                        </p>

                        <p className="mt-0.5 text-xs text-slate-400">
                          calibrated confidence
                        </p>
                      </div>
                    </div>

                    {/* Decision metadata */}
                    <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
                      {r.original_ml_decision && (
                        <Badge
                          variant={
                            DECISION_TONE[r.original_ml_decision]
                          }
                        >
                          ML:{" "}
                          {
                            DECISION_LABELS[
                              r.original_ml_decision
                            ]
                          }
                        </Badge>
                      )}

                      <Badge variant="neutral">
                        {r.status}
                      </Badge>

                      <RiskFlags flags={r.risk_flags} />

                      <span className="ml-auto hidden text-sm font-medium text-slate-400 transition group-hover:text-slate-900 sm:block">
                        Review case →
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </main>
  );
}