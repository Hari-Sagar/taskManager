from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.core.deps import get_current_user
from habit_tracker.core.rate_limit import limiter
from habit_tracker.db.session import get_db
from habit_tracker.models.user import User
from habit_tracker.schemas.entry import EntryCreate, EntryResponse, EntryUpdate
from habit_tracker.services import entries as entries_service
from habit_tracker.services import habits as habits_service

router = APIRouter(prefix="/habits/{habit_id}/entries", tags=["entries"])


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.post("", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_entry(
    request: Request,
    habit_id: int,
    body: EntryCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Check in for a habit — defaults to today if `local_date` is
    omitted, or backfill a past date. One entry per habit per day; use
    PATCH to change an existing one instead of creating a duplicate."""
    try:
        return await entries_service.create_entry(session, current_user, habit_id, body)
    except habits_service.HabitNotFound:
        raise _not_found("Habit not found")
    except entries_service.DuplicateEntry:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An entry already exists for this habit and date — use PATCH to change it",
        )


@router.patch("/{local_date}", response_model=EntryResponse)
async def update_entry(
    habit_id: int,
    local_date: date,
    body: EntryUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Correct a past check-in (e.g. mark it skipped instead of done, or
    fix a logged value). Recalculates the habit's streak."""
    try:
        return await entries_service.update_entry(session, current_user, habit_id, local_date, body)
    except habits_service.HabitNotFound:
        raise _not_found("Habit not found")
    except entries_service.EntryNotFound:
        raise _not_found("Entry not found")


@router.delete("/{local_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    habit_id: int,
    local_date: date,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Undo a check-in for a given date. Recalculates the habit's streak."""
    try:
        await entries_service.delete_entry(session, current_user, habit_id, local_date)
    except habits_service.HabitNotFound:
        raise _not_found("Habit not found")
    except entries_service.EntryNotFound:
        raise _not_found("Entry not found")
