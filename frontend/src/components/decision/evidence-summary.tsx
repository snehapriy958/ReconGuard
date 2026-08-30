import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { humanizeFeatureName } from "@/lib/feature-labels";
import type { EvidenceItem } from "@/lib/api-types";

const strengthTone = { strong: "success", moderate: "warning", weak: "neutral" } as const;

/**
 * LAYER 2 — EVIDENCE QUALITY (top attribution).
 * Renders the real, persisted `evidence` array — the actual pred_contrib
 * attributions computed by the model at decision time (see
 * backend/app/pipeline.py). Nothing here is invented: every line is one
 * evidence row the backend already stored.
 */
export function EvidenceSummary({ evidence }: { evidence: EvidenceItem[] }) {
  const supporting = evidence.filter((e) => e.direction === "supports_match");
  const weakening = evidence.filter((e) => e.direction !== "supports_match");

  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-4 text-sm font-medium text-slate-700">
          Why this decision?
        </CardTitle>

        {evidence.length === 0 ? (
          <p className="text-sm text-slate-500">
            No evidence attribution was recorded for this decision.
          </p>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-emerald-700">
                Supporting evidence
              </p>
              {supporting.length === 0 ? (
                <p className="text-sm text-slate-400">None among the top attributions.</p>
              ) : (
                <ul className="space-y-2">
                  {supporting.map((e) => (
                    <li key={e.feature} className="flex items-start gap-2 text-sm">
                      <span className="mt-0.5 text-emerald-600">✓</span>
                      <span className="text-slate-700">
                        {humanizeFeatureName(e.feature)}
                        <Badge variant={strengthTone[e.strength]} className="ml-2 text-[10px]">
                          {e.strength}
                        </Badge>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-amber-700">
                Weakening evidence
              </p>
              {weakening.length === 0 ? (
                <p className="text-sm text-slate-400">None among the top attributions.</p>
              ) : (
                <ul className="space-y-2">
                  {weakening.map((e) => (
                    <li key={e.feature} className="flex items-start gap-2 text-sm">
                      <span className="mt-0.5 text-amber-600">⚠</span>
                      <span className="text-slate-700">
                        {humanizeFeatureName(e.feature)}
                        {e.direction === "creates_ambiguity" && " (creates ambiguity)"}
                        <Badge variant={strengthTone[e.strength]} className="ml-2 text-[10px]">
                          {e.strength}
                        </Badge>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
