import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: number | string;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
  hint?: string;
}

const toneClasses: Record<NonNullable<StatCardProps["tone"]>, string> = {
  neutral: "text-slate-950",
  success: "text-emerald-600",
  warning: "text-amber-600",
  danger: "text-red-600",
  info: "text-blue-600",
};

const indicatorClasses: Record<
  NonNullable<StatCardProps["tone"]>,
  string
> = {
  neutral: "bg-slate-300",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
  info: "bg-blue-500",
};

export function StatCard({
  label,
  value,
  tone = "neutral",
  hint,
}: StatCardProps) {
  return (
    <Card className="overflow-hidden border-slate-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      <CardContent className="relative p-5">
        <span
          className={cn(
            "absolute left-0 top-0 h-full w-1",
            indicatorClasses[tone]
          )}
          aria-hidden="true"
        />

        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
          {label}
        </p>

        <p
          className={cn(
            "mt-2 text-2xl font-bold tracking-tight tabular-nums",
            toneClasses[tone]
          )}
        >
          {typeof value === "number" ? value.toLocaleString() : value}
        </p>

        {hint && (
          <p className="mt-2 text-xs leading-5 text-slate-400">
            {hint}
          </p>
        )}
      </CardContent>
    </Card>
  );
}