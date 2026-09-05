"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import type { BatchSummary } from "@/lib/api-types";

const COLORS: Record<string, string> = {
  "Auto Matched": "#10b981",
  "Needs Review": "#f59e0b",
  "Likely No Match / Exception": "#ef4444",
};

/**
 * Answers: "What happened to this reconciliation batch?"
 * Data source: BatchSummary, already returned by GET /batches/{id} — no
 * new endpoint needed, this is a pure client-side reshaping of existing data.
 *
 * NOTE: "Likely No Match" and "Exceptions" are merged into one bar, not
 * shown separately. In the current pipeline (see backend/app/pipeline.py),
 * every LIKELY_NO_MATCH decision becomes an EXCEPTION in the same
 * processing pass — the two counts are always identical (1:1). Showing
 * them as separate bars would either double-count the same decisions or
 * (if naively subtracted) always render a zero-height "Likely No Match"
 * bar. Merging them is the honest representation of what the data actually
 * distinguishes today.
 */
export function OutcomeDistributionChart({ summary }: { summary: BatchSummary }) {
  const data = [
    { name: "Auto Matched", value: summary.high_confidence_matches },
    { name: "Needs Review", value: summary.needs_review },
    { name: "Likely No Match / Exception", value: summary.exceptions },
  ].filter((d) => d.value > 0); // honest: never render a zero-height bar as if it were real data

  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-1 text-sm font-medium text-slate-700">
          Reconciliation outcomes
        </CardTitle>
        <p className="mb-4 text-xs text-slate-400">
          What happened to the {summary.candidates_generated} candidates in
          this batch.
        </p>
        {data.length === 0 ? (
          <p className="text-sm text-slate-500">No decisions to chart yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data} layout="vertical" margin={{ left: 16, right: 16 }}>
              <XAxis type="number" allowDecimals={false} />
              <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: number) => [`${v}`, "count"]} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {data.map((d) => (
                  <Cell key={d.name} fill={COLORS[d.name]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
