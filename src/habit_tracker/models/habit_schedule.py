import enum
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from habit_tracker.db.base import Base, IDMixin


class FrequencyType(str, enum.Enum):
    DAILY = "daily"
    WEEKLY_DAYS = "weekly_days"
    TIMES_PER_WEEK = "times_per_week"


class HabitSchedule(IDMixin, Base):
    __tablename__ = "habit_schedules"

    habit_id: Mapped[int] = mapped_column(Integer, ForeignKey("habits.id"), nullable=False, index=True)
    frequency_type: Mapped[FrequencyType] = mapped_column(Enum(FrequencyType), nullable=False)
    frequency_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
