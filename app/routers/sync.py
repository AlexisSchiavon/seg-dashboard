from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import SessionLocal, get_db
from app.models import SyncLog
from app.schemas.sync import SyncStatus, SyncTriggerResponse
from app.sync.jobs import sync_pipedrive, sync_sheets

router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(get_current_user)])


def _run_sync_in_background():
    """Run Pipedrive then Sheets syncs sequentially (manual 'Sincronizar ahora' trigger).

    Each sync has its own SyncLog(source=...) row and concurrency guard.
    """
    db = SessionLocal()
    try:
        sync_pipedrive(db)
        sync_sheets(db)
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
