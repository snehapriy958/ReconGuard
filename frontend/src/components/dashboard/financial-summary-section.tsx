"use client";

import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency, formatPercent } from "@/lib/formatters";
import type { FinancialSideMetrics, FinancialSummary } from "@/lib/api-types";
import { FinancialBreakdownChart } from "./charts/financial-breakdown-chart";

interface FinancialSummarySectionProps {
  financials: FinancialSummary;
}

function SideCard({
  title,
  subtitle,
  metrics,
  colorScheme,
}: {
  title: string;
  subtitle: string;
  metrics: FinancialSideMetrics;
  colorScheme: "indigo" | "sky";
}) {
  const isIndigo = colorScheme === "indigo";
  const badgeBg = isIndigo ? "bg-indigo-50 text-indigo-700 border-indigo-200" : "bg-sky-50 text-sky-700 border-sky-200";

  return (
    <Card className="flex flex-col justify-between border-slate-200 shadow-xs">
      <CardContent className="p-6">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div>
            <h3 className="text-base font-semibold text-slate-900">{title}</h3>
            <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
          </div>
          <span className={`text-xs font-mono font-semibold px-2.5 py-1 rounded-full border ${badgeBg}`}>
            {formatPercent(metrics.matched_rate)} Reconciled
          </span>
        </div>

        {/* Total Source Value */}
        <div className="py-4 border-b border-slate-100">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Value</p>
          <p className="text-2xl font-bold font-mono text-slate-950 mt-1">
            {formatCurrency(metrics.total_amount)}
          </p>
        </div>

        {/* Breakdown Buckets */}
        <div className="grid grid-cols-3 gap-3 pt-4 text-xs">
          <div className="rounded-lg bg-emerald-50/60 border border-emerald-100 p-3">
            <span className="text-[11px] font-medium text-emerald-800 uppercase tracking-wider block">
              Matched
            </span>
            <span className="text-sm font-bold font-mono text-emerald-950 mt-1 block">
              {formatCurrency(metrics.matched_amount)}
            </span>
            <span className="text-[11px] text-emerald-700 mt-0.5 block">
              {formatPercent(metrics.matched_rate)}
            </span>
          </div>

          <div className="rounded-lg bg-amber-50/60 border border-amber-100 p-3">
            <span className="text-[11px] font-medium text-amber-800 uppercase tracking-wider block">
              In Review
            </span>
            <span className="text-sm font-bold font-mono text-amber-950 mt-1 block">
              {formatCurrency(metrics.review_amount)}
            </span>
            <span className="text-[11px] text-amber-700 mt-0.5 block">
              {formatPercent(metrics.review_rate)}
            </span>
          </div>

          <div className="rounded-lg bg-red-50/60 border border-red-100 p-3">
            <span className="text-[11px] font-medium text-red-800 uppercase tracking-wider block">
              Exception
            </span>
            <span className="text-sm font-bold font-mono text-red-950 mt-1 block">
              {formatCurrency(metrics.exception_amount)}
            </span>
            <span className="text-[11px] text-red-700 mt-0.5 block">
              {formatPercent(metrics.exception_rate)}
            </span>
          </div>
        </div>

        {/* Invariant Footer */}
        <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-400 flex items-center justify-between">
          <span>Unique Source Records Accounting</span>
          <span className="font-mono">
            {formatCurrency(metrics.matched_amount)} + {formatCurrency(metrics.review_amount)} + {formatCurrency(metrics.exception_amount)} = {formatCurrency(metrics.total_amount)}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

export function FinancialSummarySection({ financials }: FinancialSummarySectionProps) {
  return (
    <section className="mb-8" aria-label="Financial Reconciliation Metrics">
      <div className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
          Financial Accounting
        </p>
        <div className="mt-1 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-slate-900">
              Financial Reconciliation Summary
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Unique source record financial accumulation ensuring zero candidate-group double counting.
            </p>
          </div>
        </div>
      </div>

      {/* Grid: Ledger Card & Settlement Card */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 mb-6">
        <SideCard
          title="Internal Accounts Ledger"
          subtitle="Unique ledger record amounts"
          metrics={financials.ledger}
          colorScheme="indigo"
        />

        <SideCard
          title="External Settlement Records"
          subtitle="Unique settlement record amounts"
          metrics={financials.settlement}
          colorScheme="sky"
        />
      </div>

      {/* Visual Breakdown Chart */}
      <FinancialBreakdownChart financials={financials} />
    </section>
  );
}
