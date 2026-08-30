import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/**
 * LAYER 3 — OPERATIONAL RISK.
 * Renders real risk_flags + real risk_flag_explanations (both sourced
 * server-side, the latter from backend/app/workflow/risk.py's
 * risk_explanation() — never invented in the frontend). This component
 * takes no probability prop at all, so it structurally cannot blend risk
 * into confidence even by accident.
 */
export function OperationalRiskCard({
  riskFlags,
  explanations,
}: {
  riskFlags: string[];
  explanations: Record<string, string>;
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-1 text-sm font-medium text-slate-700">
          Operational risk
        </CardTitle>
        <p className="mb-4 text-xs text-slate-400">
          These flags describe operational context and known evaluation
          limitations. They do not modify the model&apos;s calibrated
          probability shown above.
        </p>

        {riskFlags.length === 0 ? (
          <p className="text-sm text-slate-500">No risk flags for this decision.</p>
        ) : (
          <ul className="space-y-3">
            {riskFlags.map((flag) => (
              <li key={flag} className="flex items-start gap-2">
                <span className="mt-0.5 text-amber-600">⚠</span>
                <div>
                  <Badge variant="warning">{flag}</Badge>
                  <p className="mt-1 text-sm text-slate-600">
                    {explanations[flag] ?? "No further explanation recorded."}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
