"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { listExceptions } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { LoadingState, ErrorState, EmptyState } from "@/components/dashboard/states";
import { Badge } from "@/components/ui/badge";
import { RelationshipDisplay } from "@/components/dashboard/relationship-display";
import { RiskFlags } from "@/components/dashboard/risk-flags";
import { formatProbability } from "@/lib/decision-display";
import { humanizeRootCause, rootCauseTone } from "@/lib/root-cause-display";

export default function ExceptionQueuePage() {
  const state = useApi(() => listExceptions(), []);
  const [causeFilter, setCauseFilter] = useState<string | "ALL">("ALL");

  const causes = useMemo(() => {
    if (state.status !== "success") return [];
    const set = new Set(state.data.exceptions.map((e) => e.primary_root_cause).filter(Boolean) as string[]);
    return Array.from(set);
  }, [state]);

  const filtered =
    state.status === "success"
      ? state.data.exceptions.filter((e) => causeFilter === "ALL" || e.primary_root_cause === causeFilter)
      : [];

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="mb-1 text-xl font-semibold text-slate-900">Exception Intelligence</h1>
      <p className="mb-6 text-sm text-slate-500">
        Why these candidates weren&apos;t automatically reconciled, with the
        evidence behind each explanation.
      </p>

      {state.status === "success" && causes.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            onClick={() => setCauseFilter("ALL")}
            className={`rounded-full px-3 py-1 text-xs font-medium ${causeFilter === "ALL" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
          >
            All
          </button>
          {causes.map((c) => (
            <button
              key={c}
              onClick={() => setCauseFilter(c)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${causeFilter === c ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
            >
              {humanizeRootCause(c)}
            </button>
          ))}
        </div>
      )}

      {state.status === "loading" && <LoadingState label="Loading exceptions…" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={state.refetch} />}

      {state.status === "success" && state.data.exceptions.length === 0 && (
        <EmptyState>No exceptions were produced for this batch.</EmptyState>
      )}

      {state.status === "success" && state.data.exceptions.length > 0 && filtered.length === 0 && (
        <EmptyState>No exceptions match this root cause.</EmptyState>
      )}

      {filtered.length > 0 && (
        <ul className="space-y-3">
          {filtered.map((e) => (
            <li key={e.exception_id}>
              <Link
                href={`/exceptions/${e.exception_id}`}
                className="block rounded-lg border border-slate-200 bg-white p-4 transition-colors hover:border-slate-300"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    {e.ledger_record_ids && e.settlement_record_ids && e.relationship_type && (
                      <RelationshipDisplay
                        relationshipType={e.relationship_type}
                        ledgerIds={e.ledger_record_ids}
                        settlementIds={e.settlement_record_ids}
                      />
                    )}
                  </div>
                  {e.calibrated_probability !== null && (
                    <div className="text-right">
                      <p className="text-lg font-semibold tabular-nums text-slate-900">
                        {formatProbability(e.calibrated_probability)}
                      </p>
                      <p className="text-xs text-slate-400">calibrated confidence</p>
                    </div>
                  )}
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {e.primary_root_cause && (
                    <Badge variant={rootCauseTone(e.primary_root_cause)}>
                      {humanizeRootCause(e.primary_root_cause)}
                    </Badge>
                  )}
                  {e.risk_flags && <RiskFlags flags={e.risk_flags} />}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
