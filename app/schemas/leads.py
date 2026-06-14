"""Pydantic response schemas for the leads endpoints (Plan 03-01).

Plain BaseModel for computed aggregates — no from_attributes needed since
all responses are built from service-layer dicts, not ORM rows directly.
(Same convention as app/schemas/dashboard.py per 02-PATTERNS.md.)
"""
from datetime import datetime

from pydantic import BaseModel


class TalentLeadBar(BaseModel):
    talent_id: int | None
    name: str
    total: int
    calificados: int
    is_sin_talento: bool = False


class LeadsSummary(BaseModel):
    leads_totales: int
    calificados: int
    por_talento: list[TalentLeadBar]


class LeadRow(BaseModel):
    id: int
    sheet_row_id: int
    remitente_nombre: str
    remitente_email: str
    asunto: str
    fecha_recepcion: datetime | None
    talent_id: int | None
    talent_name: str | None
    status_filtrado: str
    status_display: str  # Mapped via STATUS_DISPLAY at service layer
    fuente: str
    score_calidad: int | None
    bloqueado: bool
    convertido_a_prospecto: bool
