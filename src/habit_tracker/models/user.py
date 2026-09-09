from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from habit_tracker.db.base import Base, CreatedAtMixin, IDMixin


class User(IDMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="UTC")
    day_start_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
