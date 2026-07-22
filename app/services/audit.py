"""Audit trail helper (Prompt 3, Feature 1).

log_action() writes one row to `audit_log`. It NEVER propagates an exception to
the caller: a failed audit write must not break the primary operation.

Sensitive keys (tokens, passwords) are redacted from the payload before storage.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import AuditLog

logger = logging.getLogger("app.audit")

MAX_PAYLOAD_BYTES = 10 * 1024  # 10 KB

# Canonical action types (Prompt 3 Feature 1).
ACTION_TYPES = frozenset({
    "TALENT_ASSIGNED", "TALENT_REMOVED", "SYNC_COMPLETED", "SYNC_FAILED",
    "DATA_HEALTH_ALERT", "MANUAL_UPDATE", "REPORT_GENERATED", "LOGIN", "LOGOUT",
    "TRELLO_CARD_CREATED",
})

# Keys whose values must never be persisted (compared case-insensitively).
REDACT_KEYS = frozenset({
    "api_token", "password", "hashed_password", "secret_key", "authorization",
    "token", "anthropic_api_key", "trello_token", "pipedrive_api_token",
})
_REDACTED = "[REDACTED]"


def _redact(obj):
    """Recursively replace sensitive values with [REDACTED]."""
    if isinstance(obj, dict):
        return {
            k: (_REDACTED if str(k).lower() in REDACT_KEYS else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_redact(v) for v in obj]
    return obj


def _serialize_payload(payload: dict | None) -> str | None:
    """Serialize payload to JSON, redacting secrets and truncating to 10 KB."""
    if payload is None:
        return None
    try:
        text = json.dumps(_redact(payload), default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        text = json.dumps({"_unserializable": str(payload)[:500]})
    if len(text.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        # Keep it valid JSON: store a truncated preview under a marker.
        preview = text[: MAX_PAYLOAD_BYTES - 200]
        text = json.dumps({"_truncated": True, "preview": preview}, ensure_ascii=False)
    return text


def log_action(
    action_type: str,
    actor: str = "system",
    entity_type: str | None = None,
    entity_id=None,
    payload: dict | None = None,
    notes: str | None = None,
    db: Session | None = None,
) -> None:
    """Record an audit entry. Never raises.

    If `db` is provided, the row is written inside a SAVEPOINT on that session so a
    failure rolls back only the audit insert (never the caller's transaction). If
    `db` is None, a short-lived session is opened and committed independently
    (used by background jobs where there is no ambient session).
    """
    if action_type not in ACTION_TYPES:
        logger.warning("audit: unknown action_type=%r (recorded anyway)", action_type)
    entry_kwargs = dict(
        action_type=action_type,
        actor=actor,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        payload_json=_serialize_payload(payload),
        notes=notes,
    )
    try:
        if db is not None:
            with db.begin_nested():  # SAVEPOINT — isolates a failure
                db.add(AuditLog(**entry_kwargs))
        else:
            own = SessionLocal()
            try:
                own.add(AuditLog(**entry_kwargs))
                own.commit()
            finally:
                own.close()
    except Exception:  # noqa: BLE001 — audit must never break the caller
        logger.exception("audit log_action failed (action_type=%s)", action_type)


def list_logs(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id=None,
    action_type: str | None = None,
    actor: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    cursor: int = 0,
) -> tuple[list[AuditLog], int, int | None]:
    """Return (rows, total, next_cursor) filtered and paginated, newest first."""
    limit = max(1, min(int(limit), 200))
    cursor = max(0, int(cursor))
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.filter(AuditLog.entity_id == str(entity_id))
    if action_type:
        q = q.filter(AuditLog.action_type == action_type)
    if actor:
        q = q.filter(AuditLog.actor == actor)
    if since is not None:
        q = q.filter(AuditLog.timestamp >= since)
    if until is not None:
        q = q.filter(AuditLog.timestamp <= until)
    total = q.count()
    rows = (
        q.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .offset(cursor)
        .limit(limit)
        .all()
    )
    consumed = cursor + len(rows)
    next_cursor = consumed if consumed < total else None
    return rows, total, next_cursor


# Action types that must NEVER be purged: they are durable facts other logic
# depends on. TRELLO_CARD_CREATED is the idempotency source of truth for Trello
# auto-create — purging it would let the system recreate a card a user deleted.
NON_PURGEABLE_ACTION_TYPES = frozenset({"TRELLO_CARD_CREATED"})


def purge_old_logs(db: Session | None = None) -> int:
    """Delete audit rows older than AUDIT_LOG_RETENTION_DAYS (default 90),
    EXCEPT durable-fact action types (NON_PURGEABLE_ACTION_TYPES).

    Returns the number of rows deleted. Safe to call from a scheduled job.
    """
    days = getattr(settings, "AUDIT_LOG_RETENTION_DAYS", 90) or 90
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    close_after = db is None
    db = db or SessionLocal()
    try:
        result = db.execute(
            delete(AuditLog).where(
                AuditLog.timestamp < cutoff,
                AuditLog.action_type.notin_(NON_PURGEABLE_ACTION_TYPES),
            )
        )
        db.commit()
        return result.rowcount or 0
    finally:
        if close_after:
            db.close()
