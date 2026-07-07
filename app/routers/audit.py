"""Audit log router — authenticated read-only access to the forensic trail.

Business logic (query + filters) lives in app/services/audit.py.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.schemas.audit import AuditLogPage, AuditLogRow
from app.services import audit as audit_service

router = APIRouter(
    prefix="/api/audit",
    tags=["audit"],
    dependencies=[Depends(get_current_user)],
)


def _parse_dt(value: str | None, field: str) -> datetime | None:
    if value is None:
        return None
    try:
        # Accept plain dates ("2026-07-01") and full ISO timestamps.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Fecha inválida en '{field}': {value!r} (usar ISO 8601)",
        )


@router.get("/logs", response_model=AuditLogPage)
def list_audit_logs(
    entity_type: str | None = None,
    entity_id: str | None = None,
    action_type: str | None = None,
    actor: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Filtered, paginated audit trail (newest first).

    Examples:
      - Historia de un deal: ?entity_type=deal&entity_id=99
      - Asignaciones desde una fecha: ?action_type=TALENT_ASSIGNED&since=2026-07-01
      - Sincronizaciones fallidas: ?action_type=SYNC_FAILED
    """
    rows, total, next_cursor = audit_service.list_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action_type=action_type,
        actor=actor,
        since=_parse_dt(since, "since"),
        until=_parse_dt(until, "until"),
        limit=limit,
        cursor=cursor,
    )
    return AuditLogPage(
        items=[AuditLogRow.from_orm_row(r) for r in rows],
        total=total,
        next_cursor=next_cursor,
    )
