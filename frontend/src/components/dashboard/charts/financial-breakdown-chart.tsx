"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { formatCurrency } from "@/lib/formatters";
import type { FinancialSummary } from "@/lib/api-types";

interface FinancialBreakdownChartProps {
  financials: FinancialSummary;
}

export function FinancialBreakdownChart({ financials }: FinancialBreakdownChartProps) {
  const data = [
    {
      name: "Ledger",
      Matched: financials.ledger.matched_amount,
      Review: financials.ledger.review_amount,
      Exception: financials.ledger.exception_amount,
    },
    {
      name: "Settlement",
      Matched: financials.settlement.matched_amount,
      Review: financials.settlement.review_amount,
      Exception: financials.settlement.exception_amount,
    },
  ];

  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-1 text-sm font-medium text-slate-700">
          Financial Exposure Breakdown
        </CardTitle>
        <p className="mb-4 text-xs text-slate-400">
          Distribution of reconciled, pending review, and exception amounts across both sides.
        </p>

        <ResponsiveContainer width="100%" height={260}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ left: 16, right: 16, top: 8, bottom: 8 }}
          >
            <XAxis
              type="number"
              tickFormatter={(v: number) => {
                if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L`;
                if (v >= 1000) return `₹${(v / 1000).toFixed(0)}k`;
                return `₹${v}`;
              }}
            />
            <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 12 }} />
            <Tooltip
              formatter={(value: unknown, name: unknown) => [
                formatCurrency(Number(value)),
                String(name),
              ]}
            />
            <Legend
              wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
            />
            <Bar dataKey="Matched" fill="#10b981" stackId="exposure" radius={[0, 0, 0, 0]} />
            <Bar dataKey="Review" fill="#f59e0b" stackId="exposure" radius={[0, 0, 0, 0]} />
            <Bar dataKey="Exception" fill="#ef4444" stackId="exposure" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
