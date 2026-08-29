import { Badge } from "@/components/ui/badge";
import type { BatchStatus } from "@/lib/api-types";

const statusVariant: Record<BatchStatus, "success" | "danger" | "neutral" | "info"> = {
  COMPLETED: "success",
  FAILED: "danger",
  PROCESSING: "info",
  CREATED: "neutral",
};

export function BatchStatusBadge({ status }: { status: BatchStatus }) {
  return <Badge variant={statusVariant[status]}>{status}</Badge>;
}
