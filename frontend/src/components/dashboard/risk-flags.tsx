import { Badge } from "@/components/ui/badge";

export function RiskFlags({ flags }: { flags: string[] }) {
  if (flags.length === 0) {
    return <span className="text-xs text-slate-400">No risk flags</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {flags.map((f) => (
        <Badge key={f} variant="warning" className="text-[10px]">
          {f}
        </Badge>
      ))}
    </div>
  );
}
