"use client";

import { useState, useRef, DragEvent, ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import Papa from "papaparse";
import { UploadCloud, FileText, CheckCircle2, AlertCircle, Loader2, ArrowRight } from "lucide-react";
import { uploadBatch, ApiError } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/formatters";
import type { CsvValidationErrorDetail, CsvValidationResponseError } from "@/lib/api-types";

interface ParsedFileInfo {
  file: File;
  name: string;
  size: number;
  rowCount: number;
  columns: string[];
  totalAmount: number | null;
  isValid: boolean;
  errors: string[];
}

const REQUIRED_LEDGER = ["ledger_id", "vendor_name", "amount", "txn_date"];
const REQUIRED_SETTLEMENT = ["settlement_id", "vendor_name", "amount", "txn_date"];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function UploadPage() {
  const router = useRouter();

  const [ledgerInfo, setLedgerInfo] = useState<ParsedFileInfo | null>(null);
  const [settlementInfo, setSettlementInfo] = useState<ParsedFileInfo | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState<{ message: string; errors?: CsvValidationErrorDetail[] } | null>(null);

  const ledgerInputRef = useRef<HTMLInputElement>(null);
  const settlementInputRef = useRef<HTMLInputElement>(null);

  const [ledgerDragging, setLedgerDragging] = useState(false);
  const [settlementDragging, setSettlementDragging] = useState(false);

  function parseAndValidate(
    file: File,
    type: "ledger" | "settlement",
    onComplete: (info: ParsedFileInfo) => void
  ) {
    setApiError(null);
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const rawFields = results.meta.fields ?? [];
        const columns = rawFields.map((f) => f.trim().toLowerCase());
        const required = type === "ledger" ? REQUIRED_LEDGER : REQUIRED_SETTLEMENT;

        const missing = required.filter((r) => !columns.includes(r));
        const errors: string[] = [];

        if (missing.length > 0) {
          errors.push(`Missing required columns: ${missing.join(", ")}`);
        }

        if (results.data.length === 0) {
          errors.push("File has no data rows");
        }

        // Sum amount if amount column exists
        let totalAmount: number | null = null;
        if (columns.includes("amount")) {
          let sum = 0;
          let validNumbers = 0;
          for (const row of results.data) {
            // Find key case-insensitively
            const amtKey = Object.keys(row).find((k) => k.trim().toLowerCase() === "amount");
            if (amtKey) {
              const val = parseFloat(row[amtKey]?.trim() || "");
              if (!isNaN(val)) {
                sum += val;
                validNumbers++;
              }
            }
          }
          if (validNumbers > 0) {
            totalAmount = sum;
          }
        }

        onComplete({
          file,
          name: file.name,
          size: file.size,
          rowCount: results.data.length,
          columns,
          totalAmount,
          isValid: errors.length === 0,
          errors,
        });
      },
      error: (err) => {
        onComplete({
          file,
          name: file.name,
          size: file.size,
          rowCount: 0,
          columns: [],
          totalAmount: null,
          isValid: false,
          errors: [`CSV parse error: ${err.message}`],
        });
      },
    });
  }

  function handleFileSelect(file: File, type: "ledger" | "settlement") {
    if (type === "ledger") {
      parseAndValidate(file, "ledger", setLedgerInfo);
    } else {
      parseAndValidate(file, "settlement", setSettlementInfo);
    }
  }

  async function handleSubmit() {
    if (!ledgerInfo || !settlementInfo) return;
    if (!ledgerInfo.isValid || !settlementInfo.isValid) return;

    setIsSubmitting(true);
    setApiError(null);

    try {
      const res = await uploadBatch(ledgerInfo.file, settlementInfo.file);
      router.push(`/batches/${res.batch_id}`);
    } catch (err) {
      if (err instanceof ApiError && err.detail) {
        const detail = err.detail as CsvValidationResponseError;
        if (typeof detail === "object" && detail !== null && Array.isArray(detail.errors)) {
          setApiError({
            message: detail.message || "CSV validation failed",
            errors: detail.errors,
          });
        } else {
          setApiError({ message: err.message });
        }
      } else if (err instanceof Error) {
        setApiError({ message: err.message });
      } else {
        setApiError({ message: "An unexpected error occurred while processing the batch." });
      }
      setIsSubmitting(false);
    }
  }

  const canSubmit = Boolean(
    ledgerInfo?.isValid && settlementInfo?.isValid && !isSubmitting
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
          Upload Reconciliation Batch
        </h1>
        <p className="mt-2 text-sm text-slate-500 max-w-2xl">
          Submit your internal accounts ledger and external settlement files.
          ReconGuard will validate both schemas, extract structural candidate groups,
          and run ML matching and probability calibration synchronously.
        </p>
      </div>

      {/* API Error Notification */}
      {apiError && (
        <div className="mb-8 rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-900 shadow-xs">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-950">{apiError.message}</h3>
              {apiError.errors && apiError.errors.length > 0 && (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-left text-xs border border-red-200 bg-white/70 rounded-md">
                    <thead>
                      <tr className="border-b border-red-200 bg-red-100/50 text-red-900 font-semibold">
                        <th className="px-3 py-1.5">File</th>
                        <th className="px-3 py-1.5">Row</th>
                        <th className="px-3 py-1.5">Field</th>
                        <th className="px-3 py-1.5">Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-red-100 text-red-800">
                      {apiError.errors.map((e, idx) => (
                        <tr key={idx}>
                          <td className="px-3 py-1.5 font-medium capitalize">{e.file}</td>
                          <td className="px-3 py-1.5 font-mono">{e.row ?? "—"}</td>
                          <td className="px-3 py-1.5 font-mono">{e.field ?? "—"}</td>
                          <td className="px-3 py-1.5">{e.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="mt-2 text-xs text-red-700">
                Please fix the indicated row or schema errors in your CSV and re-upload.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Dual Upload Cards Grid */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Ledger Upload Card */}
        <Card className="flex flex-col border-slate-200 shadow-xs">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-semibold text-slate-900">
                1. Internal Ledger CSV
              </CardTitle>
              {ledgerInfo && (
                <div className="flex items-center gap-2">
                  <Badge variant={ledgerInfo.isValid ? "success" : "danger"}>
                    {ledgerInfo.isValid ? "Valid" : "Invalid Schema"}
                  </Badge>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setLedgerInfo(null);
                      if (ledgerInputRef.current) ledgerInputRef.current.value = "";
                    }}
                    className="text-xs text-slate-400 hover:text-slate-600 font-medium"
                    aria-label="Remove ledger file"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>
            <CardDescription className="text-xs text-slate-500">
              Required: <code className="font-mono text-[11px] bg-slate-100 px-1 py-0.5 rounded">ledger_id, vendor_name, amount, txn_date</code>
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col justify-between pt-0">
            {/* Dropzone */}
            <div
              onDragOver={(e: DragEvent<HTMLDivElement>) => {
                e.preventDefault();
                setLedgerDragging(true);
              }}
              onDragLeave={() => setLedgerDragging(false)}
              onDrop={(e: DragEvent<HTMLDivElement>) => {
                e.preventDefault();
                setLedgerDragging(false);
                if (e.dataTransfer.files?.[0]) {
                  handleFileSelect(e.dataTransfer.files[0], "ledger");
                }
              }}
              onClick={() => ledgerInputRef.current?.click()}
              className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition-colors ${
                ledgerDragging
                  ? "border-slate-900 bg-slate-100"
                  : ledgerInfo?.isValid
                  ? "border-emerald-300 bg-emerald-50/30 hover:bg-emerald-50/50"
                  : "border-slate-200 bg-slate-50 hover:bg-slate-100/70"
              }`}
            >
              <input
                ref={ledgerInputRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                data-testid="ledger-file-input"
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  if (e.target.files?.[0]) {
                    handleFileSelect(e.target.files[0], "ledger");
                  }
                }}
              />
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-xs border border-slate-200 mb-3">
                {ledgerInfo?.isValid ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                ) : (
                  <UploadCloud className="h-5 w-5 text-slate-600" />
                )}
              </div>
              <p className="text-xs font-semibold text-slate-800">
                {ledgerInfo ? ledgerInfo.name : "Select or drag ledger CSV"}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Supports UTF-8 encoded .csv up to 10 MB
              </p>
            </div>

            {/* File Info & Preview */}
            {ledgerInfo && (
              <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3 text-xs space-y-2">
                <div className="flex justify-between text-slate-600">
                  <span>File size:</span>
                  <span className="font-mono text-slate-900">{formatFileSize(ledgerInfo.size)}</span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Records detected:</span>
                  <span className="font-mono text-slate-900">{ledgerInfo.rowCount.toLocaleString()}</span>
                </div>
                {ledgerInfo.totalAmount !== null && (
                  <div className="flex justify-between text-slate-600">
                    <span>Total ledger amount:</span>
                    <span className="font-mono font-medium text-slate-900">
                      {formatCurrency(ledgerInfo.totalAmount)}
                    </span>
                  </div>
                )}
                {ledgerInfo.errors.length > 0 && (
                  <div className="rounded bg-red-50 p-2 text-red-700">
                    {ledgerInfo.errors.map((err, i) => (
                      <p key={i}>• {err}</p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Settlement Upload Card */}
        <Card className="flex flex-col border-slate-200 shadow-xs">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-semibold text-slate-900">
                2. Settlement CSV
              </CardTitle>
              {settlementInfo && (
                <div className="flex items-center gap-2">
                  <Badge variant={settlementInfo.isValid ? "success" : "danger"}>
                    {settlementInfo.isValid ? "Valid" : "Invalid Schema"}
                  </Badge>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSettlementInfo(null);
                      if (settlementInputRef.current) settlementInputRef.current.value = "";
                    }}
                    className="text-xs text-slate-400 hover:text-slate-600 font-medium"
                    aria-label="Remove settlement file"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>
            <CardDescription className="text-xs text-slate-500">
              Required: <code className="font-mono text-[11px] bg-slate-100 px-1 py-0.5 rounded">settlement_id, vendor_name, amount, txn_date</code>
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col justify-between pt-0">
            {/* Dropzone */}
            <div
              onDragOver={(e: DragEvent<HTMLDivElement>) => {
                e.preventDefault();
                setSettlementDragging(true);
              }}
              onDragLeave={() => setSettlementDragging(false)}
              onDrop={(e: DragEvent<HTMLDivElement>) => {
                e.preventDefault();
                setSettlementDragging(false);
                if (e.dataTransfer.files?.[0]) {
                  handleFileSelect(e.dataTransfer.files[0], "settlement");
                }
              }}
              onClick={() => settlementInputRef.current?.click()}
              className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition-colors ${
                settlementDragging
                  ? "border-slate-900 bg-slate-100"
                  : settlementInfo?.isValid
                  ? "border-emerald-300 bg-emerald-50/30 hover:bg-emerald-50/50"
                  : "border-slate-200 bg-slate-50 hover:bg-slate-100/70"
              }`}
            >
              <input
                ref={settlementInputRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                data-testid="settlement-file-input"
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  if (e.target.files?.[0]) {
                    handleFileSelect(e.target.files[0], "settlement");
                  }
                }}
              />
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-xs border border-slate-200 mb-3">
                {settlementInfo?.isValid ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                ) : (
                  <UploadCloud className="h-5 w-5 text-slate-600" />
                )}
              </div>
              <p className="text-xs font-semibold text-slate-800">
                {settlementInfo ? settlementInfo.name : "Select or drag settlement CSV"}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Supports UTF-8 encoded .csv up to 10 MB
              </p>
            </div>

            {/* File Info & Preview */}
            {settlementInfo && (
              <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3 text-xs space-y-2">
                <div className="flex justify-between text-slate-600">
                  <span>File size:</span>
                  <span className="font-mono text-slate-900">{formatFileSize(settlementInfo.size)}</span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Records detected:</span>
                  <span className="font-mono text-slate-900">{settlementInfo.rowCount.toLocaleString()}</span>
                </div>
                {settlementInfo.totalAmount !== null && (
                  <div className="flex justify-between text-slate-600">
                    <span>Total settlement amount:</span>
                    <span className="font-mono font-medium text-slate-900">
                      {formatCurrency(settlementInfo.totalAmount)}
                    </span>
                  </div>
                )}
                {settlementInfo.errors.length > 0 && (
                  <div className="rounded bg-red-50 p-2 text-red-700">
                    {settlementInfo.errors.map((err, i) => (
                      <p key={i}>• {err}</p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Action Bar */}
      <div className="mt-8 flex flex-col items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-xs sm:flex-row">
        <div className="flex items-center gap-3">
          <FileText className="h-5 w-5 text-slate-400" />
          <div className="text-xs text-slate-500">
            {canSubmit ? (
              <span className="font-medium text-emerald-700">
                Both files validated successfully. Ready for reconciliation.
              </span>
            ) : (
              <span>
                Please select valid Ledger and Settlement CSV files to proceed.
              </span>
            )}
          </div>
        </div>

        <Button
          type="button"
          disabled={!canSubmit}
          onClick={handleSubmit}
          className="w-full sm:w-auto min-w-[200px]"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Reconciling Batch…
            </>
          ) : (
            <>
              Reconcile Batch
              <ArrowRight className="ml-2 h-4 w-4" />
            </>
          )}
        </Button>
      </div>

      {/* Information Box */}
      <div className="mt-8 rounded-xl border border-slate-200/80 bg-slate-100/50 p-5 text-xs text-slate-500 leading-relaxed">
        <p className="font-medium text-slate-700 mb-1">
          Processing Note
        </p>
        <p>
          ReconGuard processes batches synchronously end-to-end. Upon clicking Reconcile, the system
          executes pairwise and structural candidate blocking, extracts 22 ML features, runs calibrated LightGBM
          inference, and generates an immutable audit timeline. Batches with hundreds of records typically complete
          in 2 to 6 seconds.
        </p>
      </div>
    </div>
  );
}
