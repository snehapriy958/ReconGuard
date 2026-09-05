"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { humanizeRootCause } from "@/lib/root-cause-display";
import type { ExceptionListItem } from "@/lib/api-types";

/**
 * Answers: "Why are reconciliation attempts failing?" Data source:
 * GET /exceptions?batch_id=... (Phase 6.6's endpoint, batch-scoped in this
 * phase). Only categories that actually occurred are shown — never a
 * padded-out list of every possible taxonomy entry.
 */
export function RootCauseDistributionChart({ exceptions }: { exceptions: ExceptionListItem[] }) {
  if (exceptions.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-slate-500">
          No exceptions in this batch.
        </CardContent>
      </Card>
    );
  }

  const counts = new Map<string, number>();
  for (const e of exceptions) {
    if (!e.primary_root_cause) continue;
    counts.set(e.primary_root_cause, (counts.get(e.primary_root_cause) ?? 0) + 1);
  }
  const data = Array.from(counts.entries())
    .map(([cause, count]) => ({ cause: humanizeRootCause(cause), count }))
    .sort((a, b) => b.count - a.count);

  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-1 text-sm font-medium text-slate-700">
          Why reconciliation failed
        </CardTitle>
        <p className="mb-4 text-xs text-slate-400">
          Primary root cause across {exceptions.length} exception
          {exceptions.length === 1 ? "" : "s"} in this batch.
        </p>
        <ResponsiveContainer width="100%" height={Math.max(160, data.length * 40)}>
          <BarChart data={data} layout="vertical" margin={{ left: 16, right: 16 }}>
            <XAxis type="number" allowDecimals={false} />
            <YAxis type="category" dataKey="cause" width={150} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v: number) => [`${v}`, "exceptions"]} />
            <Bar dataKey="count" fill="#ef4444" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
