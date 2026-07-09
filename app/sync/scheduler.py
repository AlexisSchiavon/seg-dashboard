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

    Prompt 3 Feature 1: emits a SYNC_COMPLETED / SYNC_FAILED audit entry per
    source (read from the returned SyncLog). Auditing never breaks the sync.
    """
    from app.services.audit import log_action

    db = SessionLocal()
    try:
        for source, fn in (
            ("pipedrive", sync_pipedrive),
            ("sheets", sync_sheets),
            ("trello", sync_trello),
        ):
            try:
                log = fn(db)
                status = getattr(log, "status", "unknown")
                if status == "success":
                    log_action(
                        "SYNC_COMPLETED", actor="sync", entity_type="system",
                        entity_id=source,
                        payload={"source": source,
                                 "records_synced": getattr(log, "records_synced", None)},
                    )
                else:
                    log_action(
                        "SYNC_FAILED", actor="sync", entity_type="system", entity_id=source,
                        payload={"source": source, "status": status,
                                 "error": getattr(log, "error_message", None)},
                    )
            except Exception as exc:  # noqa: BLE001 — one source must not stop the rest
                log_action(
                    "SYNC_FAILED", actor="sync", entity_type="system", entity_id=source,
                    payload={"source": source, "exception": str(exc)},
                )
    finally:
        db.close()


def _purge_audit_logs():
    """Weekly cleanup of audit rows older than the retention window."""
    from app.services.audit import purge_old_logs
    purge_old_logs()


def _run_health_snapshots():
    """Hourly data-health checks + snapshot (emits DATA_HEALTH_ALERT on growth)."""
    from app.services.health_checks import save_snapshots
    db = SessionLocal()
    try:
        save_snapshots(db)
    except Exception:  # noqa: BLE001 — health snapshots must never crash the scheduler
        pass
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
    # Prompt 3 Feature 1 — weekly audit-log retention cleanup.
    scheduler.add_job(
        _purge_audit_logs,
        "interval",
        weeks=1,
        id="audit_purge",
        replace_existing=True,
    )
    # Prompt 3 Feature 2 — hourly data-health snapshots.
    scheduler.add_job(
        _run_health_snapshots,
        "interval",
        minutes=60,
        id="health_snapshots",
        replace_existing=True,
    )
    scheduler.start()


def shutdown():
    scheduler.shutdown(wait=False)
