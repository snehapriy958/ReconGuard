"use client";

import Link from "next/link";
import { use } from "react";
import { getReview, getDecision } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { LoadingState, ErrorState } from "@/components/dashboard/states";
import { Badge } from "@/components/ui/badge";
import {
  DECISION_LABELS,
  DECISION_TONE,
  RELATIONSHIP_LABELS,
} from "@/lib/decision-display";
import { ConfidenceCard } from "@/components/decision/confidence-card";
import { EvidenceSummary } from "@/components/decision/evidence-summary";
import { EvidenceBreakdown } from "@/components/decision/evidence-breakdown";
import { RawRecordComparison, WhatChanged } from "@/components/decision/record-comparison";
import { OperationalRiskCard } from "@/components/decision/operational-risk-card";
import { ReviewHistory } from "@/components/decision/review-history";
import { ReviewActions } from "@/components/decision/review-actions";

export default function ReviewDetailPage({
  params,
}: {
  params: Promise<{ reviewId: string }>;
}) {
  const { reviewId } = use(params);
  const reviewState = useApi(() => getReview(reviewId), [reviewId]);
  const decisionId = reviewState.status === "success" ? reviewState.data.decision_id : null;
  const decisionState = useApi(
    () => (decisionId ? getDecision(decisionId) : Promise.reject(new Error("no decision id"))),
    [decisionId]
  );

  function refreshAfterAction() {
    // Real backend confirmed the action — refetch BOTH resources from real
    // state rather than assuming the local UI already reflects it. This is
    // the "do not simulate success locally" invariant made concrete.
    reviewState.refetch();
    decisionState.refetch();
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <Link href="/reviews" className="text-sm text-slate-500 hover:text-slate-700">
        ← Back to review queue
      </Link>

      {reviewState.status === "loading" && (
        <div className="mt-4">
          <LoadingState label="Loading review…" />
        </div>
      )}
      {reviewState.status === "error" && (
        <div className="mt-4">
          <ErrorState error={reviewState.error} onRetry={reviewState.refetch} />
        </div>
      )}

      {reviewState.status === "success" && (
        <div className="mt-4 space-y-6">
          <div>
            <h1 className="font-mono text-lg font-semibold text-slate-900">
              {reviewState.data.review_id}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              {reviewState.data.original_ml_decision && (
                <div>
                  <span className="text-slate-500">Original ML Decision: </span>
                  <Badge variant={DECISION_TONE[reviewState.data.original_ml_decision]}>
                    {DECISION_LABELS[reviewState.data.original_ml_decision]}
                  </Badge>
                </div>
              )}
              <div>
                <span className="text-slate-500">Review Status: </span>
                <Badge variant="neutral">{reviewState.data.status}</Badge>
              </div>
              <div className="text-slate-500">
                {RELATIONSHIP_LABELS[reviewState.data.relationship_type]}
              </div>
            </div>
          </div>

          {decisionState.status === "loading" && <LoadingState label="Loading decision detail…" />}
          {decisionState.status === "error" && (
            <ErrorState error={decisionState.error} onRetry={decisionState.refetch} />
          )}

          {decisionState.status === "success" && (
            <>
              <ConfidenceCard
                probability={decisionState.data.probability}
                decision={decisionState.data.decision}
                thresholds={decisionState.data.thresholds}
              />
              <EvidenceSummary evidence={decisionState.data.evidence} />
              {decisionState.data.all_features && (
                <EvidenceBreakdown features={decisionState.data.all_features} />
              )}
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

              <ReviewHistory
                modelDecision={decisionState.data.decision}
                modelDecisionAt={decisionState.data.created_at}
                reviewStatus={reviewState.data.status}
                resolvedAt={reviewState.data.resolved_at}
                assignedReviewer={reviewState.data.assigned_reviewer}
              />

              <ReviewActions
                reviewId={reviewState.data.review_id}
                status={reviewState.data.status}
                onResolved={refreshAfterAction}
              />
            </>
          )}
        </div>
      )}
    </main>
  );
}
