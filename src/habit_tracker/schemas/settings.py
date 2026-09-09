from datetime import time
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, field_validator


class NotificationSettings(BaseModel):
    enabled: bool
    remind_local_time: Optional[time] = None


class NotificationUpdate(BaseModel):
    enabled: Optional[bool] = None
    remind_local_time: Optional[time] = None


class SettingsResponse(BaseModel):
    timezone: str
    day_start_hour: int
    notifications: NotificationSettings


class SettingsUpdate(BaseModel):
    timezone: Optional[str] = None
    day_start_hour: Optional[int] = None
    notifications: Optional[NotificationUpdate] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError(f"unknown timezone: {value!r}")
        return value
