from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from habit_tracker.models.refresh_token import RefreshToken
from habit_tracker.models.user import User


async def test_refresh_token_fk_and_query_by_user_id(db_session):
    """PLAN.md item 4 acceptance: table has an FK to users; inserting a
    token row and querying by user_id works."""
    user = User(email="rt@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = RefreshToken(
        user_id=user.id,
        token_hash="hash123",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db_session.add(token)
    await db_session.commit()

    result = await db_session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
    fetched = result.scalar_one()
    assert fetched.token_hash == "hash123"
    assert fetched.revoked_at is None
