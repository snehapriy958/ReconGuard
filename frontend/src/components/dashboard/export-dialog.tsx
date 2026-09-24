"use client";

import * as React from "react";
import {
  X,
  Download,
  FileSpreadsheet,
  FileCheck2,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import {
  getBatchExportUrl,
  getReconciliationStatement,
} from "@/lib/api-client";
import type { ReconciliationStatementResponse } from "@/lib/api-types";

export interface ExportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  batchId: string;
}

export function ExportDialog({ isOpen, onClose, batchId }: ExportDialogProps) {
  const [statement, setStatement] = React.useState<ReconciliationStatementResponse | null>(null);
  const [isLoadingStatement, setIsLoadingStatement] = React.useState(false);
  const [statementError, setStatementError] = React.useState<string | null>(null);
  const [isDownloadingStatement, setIsDownloadingStatement] = React.useState(false);

  // Load statement metadata when dialog opens
  React.useEffect(() => {
    if (!isOpen || !batchId) return;

    let isMounted = true;
    setIsLoadingStatement(true);
    setStatementError(null);

    getReconciliationStatement(batchId)
      .then((data) => {
        if (isMounted) {
          setStatement(data);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setStatementError(err instanceof Error ? err.message : "Failed to load statement");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingStatement(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, batchId]);

  // Handle escape key
  React.useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  const matchedExportUrl = getBatchExportUrl(batchId, "matched");
  const exceptionsExportUrl = getBatchExportUrl(batchId, "exceptions");

  const handleDownloadCsv = (url: string, filename: string) => {
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleDownloadStatement = async () => {
    try {
      setIsDownloadingStatement(true);
      const data = statement ?? (await getReconciliationStatement(batchId));
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `reconguard_${batchId}_statement.json`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      setStatementError(err instanceof Error ? err.message : "Failed to download statement");
    } finally {
      setIsDownloadingStatement(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
    >
      {/* Backdrop */}
      <div
        data-testid="export-dialog-backdrop"
        onClick={onClose}
        className="fixed inset-0 bg-slate-950/50 backdrop-blur-xs transition-opacity"
        aria-hidden="true"
      />

      {/* Modal Container */}
      <div className="relative w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl sm:p-7 z-10 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700 font-mono">
                {batchId}
              </span>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Close Package
              </span>
            </div>
            <h2
              id="export-dialog-title"
              className="mt-1 text-xl font-bold tracking-tight text-slate-950"
            >
              Export Reconciliation Package
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Download audit-ready close files, exception summaries, and reconciliation closing statements.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close export dialog"
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 focus:outline-none"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content Body / Cards */}
        <div className="mt-6 space-y-4">
          {/* Card 1: Reconciled Matched Export */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4.5 transition hover:border-slate-300">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-emerald-100 p-2.5 text-emerald-700">
                  <FileCheck2 className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">
                      Matched Source Records
                    </h3>
                    <span className="rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 border border-emerald-200">
                      CSV
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500 leading-relaxed max-w-md">
                    Reconciled ledger and settlement records including auto-matches and reviewer-approved decisions. Preserves 1:1, 1:N, and N:1 structural groups without amount duplication.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleDownloadCsv(matchedExportUrl, `reconguard_${batchId}_matched.csv`)}
                className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs border border-slate-300 transition hover:bg-slate-50 hover:text-slate-900"
              >
                <Download className="h-3.5 w-3.5" />
                Download CSV
              </button>
            </div>
          </div>

          {/* Card 2: Unresolved Exceptions Export */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4.5 transition hover:border-slate-300">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-amber-100 p-2.5 text-amber-700">
                  <AlertTriangle className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">
                      Unresolved Exceptions
                    </h3>
                    <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 border border-amber-200">
                      CSV
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500 leading-relaxed max-w-md">
                    All unresolved records and broken pairs mapped to standardized primary root causes (e.g. No Viable Candidate, Structural Match Failure, Model Uncertainty).
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleDownloadCsv(exceptionsExportUrl, `reconguard_${batchId}_exceptions.csv`)}
                className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs border border-slate-300 transition hover:bg-slate-50 hover:text-slate-900"
              >
                <Download className="h-3.5 w-3.5" />
                Download CSV
              </button>
            </div>
          </div>

          {/* Card 3: Financial Closing Statement */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4.5 transition hover:border-slate-300">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-indigo-100 p-2.5 text-indigo-700">
                  <FileSpreadsheet className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">
                      Reconciliation Closing Statement
                    </h3>
                    <span className="rounded bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700 border border-indigo-200">
                      JSON
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500 leading-relaxed max-w-md">
                    Application-level close package verifying financial amounts, resolution rates, and mathematical conservation invariants across ledger and settlement records.
                  </p>

                  {/* Invariant status badge / preview */}
                  <div className="mt-2.5 flex flex-wrap items-center gap-2">
                    {isLoadingStatement && (
                      <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Verifying close invariants…
                      </span>
                    )}

                    {!isLoadingStatement && statement && (
                      <>
                        {statement.invariants.all_invariants_hold ? (
                          <span
                            data-testid="invariants-verified-badge"
                            className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-200"
                          >
                            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                            Financial Invariants Verified
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-[11px] font-semibold text-rose-700 border border-rose-200">
                            <AlertTriangle className="h-3.5 w-3.5 text-rose-600" />
                            Invariant Warning Detected
                          </span>
                        )}

                        <span className="text-[11px] text-slate-400">
                          Ledger: ${statement.ledger.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </span>
                      </>
                    )}

                    {statementError && (
                      <span className="text-xs text-rose-600">
                        {statementError}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleDownloadStatement}
                disabled={isDownloadingStatement}
                className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-slate-900 px-3.5 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-slate-800 disabled:opacity-50"
              >
                {isDownloadingStatement ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                Download JSON
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 flex items-center justify-end border-t border-slate-100 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
