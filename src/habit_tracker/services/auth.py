from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.core.config import settings
from habit_tracker.db.base import as_aware_utc
from habit_tracker.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from habit_tracker.models.refresh_token import RefreshToken
from habit_tracker.models.user import User


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class InvalidRefreshToken(Exception):
    pass


async def register_user(session: AsyncSession, email: str, password: str) -> User:
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyRegistered(email)

    user = User(email=email, hashed_password=hash_password(password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentials()
    return user


async def issue_token_pair(session: AsyncSession, user: User) -> tuple[str, str]:
    access_token = create_access_token(subject=str(user.id))

    raw_refresh_token, token_hash = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    session.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    await session.commit()

    return access_token, raw_refresh_token


async def _get_active_refresh_token(session: AsyncSession, raw_refresh_token: str) -> RefreshToken:
    token_hash = hash_refresh_token(raw_refresh_token)
    result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    token = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if token is None or token.revoked_at is not None or as_aware_utc(token.expires_at) < now:
        raise InvalidRefreshToken()
    return token


async def refresh_token_pair(session: AsyncSession, raw_refresh_token: str) -> tuple[str, str]:
    """Validates raw_refresh_token, revokes it, and issues a new pair
    (rotation) — per ARCHITECTURE.md's token-rotation decision."""
    token = await _get_active_refresh_token(session, raw_refresh_token)
    user = await session.get(User, token.user_id)

    token.revoked_at = datetime.now(timezone.utc)
    await session.commit()

    return await issue_token_pair(session, user)


async def revoke_refresh_token(session: AsyncSession, raw_refresh_token: str) -> None:
    token = await _get_active_refresh_token(session, raw_refresh_token)
    token.revoked_at = datetime.now(timezone.utc)
    await session.commit()
