"""Tests for app/services/periods.py — Fase 7 date-period helpers.

parse_period turns a ("month"|"quarter", "YYYY-MM"|"YYYY-QN") pair into an
inclusive (start_date, end_date) tuple. current_*_value give the defaults
(D2: always current month). available_* list the periods that actually have a
won deal, for populating the frontend dropdowns.
"""

from datetime import date, datetime

import pytest

from app.services import periods
from app.models import Deal


# ---------------------------------------------------------------------------
# parse_period — month
# ---------------------------------------------------------------------------

def test_parse_period_month_basic():
    start, end = periods.parse_period("month", "2026-06")
    assert start == date(2026, 6, 1)
    assert end == date(2026, 6, 30)


def test_parse_period_month_february_non_leap():
    start, end = periods.parse_period("month", "2025-02")
    assert start == date(2025, 2, 1)
    assert end == date(2025, 2, 28)


def test_parse_period_month_february_leap():
    start, end = periods.parse_period("month", "2024-02")
    assert end == date(2024, 2, 29)


def test_parse_period_month_31_day_month():
    start, end = periods.parse_period("month", "2026-01")
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 31)


# ---------------------------------------------------------------------------
# parse_period — quarter
# ---------------------------------------------------------------------------

def test_parse_period_quarter_q1():
    start, end = periods.parse_period("quarter", "2026-Q1")
    assert start == date(2026, 1, 1)
    assert end == date(2026, 3, 31)


def test_parse_period_quarter_q2():
    start, end = periods.parse_period("quarter", "2026-Q2")
    assert start == date(2026, 4, 1)
    assert end == date(2026, 6, 30)


def test_parse_period_quarter_q4_crosses_into_next_year():
    # Q4 ends Dec 31 of the SAME year — the year does not roll over mid-quarter.
    start, end = periods.parse_period("quarter", "2026-Q4")
    assert start == date(2026, 10, 1)
    assert end == date(2026, 12, 31)


# ---------------------------------------------------------------------------
# parse_period — invalid input (D6: 400 at the endpoint, ValueError here)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "period_type,period_value",
    [
        ("month", "2026-13"),     # month 13 impossible
        ("month", "2026-00"),     # month 00 impossible
        ("month", "2026-6"),      # not zero-padded
        ("month", "garbage"),     # not even a date
        ("month", "2026-06-01"),  # too granular (a day, not a month)
        ("quarter", "2026-Q0"),   # quarter 0 impossible
        ("quarter", "2026-Q5"),   # quarter 5 impossible
        ("quarter", "2026-Q"),    # missing digit
        ("quarter", "2026-06"),   # month value passed as quarter
        ("year", "2026"),         # unsupported period_type
    ],
)
def test_parse_period_invalid_raises(period_type, period_value):
    with pytest.raises(ValueError):
        periods.parse_period(period_type, period_value)


# ---------------------------------------------------------------------------
# current_*_value (D2 default = current month)
# ---------------------------------------------------------------------------

def test_current_month_value_matches_today():
    assert periods.current_month_value() == date.today().strftime("%Y-%m")


def test_current_quarter_value_matches_today():
    today = date.today()
    expected_q = (today.month - 1) // 3 + 1
    assert periods.current_quarter_value() == f"{today.year}-Q{expected_q}"


def test_current_quarter_value_is_round_trippable():
    # The value current_quarter_value produces must parse without error.
    start, end = periods.parse_period("quarter", periods.current_quarter_value())
    assert start <= end


# ---------------------------------------------------------------------------
# available_months / available_quarters (won deals only, descending)
# ---------------------------------------------------------------------------

def _won_deal(pipedrive_id, won_time):
    return Deal(
        pipedrive_id=pipedrive_id,
        title=f"Deal {pipedrive_id}",
        value=1000.0,
        stage_id=1,
        stage_name="Cerrado",
        status="won",
        update_time="2026-06-01T00:00:00",
        won_time=won_time,
    )


def test_available_months_lists_won_months_descending(db_session):
    db_session.add_all([
        _won_deal(1, datetime(2026, 6, 10)),
        _won_deal(2, datetime(2026, 4, 5)),
        _won_deal(3, datetime(2026, 6, 20)),  # duplicate month, deduped
    ])
    db_session.commit()

    assert periods.available_months(db_session) == ["2026-06", "2026-04"]


def test_available_months_excludes_non_won_and_null_won_time(db_session):
    open_deal = Deal(
        pipedrive_id=10, title="Open", value=1.0, stage_id=1, stage_name="Lead",
        status="open", update_time="2026-06-01T00:00:00", won_time=None,
    )
    won_no_time = _won_deal(11, None)  # won but never stamped
    db_session.add_all([open_deal, won_no_time])
    db_session.commit()

    assert periods.available_months(db_session) == []


def test_available_quarters_lists_won_quarters_descending(db_session):
    db_session.add_all([
        _won_deal(1, datetime(2026, 6, 10)),   # Q2
        _won_deal(2, datetime(2026, 2, 5)),    # Q1
        _won_deal(3, datetime(2026, 5, 1)),    # Q2 again, deduped
    ])
    db_session.commit()

    assert periods.available_quarters(db_session) == ["2026-Q2", "2026-Q1"]


def test_available_quarters_empty_when_no_won_deals(db_session):
    assert periods.available_quarters(db_session) == []
