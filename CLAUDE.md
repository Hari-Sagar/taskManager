# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

habit-tracker: a FastAPI-based habit tracking API. Full product/data-model
spec (scope decisions, data model, API surface, edge cases) lives in
`REQUIREMENTS.md`; component layout, finalized data model, API contract,
and the streak-calculation design (running counters, updated
transactionally on check-in) live in `ARCHITECTURE.md`; the ordered,
testable-increment build checklist lives in `PLAN.md` — read all three
before touching models or endpoints.

**`PLAN.md` is fully implemented** (all 12 phases / 38 items checked off) —
it's now a record of what was built and why, not a to-do list. New work
should still follow its test-first, small-increment style, but there's
nothing left to "work through in order."

## Directory layout

- `src/habit_tracker/` — application package (src layout)
  - `main.py` — FastAPI app instance; CORS + slowapi rate-limit middleware wired here
  - `api/v1/` — route handlers only (auth, habits, entries, today, settings, export_import) — no business logic
  - `core/` — `config.py` (pydantic-settings), `security.py` (password hashing + JWT), `deps.py` (`get_current_user`), `rate_limit.py`
  - `db/` — SQLAlchemy declarative base (`base.py`, incl. `as_aware_utc()` — see Testing notes) and async engine/session (`session.py`)
  - `models/` — SQLAlchemy ORM models, one module per table (`user`, `refresh_token`, `habit`, `habit_schedule`, `entry`, `notification_preference`)
  - `schemas/` — Pydantic request/response models
  - `services/` — the actual domain logic, framework-agnostic and what tests target directly:
    - `streak.py` — the running-counter engine: `recompute()` (ground truth), `apply_checkin()` (fast path + fallback), `reconcile()` (archived-habit-aware, used by the nightly job)
    - `schedule.py` — `local_today()`, `is_due_on()`, `period_key()`, `active_schedule_as_of()`
    - `auth.py`, `habits.py`, `entries.py`, `today.py`, `settings.py`, `notifications.py`, `export_import.py`
  - `jobs/scheduler.py` — `run_nightly_reconciliation()`, `run_notification_sweep()`, and the APScheduler wiring (`create_scheduler()`)
- `alembic/` — migrations; `env.py` is wired to `Base.metadata` and to
  `core.config.settings.database_url` (overridable — see Testing notes)
- `tests/` — mirrors the package layout (`models/`, `services/`, `api/`, `jobs/`, `core/`)
- `Dockerfile`, `docker-compose.yml`, `.env.example` — self-hosting via Docker, SQLite on a named volume (verified end-to-end, see `PLAN.md` Phase 12)
- `pyproject.toml` — project metadata and dependencies (hatchling build backend)

Style/lint rules have not been chosen yet.

## Environment

Only Python 3.9.6 is available in this environment (no pyenv/Homebrew/uv
to get 3.11+); `requires-python` was lowered from the original 3.11 target
to `>=3.9` to match. Revisit if a newer interpreter becomes available —
nothing implemented so far depends on 3.9 specifically.

A `.venv/` (gitignored) holds the project + dev dependencies:
```
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Commands

- Run tests: `.venv/bin/pytest` (pytest + pytest-asyncio, `asyncio_mode = auto` — see `pyproject.toml`)
- Run a single test: `.venv/bin/pytest tests/models/test_user.py::test_duplicate_email_raises_integrity_error`
- Apply migrations: `.venv/bin/alembic upgrade head`
- Autogenerate a migration after changing a model: `.venv/bin/alembic revision --autogenerate -m "..."`  — then **read the generated file**, autogenerate doesn't always get it right
- Run the app: `.venv/bin/uvicorn habit_tracker.main:app --reload`
- Run self-hosted via Docker: copy `.env.example` to `.env`, fill in `JWT_SECRET_KEY` (`python -c "import secrets; print(secrets.token_urlsafe(32))"`), then `JWT_SECRET_KEY=... docker compose up` (or export it via `.env` — compose picks that up automatically)

## Testing notes

- Tests that need a real database use the `migrated_db` / `db_session`
  fixtures in `tests/conftest.py`, which run the actual Alembic migrations
  against a fresh temp SQLite file per test (via `alembic.command.upgrade`)
  — not `Base.metadata.create_all()` — so a test can catch a migration
  that's drifted from the model.
- `alembic/env.py` only falls back to `core.config.settings.database_url`
  when the caller hasn't already set `sqlalchemy.url` on the `Config`
  object — this is what lets `conftest.py` point migrations at a temp DB.
  Don't remove that fallback-only check when touching `env.py`.
- API-level tests use the `client` fixture (an `httpx.AsyncClient` wired
  to the real FastAPI app via `dependency_overrides`) and the
  `register_and_login` fixture (returns ready-to-use auth headers for a
  fresh user) — both in `tests/conftest.py`.
- `db/base.py: as_aware_utc()` exists because SQLite drops tzinfo on
  round-trip even for a `DateTime(timezone=True)` column — a value
  written as UTC-aware comes back naive. Any code comparing a DB-sourced
  datetime against `datetime.now(timezone.utc)` needs this, or it raises
  `TypeError: can't compare offset-naive and offset-aware datetimes` (bit
  us once in `services/auth.py`'s refresh-token expiry check).
- `core/rate_limit.py: limiter`'s storage is a process-lifetime
  singleton — `tests/conftest.py` has an autouse fixture that resets it
  before/after every test; don't remove it or rate-limit tests become
  order-dependent.
- Tests that need "a habit that's existed for a while" (multi-day streaks,
  backdated schedules) must explicitly move the `HabitSchedule.effective_from`
  back via `db_session` after creating the habit through the API — a
  freshly-created habit's schedule starts `effective_from=today`, so
  entries dated before that are correctly outside any schedule and won't
  count (this is real streak-engine behavior, not a test artifact — see
  `tests/api/test_entries_update_delete.py`'s `_create_daily_habit` helper
  for the pattern).
