"""Fase 7 — shared date-period helpers for month/quarter filtering.

A "period" is either a month ("YYYY-MM", e.g. "2026-06") or a quarter
("YYYY-QN", e.g. "2026-Q2"). parse_period turns one into an inclusive
(start_date, end_date) date tuple that callers feed to the date-range queries
(D7: bounds are UTC calendar dates; the inclusive end is the period's last day).

This module is the single source of truth for period parsing so the
Por Talento endpoint, the Reporte PDF, and the frontend dropdowns all agree on
the format and the boundaries (D6).
"""

import calendar
import re
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Deal

_MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_QUARTER_RE = re.compile(r"^(\d{4})-Q([1-4])$")

# Quarter number (1-4) -> (first month, last month)
_QUARTER_MONTHS = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}


def parse_period(period_type: str, period_value: str) -> tuple[date, date]:
    """Return the inclusive (start_date, end_date) for a period.

    period_type: "month" or "quarter".
    period_value: "YYYY-MM" for month, "YYYY-QN" for quarter (D6).

    Raises ValueError if period_type is unknown or period_value does not match
    the expected format / is out of range (e.g. month 13, quarter 5). Callers
    at the HTTP boundary translate this into a 400.
    """
    if period_type == "month":
        m = _MONTH_RE.match(period_value)
        if not m:
            raise ValueError(f"Invalid month period_value: {period_value!r} (expected YYYY-MM)")
        year, month = int(m.group(1)), int(m.group(2))
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    if period_type == "quarter":
        m = _QUARTER_RE.match(period_value)
        if not m:
            raise ValueError(f"Invalid quarter period_value: {period_value!r} (expected YYYY-QN)")
        year, quarter = int(m.group(1)), int(m.group(2))
        first_month, last_month = _QUARTER_MONTHS[quarter]
        last_day = calendar.monthrange(year, last_month)[1]
        return date(year, first_month, 1), date(year, last_month, last_day)

    raise ValueError(f"Unsupported period_type: {period_type!r} (expected 'month' or 'quarter')")


def current_month_value() -> str:
    """Return the current month as "YYYY-MM" (D2: default period)."""
    return date.today().strftime("%Y-%m")


def current_quarter_value() -> str:
    """Return the current quarter as "YYYY-QN" (D2: default period)."""
    today = date.today()
    quarter = (today.month - 1) // 3 + 1
    return f"{today.year}-Q{quarter}"


def available_months(db: Session) -> list[str]:
    """Return distinct "YYYY-MM" strings for months that have at least one won deal.

    Sourced from Deal.won_time (5.3) — won deals only, NULL won_time excluded
    (cannot be placed in a month). Descending (most recent first) for the dropdown.
    """
    rows = (
        db.query(Deal.won_time)
        .filter(Deal.status == "won", Deal.won_time.isnot(None))
        .all()
    )
    months = {wt.strftime("%Y-%m") for (wt,) in rows if wt is not None}
    return sorted(months, reverse=True)


def available_quarters(db: Session) -> list[str]:
    """Return distinct "YYYY-QN" strings for quarters that have at least one won deal.

    Same source as available_months (Deal.won_time, won deals only), bucketed
    into quarters. Descending for the dropdown.
    """
    rows = (
        db.query(Deal.won_time)
        .filter(Deal.status == "won", Deal.won_time.isnot(None))
        .all()
    )
    quarters = set()
    for (wt,) in rows:
        if wt is None:
            continue
        quarter = (wt.month - 1) // 3 + 1
        quarters.add(f"{wt.year}-Q{quarter}")
    return sorted(quarters, reverse=True)
