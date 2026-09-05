"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import type { Decision } from "@/lib/api-types";

const BUCKET_WIDTH = 0.1;

/**
 * Answers: "Where is the model confident, and where is uncertainty
 * concentrated?" Data source: the same Decision[] already returned by
 * GET /batches/{id}/decisions (Phase 6.3) — binned into 10 buckets
 * client-side, no new endpoint needed at this data scale.
 */
export function ConfidenceDistributionChart({ decisions }: { decisions: Decision[] }) {
  if (decisions.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-slate-500">
          No decisions to chart yet.
        </CardContent>
      </Card>
    );
  }

  const buckets = Array.from({ length: 10 }, (_, i) => ({
    bucket: `${Math.round(i * 10)}-${Math.round((i + 1) * 10)}%`,
    start: i * BUCKET_WIDTH,
    count: 0,
  }));
  for (const d of decisions) {
    const idx = Math.min(9, Math.floor(d.probability.calibrated / BUCKET_WIDTH));
    buckets[idx].count += 1;
  }

  // Thresholds are identical across every decision in a batch (one model
  // bundle, one policy) — real values from the data, not hardcoded.
  const high = decisions[0].thresholds.high;
  const low = decisions[0].thresholds.low;

  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-1 text-sm font-medium text-slate-700">
          Confidence distribution
        </CardTitle>
        <p className="mb-4 text-xs text-slate-400">
          Calibrated probability across {decisions.length} candidates.
          Dashed lines mark the real auto-match ({Math.round(high * 100)}%)
          and review ({Math.round(low * 100)}%) thresholds. Confidence
          reflects the model&apos;s calibrated estimate — it is not a
          guarantee of correctness.
        </p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={buckets} margin={{ left: 8, right: 8 }}>
            <XAxis dataKey="bucket" tick={{ fontSize: 10 }} interval={1} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v: number) => [`${v}`, "decisions"]} />
            <ReferenceLine
              x={buckets[Math.min(9, Math.floor(low / BUCKET_WIDTH))].bucket}
              stroke="#f59e0b"
              strokeDasharray="4 4"
            />
            <ReferenceLine
              x={buckets[Math.min(9, Math.floor(high / BUCKET_WIDTH))].bucket}
              stroke="#10b981"
              strokeDasharray="4 4"
            />
            <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
