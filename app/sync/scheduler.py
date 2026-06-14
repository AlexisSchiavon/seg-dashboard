"""Hourly Pipedrive sync, scheduled via APScheduler and wired into
app/main.py's lifespan (start on app startup, shutdown on app shutdown).
"""
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.sync.jobs import sync_pipedrive

scheduler = BackgroundScheduler()


def _run_pipedrive_sync():
    db = SessionLocal()
    try:
        sync_pipedrive(db)
    finally:
        db.close()


def start():
    scheduler.add_job(
        _run_pipedrive_sync,
        "interval",
        hours=1,
        id="sync_pipedrive",
        replace_existing=True,
    )
    scheduler.start()


def shutdown():
    scheduler.shutdown(wait=False)
