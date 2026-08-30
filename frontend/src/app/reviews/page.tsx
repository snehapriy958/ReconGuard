"use client";

import { useState } from "react";
import Link from "next/link";
import { listReviews } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { LoadingState, ErrorState, EmptyState } from "@/components/dashboard/states";
import { Badge } from "@/components/ui/badge";
import { RelationshipDisplay } from "@/components/dashboard/relationship-display";
import { RiskFlags } from "@/components/dashboard/risk-flags";
import { DECISION_LABELS, DECISION_TONE, formatProbability } from "@/lib/decision-display";
import type { ReviewStatus } from "@/lib/api-types";

const STATUS_TABS: { key: ReviewStatus | "ALL"; label: string }[] = [
  { key: "OPEN", label: "Open" },
  { key: "APPROVED", label: "Approved" },
  { key: "REJECTED", label: "Rejected" },
  { key: "ALL", label: "All" },
];

export default function ReviewQueuePage() {
  const [tab, setTab] = useState<ReviewStatus | "ALL">("OPEN");
  const state = useApi(() => listReviews(tab === "ALL" ? undefined : tab), [tab]);

  // Ordering policy, stated plainly: no backend priority field exists yet
  // (spec §3 explicitly forbids inventing a fake "AI priority score"), so
  // the only transparent, deterministic ordering available is oldest-first
  // — the case that's been waiting longest gets attention first.
  const sorted =
    state.status === "success"
      ? [...state.data.reviews].sort(
          (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        )
      : [];

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="mb-1 text-xl font-semibold text-slate-900">Review Queue</h1>
      <p className="mb-6 text-sm text-slate-500">
        Ordered oldest-first — the longest-waiting case appears first. No
        priority scoring is applied.
      </p>

      <div className="mb-4 flex gap-2">
        {STATUS_TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              tab === t.key
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {state.status === "loading" && <LoadingState label="Loading review queue…" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={state.refetch} />}

      {state.status === "success" && sorted.length === 0 && (
        <EmptyState>
          {tab === "OPEN"
            ? "No decisions are currently awaiting review."
            : `No ${tab.toLowerCase()} reviews found.`}
        </EmptyState>
      )}

      {state.status === "success" && sorted.length > 0 && (
        <ul className="space-y-3">
          {sorted.map((r) => (
            <li key={r.review_id}>
              <Link
                href={`/reviews/${r.review_id}`}
                className="block rounded-lg border border-slate-200 bg-white p-4 transition-colors hover:border-slate-300"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    {r.ledger_record_ids && r.settlement_record_ids && (
                      <RelationshipDisplay
                        relationshipType={r.relationship_type}
                        ledgerIds={r.ledger_record_ids}
                        settlementIds={r.settlement_record_ids}
                      />
                    )}
                    {r.batch_id && (
                      <p className="mt-1 font-mono text-xs text-slate-400">
                        {r.batch_id}
                      </p>
                    )}
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-semibold tabular-nums text-slate-900">
                      {formatProbability(r.calibrated_probability)}
                    </p>
                    <p className="text-xs text-slate-400">calibrated confidence</p>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {r.original_ml_decision && (
                    <Badge variant={DECISION_TONE[r.original_ml_decision]}>
                      ML: {DECISION_LABELS[r.original_ml_decision]}
                    </Badge>
                  )}
                  <Badge variant="neutral">{r.status}</Badge>
                  <RiskFlags flags={r.risk_flags} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
