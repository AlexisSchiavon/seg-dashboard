"""Every-30-minute sync job for Pipedrive, Google Sheets, and Trello, scheduled via
APScheduler and wired into app/main.py's lifespan (start on app startup,
shutdown on app shutdown).
"""
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.sync.jobs import sync_pipedrive, sync_sheets, sync_trello

scheduler = BackgroundScheduler()


def _run_all_syncs():
    """Run Pipedrive, then Sheets, then Trello syncs sequentially.

    Each sync writes its own SyncLog(source=...) row independently.
    If Pipedrive fails, Sheets and Trello are still attempted — each has its
    own try/except inside the job function.
    """
    db = SessionLocal()
    try:
        sync_pipedrive(db)
        sync_sheets(db)
        sync_trello(db)
    finally:
        db.close()


def start():
    scheduler.add_job(
        _run_all_syncs,
        "interval",
        minutes=30,
        id="sync_all",
        replace_existing=True,
    )
    scheduler.start()


def shutdown():
    scheduler.shutdown(wait=False)
