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


class TalentDetail(BaseModel):
    talent_id: int
    name: str
    category: str | None = None
    kpis: list[KpiTile]
    funnel: list[StageBucket]
    lost_summary: list[LostReasonSummary]
    lost_opportunities: list[LostOpportunity]
    brand_categories: list[BrandCategorySlice]
