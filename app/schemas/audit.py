"""Pydantic schemas for the audit log endpoints (Prompt 3, Feature 1)."""
import json
from datetime import datetime

from pydantic import BaseModel


class AuditLogRow(BaseModel):
    id: int
    timestamp: datetime
    actor: str
    action_type: str
    entity_type: str | None = None
    entity_id: str | None = None
    payload: dict | None = None
    notes: str | None = None

    @classmethod
    def from_orm_row(cls, row) -> "AuditLogRow":
        payload = None
        if row.payload_json:
            try:
                payload = json.loads(row.payload_json)
            except (ValueError, TypeError):
                payload = {"_raw": row.payload_json}
        return cls(
            id=row.id,
            timestamp=row.timestamp,
            actor=row.actor,
            action_type=row.action_type,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            payload=payload,
            notes=row.notes,
        )


class AuditLogPage(BaseModel):
    items: list[AuditLogRow]
    total: int
    next_cursor: int | None = None
