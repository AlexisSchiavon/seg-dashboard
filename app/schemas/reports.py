"""Pydantic response schemas for the reports endpoints (Plan 05-01).

Plain BaseModel for computed aggregates — no from_attributes needed since
all responses are built from service-layer dicts, not ORM rows directly.
(Same convention as app/schemas/leads.py per 03-PATTERNS.md.)
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReportGenerate(BaseModel):
    """POST /reports/generate request body.

    Fase 9.5: the report can target one talent, several, or all of them.
    - talent_ids is the Fase-9.5 way: a list of ids, or the literal "all"
      (consolidated report over every active talent).
    - talent_id is the legacy singular field, kept for back-compat; treated as
      talent_ids=[talent_id] when talent_ids is omitted.

    Fase 7 (D8): the period can be a month or a quarter.
    - period_type/period_value take precedence when both are present.
    - `month` is the legacy period parameter, treated as period_type="month".
    The router validates period_value via periods.parse_period (400 on bad input).
    """

    # Fase 9.5 target — list of talent ids or the literal "all".
    talent_ids: list[int] | Literal["all"] | None = None
    # DEPRECATED back-compat singular target (was required pre-9.5).
    talent_id: int | None = None
    # DEPRECATED (D8): legacy month. Strict YYYY-MM regex rejects malformed months
    # (e.g. 2026-00, 2026-13) at the schema boundary (422).
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
    """GET /reports/ list item. talent_id is None for consolidated reports."""

    id: int
    talent_id: int | None
    talent_name: str
    month: str
    generated_at: datetime
    file_size_bytes: int
