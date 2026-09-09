from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel

from habit_tracker.models.entry import EntryStatus
from habit_tracker.models.habit_schedule import FrequencyType


class ExportHabit(BaseModel):
    export_id: int  # index within this export payload; schedules/entries reference it below
    name: str
    description: Optional[str] = None
    unit: Optional[str] = None
    target_value: Optional[float] = None
    # Deliberately no current_streak/longest_streak — those are derived
    # state, re-established by recompute() on import, not raw values that
    # get copied across (ARCHITECTURE.md).


class ExportSchedule(BaseModel):
    habit_export_id: int
    frequency_type: FrequencyType
    frequency_config: dict
    effective_from: date


class ExportEntry(BaseModel):
    habit_export_id: int
    local_date: date
    completed_at: datetime
    status: EntryStatus
    value: Optional[float] = None


class ExportPayload(BaseModel):
    habits: List[ExportHabit]
    schedules: List[ExportSchedule]
    entries: List[ExportEntry]


class ImportCounts(BaseModel):
    habits: int
    entries: int


class ImportResult(BaseModel):
    imported: ImportCounts
    skipped: ImportCounts
