from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip even for a `DateTime(timezone=True)`
    column, so a value written as UTC-aware comes back naive. Every value we
    write is UTC, so re-attach that offset rather than compare a naive value
    against an aware `datetime.now(timezone.utc)` (which raises TypeError)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class Base(DeclarativeBase):
    """Shared declarative base — Alembic's target_metadata points here."""


class IDMixin:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
