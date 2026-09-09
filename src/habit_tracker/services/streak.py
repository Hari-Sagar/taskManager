"""The running-counter streak engine — see ARCHITECTURE.md "Streak design".

recompute() is the ground truth: it walks a habit's Entry rows against its
HabitSchedule history from scratch and is always correct. apply_checkin()
is a fast-path optimization layered on top for the common case (checking
in for the very next expected period); anything it can't handle cheaply
and safely falls through to recompute() — so there is exactly one place
streak logic can be wrong, not two algorithms that can drift apart.
"""

from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.models.entry import Entry, EntryStatus
from habit_tracker.models.habit import Habit
from habit_tracker.models.habit_schedule import FrequencyType, HabitSchedule
from habit_tracker.models.user import User
from habit_tracker.services.schedule import is_due_on, local_today, period_key


async def _load_schedules(session: AsyncSession, habit_id: int) -> List[HabitSchedule]:
    result = await session.execute(
        select(HabitSchedule)
        .where(HabitSchedule.habit_id == habit_id)
        .order_by(HabitSchedule.effective_from, HabitSchedule.id)
    )
    return list(result.scalars().all())


def _resolve_schedule_for_date(schedules: List[HabitSchedule], on_date: date) -> Optional[HabitSchedule]:
    """In-memory equivalent of services.schedule.active_schedule_as_of,
    for use when the whole schedule history is already loaded — same
    effective_from/id tie-break."""
    candidates = [s for s in schedules if s.effective_from <= on_date]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (s.effective_from, s.id))


def _qualifies(habit: Habit, entry: Entry) -> bool:
    """A DONE entry counts toward the streak; for quantifiable habits it
    must also meet the target (PLAN.md Phase 7) — partial progress is
    stored but earns no streak credit."""
    if entry.status != EntryStatus.DONE:
        return False
    if habit.target_value is None:
        return True
    return entry.value is not None and entry.value >= habit.target_value


async def _load_qualifying_entries(session: AsyncSession, habit: Habit) -> List[Entry]:
    result = await session.execute(
        select(Entry).where(Entry.habit_id == habit.id).order_by(Entry.local_date)
    )
    return [e for e in result.scalars().all() if _qualifies(habit, e)]


async def _count_qualifying_in_period(session: AsyncSession, habit: Habit, period_start: date) -> int:
    week_end = period_start + timedelta(days=6)
    result = await session.execute(
        select(Entry).where(
            Entry.habit_id == habit.id,
            Entry.local_date >= period_start,
            Entry.local_date <= week_end,
        )
    )
    return sum(1 for e in result.scalars().all() if _qualifies(habit, e))


async def recompute(session: AsyncSession, habit: Habit) -> None:
    """Overwrites current_streak/longest_streak/streak_last_counted_period_start
    on `habit` from scratch. Bounded to this one habit — not a whole-table
    scan. Does not commit; the caller controls the transaction."""
    schedules = await _load_schedules(session, habit.id)
    if not schedules:
        habit.current_streak = 0
        habit.longest_streak = 0
        habit.streak_last_counted_period_start = None
        return

    user = await session.get(User, habit.user_id)
    qualifying_entries = await _load_qualifying_entries(session, habit)
    qualifying_dates = {e.local_date for e in qualifying_entries}

    period_counts: dict = {}
    for e in qualifying_entries:
        s = _resolve_schedule_for_date(schedules, e.local_date)
        if s is not None and s.frequency_type == FrequencyType.TIMES_PER_WEEK:
            key = period_key(s, e.local_date)
            period_counts[key] = period_counts.get(key, 0) + 1

    earliest = min(s.effective_from for s in schedules)
    today = local_today(user)

    # Walk every day from the habit's start to today, collapsing into the
    # ordered list of distinct *periods* that were actually due, each
    # tagged with whether it was satisfied.
    ordered_periods: List[tuple] = []
    seen = set()
    day = earliest
    while day <= today:
        schedule = _resolve_schedule_for_date(schedules, day)
        if schedule is not None and is_due_on(schedule, day):
            key = period_key(schedule, day)
            if key not in seen:
                seen.add(key)
                if schedule.frequency_type == FrequencyType.TIMES_PER_WEEK:
                    target = schedule.frequency_config.get("target", 1)
                    satisfied = period_counts.get(key, 0) >= target
                else:
                    satisfied = key in qualifying_dates
                ordered_periods.append((key, satisfied))
        day += timedelta(days=1)

    longest = 0
    run = 0
    for _, satisfied in ordered_periods:
        if satisfied:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    current = 0
    last_counted = None
    n = len(ordered_periods)
    for i in range(n - 1, -1, -1):
        key, satisfied = ordered_periods[i]
        if satisfied:
            current += 1
            if last_counted is None:
                last_counted = key
        elif i == n - 1:
            continue  # today/this week isn't over yet — not a break
        else:
            break

    habit.current_streak = current
    habit.longest_streak = max(longest, current)
    habit.streak_last_counted_period_start = last_counted


def _expected_next_period(
    schedule: HabitSchedule, schedules: List[HabitSchedule], last_counted: date
) -> Optional[date]:
    """The period immediately after `last_counted`, under `schedule` — but
    only if `schedule` is the same schedule that was active when
    last_counted was set. If the schedule changed since, returns None so
    the caller falls back to recompute() rather than guessing at
    mismatched period semantics (e.g. daily -> times_per_week)."""
    last_counted_schedule = _resolve_schedule_for_date(schedules, last_counted)
    if last_counted_schedule is None or last_counted_schedule.id != schedule.id:
        return None

    if schedule.frequency_type == FrequencyType.TIMES_PER_WEEK:
        return last_counted + timedelta(days=7)

    day = last_counted + timedelta(days=1)
    bound = last_counted + timedelta(days=400)
    while day <= bound:
        if is_due_on(schedule, day):
            return day
        day += timedelta(days=1)
    return None


async def apply_checkin(session: AsyncSession, habit: Habit, entry: Entry) -> None:
    """Called when a new DONE entry is created. Tries an O(1) increment
    for the common case; anything else (first-ever entry, a gap, a
    backfill, a schedule change, or a times_per_week period that isn't
    newly satisfied) is handled by recompute() or is a safe no-op."""
    if not _qualifies(habit, entry):
        return

    schedules = await _load_schedules(session, habit.id)
    schedule = _resolve_schedule_for_date(schedules, entry.local_date)
    if schedule is None or not is_due_on(schedule, entry.local_date):
        return  # doesn't correspond to any counted period

    period = period_key(schedule, entry.local_date)

    if schedule.frequency_type == FrequencyType.TIMES_PER_WEEK:
        target = schedule.frequency_config.get("target", 1)
        count = await _count_qualifying_in_period(session, habit, period)
        if count != target:
            # Not yet at target (no-op) or already past it (already
            # counted by an earlier check-in this period) — either way,
            # the counters are already correct as they stand.
            return

    if habit.streak_last_counted_period_start is not None and period == _expected_next_period(
        schedule, schedules, habit.streak_last_counted_period_start
    ):
        habit.current_streak += 1
        habit.longest_streak = max(habit.longest_streak, habit.current_streak)
        habit.streak_last_counted_period_start = period
    else:
        await recompute(session, habit)


async def reconcile(session: AsyncSession, habit: Habit) -> None:
    """Used by the nightly job (PLAN.md Phase 8) and safe to call anytime:
    archived habits are frozen — see ARCHITECTURE.md — so their streak is
    left untouched rather than recomputed."""
    if habit.archived_at is not None:
        return
    await recompute(session, habit)
