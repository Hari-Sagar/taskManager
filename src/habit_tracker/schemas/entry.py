from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from habit_tracker.models.entry import EntryStatus


class EntryCreate(BaseModel):
    local_date: Optional[date] = None
    status: EntryStatus
    value: Optional[float] = None


class EntryUpdate(BaseModel):
    status: Optional[EntryStatus] = None
    value: Optional[float] = None


class EntryResponse(BaseModel):
    id: int
    habit_id: int
    local_date: date
    completed_at: datetime
    status: EntryStatus
    value: Optional[float]
    edited_at: Optional[datetime]

    model_config = {"from_attributes": True}
