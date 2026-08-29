import { ArrowRight, ArrowLeftRight } from "lucide-react";
import type { RelationshipType } from "@/lib/api-types";

function RecordIds({ ids }: { ids: string[] }) {
  return (
    <span className="font-mono text-xs">
      {ids.map((id, i) => (
        <span key={id}>
          {i > 0 && <span className="text-slate-400"> + </span>}
          <span
            className="inline-block max-w-[9rem] truncate align-bottom"
            title={id}
          >
            {id}
          </span>
        </span>
      ))}
    </span>
  );
}

/**
 * ONE_TO_ONE:  LED-001 ↔ STL-001
 * ONE_TO_MANY: LED-001 → STL-001 + STL-002
 * MANY_TO_ONE: LED-001 + LED-002 → STL-001
 * Never flattened into a single misleading ID, per spec.
 */
export function RelationshipDisplay({
  relationshipType,
  ledgerIds,
  settlementIds,
}: {
  relationshipType: RelationshipType;
  ledgerIds: string[];
  settlementIds: string[];
}) {
  if (relationshipType === "one_to_one") {
    return (
      <div className="flex items-center gap-1.5">
        <RecordIds ids={ledgerIds} />
        <ArrowLeftRight className="h-3 w-3 shrink-0 text-slate-400" />
        <RecordIds ids={settlementIds} />
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1.5">
      <RecordIds ids={ledgerIds} />
      <ArrowRight className="h-3 w-3 shrink-0 text-slate-400" />
      <RecordIds ids={settlementIds} />
    </div>
  );
}
