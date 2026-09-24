"""
ReconGuard — CSV parsing and server-side validation for ledger and settlement files.
"""
import csv
import io
import math
from datetime import datetime
from typing import Literal

REQUIRED_LEDGER_COLUMNS = ["ledger_id", "vendor_name", "amount", "txn_date"]
REQUIRED_SETTLEMENT_COLUMNS = ["settlement_id", "vendor_name", "amount", "txn_date"]
OPTIONAL_COLUMNS = ["reference_id", "description"]


def validate_and_parse_csv(
    file_bytes: bytes,
    file_type: Literal["ledger", "settlement"],
    max_errors: int = 50,
) -> tuple[list[dict], list[dict]]:
    """
    Parses and validates a CSV file for ledger or settlement records.

    Returns:
        (records, errors)
        - records: list of sanitized dicts conforming to LedgerRecordIn / SettlementRecordIn schema
        - errors: list of error dicts with structure {"file": ..., "row": ..., "field": ..., "message": ...}
    """
    errors: list[dict] = []
    records: list[dict] = []

    # 1. Check file presence / emptiness
    if not file_bytes or len(file_bytes.strip()) == 0:
        return records, [{"file": file_type, "message": f"Uploaded {file_type} file is empty"}]

    # 2. Decode bytes safely
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("latin-1")
        except Exception:
            return records, [{
                "file": file_type,
                "message": f"Unable to decode {file_type} CSV. File must be UTF-8 encoded text.",
            }]

    # 3. Parse CSV rows
    f = io.StringIO(text)
    try:
        reader = csv.reader(f)
        try:
            header_row = next(reader)
        except StopIteration:
            return records, [{"file": file_type, "message": f"Uploaded {file_type} file is empty"}]
    except csv.Error as e:
        return records, [{"file": file_type, "message": f"Malformed CSV format: {e}"}]

    # Normalize header names (lowercase, stripped)
    header_map: dict[str, int] = {}
    for idx, col in enumerate(header_row):
        normalized = col.strip().lower()
        if normalized and normalized not in header_map:
            header_map[normalized] = idx

    id_col = "ledger_id" if file_type == "ledger" else "settlement_id"
    required_cols = REQUIRED_LEDGER_COLUMNS if file_type == "ledger" else REQUIRED_SETTLEMENT_COLUMNS

    # Check for missing required columns
    missing_cols = [c for c in required_cols if c not in header_map]
    if missing_cols:
        for c in missing_cols:
            errors.append({
                "file": file_type,
                "row": 1,
                "field": c,
                "message": f"Missing required column '{c}' in {file_type} CSV",
            })
        return records, errors

    seen_ids: set[str] = set()

    # 4. Validate data rows (row index starts at 2 because row 1 is header)
    for row_idx, row in enumerate(reader, start=2):
        if len(errors) >= max_errors:
            break

        # Check for completely blank row (e.g. trailing newline)
        if not row or all(c.strip() == "" for c in row):
            continue

        row_errors: list[dict] = []

        # Helper to get column value by name safely
        def get_val(col_name: str) -> str:
            col_pos = header_map.get(col_name)
            if col_pos is not None and col_pos < len(row):
                return row[col_pos].strip()
            return ""

        # --- Identifier validation ---
        record_id = get_val(id_col)
        if not record_id:
            row_errors.append({
                "file": file_type,
                "row": row_idx,
                "field": id_col,
                "message": f"Missing required identifier '{id_col}'",
            })
        elif record_id in seen_ids:
            row_errors.append({
                "file": file_type,
                "row": row_idx,
                "field": id_col,
                "message": f"Duplicate {id_col} '{record_id}' found in {file_type} CSV",
            })
        else:
            seen_ids.add(record_id)

        # --- Vendor name validation ---
        vendor_name = get_val("vendor_name")
        if not vendor_name:
            row_errors.append({
                "file": file_type,
                "row": row_idx,
                "field": "vendor_name",
                "message": "vendor_name is required and cannot be empty",
            })

        # --- Amount validation ---
        amount_raw = get_val("amount")
        amount_val: float = 0.0
        if not amount_raw:
            row_errors.append({
                "file": file_type,
                "row": row_idx,
                "field": "amount",
                "message": "Missing required numeric amount",
            })
        else:
            try:
                amount_val = float(amount_raw)
                if math.isnan(amount_val) or math.isinf(amount_val):
                    raise ValueError("NaN or Inf amount")
            except ValueError:
                row_errors.append({
                    "file": file_type,
                    "row": row_idx,
                    "field": "amount",
                    "message": f"Invalid numeric amount '{amount_raw}'",
                })

        # --- Date validation ---
        txn_date_raw = get_val("txn_date")
        txn_date_clean = ""
        if not txn_date_raw:
            row_errors.append({
                "file": file_type,
                "row": row_idx,
                "field": "txn_date",
                "message": "Missing required transaction date",
            })
        else:
            parsed_date = None
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
                try:
                    parsed_date = datetime.strptime(txn_date_raw, fmt)
                    break
                except ValueError:
                    pass

            if parsed_date is None:
                try:
                    parsed_date = datetime.fromisoformat(txn_date_raw)
                except ValueError:
                    pass

            if parsed_date is not None:
                txn_date_clean = parsed_date.strftime("%Y-%m-%d")
            else:
                row_errors.append({
                    "file": file_type,
                    "row": row_idx,
                    "field": "txn_date",
                    "message": f"Invalid date '{txn_date_raw}', expected format YYYY-MM-DD",
                })

        # --- Optional fields ---
        reference_id = get_val("reference_id")
        description = get_val("description")

        if row_errors:
            errors.extend(row_errors)
        else:
            records.append({
                id_col: record_id,
                "vendor_name": vendor_name,
                "amount": amount_val,
                "txn_date": txn_date_clean,
                "reference_id": reference_id,
                "description": description,
            })

    if not records and not errors:
        errors.append({"file": file_type, "message": f"{file_type} CSV contains no data rows"})

    return records, errors
