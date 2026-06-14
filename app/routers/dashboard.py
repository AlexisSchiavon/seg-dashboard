"""Dashboard read endpoints: /dashboard/summary and /dashboard/funnel.

Auth-protected via dependencies=[Depends(get_current_user)] (same pattern as
app/routers/talents.py). Both endpoints delegate to services/kpis.py and
services/funnel.py — no business logic lives in the router.

T-02B-01 mitigated: all routes require a valid JWT cookie.
T-02B-02 mitigated: response_model validates the shape at the boundary.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Deal, SyncLog
from app.schemas.dashboard import DashboardSummary, FunnelOverview, KpiTile, RankingRow, ActivityItem
from app.services import kpis as kpi_service
from app.services import funnel as funnel_service

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
    if not _has_data(db):
        return DashboardSummary(
            kpis=[],
            ranking=[],
            activity=[],
            has_data=False,
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
