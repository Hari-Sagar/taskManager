"""Backup export/import. Import's conflict policy (REQUIREMENTS.md,
flagged there as a recommendation to confirm): skip duplicates — a habit
is matched to an existing one by name, an entry is matched by
(habit, local_date) — rather than overwrite-by-default."""

from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.models.entry import Entry
from habit_tracker.models.habit import Habit
from habit_tracker.models.habit_schedule import HabitSchedule
from habit_tracker.models.user import User
from habit_tracker.schemas.export_import import (
    ExportEntry,
    ExportHabit,
    ExportPayload,
    ExportSchedule,
    ImportCounts,
    ImportResult,
)
from habit_tracker.services import streak as streak_service


async def export_data(session: AsyncSession, user: User) -> ExportPayload:
    habits_result = await session.execute(select(Habit).where(Habit.user_id == user.id).order_by(Habit.id))
    habits = habits_result.scalars().all()

    export_habits = []
    export_schedules = []
    export_entries = []

    for export_id, habit in enumerate(habits):
        export_habits.append(
            ExportHabit(
                export_id=export_id,
                name=habit.name,
                description=habit.description,
                unit=habit.unit,
                target_value=habit.target_value,
            )
        )

        schedules_result = await session.execute(select(HabitSchedule).where(HabitSchedule.habit_id == habit.id))
        for s in schedules_result.scalars().all():
            export_schedules.append(
                ExportSchedule(
                    habit_export_id=export_id,
                    frequency_type=s.frequency_type,
                    frequency_config=s.frequency_config,
                    effective_from=s.effective_from,
                )
            )

        entries_result = await session.execute(select(Entry).where(Entry.habit_id == habit.id))
        for e in entries_result.scalars().all():
            export_entries.append(
                ExportEntry(
                    habit_export_id=export_id,
                    local_date=e.local_date,
                    completed_at=e.completed_at,
                    status=e.status,
                    value=e.value,
                )
            )

    return ExportPayload(habits=export_habits, schedules=export_schedules, entries=export_entries)


async def import_data(session: AsyncSession, user: User, payload: ExportPayload) -> ImportResult:
    imported_habits = 0
    skipped_habits = 0
    imported_entries = 0
    skipped_entries = 0

    existing_result = await session.execute(select(Habit).where(Habit.user_id == user.id))
    existing_by_name = {h.name: h for h in existing_result.scalars().all()}

    habit_for_export_id: Dict[int, Habit] = {}

    for export_habit in payload.habits:
        existing = existing_by_name.get(export_habit.name)
        if existing is not None:
            habit_for_export_id[export_habit.export_id] = existing
            skipped_habits += 1
            continue

        habit = Habit(
            user_id=user.id,
            name=export_habit.name,
            description=export_habit.description,
            unit=export_habit.unit,
            target_value=export_habit.target_value,
        )
        session.add(habit)
        await session.flush()
        habit_for_export_id[export_habit.export_id] = habit
        existing_by_name[habit.name] = habit
        imported_habits += 1

        # Schedules only copied for newly-created habits — an existing
        # habit already has its own schedule history.
        for export_schedule in payload.schedules:
            if export_schedule.habit_export_id == export_habit.export_id:
                session.add(
                    HabitSchedule(
                        habit_id=habit.id,
                        frequency_type=export_schedule.frequency_type,
                        frequency_config=export_schedule.frequency_config,
                        effective_from=export_schedule.effective_from,
                    )
                )

    await session.flush()

    touched_habit_ids = set()
    for export_entry in payload.entries:
        habit = habit_for_export_id.get(export_entry.habit_export_id)
        if habit is None:
            continue  # orphaned reference in the payload — ignore defensively

        existing_entry = await session.execute(
            select(Entry).where(Entry.habit_id == habit.id, Entry.local_date == export_entry.local_date)
        )
        if existing_entry.scalar_one_or_none() is not None:
            skipped_entries += 1
            continue

        session.add(
            Entry(
                habit_id=habit.id,
                local_date=export_entry.local_date,
                completed_at=export_entry.completed_at,
                status=export_entry.status,
                value=export_entry.value,
            )
        )
        imported_entries += 1
        touched_habit_ids.add(habit.id)

    await session.flush()

    # One recompute() per touched habit — not a replay of apply_checkin()
    # per historical entry (ARCHITECTURE.md's Export/Import contract note).
    for habit_id in touched_habit_ids:
        habit = await session.get(Habit, habit_id)
        await streak_service.recompute(session, habit)

    await session.commit()

    return ImportResult(
        imported=ImportCounts(habits=imported_habits, entries=imported_entries),
        skipped=ImportCounts(habits=skipped_habits, entries=skipped_entries),
    )
