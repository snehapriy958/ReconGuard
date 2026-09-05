"use client";

import Link from "next/link";
import { use } from "react";
import { getException, getDecision } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { LoadingState, ErrorState } from "@/components/dashboard/states";
import { Badge } from "@/components/ui/badge";
import { RELATIONSHIP_LABELS, WORKFLOW_STATE_LABELS, WORKFLOW_STATE_TONE } from "@/lib/decision-display";
import { RootCauseCard } from "@/components/decision/root-cause-card";
import { RawRecordComparison, WhatChanged } from "@/components/decision/record-comparison";
import { OperationalRiskCard } from "@/components/decision/operational-risk-card";

export default function ExceptionDetailPage({
  params,
}: {
  params: Promise<{ exceptionId: string }>;
}) {
  const { exceptionId } = use(params);
  const excState = useApi(() => getException(exceptionId), [exceptionId]);
  const decisionId = excState.status === "success" ? excState.data.decision_id : null;
  const decisionState = useApi(
    () => (decisionId ? getDecision(decisionId) : Promise.reject(new Error("no decision id"))),
    [decisionId]
  );

  return (
    <main className="mx-auto max-w-3xl p-8">
      <Link href="/exceptions" className="text-sm text-slate-500 hover:text-slate-700">
        ← Back to exceptions
      </Link>

      {excState.status === "loading" && (
        <div className="mt-4">
          <LoadingState label="Loading exception…" />
        </div>
      )}
      {excState.status === "error" && (
        <div className="mt-4">
          <ErrorState error={excState.error} onRetry={excState.refetch} />
        </div>
      )}

      {excState.status === "success" && (
        <div className="mt-4 space-y-6">
          <div>
            <h1 className="font-mono text-lg font-semibold text-slate-900">
              {excState.data.exception_id}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              {excState.data.workflow_state && (
                <div>
                  <span className="text-slate-500">Workflow status: </span>
                  <Badge variant={WORKFLOW_STATE_TONE[excState.data.workflow_state]}>
                    {WORKFLOW_STATE_LABELS[excState.data.workflow_state]}
                  </Badge>
                </div>
              )}
              {excState.data.relationship_type && (
                <div className="text-slate-500">
                  {RELATIONSHIP_LABELS[excState.data.relationship_type]}
                </div>
              )}
              {excState.data.batch_id && (
                <span className="font-mono text-xs text-slate-400">{excState.data.batch_id}</span>
              )}
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Original recorded reason: &ldquo;{excState.data.original_reason}&rdquo;
            </p>
          </div>

          <RootCauseCard analysis={excState.data.root_cause_analysis} />

          {decisionId && (
            <Link
              href={`/decisions/${decisionId}`}
              className="inline-flex items-center text-sm font-medium text-slate-700 hover:text-slate-950"
            >
              View decision &amp; audit →
            </Link>
          )}

          {decisionState.status === "loading" && <LoadingState label="Loading related records…" />}
          {decisionState.status === "success" && (
            <>
              <RawRecordComparison
                relationshipType={decisionState.data.relationship_type}
                ledgerIds={decisionState.data.ledger_record_ids}
                settlementIds={decisionState.data.settlement_record_ids}
                ledgerRecords={decisionState.data.ledger_records}
                settlementRecords={decisionState.data.settlement_records}
              />
              <WhatChanged
                ledgerRecords={decisionState.data.ledger_records}
                settlementRecords={decisionState.data.settlement_records}
              />
              <OperationalRiskCard
                riskFlags={decisionState.data.risk_flags}
                explanations={decisionState.data.risk_flag_explanations}
              />
            </>
          )}
        </div>
      )}
    </main>
  );
}
