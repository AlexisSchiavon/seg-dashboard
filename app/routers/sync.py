import logging

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import SessionLocal, get_db
from app.models import SyncLog
from app.schemas.sync import SyncStatus, SyncTriggerResponse
from app.sync.jobs import sync_pipedrive, sync_sheets, sync_trello

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(get_current_user)])


def _run_sync_in_background():
    """Run Pipedrive, Sheets, then Trello syncs sequentially (manual 'Sincronizar ahora' trigger).

    Each sync has its own SyncLog(source=...) row and per-source concurrency guard.
    If Pipedrive sync fails, Sheets and Trello are skipped — downstream data would be
    inconsistent against a stale deal table.
    """
    db = SessionLocal()
    try:
        sync_pipedrive(db)
        pd_log = (
            db.query(SyncLog)
            .filter(SyncLog.source == "pipedrive")
            .order_by(SyncLog.started_at.desc())
            .first()
        )
        if pd_log and pd_log.status == "error":
            logger.warning(
                "sync_pipedrive failed (%s) — skipping sheets and trello sync",
                pd_log.error_message,
            )
            return
        sync_sheets(db)
        sync_trello(db)
    finally:
        db.close()


@router.post("/pipedrive", response_model=SyncTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Pitfall 5: if a sync is already running, no-op — do not schedule a second one.
    running = (
        db.query(SyncLog)
        .filter(SyncLog.status == "running")
        .order_by(SyncLog.started_at.desc())
        .first()
    )
    if running is not None:
        return SyncTriggerResponse(status="already_running")

    background_tasks.add_task(_run_sync_in_background)
    return SyncTriggerResponse(status="accepted")


@router.get("/status", response_model=SyncStatus)
def get_sync_status(db: Session = Depends(get_db)):
    latest = db.query(SyncLog).order_by(SyncLog.started_at.desc()).first()
    if latest is None:
        return SyncStatus()
    return latest
