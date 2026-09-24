"""
ReconGuard — Demo Scenario Datasets Registry & Loader.

Manages curated, allowlisted demonstration datasets so users can run
reconciliation scenarios without needing their own CSV files.

Strict Allowlist:
- 'clean-settlement': Clean Daily Settlement (routine 1:1 matching)
- 'structural-splits': Structural 1:N & N:1 Batches (split & batched payments)
- 'discrepancies-exceptions': Discrepancy & Exception Queue (fees, lags, unmatched items)
- 'balanced-portfolio': Balanced Real-World Batch (representative distribution)

Security:
Arbitrary filesystem paths are NEVER accepted. Only explicit allowlisted keys
defined in DEMO_DATASETS can be resolved.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from backend.app.csv_validator import validate_and_parse_csv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_BASE_DIR = REPO_ROOT / "data" / "demo"


@dataclass(frozen=True)
class DemoDatasetMetadata:
    id: str
    name: str
    description: str
    ledger_record_count: int
    settlement_record_count: int
    tags: list[str]
    ledger_filename: str = "ledger.csv"
    settlement_filename: str = "settlement.csv"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "ledger_record_count": self.ledger_record_count,
            "settlement_record_count": self.settlement_record_count,
            "tags": list(self.tags),
        }


DEMO_DATASETS: dict[str, DemoDatasetMetadata] = {
    "clean-settlement": DemoDatasetMetadata(
        id="clean-settlement",
        name="Clean Daily Settlement",
        description="Routine high-confidence 1:1 transactions with matching amounts, clean reference identifiers, and minimal date drift.",
        ledger_record_count=20,
        settlement_record_count=20,
        tags=["1:1", "high-confidence", "clean-references", "routine-settlement"],
    ),
    "structural-splits": DemoDatasetMetadata(
        id="structural-splits",
        name="Structural 1:N & N:1 Batches",
        description="Complex multi-record matching exercising both 1:N split settlements (multi-installment payouts) and N:1 merchant batch disbursements.",
        ledger_record_count=25,
        settlement_record_count=25,
        tags=["1:N", "N:1", "structural-matches", "batch-settlement", "split-payments"],
    ),
    "discrepancies-exceptions": DemoDatasetMetadata(
        id="discrepancies-exceptions",
        name="Discrepancy & Exception Queue",
        description="Reconciliation challenges featuring unrecorded processor fees, missing reference IDs, multi-week date lags, and unmatched pending records.",
        ledger_record_count=20,
        settlement_record_count=20,
        tags=["exceptions", "amount-drift", "missing-reference", "date-skew", "human-review"],
    ),
    "balanced-portfolio": DemoDatasetMetadata(
        id="balanced-portfolio",
        name="Balanced Real-World Batch",
        description="A representative enterprise operational batch combining clean pairwise matches, structural splits, human review candidates, and exceptions.",
        ledger_record_count=40,
        settlement_record_count=45,
        tags=["representative", "mixed-portfolio", "full-pipeline", "production-sample"],
    ),
}


def list_demo_datasets() -> list[dict[str, Any]]:
    """Return public metadata for all allowlisted demo scenarios."""
    return [meta.to_dict() for meta in DEMO_DATASETS.values()]


def get_demo_dataset_metadata(dataset_id: str) -> DemoDatasetMetadata | None:
    """Look up metadata for a specific dataset ID if allowlisted, else None."""
    return DEMO_DATASETS.get(dataset_id)


def get_demo_dataset_file_path(dataset_id: str, file_type: str) -> Path:
    """Resolve the absolute path to a demo dataset CSV file.

    Raises KeyError if dataset_id is not allowlisted or file_type is invalid.
    """
    if dataset_id not in DEMO_DATASETS:
        raise KeyError(f"Unknown demo dataset: {dataset_id}")
    if file_type not in ("ledger", "settlement"):
        raise ValueError(f"Invalid file_type: {file_type}. Expected 'ledger' or 'settlement'.")

    meta = DEMO_DATASETS[dataset_id]
    filename = meta.ledger_filename if file_type == "ledger" else meta.settlement_filename
    path = (DEMO_BASE_DIR / dataset_id / filename).resolve()

    # Safety assertion against path traversal
    if not str(path).startswith(str(DEMO_BASE_DIR.resolve())):
        raise ValueError("Path traversal attempt detected")
    if not path.is_file():
        raise FileNotFoundError(f"Demo file not found on disk: {path}")

    return path


def get_demo_dataset_records(dataset_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load and validate the allowlisted dataset's ledger and settlement records.

    Returns:
        (ledger_records, settlement_records) as parsed dict lists ready for
        process_batch().

    Raises:
        KeyError: If dataset_id is not in the allowlist.
        FileNotFoundError: If the underlying files are missing.
        ValueError: If validation fails.
    """
    ledger_path = get_demo_dataset_file_path(dataset_id, "ledger")
    settlement_path = get_demo_dataset_file_path(dataset_id, "settlement")

    with open(ledger_path, "rb") as f:
        ledger_bytes = f.read()
    with open(settlement_path, "rb") as f:
        settlement_bytes = f.read()

    ledger_records, ledger_errors = validate_and_parse_csv(ledger_bytes, "ledger")
    if ledger_errors:
        err_msg = "; ".join(e["message"] for e in ledger_errors[:3])
        raise ValueError(f"Demo ledger dataset '{dataset_id}' failed schema validation: {err_msg}")

    settlement_records, settlement_errors = validate_and_parse_csv(settlement_bytes, "settlement")
    if settlement_errors:
        err_msg = "; ".join(e["message"] for e in settlement_errors[:3])
        raise ValueError(f"Demo settlement dataset '{dataset_id}' failed schema validation: {err_msg}")

    return ledger_records, settlement_records
