import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { AuditEventCard } from "@/components/decision/audit-event-card";
import type { AuditEventItem } from "@/lib/api-types";

/**
 * Renders events in the exact order the backend returned them — never
 * re-sorts client-side. The backend is the ordering authority (spec Step
 * 12), so trusting its order here isn't a shortcut, it's the design.
 */
export function AuditTimeline({ events }: { events: AuditEventItem[] }) {
  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-4 text-sm font-medium text-slate-700">
          Audit timeline
        </CardTitle>
        {events.length === 0 ? (
          <p className="text-sm text-slate-500">No audit events recorded yet.</p>
        ) : (
          <ol className="space-y-3">
            {events.map((e) => (
              <AuditEventCard key={e.event_id} event={e} />
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
