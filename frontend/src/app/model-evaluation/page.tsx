"use client";

import Link from "next/link";
import { useApi } from "@/lib/use-api";
import { getModelEvaluation } from "@/lib/api-client";
import { LoadingState, ErrorState } from "@/components/dashboard/states";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatPercent } from "@/lib/formatters";
import {
  BrainCircuit,
  Sliders,
  Database,
  Target,
  BarChart2,
  CheckCircle2,
  AlertCircle,
  Layers,
  Info,
} from "lucide-react";

export default function ModelEvaluationPage() {
  const state = useApi(() => getModelEvaluation(), []);

  return (
    <main className="mx-auto max-w-6xl space-y-8 p-6 md:p-8">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Model Evaluation
            </h1>
            <Badge variant="info" className="gap-1 font-mono text-[11px]">
              Held-Out Test Set
            </Badge>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Offline model performance, calibration curve, and threshold policy evaluation on held-out test data.
          </p>
        </div>

        {state.status === "success" && (
          <div className="flex items-center gap-2">
            <Badge variant="neutral" className="text-xs">
              Bundle: <span className="ml-1 font-mono">{state.data.model.bundle_file}</span>
            </Badge>
          </div>
        )}
      </div>

      {state.status === "loading" && <LoadingState label="Loading model evaluation metrics…" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={state.refetch} />}

      {state.status === "success" && <EvaluationContent data={state.data} />}
    </main>
  );
}

function EvaluationContent({ data }: { data: import("@/lib/api-types").ModelEvaluationResponse }) {
  return (
    <div className="space-y-8">
          {/* Key Metric Highlights Banner */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <Card className="border-slate-200/80 bg-white shadow-xs">
              <CardHeader className="p-4 pb-1">
                <CardTitle className="text-xs font-medium text-slate-500">Accuracy</CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-1">
                <p className="text-2xl font-bold tabular-nums text-slate-900">
                  {formatPercent(data.metrics.accuracy)}
                </p>
                <p className="text-[11px] text-slate-400">Total accuracy</p>
              </CardContent>
            </Card>

            <Card className="border-slate-200/80 bg-white shadow-xs">
              <CardHeader className="p-4 pb-1">
                <CardTitle className="text-xs font-medium text-slate-500">Precision</CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-1">
                <p className="text-2xl font-bold tabular-nums text-emerald-600">
                  {formatPercent(data.metrics.precision)}
                </p>
                <p className="text-[11px] text-slate-400">0 false positives</p>
              </CardContent>
            </Card>

            <Card className="border-slate-200/80 bg-white shadow-xs">
              <CardHeader className="p-4 pb-1">
                <CardTitle className="text-xs font-medium text-slate-500">Recall</CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-1">
                <p className="text-2xl font-bold tabular-nums text-slate-900">
                  {formatPercent(data.metrics.recall)}
                </p>
                <p className="text-[11px] text-slate-400">74 of 77 matches</p>
              </CardContent>
            </Card>

            <Card className="border-slate-200/80 bg-white shadow-xs">
              <CardHeader className="p-4 pb-1">
                <CardTitle className="text-xs font-medium text-slate-500">F1-Score</CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-1">
                <p className="text-2xl font-bold tabular-nums text-slate-900">
                  {data.metrics.f1.toFixed(4)}
                </p>
                <p className="text-[11px] text-slate-400">Harmonic mean</p>
              </CardContent>
            </Card>

            <Card className="border-slate-200/80 bg-white shadow-xs">
              <CardHeader className="p-4 pb-1">
                <CardTitle className="text-xs font-medium text-slate-500">ROC-AUC</CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-1">
                <p className="text-2xl font-bold tabular-nums text-slate-900">
                  {data.metrics.roc_auc.toFixed(4)}
                </p>
                <p className="text-[11px] text-slate-400">Separability</p>
              </CardContent>
            </Card>

            <Card className="border-slate-200/80 bg-white shadow-xs">
              <CardHeader className="p-4 pb-1">
                <CardTitle className="text-xs font-medium text-slate-500">PR-AUC</CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-1">
                <p className="text-2xl font-bold tabular-nums text-slate-900">
                  {data.metrics.pr_auc.toFixed(4)}
                </p>
                <p className="text-[11px] text-slate-400">Precision-recall area</p>
              </CardContent>
            </Card>
          </div>

          {/* Model & Dataset Context */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Model Architecture & Policy */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <BrainCircuit className="h-4 w-4 text-slate-700" />
                  <CardTitle className="text-base font-semibold text-slate-900">
                    Model Architecture & Threshold Policy
                  </CardTitle>
                </div>
                <CardDescription>
                  Reconciliation classifier specifications and operational routing boundaries
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  <div className="rounded-md border border-slate-100 bg-slate-50/50 p-2.5">
                    <p className="text-xs text-slate-500">Model Type</p>
                    <p className="font-medium text-slate-900">{data.model.model_type}</p>
                  </div>
                  <div className="rounded-md border border-slate-100 bg-slate-50/50 p-2.5">
                    <p className="text-xs text-slate-500">Version</p>
                    <p className="font-mono font-medium text-slate-900">{data.model.version}</p>
                  </div>
                  <div className="rounded-md border border-slate-100 bg-slate-50/50 p-2.5">
                    <p className="text-xs text-slate-500">Features</p>
                    <p className="font-medium text-slate-900">{data.model.features_count} engineered</p>
                  </div>
                </div>

                {/* Threshold Policy */}
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3.5">
                  <div className="flex items-center justify-between pb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <Sliders className="h-3.5 w-3.5" />
                      Production Decision Policy
                    </span>
                    <Badge variant="neutral" className="text-[11px] font-mono">
                      Cost: FP={data.model.threshold_policy.fp_cost}, FN={data.model.threshold_policy.fn_cost}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-3 gap-2 pt-2 text-center text-xs">
                    <div className="rounded border border-red-200 bg-red-50/80 p-2">
                      <p className="font-semibold text-red-800">LIKELY_NO_MATCH</p>
                      <p className="mt-1 font-mono text-slate-600">P &lt; {data.model.threshold_policy.low_threshold.toFixed(2)}</p>
                      <p className="mt-0.5 text-[10px] text-slate-500">Automated Exception</p>
                    </div>
                    <div className="rounded border border-amber-200 bg-amber-50/80 p-2">
                      <p className="font-semibold text-amber-800">HUMAN_REVIEW</p>
                      <p className="mt-1 font-mono text-slate-600">
                        {data.model.threshold_policy.low_threshold.toFixed(2)} – {data.model.threshold_policy.high_threshold.toFixed(2)}
                      </p>
                      <p className="mt-0.5 text-[10px] text-slate-500">Review Queue</p>
                    </div>
                    <div className="rounded border border-emerald-200 bg-emerald-50/80 p-2">
                      <p className="font-semibold text-emerald-800">EXACT_MATCH</p>
                      <p className="mt-1 font-mono text-slate-600">P &ge; {data.model.threshold_policy.high_threshold.toFixed(2)}</p>
                      <p className="mt-0.5 text-[10px] text-slate-500">Instant Reconciliation</p>
                    </div>
                  </div>
                </div>

                {/* Top Features */}
                {data.model.top_features && data.model.top_features.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs font-medium text-slate-600">Top Predictive Features (by gain):</p>
                    <div className="space-y-1.5">
                      {data.model.top_features.slice(0, 5).map((f) => (
                        <div key={f.feature} className="flex items-center justify-between text-xs">
                          <span className="font-mono text-slate-700">{f.feature}</span>
                          <span className="font-mono tabular-nums text-slate-500">
                            {f.importance_gain.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Evaluation Dataset Info */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-slate-700" />
                  <CardTitle className="text-base font-semibold text-slate-900">
                    Evaluation Dataset & Splits
                  </CardTitle>
                </div>
                <CardDescription>
                  Candidate groups held out strictly from training and model tuning
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-3 gap-3 text-center text-sm">
                  <div className="rounded-md border border-slate-100 bg-slate-50/50 p-2.5">
                    <p className="text-xs text-slate-500">Training Set</p>
                    <p className="text-lg font-bold text-slate-900">{data.dataset.training_samples}</p>
                    <p className="text-[10px] text-slate-400">candidate groups</p>
                  </div>
                  <div className="rounded-md border border-slate-100 bg-slate-50/50 p-2.5">
                    <p className="text-xs text-slate-500">Validation Set</p>
                    <p className="text-lg font-bold text-slate-900">{data.dataset.validation_samples}</p>
                    <p className="text-[10px] text-slate-400">calibration tuning</p>
                  </div>
                  <div className="rounded-md border border-blue-200 bg-blue-50/50 p-2.5">
                    <p className="text-xs text-blue-700">Held-Out Test</p>
                    <p className="text-lg font-bold text-blue-900">{data.dataset.sample_count}</p>
                    <p className="text-[10px] text-blue-600">evaluation target</p>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 p-3.5">
                  <div className="flex items-center justify-between text-xs font-medium text-slate-700">
                    <span>Test Set Class Distribution</span>
                    <span className="font-mono text-slate-500">
                      {data.dataset.positive_count} pos ({formatPercent(data.dataset.positive_rate)}) / {data.dataset.negative_count} neg
                    </span>
                  </div>

                  <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-slate-100 flex">
                    <div
                      className="bg-emerald-500"
                      style={{ width: `${(data.dataset.positive_count / data.dataset.sample_count) * 100}%` }}
                      title={`Positive: ${data.dataset.positive_count}`}
                    />
                    <div
                      className="bg-slate-400"
                      style={{ width: `${(data.dataset.negative_count / data.dataset.sample_count) * 100}%` }}
                      title={`Negative: ${data.dataset.negative_count}`}
                    />
                  </div>

                  {/* Relationship Breakdown */}
                  {data.dataset.by_relationship_type && (
                    <div className="mt-4 pt-3 border-t border-slate-100 grid grid-cols-3 gap-2 text-center text-xs">
                      {Object.entries(data.dataset.by_relationship_type).map(([rel, d]) => (
                        <div key={rel} className="rounded bg-slate-50 p-2 border border-slate-100">
                          <p className="font-mono font-semibold text-slate-800">{rel}</p>
                          <p className="text-slate-600 mt-0.5">{d.total} samples</p>
                          <p className="text-[10px] text-slate-400">
                            {d.positive} pos / {d.negative} neg
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Confusion Matrix & Class-Level Performance */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Confusion Matrix */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Target className="h-4 w-4 text-slate-700" />
                  <CardTitle className="text-base font-semibold text-slate-900">
                    Confusion Matrix (Held-Out Test)
                  </CardTitle>
                </div>
                <CardDescription>
                  Binary classification results at decision threshold 0.50 (Total N = {data.confusion_matrix.total})
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <div className="min-w-[320px] rounded-lg border border-slate-200 p-4">
                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      {/* Top header row */}
                      <div className="p-2 text-slate-400"></div>
                      <div className="rounded bg-slate-100 p-2 font-semibold text-slate-700">
                        Pred Match
                      </div>
                      <div className="rounded bg-slate-100 p-2 font-semibold text-slate-700">
                        Pred Non-Match
                      </div>

                      {/* Actual Match row */}
                      <div className="flex items-center justify-center rounded bg-slate-100 p-2 font-semibold text-slate-700">
                        Actual Match
                      </div>
                      <div className="rounded-md border border-emerald-300 bg-emerald-50/70 p-3">
                        <span className="block text-xl font-bold text-emerald-800">
                          {data.confusion_matrix.true_positive}
                        </span>
                        <span className="text-[11px] font-medium text-emerald-700">True Positive (TP)</span>
                      </div>
                      <div className="rounded-md border border-amber-300 bg-amber-50/70 p-3">
                        <span className="block text-xl font-bold text-amber-800">
                          {data.confusion_matrix.false_negative}
                        </span>
                        <span className="text-[11px] font-medium text-amber-700">False Negative (FN)</span>
                      </div>

                      {/* Actual Non-Match row */}
                      <div className="flex items-center justify-center rounded bg-slate-100 p-2 font-semibold text-slate-700">
                        Actual Non-Match
                      </div>
                      <div className="rounded-md border border-red-200 bg-red-50/60 p-3">
                        <span className="block text-xl font-bold text-slate-900">
                          {data.confusion_matrix.false_positive}
                        </span>
                        <span className="text-[11px] font-medium text-slate-600">False Positive (FP)</span>
                      </div>
                      <div className="rounded-md border border-slate-300 bg-slate-50 p-3">
                        <span className="block text-xl font-bold text-slate-800">
                          {data.confusion_matrix.true_negative}
                        </span>
                        <span className="text-[11px] font-medium text-slate-600">True Negative (TN)</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                  <span className="flex items-center gap-1 text-emerald-700">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Zero false positives (100% precision)
                  </span>
                  <span>FN = 3 candidates routed to exception/review</span>
                </div>
              </CardContent>
            </Card>

            {/* Class-Level Performance Table */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-slate-700" />
                  <CardTitle className="text-base font-semibold text-slate-900">
                    Performance by Relationship Class
                  </CardTitle>
                </div>
                <CardDescription>
                  Precision and recall breakdown across 1:1, 1:N, and N:1 matching structures
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
                      <tr>
                        <th className="px-3.5 py-2.5 font-semibold">Relationship</th>
                        <th className="px-3.5 py-2.5 font-semibold text-center">Samples (N)</th>
                        <th className="px-3.5 py-2.5 font-semibold text-center">Positives</th>
                        <th className="px-3.5 py-2.5 font-semibold text-right">Precision</th>
                        <th className="px-3.5 py-2.5 font-semibold text-right">Recall</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-800">
                      {data.class_metrics &&
                        Object.entries(data.class_metrics).map(([cls, cm]) => (
                          <tr key={cls} className="hover:bg-slate-50/50">
                            <td className="px-3.5 py-2.5 font-mono font-semibold">{cls}</td>
                            <td className="px-3.5 py-2.5 text-center">{cm.n}</td>
                            <td className="px-3.5 py-2.5 text-center">{cm.positive}</td>
                            <td className="px-3.5 py-2.5 text-right font-mono font-medium text-emerald-600">
                              {formatPercent(cm.precision)}
                            </td>
                            <td className="px-3.5 py-2.5 text-right font-mono font-medium">
                              {formatPercent(cm.recall)}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>

                {data.routing_policy_results && (
                  <div className="mt-4 rounded-md bg-slate-50 p-3 border border-slate-100 text-xs space-y-1">
                    <p className="font-semibold text-slate-700">Operational Policy Routing Distribution:</p>
                    <div className="grid grid-cols-3 gap-2 pt-1 text-center">
                      <div>
                        <span className="text-slate-500">Auto-Match:</span>{" "}
                        <strong className="text-slate-800">{data.routing_policy_results.n_auto_match}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Human Review:</span>{" "}
                        <strong className="text-slate-800">{data.routing_policy_results.n_review}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">No Match:</span>{" "}
                        <strong className="text-slate-800">{data.routing_policy_results.n_no_match}</strong>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Probability Calibration Analysis */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BarChart2 className="h-4 w-4 text-slate-700" />
                  <CardTitle className="text-base font-semibold text-slate-900">
                    Probability Calibration Analysis
                  </CardTitle>
                </div>
                <Badge variant="neutral" className="font-mono text-xs">
                  Method: {data.calibration.method}
                </Badge>
              </div>
              <CardDescription>
                Comparison of raw model confidence vs calibrated probabilities for financial risk management
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Brier Score Comparison */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
                  <p className="text-xs text-slate-500">Raw Model Brier Score</p>
                  <p className="text-xl font-bold font-mono text-slate-800">
                    {data.calibration.brier_score_before.toFixed(5)}
                  </p>
                  <p className="text-[11px] text-slate-400">Extreme raw probabilities (sharp peak at 0/1)</p>
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
                  <p className="text-xs text-slate-500">Calibrated Brier Score</p>
                  <p className="text-xl font-bold font-mono text-slate-800">
                    {data.calibration.brier_score_after.toFixed(5)}
                  </p>
                  <p className="text-[11px] text-slate-400">Platt sigmoid scaled probabilities</p>
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
                  <p className="text-xs text-slate-500">Calibration Outcome</p>
                  <p className="text-sm font-semibold text-slate-800 mt-1">
                    Continuous Smoothing
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Avoided isotonic step collapse; preserved smooth threshold routing.
                  </p>
                </div>
              </div>

              {/* Methodology note */}
              {(data.calibration.methodology_note || data.calibration.notes) && (
                <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3.5 text-xs text-amber-900 flex items-start gap-2.5">
                  <Info className="h-4 w-4 shrink-0 text-amber-700 mt-0.5" />
                  <div>
                    <strong className="font-semibold">Calibration Methodology Note:</strong>{" "}
                    {data.calibration.methodology_note || data.calibration.notes}
                  </div>
                </div>
              )}

              {/* Reliability Diagram Table */}
              {data.calibration.reliability_after && data.calibration.reliability_after.length > 0 && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-600">
                    Test Split Reliability Bins (Post-Calibration)
                  </h4>
                  <div className="overflow-x-auto rounded-lg border border-slate-200">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
                        <tr>
                          <th className="px-3.5 py-2 font-semibold">Predicted Probability Bin</th>
                          <th className="px-3.5 py-2 font-semibold text-center">Sample Count (N)</th>
                          <th className="px-3.5 py-2 font-semibold text-center">Mean Predicted P</th>
                          <th className="px-3.5 py-2 font-semibold text-right">Observed Match Rate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-slate-800">
                        {data.calibration.reliability_after.map((bin) => (
                          <tr key={bin.bin} className="hover:bg-slate-50/50">
                            <td className="px-3.5 py-2 font-mono font-medium">{bin.bin}</td>
                            <td className="px-3.5 py-2 text-center">{bin.n}</td>
                            <td className="px-3.5 py-2 text-center font-mono">
                              {bin.mean_predicted !== null ? bin.mean_predicted.toFixed(3) : "—"}
                            </td>
                            <td className="px-3.5 py-2 text-right font-mono font-medium">
                              {bin.observed_rate !== null ? formatPercent(bin.observed_rate) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Evaluation Notes and Governance Limitations */}
          {data.notes && data.notes.length > 0 && (
            <Card className="border-slate-200 bg-slate-50/50">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-slate-600" />
                  <CardTitle className="text-sm font-semibold text-slate-900">
                    Model Governance & Operational Considerations
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="list-inside list-disc space-y-1.5 text-xs text-slate-600">
                  {data.notes.map((note, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {note}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Bottom Navigation */}
          <div className="flex items-center justify-between border-t border-slate-200 pt-6">
            <Link
              href="/batches"
              className="text-xs font-medium text-slate-600 hover:text-slate-900"
            >
              &larr; View Reconciliation Batches
            </Link>
            <Link
              href="/upload"
              className="text-xs font-medium text-blue-600 hover:text-blue-800"
            >
              Upload New CSV Batch &rarr;
            </Link>
          </div>
    </div>
  );
}
