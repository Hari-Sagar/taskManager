import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from habit_tracker.db.base import Base, CreatedAtMixin, IDMixin


class EntryStatus(str, enum.Enum):
    DONE = "done"
    SKIPPED = "skipped"


class Entry(IDMixin, CreatedAtMixin, Base):
    __tablename__ = "entries"
    __table_args__ = (UniqueConstraint("habit_id", "local_date", name="uq_entries_habit_local_date"),)

    habit_id: Mapped[int] = mapped_column(Integer, ForeignKey("habits.id"), nullable=False, index=True)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[EntryStatus] = mapped_column(Enum(EntryStatus), nullable=False)
    value: Mapped[Optional[float]] = mapped_column(Numeric(asdecimal=False), nullable=True)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
