import { Badge } from "@/components/ui/badge";
import { StateTransition } from "@/components/decision/state-transition";
import {
  eventCategory,
  eventTitle,
  eventSummary,
  CATEGORY_TONE,
} from "@/lib/audit-event-display";
import type { AuditEventItem } from "@/lib/api-types";

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

/**
 * The invariant banner (Step 9) only renders when the REAL payload actually
 * contains both model_decision_preserved and model_calibrated_probability
 * — fields review_actions.py has persisted since Phase 5. This is never
 * shown for events that don't carry this payload shape, so it can't imply
 * a preservation guarantee the data doesn't actually demonstrate.
 */
function InvariantBanner({ payload }: { payload: Record<string, unknown> }) {
  const decision = payload.model_decision_preserved;
  const probability = payload.model_calibrated_probability;
  if (typeof decision !== "string" || typeof probability !== "number") return null;
  return (
    <div className="mt-2 rounded-md bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
      Original ML output preserved: decision stayed <strong>{decision}</strong>{" "}
      at <strong>{Math.round(probability * 100)}%</strong> calibrated
      confidence. This action only changed workflow status, not the model&apos;s
      output.
    </div>
  );
}

export function AuditEventCard({ event }: { event: AuditEventItem }) {
  const category = eventCategory(event.event_type);
  const summary = eventSummary(event);
  const payload = event.payload ?? {};

  return (
    <li className="flex gap-3">
      <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-slate-300" />
      <div className="flex-1 border-b border-slate-100 pb-4 last:border-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={CATEGORY_TONE[category]}>{category}</Badge>
          <span className="text-sm font-medium text-slate-800">
            {eventTitle(event.event_type)}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-slate-400">
          {formatTime(event.timestamp)}
          {event.actor_id && ` · ${event.actor_type.toLowerCase()}: ${event.actor_id}`}
        </p>

        <StateTransition previousState={event.previous_state} newState={event.new_state} />

        {summary && <p className="mt-1 text-sm text-slate-600">{summary}</p>}

        {(event.event_type === "REVIEW_APPROVED" || event.event_type === "REVIEW_REJECTED") && (
          <InvariantBanner payload={payload} />
        )}

        {Object.keys(payload).length > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-600">
              Technical details
            </summary>
            <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-600">
              {JSON.stringify(payload, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </li>
  );
}
