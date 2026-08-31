import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { humanizeRootCause, rootCauseTone, isSystemFailure } from "@/lib/root-cause-display";
import type { RootCauseAnalysis } from "@/lib/api-types";

/**
 * Root cause and operational risk are different concepts (spec Step 9) —
 * this component takes no risk_flags prop at all, so the two can never be
 * accidentally merged into one card.
 */
export function RootCauseCard({ analysis }: { analysis: RootCauseAnalysis }) {
  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-1 text-sm font-medium text-slate-700">
          Primary root cause
        </CardTitle>
        {isSystemFailure(analysis.primary_root_cause) && (
          <p className="mb-2 text-xs font-medium text-red-700">
            This is a technical processing issue, not a reconciliation-quality finding.
          </p>
        )}
        <Badge variant={rootCauseTone(analysis.primary_root_cause)} className="text-sm">
          {humanizeRootCause(analysis.primary_root_cause)}
        </Badge>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Observed
            </p>
            <ul className="mt-1 space-y-1 text-sm text-slate-700">
              {analysis.observed.map((o, i) => (
                <li key={i}>{o}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Interpretation
            </p>
            <ul className="mt-1 space-y-1 text-sm text-slate-700">
              {analysis.interpretation.map((o, i) => (
                <li key={i}>{o}</li>
              ))}
            </ul>
          </div>
        </div>

        {analysis.contributing_factors.length > 0 && (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Contributing factors
            </p>
            <ul className="mt-1 space-y-1 text-sm text-slate-600">
              {analysis.contributing_factors.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-4 border-t border-slate-100 pt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Investigation guidance
          </p>
          <p className="mt-1 text-sm text-slate-700">{analysis.investigation_guidance}</p>
        </div>

        <p className="mt-4 text-xs text-slate-400">
          Root-cause taxonomy v{analysis.taxonomy_version.replace("v", "")} — a
          deterministic classification, not a probability. No fabricated
          confidence score is shown.
        </p>
      </CardContent>
    </Card>
  );
}
