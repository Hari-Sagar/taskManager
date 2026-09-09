import pytest
from sqlalchemy import select

from habit_tracker.models.entry import Entry
from habit_tracker.models.habit import Habit
from habit_tracker.services import entries as entries_service


async def test_forced_failure_between_insert_and_counter_update_rolls_back_both(
    client, register_and_login, db_session, monkeypatch
):
    """PLAN.md Phase 5 item 4 acceptance: a forced failure between the
    entry insert and the counter update leaves neither persisted."""

    async def boom(session, habit, entry):
        raise RuntimeError("simulated failure between insert and counter update")

    monkeypatch.setattr(entries_service.streak_service, "apply_checkin", boom)

    headers = await register_and_login("transaction-test@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Gym", "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]

    with pytest.raises(RuntimeError):
        await client.post(f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"status": "done"})

    # Neither the entry nor any counter change should have persisted —
    # verified via a separate connection to the same underlying DB file.
    result = await db_session.execute(select(Entry).where(Entry.habit_id == habit_id))
    assert result.scalars().all() == []

    habit_result = await db_session.execute(select(Habit).where(Habit.id == habit_id))
    habit = habit_result.scalar_one()
    assert habit.current_streak == 0
    assert habit.longest_streak == 0
