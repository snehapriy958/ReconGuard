import { Card, CardContent, CardTitle } from "@/components/ui/card";
import type { RelationshipType, SourceRecordData } from "@/lib/api-types";

function field(v: unknown): string {
  if (v === null || v === undefined || v === "") return "Missing";
  if (typeof v === "number") return v.toLocaleString();
  return String(v);
}

function RecordCard({
  id,
  record,
}: {
  id: string;
  record: SourceRecordData | null;
}) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <p className="font-mono text-xs font-medium text-slate-900">{id}</p>
      {record === null ? (
        <p className="mt-1 text-xs text-red-600">Record not found</p>
      ) : (
        <dl className="mt-2 space-y-1 text-xs">
          <div className="flex justify-between gap-2">
            <dt className="text-slate-500">Vendor</dt>
            <dd className="text-right text-slate-800">{field(record.vendor_name)}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-slate-500">Amount</dt>
            <dd className="text-right tabular-nums text-slate-800">
              {field(record.amount)}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-slate-500">Date</dt>
            <dd className="text-right text-slate-800">{field(record.txn_date)}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-slate-500">Reference</dt>
            <dd className="text-right text-slate-800">{field(record.reference_id)}</dd>
          </div>
          {record.description !== undefined && (
            <div className="flex justify-between gap-2">
              <dt className="text-slate-500">Description</dt>
              <dd className="text-right text-slate-800">{field(record.description)}</dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}

export function RawRecordComparison({
  relationshipType,
  ledgerIds,
  settlementIds,
  ledgerRecords,
  settlementRecords,
}: {
  relationshipType: RelationshipType;
  ledgerIds: string[];
  settlementIds: string[];
  ledgerRecords: (SourceRecordData | null)[];
  settlementRecords: (SourceRecordData | null)[];
}) {
  const arrow = relationshipType === "one_to_one" ? "↔" : "→";
  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-4 text-sm font-medium text-slate-700">
          Raw record comparison
        </CardTitle>
        <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
          <div className="flex-1 space-y-2">
            <p className="text-xs font-medium text-slate-500">Ledger</p>
            {ledgerIds.map((id, i) => (
              <RecordCard key={id} id={id} record={ledgerRecords[i]} />
            ))}
          </div>
          <div className="shrink-0 self-center text-lg text-slate-400">{arrow}</div>
          <div className="flex-1 space-y-2">
            <p className="text-xs font-medium text-slate-500">Settlement</p>
            {settlementIds.map((id, i) => (
              <RecordCard key={id} id={id} record={settlementRecords[i]} />
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function DiffRow({
  label,
  ledgerValue,
  settlementValue,
  diff,
}: {
  label: string;
  ledgerValue: string;
  settlementValue: string;
  diff?: string;
}) {
  return (
    <div className="border-t border-slate-100 py-3 first:border-t-0 first:pt-0">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span className="text-slate-600">
          Ledger: <span className="text-slate-900">{ledgerValue}</span>
        </span>
        <span className="text-slate-600">
          Settlement: <span className="text-slate-900">{settlementValue}</span>
        </span>
        {diff && <span className="text-amber-700">{diff}</span>}
      </div>
    </div>
  );
}

/**
 * For structural groups, compares the LEDGER TOTAL against the SETTLEMENT
 * TOTAL (sum of all members on that side) — never an individual member's
 * amount against a multi-record group, which would misrepresent the
 * comparison per spec's explicit warning.
 */
export function WhatChanged({
  ledgerRecords,
  settlementRecords,
}: {
  ledgerRecords: (SourceRecordData | null)[];
  settlementRecords: (SourceRecordData | null)[];
}) {
  const ledgerPresent = ledgerRecords.every((r) => r !== null) as boolean;
  const settlementPresent = settlementRecords.every((r) => r !== null) as boolean;

  if (!ledgerPresent || !settlementPresent) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-slate-500">
          Some underlying records are unavailable, so a full comparison
          can&apos;t be shown.
        </CardContent>
      </Card>
    );
  }

  const isGroup = ledgerRecords.length > 1 || settlementRecords.length > 1;
  const ledgerTotal = (ledgerRecords as SourceRecordData[]).reduce(
    (sum, r) => sum + (typeof r.amount === "number" ? r.amount : 0),
    0
  );
  const settlementTotal = (settlementRecords as SourceRecordData[]).reduce(
    (sum, r) => sum + (typeof r.amount === "number" ? r.amount : 0),
    0
  );
  const amountDiff = settlementTotal - ledgerTotal;

  const singleLedger = ledgerRecords[0] as SourceRecordData;
  const singleSettlement = settlementRecords[0] as SourceRecordData;

  return (
    <Card>
      <CardContent className="p-6">
        <CardTitle className="mb-2 text-sm font-medium text-slate-700">
          What changed?
        </CardTitle>
        <DiffRow
          label="Amount"
          ledgerValue={isGroup ? `${field(ledgerTotal)} (total)` : field(singleLedger.amount)}
          settlementValue={
            isGroup ? `${field(settlementTotal)} (group total)` : field(singleSettlement.amount)
          }
          diff={`Difference: ${amountDiff >= 0 ? "+" : ""}${amountDiff.toFixed(2)}`}
        />
        {!isGroup && (
          <>
            <DiffRow
              label="Vendor"
              ledgerValue={field(singleLedger.vendor_name)}
              settlementValue={field(singleSettlement.vendor_name)}
            />
            <DiffRow
              label="Date"
              ledgerValue={field(singleLedger.txn_date)}
              settlementValue={field(singleSettlement.txn_date)}
            />
            <DiffRow
              label="Reference"
              ledgerValue={field(singleLedger.reference_id)}
              settlementValue={field(singleSettlement.reference_id)}
            />
          </>
        )}
        {isGroup && (
          <p className="mt-2 text-xs text-slate-400">
            Vendor/date/reference comparisons are shown per-record above in
            the raw record comparison — a structural group doesn&apos;t
            have one single value to compare on those fields the way a
            one-to-one match does.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
