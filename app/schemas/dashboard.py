"""Pydantic response schemas for the dashboard endpoints (Plan 02-02).

Plain BaseModel for computed aggregates (no ORM row backing); from_attributes
only on ORM-backed reads per Phase 2 convention (02-PATTERNS.md).
"""

from datetime import datetime
from pydantic import BaseModel


class KpiTile(BaseModel):
    label: str
    value: float
    count: int | None = None
    variant: str  # accent | amber | green | purple | blue


class RankingRow(BaseModel):
    talent_id: int | None
    name: str
    category: str | None = None
    revenue: float
    deal_count: int
    is_sin_talento: bool = False


class ActivityItem(BaseModel):
    title: str
    to_stage: str
    talent_name: str
    detected_at: datetime


class BottleneckInfo(BaseModel):
    stage_a: str
    stage_b: str
    conversion_pct: float


class StageBucket(BaseModel):
    stage: str
    count: int
    amount: float


class DashboardSummary(BaseModel):
    kpis: list[KpiTile]
    ranking: list[RankingRow]
    activity: list[ActivityItem]
    has_data: bool
    leads_totales: int = 0
    calificados: int = 0


class FunnelOverview(BaseModel):
    stages: list[StageBucket]
    bottleneck: BottleneckInfo | None = None
    insufficient_data: bool = False
    has_data: bool


# ---------------------------------------------------------------------------
# Plan 02-03: Per-talent detail schemas
# ---------------------------------------------------------------------------

class LostReasonSummary(BaseModel):
    reason: str
    count: int


class LostOpportunity(BaseModel):
    title: str
    amount: float
    loss_reason: str | None = None


class BrandCategorySlice(BaseModel):
    category: str
    count: int
    pct: float


# ---------------------------------------------------------------------------
# Phase 4 — DASH-02: Revenue projection + collection calendar + deal rows
# ---------------------------------------------------------------------------


class MonthProjection(BaseModel):
    """One month's cobrado/proyeccion/pendiente layers for the income projection chart."""
    month: str              # e.g. "Jun 2026" — English 3-letter abbreviation
    cobrado: float          # cerrado cards (green bar layer)
    proyeccion: float       # ejecucion cards (blue bar layer)
    pendiente: float        # cobranza cards (amber bar layer)
    is_current: bool = False  # True for the current month (shows "Real" sublabel)


class CalendarEntry(BaseModel):
    """One month node in the payment calendar timeline."""
    month: str          # e.g. "Jun 2026"
    amount: float       # total expected collection for the month (all layers)


class DealRow(BaseModel):
    """Individual deal row for the campaign table and top-3 medal cards."""
    title: str
    amount: float
    list_state: str                     # ejecucion | cobranza | cerrado | perdido
    trello_card_id: str | None = None   # None for unlinked / lost deals
    stage_name: str | None = None       # Pipedrive stage name for filter resolution


class TalentDetail(BaseModel):
    talent_id: int
    name: str
    category: str | None = None
    kpis: list[KpiTile]
    funnel: list[StageBucket]
    lost_summary: list[LostReasonSummary]
    lost_opportunities: list[LostOpportunity]
    brand_categories: list[BrandCategorySlice]
    # Phase 4 additions — Optional so existing tests without Trello data remain unbroken
    income_projection: list[MonthProjection] | None = None   # 4-month sliding window
    payment_calendar: list[CalendarEntry] | None = None      # matching 4-month calendar
    deals: list[DealRow] | None = None                        # individual deal rows
