"use client";

import Link from "next/link";
import { use } from "react";
import { getDecision, getDecisionAudit, ApiError } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { LoadingState, ErrorState } from "@/components/dashboard/states";
import { Badge } from "@/components/ui/badge";
import { DECISION_LABELS, DECISION_TONE, WORKFLOW_STATE_LABELS, WORKFLOW_STATE_TONE, RELATIONSHIP_LABELS } from "@/lib/decision-display";
import { ConfidenceCard } from "@/components/decision/confidence-card";
import { EvidenceSummary } from "@/components/decision/evidence-summary";
import { EvidenceBreakdown } from "@/components/decision/evidence-breakdown";
import { RawRecordComparison, WhatChanged } from "@/components/decision/record-comparison";
import { OperationalRiskCard } from "@/components/decision/operational-risk-card";
import { AuditTimeline } from "@/components/decision/audit-timeline";

export default function DecisionDetailPage({
  params,
}: {
  params: Promise<{ decisionId: string }>;
}) {
  const { decisionId } = use(params);
  const state = useApi(() => getDecision(decisionId), [decisionId]);
  const auditState = useApi(() => getDecisionAudit(decisionId), [decisionId]);

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
          {state.error instanceof ApiError && state.error.status === 404 ? (
            <div className="mt-4 rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600">
              This decision could not be found. It may belong to a different
              batch or the ID may be incorrect.
            </div>
          ) : (
            <ErrorState error={state.error} onRetry={state.refetch} />
          )}
        </div>
      )}

      {state.status === "success" && (
        <div className="mt-4 space-y-6">
          {/* HEADER — ML decision and workflow resolution both visible, never conflated */}
          <div>
            <h1 className="font-mono text-lg font-semibold text-slate-900">
              {state.data.decision_id}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              <div>
                <span className="text-slate-500">ML Decision: </span>
                <Badge variant={DECISION_TONE[state.data.decision]}>
                  {DECISION_LABELS[state.data.decision]}
                </Badge>
              </div>
              <div>
                <span className="text-slate-500">Workflow Status: </span>
                <Badge variant={WORKFLOW_STATE_TONE[state.data.workflow_state]}>
                  {WORKFLOW_STATE_LABELS[state.data.workflow_state]}
                </Badge>
              </div>
              <div className="text-slate-500">
                {RELATIONSHIP_LABELS[state.data.relationship_type]}
              </div>
            </div>
          </div>

          {/* SECTION A */}
          <ConfidenceCard
            probability={state.data.probability}
            decision={state.data.decision}
            thresholds={state.data.thresholds}
          />

          {/* SECTION B */}
          <EvidenceSummary evidence={state.data.evidence} />

          {/* SECTION C */}
          {state.data.all_features ? (
            <EvidenceBreakdown features={state.data.all_features} />
          ) : (
            <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
              Detailed technical evidence is not available for this decision
              right now.
            </div>
          )}

          {/* SECTION D */}
          <RawRecordComparison
            relationshipType={state.data.relationship_type}
            ledgerIds={state.data.ledger_record_ids}
            settlementIds={state.data.settlement_record_ids}
            ledgerRecords={state.data.ledger_records}
            settlementRecords={state.data.settlement_records}
          />

          {/* SECTION E */}
          <WhatChanged
            ledgerRecords={state.data.ledger_records}
            settlementRecords={state.data.settlement_records}
          />

          {/* SECTION F */}
          <OperationalRiskCard
            riskFlags={state.data.risk_flags}
            explanations={state.data.risk_flag_explanations}
          />

          {/* SECTION G — audit timeline, scoped to THIS decision only */}
          {auditState.status === "success" && <AuditTimeline events={auditState.data.events} />}
          {auditState.status === "loading" && <LoadingState label="Loading audit timeline…" />}
          {auditState.status === "error" && (
            <ErrorState error={auditState.error} onRetry={auditState.refetch} />
          )}
        </div>
      )}
    </main>
  );
}
