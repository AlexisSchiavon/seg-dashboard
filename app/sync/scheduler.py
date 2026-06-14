"""Hourly sync job for Pipedrive and Google Sheets, scheduled via APScheduler
and wired into app/main.py's lifespan (start on app startup, shutdown on app shutdown).
"""
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.sync.jobs import sync_pipedrive, sync_sheets

scheduler = BackgroundScheduler()


def _run_all_syncs():
    """Run Pipedrive then Sheets syncs sequentially.

    Each sync writes its own SyncLog(source=...) row independently.
    If Pipedrive fails, Sheets is still attempted — each has its own try/except.
    """
    db = SessionLocal()
    try:
        sync_pipedrive(db)
        sync_sheets(db)
    finally:
        db.close()


def start():
    scheduler.add_job(
        _run_all_syncs,
        "interval",
        hours=1,
        id="sync_all",
        replace_existing=True,
    )
    scheduler.start()


def shutdown():
    scheduler.shutdown(wait=False)
