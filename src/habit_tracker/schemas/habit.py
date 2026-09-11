from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from habit_tracker.models.habit_schedule import FrequencyType

_FREQUENCY_CONFIG_DESCRIPTION = (
    "Shape depends on frequency_type: `{}` for daily; "
    '`{"days": [0-6]}` (0=Monday) for weekly_days; '
    '`{"target": N}` for times_per_week.'
)


class HabitCreate(BaseModel):
    name: str
    description: Optional[str] = None
    unit: Optional[str] = None
    target_value: Optional[float] = None
    frequency_type: FrequencyType
    frequency_config: dict = Field(
        examples=[{}, {"days": [0, 2, 4]}, {"target": 3}],
        description=_FREQUENCY_CONFIG_DESCRIPTION,
    )


class HabitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    target_value: Optional[float] = None
    frequency_type: Optional[FrequencyType] = None
    frequency_config: Optional[dict] = Field(
        default=None,
        examples=[{}, {"days": [0, 2, 4]}, {"target": 3}],
        description=_FREQUENCY_CONFIG_DESCRIPTION + " Must be provided together with frequency_type.",
    )

    @model_validator(mode="after")
    def frequency_fields_come_together(self):
        has_type = self.frequency_type is not None
        has_config = self.frequency_config is not None
        if has_type != has_config:
            raise ValueError("frequency_type and frequency_config must be provided together")
        return self


class HabitStats(BaseModel):
    current_streak: int
    longest_streak: int


class HabitResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    unit: Optional[str]
    target_value: Optional[float]
    current_streak: int
    longest_streak: int
    archived_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
