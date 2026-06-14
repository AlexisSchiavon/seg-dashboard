from datetime import datetime

from pydantic import BaseModel


class SyncStatus(BaseModel):
    status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    records_synced: int = 0
    error_message: str | None = None

    model_config = {"from_attributes": True}


class SyncTriggerResponse(BaseModel):
    status: str
