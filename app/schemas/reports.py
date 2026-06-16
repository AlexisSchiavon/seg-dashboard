"""Pydantic response schemas for the reports endpoints (Plan 05-01).

Plain BaseModel for computed aggregates — no from_attributes needed since
all responses are built from service-layer dicts, not ORM rows directly.
(Same convention as app/schemas/leads.py per 03-PATTERNS.md.)
"""
from datetime import datetime

from pydantic import BaseModel, Field


class ReportGenerate(BaseModel):
    """POST /reports/generate request body."""

    talent_id: int
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")  # T-05-VAL: rejects malformed month strings and invalid month values (e.g. 2026-00, 2026-13)


class NarrativeSections(BaseModel):
    """The 3 Claude-generated prose sections returned to the frontend."""

    resumen_ejecutivo: str
    deals_destacados: str
    recomendacion: str


class ReportOut(BaseModel):
    """POST /reports/generate response — metadata + narrative for in-page preview."""

    id: int
    talent_id: int
    talent_name: str
    month: str
    generated_at: datetime
    file_path: str
    file_size_bytes: int
    narrative: NarrativeSections  # returned to frontend for dark preview card


class ReportHistoryItem(BaseModel):
    """GET /reports/ list item."""

    id: int
    talent_id: int
    talent_name: str
    month: str
    generated_at: datetime
    file_size_bytes: int
