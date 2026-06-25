from datetime import datetime, timezone

from pydantic import BaseModel, field_serializer


class SyncStatus(BaseModel):
    status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    records_synced: int = 0
    error_message: str | None = None

    model_config = {"from_attributes": True}

    @field_serializer("started_at", "finished_at")
    def _serialize_utc(self, value: datetime | None) -> str | None:
        """5.5.2: emit timestamps as UTC with an explicit offset.

        Sync timestamps are written as UTC but SQLite stores them naive (no tz),
        so they come back without an offset. Serialized that way, the frontend's
        `new Date(...)` parses them as LOCAL time → in production (server UTC,
        client CST) the value looks ~6h in the future → "hace 0 min" forever.
        Assuming naive = UTC and appending the offset fixes the client delta.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


class SyncTriggerResponse(BaseModel):
    status: str
