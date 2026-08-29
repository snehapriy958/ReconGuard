import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { ApiError } from "@/lib/api-client";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <Card>
      <CardContent className="py-8 text-center text-sm text-slate-500">
        {label}
      </CardContent>
    </Card>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: ApiError | Error;
  onRetry?: () => void;
}) {
  return (
    <Card className="border-red-200 bg-red-50">
      <CardContent className="py-6">
        <p className="text-sm font-medium text-red-800">Something went wrong</p>
        <p className="mt-1 text-sm text-red-700">{error.message}</p>
        {onRetry && (
          <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
            Retry
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="py-8 text-center text-sm text-slate-500">
        {children}
      </CardContent>
    </Card>
  );
}
