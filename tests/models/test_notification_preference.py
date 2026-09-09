import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from habit_tracker.models.notification_preference import NotificationPreference
from habit_tracker.models.user import User


async def test_notification_preference_is_one_to_one_with_user(db_session):
    """PLAN.md item 8 acceptance: table is one-to-one with users via
    user_id as PK/FK."""
    user = User(email="notify@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    user_id = user.id  # captured before rollback expires `user`'s attributes below

    pref = NotificationPreference(user_id=user_id, enabled=True)
    db_session.add(pref)
    await db_session.commit()

    # A second row for the same user_id is a PK collision, not a distinct
    # row — insert via Core (not the ORM session) to avoid the identity
    # map merging the two in-memory objects before that constraint is
    # even reached.
    with pytest.raises(IntegrityError):
        await db_session.execute(
            insert(NotificationPreference).values(user_id=user_id, enabled=False)
        )
        await db_session.commit()
    await db_session.rollback()

    result = await db_session.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    assert result.scalar_one().enabled is True
