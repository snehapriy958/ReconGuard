"""
ReconLens — numeric features (amount + date deltas).

Handles the two failure modes explicitly called out in the spec: silent NaN/inf
production, and date-format mismatches between the two sources.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd


def parse_date(raw) -> Optional[date]:
    """Parse a date value from either source, tolerating the timestamp-vs-date
    format difference Phase 1 originally had (now fixed at generation, but the
    feature layer must not silently assume it stays fixed — a future data
    source could reintroduce mixed formats, so we parse defensively here too).
    """
    if raw is None or (isinstance(raw, float)):
        return None
    s = str(raw).strip()
    if not s:
        return None
    ts = pd.to_datetime(s, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"Unparseable date value: {raw!r}")
    return ts.date()


def abs_amount_diff(ledger_amount: float, settlement_amount: float) -> float:
    return abs(round(float(ledger_amount) - float(settlement_amount), 4))


def relative_amount_diff(ledger_amount: float, settlement_amount: float) -> float:
    """abs diff / ledger_amount — denominator anchored to the ledger amount
    (treated as the source of truth: the ledger is Razorpay's own record)
    rather than to the smaller of the two, which would inflate the ratio
    when settlement drops a large fee.

    A zero or negative ledger_amount is NOT a numeric edge case to smooth
    over with an epsilon — a real transaction cannot have a zero or negative
    amount, so this indicates upstream data corruption. Raising here (rather
    than returning a huge or negative "relative diff") keeps a bad row from
    silently entering the ML-ready dataset with a distorted feature value;
    validate.py is expected to catch this before it ever reaches here.
    """
    la = float(ledger_amount)
    if la <= 0:
        raise ValueError(
            f"relative_amount_diff requires a positive ledger_amount, got {la}. "
            f"This should have been caught by upstream data validation."
        )
    diff = abs_amount_diff(ledger_amount, settlement_amount)
    return round(diff / la, 6)


def amount_ratio(ledger_amount: float, settlement_amount: float) -> float:
    """settlement / ledger. 1.0 = exact match, <1.0 = settlement is lower
    (fee deduction, the common case). Same zero/negative-ledger guard as
    relative_amount_diff, for the same reason.
    """
    la = float(ledger_amount)
    if la <= 0:
        raise ValueError(
            f"amount_ratio requires a positive ledger_amount, got {la}. "
            f"This should have been caught by upstream data validation."
        )
    sa = float(settlement_amount)
    return round(sa / la, 6)


def date_diff_days(ledger_date_raw, settlement_date_raw) -> int:
    ld = parse_date(ledger_date_raw)
    sd = parse_date(settlement_date_raw)
    if ld is None or sd is None:
        raise ValueError(
            f"date_diff_days requires both dates present; got ledger={ledger_date_raw!r}, "
            f"settlement={settlement_date_raw!r}. A missing transaction date on either "
            f"side is a data-quality problem, not a feature-engineering one — it should "
            f"be caught by validate.py before reaching this function."
        )
    return (sd - ld).days
