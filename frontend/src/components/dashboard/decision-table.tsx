"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Decision, DecisionLabel, RelationshipType } from "@/lib/api-types";
import {
  DECISION_LABELS,
  DECISION_TONE,
  WORKFLOW_STATE_LABELS,
  WORKFLOW_STATE_TONE,
  RELATIONSHIP_LABELS,
  formatProbability,
} from "@/lib/decision-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/dashboard/states";
import { RelationshipDisplay } from "@/components/dashboard/relationship-display";
import { RiskFlags } from "@/components/dashboard/risk-flags";

type DecisionFilter = DecisionLabel | "ALL";
type RelationshipFilter = RelationshipType | "ALL";
type RiskFilter = "ALL" | "FLAGGED" | "NONE";
type SortKey = "confidence" | "decision" | "relationship_type";

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
        active
          ? "bg-slate-900 text-white"
          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
      }`}
    >
      {children}
    </button>
  );
}

export function DecisionTable({ decisions }: { decisions: Decision[] }) {
  const router = useRouter();
  const [decisionFilter, setDecisionFilter] = useState<DecisionFilter>("ALL");
  const [relationshipFilter, setRelationshipFilter] = useState<RelationshipFilter>("ALL");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("ALL");
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortAsc, setSortAsc] = useState(false);

  const filtered = useMemo(() => {
    let rows = decisions;
    if (decisionFilter !== "ALL") {
      rows = rows.filter((d) => d.decision === decisionFilter);
    }
    if (relationshipFilter !== "ALL") {
      rows = rows.filter((d) => d.relationship_type === relationshipFilter);
    }
    if (riskFilter === "FLAGGED") {
      rows = rows.filter((d) => d.risk_flags.length > 0);
    } else if (riskFilter === "NONE") {
      rows = rows.filter((d) => d.risk_flags.length === 0);
    }
    if (sortKey) {
      rows = [...rows].sort((a, b) => {
        let cmp = 0;
        if (sortKey === "confidence") cmp = a.probability.calibrated - b.probability.calibrated;
        if (sortKey === "decision") cmp = a.decision.localeCompare(b.decision);
        if (sortKey === "relationship_type") cmp = a.relationship_type.localeCompare(b.relationship_type);
        return sortAsc ? cmp : -cmp;
      });
    }
    return rows;
  }, [decisions, decisionFilter, relationshipFilter, riskFilter, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc((a) => !a);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  if (decisions.length === 0) {
    return <EmptyState>No decisions were produced for this batch.</EmptyState>;
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-slate-500">Decision:</span>
        <FilterChip active={decisionFilter === "ALL"} onClick={() => setDecisionFilter("ALL")}>
          All
        </FilterChip>
        {(Object.keys(DECISION_LABELS) as DecisionLabel[]).map((d) => (
          <FilterChip key={d} active={decisionFilter === d} onClick={() => setDecisionFilter(d)}>
            {DECISION_LABELS[d]}
          </FilterChip>
        ))}

        <span className="ml-3 text-xs font-medium text-slate-500">Relationship:</span>
        <FilterChip active={relationshipFilter === "ALL"} onClick={() => setRelationshipFilter("ALL")}>
          All
        </FilterChip>
        {(Object.keys(RELATIONSHIP_LABELS) as RelationshipType[]).map((r) => (
          <FilterChip
            key={r}
            active={relationshipFilter === r}
            onClick={() => setRelationshipFilter(r)}
          >
            {RELATIONSHIP_LABELS[r]}
          </FilterChip>
        ))}

        <span className="ml-3 text-xs font-medium text-slate-500">Risk:</span>
        <FilterChip active={riskFilter === "ALL"} onClick={() => setRiskFilter("ALL")}>
          All
        </FilterChip>
        <FilterChip active={riskFilter === "FLAGGED"} onClick={() => setRiskFilter("FLAGGED")}>
          Risk Flagged
        </FilterChip>
        <FilterChip active={riskFilter === "NONE"} onClick={() => setRiskFilter("NONE")}>
          No Risk Flags
        </FilterChip>
      </div>

      {filtered.length === 0 ? (
        <EmptyState>
          No decisions match the current filters.{" "}
          <button
            className="text-slate-700 underline"
            onClick={() => {
              setDecisionFilter("ALL");
              setRelationshipFilter("ALL");
              setRiskFilter("ALL");
            }}
          >
            Clear filters
          </button>{" "}
          to see all {decisions.length} decisions.
        </EmptyState>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium text-slate-500">
              <tr>
                <th className="p-3">Records</th>
                <th className="p-3">
                  <button
                    className="flex items-center gap-1 hover:text-slate-700"
                    onClick={() => toggleSort("relationship_type")}
                  >
                    Relationship {sortKey === "relationship_type" && (sortAsc ? "↑" : "↓")}
                  </button>
                </th>
                <th className="p-3">
                  <button
                    className="flex items-center gap-1 hover:text-slate-700"
                    onClick={() => toggleSort("confidence")}
                  >
                    Model Confidence {sortKey === "confidence" && (sortAsc ? "↑" : "↓")}
                  </button>
                </th>
                <th className="p-3">
                  <button
                    className="flex items-center gap-1 hover:text-slate-700"
                    onClick={() => toggleSort("decision")}
                  >
                    Decision {sortKey === "decision" && (sortAsc ? "↑" : "↓")}
                  </button>
                </th>
                <th className="p-3">Risk</th>
                <th className="p-3">Workflow Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d) => {
                return (
                  <tr
                    key={d.decision_id}
                    onClick={() => router.push(`/decisions/${d.decision_id}`)}
                    className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50"
                  >
                    <td className="p-3">
                      <RelationshipDisplay
                        relationshipType={d.relationship_type}
                        ledgerIds={d.ledger_record_ids}
                        settlementIds={d.settlement_record_ids}
                      />
                    </td>
                    <td className="p-3 text-slate-600">
                      {RELATIONSHIP_LABELS[d.relationship_type]}
                    </td>
                    <td className="p-3 tabular-nums font-medium text-slate-900">
                      {formatProbability(d.probability.calibrated)}
                    </td>
                    <td className="p-3">
                      <Badge variant={DECISION_TONE[d.decision]}>
                        {DECISION_LABELS[d.decision]}
                      </Badge>
                    </td>
                    <td className="p-3">
                      <RiskFlags flags={d.risk_flags} />
                    </td>
                    <td className="p-3">
                      <Badge variant={WORKFLOW_STATE_TONE[d.workflow_state]}>
                        {WORKFLOW_STATE_LABELS[d.workflow_state]}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
