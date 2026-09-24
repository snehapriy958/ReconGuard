"""Financial accounting and metrics aggregation for reconciliation batches.

This module provides unique-source-record financial accumulation to prevent
double-counting across candidate groups, supporting:
- 1:1, 1:N (one-to-many), and N:1 (many-to-one) candidate groups
- Precedence: HIGH_CONFIDENCE_MATCH > NEEDS_REVIEW > LIKELY_NO_MATCH
- Zero-candidate source records as exceptions
- Decimal precision for financial calculations
- Strict invariant: matched + review + exception == total for both ledger and settlement
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional
from pydantic import BaseModel, Field


def _to_decimal(val: Any) -> Decimal:
    """Safely convert any numeric/string value to Decimal."""
    if val is None or val == "":
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


class FinancialSideSummary(BaseModel):
    """Financial breakdown and rates for one reconciliation side (ledger or settlement)."""
    total_amount: float = Field(..., description="Total unique source amount")
    matched_amount: float = Field(..., description="Amount matched with high confidence")
    review_amount: float = Field(..., description="Amount requiring human review")
    exception_amount: float = Field(..., description="Amount classified as exception / unmatched")
    matched_rate: float = Field(..., description="Ratio of matched to total amount")
    review_rate: float = Field(..., description="Ratio of review to total amount")
    exception_rate: float = Field(..., description="Ratio of exception to total amount")

    def to_dict(self) -> dict[str, float]:
        return {
            "total_amount": self.total_amount,
            "matched_amount": self.matched_amount,
            "review_amount": self.review_amount,
            "exception_amount": self.exception_amount,
            "matched_rate": self.matched_rate,
            "review_rate": self.review_rate,
            "exception_rate": self.exception_rate,
        }


class FinancialSummary(BaseModel):
    """Complete financial summary containing ledger and settlement metrics."""
    ledger: FinancialSideSummary
    settlement: FinancialSideSummary

    def to_dict(self) -> dict[str, dict[str, float]]:
        return {
            "ledger": self.ledger.to_dict(),
            "settlement": self.settlement.to_dict(),
        }


class FinancialAccumulator:
    """Accumulates financial reconciliation metrics by UNIQUE source record.

    Ensures that records participating in multiple candidate groups or structural
    (1:N, N:1) matches are counted exactly once in totals and in outcomes.
    """

    # Outcome precedence mapping
    PRECEDENCE_HIGH_CONFIDENCE_MATCH = 3
    PRECEDENCE_NEEDS_REVIEW = 2
    PRECEDENCE_LIKELY_NO_MATCH = 1
    PRECEDENCE_NONE = 0

    OUTCOME_TO_PRIORITY = {
        "HIGH_CONFIDENCE_MATCH": PRECEDENCE_HIGH_CONFIDENCE_MATCH,
        "NEEDS_REVIEW": PRECEDENCE_NEEDS_REVIEW,
        "LIKELY_NO_MATCH": PRECEDENCE_LIKELY_NO_MATCH,
    }

    def __init__(
        self,
        ledger_records: Iterable[dict[str, Any]],
        settlement_records: Iterable[dict[str, Any]],
    ) -> None:
        # Store unique records and their exact source amount
        self._unique_ledger: dict[str, Decimal] = {}
        for r in ledger_records:
            lid = str(r["ledger_id"])
            if lid not in self._unique_ledger:
                self._unique_ledger[lid] = _to_decimal(r.get("amount", 0))

        self._unique_settlement: dict[str, Decimal] = {}
        for r in settlement_records:
            sid = str(r["settlement_id"])
            if sid not in self._unique_settlement:
                self._unique_settlement[sid] = _to_decimal(r.get("amount", 0))

        # Default outcome priority is 0 (unmatched / exception)
        self._ledger_priority: dict[str, int] = {lid: self.PRECEDENCE_NONE for lid in self._unique_ledger}
        self._settlement_priority: dict[str, int] = {sid: self.PRECEDENCE_NONE for sid in self._unique_settlement}

    def record_candidate_outcome(
        self,
        ledger_ids: Iterable[str],
        settlement_ids: Iterable[str],
        outcome: str,
    ) -> None:
        """Record the reconciliation outcome for a candidate group.

        Updates the outcome priority of each participating ledger and settlement
        record if the new outcome has higher precedence than existing outcomes.
        """
        priority = self.OUTCOME_TO_PRIORITY.get(outcome, self.PRECEDENCE_NONE)

        for lid in ledger_ids:
            lid_str = str(lid)
            if lid_str in self._ledger_priority:
                if priority > self._ledger_priority[lid_str]:
                    self._ledger_priority[lid_str] = priority

        for sid in settlement_ids:
            sid_str = str(sid)
            if sid_str in self._settlement_priority:
                if priority > self._settlement_priority[sid_str]:
                    self._settlement_priority[sid_str] = priority

    def record_decisions(self, decisions: Iterable[Any]) -> None:
        """Convenience method to record multiple decisions (objects or dicts)."""
        for d in decisions:
            if isinstance(d, dict):
                lids = d.get("ledger_record_ids", [])
                sids = d.get("settlement_record_ids", [])
                outcome = d.get("decision", "")
            else:
                lids = getattr(d, "ledger_record_ids", [])
                sids = getattr(d, "settlement_record_ids", [])
                outcome = getattr(d, "decision", "")
            self.record_candidate_outcome(lids, sids, outcome)

    def _compute_side(
        self,
        unique_records: dict[str, Decimal],
        priorities: dict[str, int],
    ) -> FinancialSideSummary:
        total = Decimal("0.00")
        matched = Decimal("0.00")
        review = Decimal("0.00")
        exception = Decimal("0.00")

        for rid, amt in unique_records.items():
            p = priorities.get(rid, self.PRECEDENCE_NONE)
            if p == self.PRECEDENCE_HIGH_CONFIDENCE_MATCH:
                matched += amt
            elif p == self.PRECEDENCE_NEEDS_REVIEW:
                review += amt
            else:
                # LIKELY_NO_MATCH or zero candidates (PRECEDENCE_NONE)
                exception += amt
            total += amt

        # Invariant check: matched + review + exception == total
        if matched + review + exception != total:
            raise ValueError(
                f"Financial invariant violated: matched({matched}) + review({review}) + exception({exception}) != total({total})"
            )

        if total > Decimal("0.00"):
            matched_rate = matched / total
            review_rate = review / total
            exception_rate = exception / total
        else:
            matched_rate = Decimal("0.00")
            review_rate = Decimal("0.00")
            exception_rate = Decimal("0.00")

        # Serialized amounts rounded to 2 decimal places, rates to 4 decimal places
        total_float = round(float(total), 2)
        matched_float = round(float(matched), 2)
        review_float = round(float(review), 2)
        # Ensure exact sum equality in float representation as well
        exception_float = round(total_float - matched_float - review_float, 2)

        return FinancialSideSummary(
            total_amount=total_float,
            matched_amount=matched_float,
            review_amount=review_float,
            exception_amount=exception_float,
            matched_rate=round(float(matched_rate), 4),
            review_rate=round(float(review_rate), 4),
            exception_rate=round(float(exception_rate), 4),
        )

    def compute_summary(self) -> FinancialSummary:
        """Computes the final financial summary for both ledger and settlement sides."""
        ledger_side = self._compute_side(self._unique_ledger, self._ledger_priority)
        settlement_side = self._compute_side(self._unique_settlement, self._settlement_priority)
        return FinancialSummary(ledger=ledger_side, settlement=settlement_side)
