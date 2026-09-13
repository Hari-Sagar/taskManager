from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.core.deps import get_current_user
from habit_tracker.db.session import get_db
from habit_tracker.models.user import User
from habit_tracker.schemas.habit import HabitCreate, HabitResponse, HabitStats, HabitUpdate
from habit_tracker.services import habits as habits_service

router = APIRouter(prefix="/habits", tags=["Habits"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")


@router.post("", response_model=HabitResponse, status_code=status.HTTP_201_CREATED)
async def create_habit(
    body: HabitCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Create a habit with its initial schedule (daily, specific weekdays,
    or N times per week). Starts at a streak of 0."""
    return await habits_service.create_habit(session, current_user, body)


@router.get("", response_model=list[HabitResponse])
async def list_habits(
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List your habits. Archived (soft-deleted) ones are excluded unless
    `include_archived=true`."""
    return await habits_service.list_habits(session, current_user, include_archived)


@router.get("/{habit_id}", response_model=HabitResponse)
async def get_habit(
    habit_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Fetch a single habit, including its current/longest streak."""
    try:
        return await habits_service.get_owned_habit(session, current_user, habit_id)
    except habits_service.HabitNotFound:
        raise _not_found()


@router.get("/{habit_id}/stats", response_model=HabitStats)
async def get_habit_stats(
    habit_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Just the streak numbers, if you don't need the rest of the habit."""
    try:
        habit = await habits_service.get_owned_habit(session, current_user, habit_id)
    except habits_service.HabitNotFound:
        raise _not_found()
    return HabitStats(current_streak=habit.current_streak, longest_streak=habit.longest_streak)


@router.patch("/{habit_id}", response_model=HabitResponse)
async def update_habit(
    habit_id: int,
    body: HabitUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Update a habit's name/description/target, or change its schedule.
    A frequency change doesn't rewrite history — it takes effect from
    today onward, so past streak calculations stay correct."""
    try:
        return await habits_service.update_habit(session, current_user, habit_id, body)
    except habits_service.HabitNotFound:
        raise _not_found()


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_habit(
    habit_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Archive a habit (soft delete). Its streak freezes and it drops out
    of the default habit list, but its history is kept — see `restore`."""
    try:
        await habits_service.archive_habit(session, current_user, habit_id)
    except habits_service.HabitNotFound:
        raise _not_found()


@router.post("/{habit_id}/restore", response_model=HabitResponse)
async def restore_habit(
    habit_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Undo archiving a habit — it reappears in your habit list."""
    try:
        return await habits_service.restore_habit(session, current_user, habit_id)
    except habits_service.HabitNotFound:
        raise _not_found()
