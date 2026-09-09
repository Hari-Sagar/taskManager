from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.core.deps import get_current_user
from habit_tracker.core.rate_limit import limiter
from habit_tracker.db.session import get_db
from habit_tracker.models.user import User
from habit_tracker.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
    UserResponse,
)
from habit_tracker.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.register_user(session, body.email, body.password)
    except auth_service.EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return user


@router.post("/login", response_model=TokenPairResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, session: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.authenticate_user(session, body.email, body.password)
    except auth_service.InvalidCredentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    access_token, refresh_token = await auth_service.issue_token_pair(session, user)
    return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_db)):
    try:
        access_token, refresh_token = await auth_service.refresh_token_pair(session, body.refresh_token)
    except auth_service.InvalidRefreshToken:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, session: AsyncSession = Depends(get_db)):
    try:
        await auth_service.revoke_refresh_token(session, body.refresh_token)
    except auth_service.InvalidRefreshToken:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Protected placeholder route — proves get_current_user works end to
    end (PLAN.md Phase 2 item 4)."""
    return current_user
