"""Pydantic response schemas for the reports endpoints (Plan 05-01).

Plain BaseModel for computed aggregates — no from_attributes needed since
all responses are built from service-layer dicts, not ORM rows directly.
(Same convention as app/schemas/leads.py per 03-PATTERNS.md.)
"""
from datetime import datetime

from pydantic import BaseModel, Field


class ReportGenerate(BaseModel):
    """POST /reports/generate request body.

    Fase 7 (D8): the report can be scoped to a month or a quarter.
    - period_type/period_value are the Fase-7 way ("month"/"quarter" + "YYYY-MM"
      / "YYYY-QN"). When both are present they take precedence.
    - `month` is the legacy parameter, now optional and DEPRECATED. A month-only
      body is treated as period_type="month", period_value=<month>.
    The router validates period_value via periods.parse_period (400 on bad input).
    """

    talent_id: int
    # DEPRECATED (D8): kept for back-compat. Strict YYYY-MM regex still rejects
    # malformed months (e.g. 2026-00, 2026-13) at the schema boundary (422).
    month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    period_type: str | None = None
    period_value: str | None = None


class ReportOut(BaseModel):
    """POST /reports/generate response — report metadata (Fase 9: no narrative, D8)."""

    id: int
    talent_id: int
    talent_name: str
    month: str
    generated_at: datetime
    file_path: str
    file_size_bytes: int


class ReportHistoryItem(BaseModel):
    """GET /reports/ list item."""

    id: int
    talent_id: int
    talent_name: str
    month: str
    generated_at: datetime
    file_size_bytes: int
