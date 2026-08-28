"""
ReconLens — idempotency.

Strategy: hash the batch's source record CONTENT (not a client-supplied key),
so resubmitting the exact same ledger/settlement rows — accidentally or via
retry after a network timeout — is detected and returns the existing batch
rather than creating duplicate financial decisions. A content hash (not a
random submission ID) is the right choice specifically because financial
idempotency should be about "did we already reconcile these records," not
"did this HTTP request happen before" — a client retrying with a new request
ID but the same data must still be caught.
"""
import hashlib
import json


def compute_batch_hash(ledger_records: list[dict], settlement_records: list[dict]) -> str:
    normalized = {
        "ledger": sorted(ledger_records, key=lambda r: r["ledger_id"]),
        "settlement": sorted(settlement_records, key=lambda r: r["settlement_id"]),
    }
    blob = json.dumps(normalized, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()
