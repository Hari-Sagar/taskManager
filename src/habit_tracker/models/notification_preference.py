from datetime import date, time
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column

from habit_tracker.db.base import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remind_local_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    last_sent_local_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
