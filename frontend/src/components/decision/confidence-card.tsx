import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DECISION_LABELS, DECISION_TONE } from "@/lib/decision-display";
import type { Decision } from "@/lib/api-types";

/**
 * LAYER 1 — MODEL CONFIDENCE ONLY.
 * This component renders exactly one number: probability.calibrated. It
 * has no prop for risk flags and no code path that could blend them in —
 * the type signature itself (destructuring only `probability`, `decision`,
 * `thresholds`) makes that structurally impossible, not just a convention.
 */
export function ConfidenceCard({
  probability,
  decision,
  thresholds,
}: Pick<Decision, "probability" | "decision" | "thresholds">) {
  const pct = Math.round(probability.calibrated * 100);

  return (
    <Card>
      <CardContent className="p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Model Confidence
        </p>
        <div className="mt-2 flex items-baseline gap-3">
          <span className="text-4xl font-semibold tabular-nums text-slate-900">
            {pct}%
          </span>
          <span className="text-sm text-slate-500">Calibrated match probability</span>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <Badge variant={DECISION_TONE[decision]}>{DECISION_LABELS[decision]}</Badge>
        </div>

        <p className="mt-4 text-xs text-slate-400">
          Raw model score: {Math.round(probability.raw * 100)}% · Auto-match
          threshold: {Math.round(thresholds.high * 100)}% · Review threshold:{" "}
          {Math.round(thresholds.low * 100)}%
        </p>
        <p className="mt-2 text-xs text-slate-400">
          This number reflects the model&apos;s calibrated probability only.
          Operational risk (below) never modifies it.
        </p>
      </CardContent>
    </Card>
  );
}
