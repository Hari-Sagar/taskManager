from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from habit_tracker.models.user import User


async def test_migration_creates_users_table_with_unique_email(migrated_db):
    """PLAN.md item 3 acceptance: the migration creates `users` with a
    unique constraint on `email` (not just the ORM model — the applied
    migration's actual schema)."""
    engine: AsyncEngine = create_async_engine(migrated_db)

    def _inspect(sync_conn):
        inspector = inspect(sync_conn)
        columns = {c["name"] for c in inspector.get_columns("users")}
        indexes = inspector.get_indexes("users")
        return columns, indexes

    async with engine.connect() as conn:
        columns, indexes = await conn.run_sync(_inspect)
    await engine.dispose()

    assert columns == {
        "id",
        "email",
        "hashed_password",
        "timezone",
        "day_start_hour",
        "created_at",
    }

    email_indexes = [ix for ix in indexes if ix["column_names"] == ["email"]]
    assert email_indexes, "expected an index on email"
    assert bool(email_indexes[0]["unique"])


async def test_duplicate_email_raises_integrity_error(db_session):
    """PLAN.md item 3 acceptance: inserting two users with the same email
    raises an integrity error."""
    db_session.add(
        User(email="a@example.com", hashed_password="x", timezone="UTC", day_start_hour=0)
    )
    await db_session.commit()

    db_session.add(
        User(email="a@example.com", hashed_password="y", timezone="UTC", day_start_hour=0)
    )
    try:
        await db_session.commit()
        assert False, "expected an IntegrityError on duplicate email"
    except IntegrityError:
        await db_session.rollback()


async def test_habit_creation_with_only_required_fields(db_session):
    """Sanity check on the model itself: only email/hashed_password are
    required; timezone/day_start_hour take their declared defaults."""
    user = User(email="b@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.timezone == "UTC"
    assert user.day_start_hour == 0
    assert user.created_at is not None
