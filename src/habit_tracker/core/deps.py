from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.core.security import InvalidTokenError, decode_access_token
from habit_tracker.db.session import get_db
from habit_tracker.models.user import User

# tokenUrl is only used to populate OpenAPI docs — login isn't form-encoded.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error

    try:
        payload = decode_access_token(token)
    except InvalidTokenError:
        raise credentials_error

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_error

    user = await session.get(User, int(user_id))
    if user is None:
        raise credentials_error

    return user
