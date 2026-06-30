"""Dashboard read endpoints: /dashboard/summary and /dashboard/funnel.

Auth-protected via dependencies=[Depends(get_current_user)] (same pattern as
app/routers/talents.py). Both endpoints delegate to services/kpis.py and
services/funnel.py — no business logic lives in the router.

T-02B-01 mitigated: all routes require a valid JWT cookie.
T-02B-02 mitigated: response_model validates the shape at the boundary.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Deal, SyncLog, Talent
from app.schemas.dashboard import (
    CalendarEntry,
    DashboardSummary,
    DealRow,
    FunnelOverview,
    KpiTile,
    MonthProjection,
    RankingRow,
    ActivityItem,
    TalentDetail,
    LostReasonSummary,
    LostOpportunity,
    BrandCategorySlice,
    StageBucket,
)
from app.services import kpis as kpi_service
from app.services import funnel as funnel_service
from app.services import leads as leads_service
from app.services import periods as periods_service
from app.services import trello_service

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


def _has_data(db: Session) -> bool:
    """Return True if at least one Deal row exists (post-first-sync check)."""
    count = db.query(func.count(Deal.id)).scalar() or 0
    return count > 0


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Session = Depends(get_db)):
    """Return global KPI tiles, talent ranking, and recent activity feed.

    has_data=False is returned when no deals exist yet (empty state trigger
    for the frontend "Aún no hay datos de Pipedrive" banner).
    """
    leads_data = leads_service.leads_summary(db)

    if not _has_data(db):
        return DashboardSummary(
            kpis=[],
            ranking=[],
            activity=[],
            has_data=False,
            leads_totales=leads_data["leads_totales"],
            calificados=leads_data["calificados"],
        )

    kpis_data = kpi_service.global_kpis(db)
    ranking_data = kpi_service.talent_ranking(db)
    activity_data = funnel_service.recent_activity(db)

    # Build typed KpiTile list with UI-SPEC variants
    kpi_tiles = [KpiTile(**tile) for tile in kpis_data["kpis"]]

    # Build typed RankingRow list
    ranking_rows = [RankingRow(**row) for row in ranking_data]

    # Build typed ActivityItem list
    activity_items = [ActivityItem(**item) for item in activity_data]

    return DashboardSummary(
        kpis=kpi_tiles,
        ranking=ranking_rows,
        activity=activity_items,
        has_data=True,
        leads_totales=leads_data["leads_totales"],
        calificados=leads_data["calificados"],
    )


@router.get("/funnel", response_model=FunnelOverview)
def get_funnel(db: Session = Depends(get_db)):
    """Return the 6-stage funnel with bottleneck detection.

    has_data=False is returned when no deals exist yet.
    """
    from app.schemas.dashboard import StageBucket, BottleneckInfo

    if not _has_data(db):
        return FunnelOverview(
            stages=[],
            bottleneck=None,
            insufficient_data=False,
            has_data=False,
        )

    funnel_data = funnel_service.funnel_overview(db)

    stages = [StageBucket(**s) for s in funnel_data["stages"]]
    bottleneck = (
        BottleneckInfo(**funnel_data["bottleneck"])
        if funnel_data["bottleneck"] is not None
        else None
    )

    return FunnelOverview(
        stages=stages,
        bottleneck=bottleneck,
        insufficient_data=funnel_data["insufficient_data"],
        has_data=funnel_data["has_data"],
    )


@router.get("/talents/{talent_id}", response_model=TalentDetail)
def get_talent_detail(
    talent_id: int,
    period_type: str = Query("month", description="'month' or 'quarter' (Fase 7/D5)"),
    period_value: str | None = Query(
        None,
        description="'YYYY-MM' or 'YYYY-QN'. Defaults to the current period (D2).",
    ),
    db: Session = Depends(get_db),
):
    """Return per-talent KPIs, funnel, lost opportunities, and brand categories.

    Fase 7 (D2/D4): period_type/period_value scope the *closed* metrics
    (Cerrados/Comisión by won_time, lost donut by update_time, Cobrado tile by
    collection_date). Active metrics (Pipeline, funnel, brand, pendiente,
    income projection, payment calendar) stay all-time snapshots. When
    period_value is omitted the current month/quarter is used (D2).

    T-02C-01 mitigated: inherited from router-level dependencies=[Depends(get_current_user)].
    T-02C-02 mitigated: FastAPI coerces talent_id: int (422 on non-int); 404 via db.get guard.
    T-02C-03 mitigated: response_model=TalentDetail validates and filters output shape.
    T-02C-04 mitigated: loss_reason stored as resolved label by Plan 02-01 (never re-resolved).
    """
    # 404 guard — same pattern as talents.py (02-PATTERNS.md)
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Talent not found",
        )

    # Resolve the period (D2 default), validate (D6) — malformed input → 400.
    if period_value is None:
        period_value = (
            periods_service.current_quarter_value()
            if period_type == "quarter"
            else periods_service.current_month_value()
        )
    try:
        start, end = periods_service.parse_period(period_type, period_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        detail = kpi_service.talent_detail(db, talent_id, start=start, end=end)
    except ValueError:
        # Defensive catch for the unlikely race where a talent is deleted
        # between the guard above and the service lookup (WR-03). Surfaces
        # as 404 rather than an uncaught ValueError → 500.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Talent not found",
        )

    # Build typed Pydantic models from service dicts
    kpi_tiles = [KpiTile(**kpi) for kpi in detail["kpis"]]
    funnel_stages = [StageBucket(**s) for s in detail["funnel"]]
    lost_summary = [LostReasonSummary(**s) for s in detail["lost_summary"]]
    lost_opps = [LostOpportunity(**o) for o in detail["lost_opportunities"]]
    brand_cats = [BrandCategorySlice(**b) for b in detail["brand_categories"]]

    # Phase 4 — DASH-02: income projection, payment calendar, individual deals
    proj_dicts = trello_service.income_projection(db, talent_id)
    cal_dicts = trello_service.payment_calendar(db, talent_id)
    deal_dicts = trello_service.deals_for_talent(db, talent_id)

    income_proj = [MonthProjection(**p) for p in proj_dicts] if proj_dicts else None
    payment_cal = [CalendarEntry(**c) for c in cal_dicts] if cal_dicts else None
    deals = [DealRow(**d) for d in deal_dicts] if deal_dicts else None

    # Phase 8 FIX-02 — money-flow tiles for the Flujo de dinero toggle view.
    # Fase 7/D4: firmadas (won_time) + cobrado (collection_date) scoped to period;
    # pendiente stays all-time inside the service.
    flujo_data = kpi_service.flujo_dinero_kpis(db, talent_id, start=start, end=end)
    flujo_dinero_tiles = [KpiTile(**k) for k in flujo_data["kpis"]]

    return TalentDetail(
        talent_id=detail["talent_id"],
        name=detail["name"],
        category=detail["category"],
        kpis=kpi_tiles,
        funnel=funnel_stages,
        lost_summary=lost_summary,
        lost_opportunities=lost_opps,
        brand_categories=brand_cats,
        income_projection=income_proj,
        payment_calendar=payment_cal,
        deals=deals,
        flujo_dinero=flujo_dinero_tiles,
    )
