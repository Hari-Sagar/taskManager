from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from habit_tracker.db.base import Base, CreatedAtMixin, IDMixin


class Habit(IDMixin, CreatedAtMixin, Base):
    __tablename__ = "habits"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_value: Mapped[Optional[float]] = mapped_column(Numeric(asdecimal=False), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Streak cache — see ARCHITECTURE.md "Streak design". Never written to
    # directly outside services/streak.py.
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak_last_counted_period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
