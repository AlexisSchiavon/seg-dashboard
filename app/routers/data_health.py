"""Data-health router (Prompt 3, Feature 2).

Read-only endpoints exposing operational data problems (TA responsibility).
Business logic lives in app/services/health_checks.py.

NOTE: prefix is /api/health — distinct from the infra liveness probe at /health.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.services import health_checks as hc

router = APIRouter(
    prefix="/api/health",
    tags=["data-health"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
def get_health(db: Session = Depends(get_db)):
    """Latest snapshot of every check + last-24h trend."""
    return hc.get_latest(db)


@router.get("/{check_id}/items")
def get_health_items(
    check_id: str,
    limit: int = Query(50, ge=1, le=200),
    cursor: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated affected items for a single check (computed live)."""
    result = hc.get_check_items(db, check_id, limit=limit, cursor=cursor)
    if result is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"check_id desconocido: {check_id!r}",
        )
    items, total, next_cursor = result
    return {"check_id": check_id, "items": items, "total": total, "next_cursor": next_cursor}
