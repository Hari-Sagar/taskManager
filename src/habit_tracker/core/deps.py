from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.core.security import InvalidTokenError, decode_access_token
from habit_tracker.db.session import get_db
from habit_tracker.models.user import User

# HTTPBearer (not OAuth2PasswordBearer) — this API's login takes JSON, not
# the OAuth2 password-flow form OAuth2PasswordBearer implies, and that
# mismatch made Swagger UI's "Authorize" dialog show a username/password/
# client-id form that doesn't actually work against this login endpoint.
# HTTPBearer gives a plain "paste your token" box instead.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_error

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise credentials_error

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_error

    user = await session.get(User, int(user_id))
    if user is None:
        raise credentials_error

    return user
