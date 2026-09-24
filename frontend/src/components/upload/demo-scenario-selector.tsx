"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Play, Loader2, Download, AlertCircle, Sparkles, Layers } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDemoDatasets, processDemoDataset, getDemoDatasetFileUrl } from "@/lib/api-client";
import { useApi } from "@/lib/use-api";
import { LoadingState, ErrorState } from "@/components/dashboard/states";
import type { DemoDatasetItem } from "@/lib/api-types";

interface DemoScenarioSelectorProps {
  className?: string;
  onScenarioProcessed?: (batchId: string) => void;
}

export function DemoScenarioSelector({
  className = "",
  onScenarioProcessed,
}: DemoScenarioSelectorProps) {
  const router = useRouter();
  const state = useApi(() => getDemoDatasets(), []);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [processError, setProcessError] = useState<{ id: string; message: string } | null>(null);

  const handleRun = async (scenario: DemoDatasetItem) => {
    setRunningId(scenario.id);
    setProcessError(null);
    try {
      const res = await processDemoDataset(scenario.id);
      if (onScenarioProcessed) {
        onScenarioProcessed(res.batch_id);
      } else {
        router.push(`/batches/${res.batch_id}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to run demonstration scenario";
      setProcessError({ id: scenario.id, message: msg });
      setRunningId(null);
    }
  };

  if (state.status === "loading") {
    return (
      <div className={`rounded-xl border border-slate-200 bg-white p-6 ${className}`}>
        <LoadingState label="Loading demonstration scenarios…" />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className={`rounded-xl border border-slate-200 bg-white p-6 ${className}`}>
        <ErrorState error={state.error} onRetry={state.refetch} />
      </div>
    );
  }

  const { datasets } = state.data;

  return (
    <div className={`space-y-4 ${className}`}>
      {processError && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
          <div className="flex-1">
            <span className="font-semibold">Reconciliation Error:</span> {processError.message}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {datasets.map((scenario) => {
          const isCurrentRunning = runningId === scenario.id;
          const isAnyRunning = runningId !== null;

          return (
            <Card
              key={scenario.id}
              className={`flex flex-col justify-between transition-all duration-150 ${
                isCurrentRunning ? "border-slate-400 bg-slate-50/50 shadow-xs" : "hover:border-slate-300"
              }`}
            >
              <CardHeader className="space-y-2 pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-100 text-slate-700">
                      <Layers className="h-4 w-4" />
                    </span>
                    <CardTitle className="text-sm font-semibold text-slate-900">
                      {scenario.name}
                    </CardTitle>
                  </div>
                </div>

                <CardDescription className="text-xs text-slate-600 leading-relaxed">
                  {scenario.description}
                </CardDescription>

                <div className="flex flex-wrap gap-1 pt-1">
                  {scenario.tags.map((tag) => (
                    <Badge
                      key={tag}
                      variant="neutral"
                      className="px-2 py-0.5 text-[11px] font-normal text-slate-600 bg-slate-100/80"
                    >
                      {tag}
                    </Badge>
                  ))}
                </div>
              </CardHeader>

              <CardContent className="space-y-3 pt-0">
                <div className="flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
                  <div className="flex items-center gap-2 font-mono text-[11px]">
                    <span className="text-slate-700 font-medium">{scenario.ledger_record_count} ledger</span>
                    <span>+</span>
                    <span className="text-slate-700 font-medium">{scenario.settlement_record_count} settlement</span>
                  </div>

                  <div className="flex items-center gap-1.5 text-[11px]">
                    <span className="text-slate-400">CSV:</span>
                    <a
                      href={getDemoDatasetFileUrl(scenario.id, "ledger")}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-0.5 text-slate-600 hover:text-slate-900 underline"
                      title="Inspect ledger CSV"
                      aria-label={`Inspect ledger CSV for ${scenario.name}`}
                    >
                      <Download className="h-3 w-3" />
                      Ledger
                    </a>
                    <span className="text-slate-300">·</span>
                    <a
                      href={getDemoDatasetFileUrl(scenario.id, "settlement")}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-0.5 text-slate-600 hover:text-slate-900 underline"
                      title="Inspect settlement CSV"
                      aria-label={`Inspect settlement CSV for ${scenario.name}`}
                    >
                      <Download className="h-3 w-3" />
                      Settlement
                    </a>
                  </div>
                </div>

                <div className="pt-1">
                  <Button
                    type="button"
                    disabled={isAnyRunning}
                    onClick={() => handleRun(scenario)}
                    className="w-full text-xs font-medium"
                    aria-label={`Run ${scenario.name} scenario`}
                  >
                    {isCurrentRunning ? (
                      <>
                        <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                        Reconciling Scenario…
                      </>
                    ) : (
                      <>
                        <Play className="mr-2 h-3 w-3 fill-current" />
                        Run Scenario
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
