# Habit Tracker — Implementation Plan

An ordered checklist derived from `ARCHITECTURE.md`. Each item is a small,
independently-testable increment — implement and verify one before
starting the next. Acceptance tests are described in prose (framework-
agnostic, since the test runner isn't chosen yet — see `CLAUDE.md`);
"unit" means it targets `services/`/`core/` directly with no HTTP layer,
"integration" means it goes through the API.

## Phase 0 — Foundations

- [x] **DB session & base model wiring** (`db/session.py`, `db/base.py`)
      Acceptance: app startup creates the configured SQLite file; a trivial `SELECT 1` roundtrip succeeds.
      Done: tests in `tests/test_foundations.py`.
- [x] **Alembic scaffolding**
      Acceptance: `alembic upgrade head` runs cleanly against a fresh DB with zero models; `alembic revision --autogenerate` produces an empty diff.
      Done: `alembic/env.py`; tests in `tests/test_foundations.py` (the "empty diff" check now runs post-migration as an ongoing models-vs-migrations drift check, since there are no longer zero models).

## Phase 1 — Core models (storage only, no endpoints)

- [x] **User model + migration**
      Acceptance: migration creates `users` with a unique constraint on `email`; inserting a duplicate email raises an integrity error.
      Done: `models/user.py`, `alembic/versions/938d77531d63_create_users_table.py`; tests in `tests/models/test_user.py`.
- [x] **RefreshToken model + migration**
      Acceptance: table has an FK to `users`; inserting a token row and querying by `user_id` works.
      Done: `models/refresh_token.py`, `alembic/versions/7c3a6a72f6ad_*.py`; tests in `tests/models/test_refresh_token.py`.
- [x] **Habit model + migration** (incl. `current_streak`, `longest_streak`, `streak_last_counted_period_start`)
      Acceptance: inserting a habit with only required fields leaves streak columns at their defaults (0, 0, null).
      Done: `models/habit.py`; tests in `tests/models/test_habit.py`.
- [x] **HabitSchedule model + migration**
      Acceptance: two schedule rows for one habit with different `effective_from` dates both insert; a helper query for "active schedule as of date X" returns the correct row when dates overlap.
      Done: `models/habit_schedule.py`; tests in `tests/models/test_habit_schedule.py`.
- [x] **Entry model + migration**
      Acceptance: the unique constraint on `(habit_id, local_date)` rejects a duplicate insert.
      Done: `models/entry.py`; tests in `tests/models/test_entry.py`.
- [x] **NotificationPreference model + migration**
      Acceptance: table is one-to-one with `users` via `user_id` as PK/FK.
      Done: `models/notification_preference.py`; tests in `tests/models/test_notification_preference.py`.

## Phase 2 — Auth

- [x] **Password hashing + JWT helpers** (`core/security.py`)
      Acceptance (unit): hash→verify round-trips and rejects a wrong password; encode→decode round-trips a token and rejects a tampered or expired one.
      Done: `core/security.py`; tests in `tests/core/test_security.py`.
- [x] **`POST /auth/register`**
      Acceptance: valid payload → 201 with the created user, no password in the response; duplicate email → 409.
      Done: `api/v1/auth.py`, `services/auth.py`; tests in `tests/api/test_auth_register.py`.
- [x] **`POST /auth/login`**
      Acceptance: correct credentials → access + refresh tokens; wrong password → 401.
      Done: tests in `tests/api/test_auth_login.py`.
- [x] **`get_current_user` dependency + one protected placeholder route**
      Acceptance: request with no/invalid bearer token → 401; valid token → 200, resolves the correct user.
      Done: `core/deps.py`, `GET /auth/me`; tests in `tests/api/test_auth_me.py`.
- [x] **`POST /auth/refresh` with rotation**
      Acceptance: a valid refresh token returns a new pair and immediately invalidates the old refresh token; an expired/revoked token → 401.
      Done: tests in `tests/api/test_auth_refresh.py`. (Caught and fixed a real bug: SQLite drops tzinfo on round-trip, so comparing a re-read `expires_at` against an aware `datetime.now(timezone.utc)` raised `TypeError` — added `db/base.py: as_aware_utc()`.)
- [x] **`POST /auth/logout`**
      Acceptance: after logout, that refresh token → 401 on a subsequent `/auth/refresh` call.
      Done: tests in `tests/api/test_auth_logout.py`.

## Phase 3 — Habits CRUD (no streak logic yet)

- [x] **`POST /habits`**
      Acceptance: creates the Habit and its first `HabitSchedule` row atomically; response has `current_streak: 0`.
      Done: `services/habits.py`, `api/v1/habits.py`; tests in `tests/api/test_habits_create.py`. Pulled `services/schedule.py: local_today()` forward from Phase 4 since creation needs "today" for the first schedule's `effective_from`.
- [x] **`GET /habits`, `GET /habits/{id}`**
      Acceptance: list returns only the caller's habits; `include_archived=false` (default) excludes archived ones; fetching another user's habit id → 404.
      Done: tests in `tests/api/test_habits_list_and_get.py`.
- [x] **`PATCH /habits/{id}` — non-frequency fields**
      Acceptance: updating `name`/`description` persists; frequency fields untouched.
      Done: tests in `tests/api/test_habits_update.py`.
- [x] **`PATCH /habits/{id}` — frequency change appends a new `HabitSchedule`**
      Acceptance: after the PATCH, "active schedule as of today" returns the new row while "active schedule as of yesterday" still returns the old one.
      Done: `services/schedule.py: active_schedule_as_of()`; tests in `tests/api/test_habits_update.py`. Adjusted from the literal acceptance wording: a same-day PATCH means both schedule rows share today's `effective_from` (there's no wall-clock "yesterday" within one test), so the real risk was an undefined tie-break — fixed by ordering `effective_from desc, id desc` and asserting the newer row wins the same-day tie, plus a genuinely-earlier date still resolving to nothing.
- [x] **`DELETE /habits/{id}` (soft delete) + `POST /habits/{id}/restore`**
      Acceptance: after DELETE, `archived_at` is set and the habit drops out of the default list; restore clears `archived_at` and it reappears.
      Done: tests in `tests/api/test_habits_delete_restore.py`.

## Phase 4 — Schedule resolution

- [x] **`services/schedule.py` — "is due on date" + period-key resolution**
      Acceptance (unit): a `daily` habit is due every date; a `weekly_days` habit is due only on its configured weekdays; two dates in the same ISO week produce the same period-key for a `times_per_week` habit and a different one across a week boundary.
      Done: `services/schedule.py: is_due_on()`, `period_key()`; tests in `tests/services/test_schedule.py` (also added coverage for `local_today()`, pulled forward in Phase 3, by making its `now` injectable for deterministic tests).

## Phase 5 — Entries + the streak engine (core of the design)

- [x] **`POST /habits/{id}/entries` — plain storage, streak logic not wired yet**
      Acceptance: creates an entry defaulting to today's `local_date`; a duplicate `(habit_id, local_date)` → 409.
      Done: `services/entries.py`, `api/v1/entries.py`; tests in `tests/api/test_entries_create.py`.
- [x] **`services/streak.py: recompute()`**
      Acceptance (unit): given a fixture of entries with a known gap, `recompute()` produces the expected `current_streak`/`longest_streak`/`streak_last_counted_period_start`. This is the ground-truth algorithm — test it standalone before the fast path exists.
      Done: `services/streak.py`; tests in `tests/services/test_streak_recompute.py` (6 scenarios: empty, consecutive, gap, today-in-progress, times_per_week, quantifiable).
- [x] **`services/streak.py: apply_checkin()` fast path + fallback**
      Acceptance (unit): checking in for the immediate next expected period increments `current_streak` by exactly 1 without calling `recompute()` (assert via spy/mock); checking in out of sequence (gap or backfill) falls back to `recompute()` and produces the same result `recompute()` alone would on that data.
      Done: tests in `tests/services/test_streak_apply_checkin.py`. Also handles a case ARCHITECTURE.md's sketch didn't fully spell out: a `times_per_week` check-in that doesn't newly satisfy its week (under target, or already past it) is a third outcome — neither fast path nor fallback, just a no-op, since the counters are already correct.
- [x] **Wire `apply_checkin()` into `POST /habits/{id}/entries` inside one DB transaction**
      Acceptance: a forced failure between the entry insert and the counter update leaves neither persisted (both roll back together).
      Done: `db/session.py: get_db()` now rolls back on exception; tests in `tests/api/test_entries_transaction.py`.
- [x] **`PATCH`/`DELETE .../entries/{date}` → unconditional `recompute()`**
      Acceptance: editing or deleting a past entry updates the counters to match a fresh `recompute()`; PATCH also sets `edited_at`.
      Done: tests in `tests/api/test_entries_update_delete.py`.
- [x] **`times_per_week` streak correctness**
      Acceptance: a 3x/week habit only reaches "done" in a week with ≥3 done entries, and `current_streak` increments once per satisfied week, not once per entry.
      Done: tests in `tests/api/test_entries_times_per_week.py`.
- [x] **Archived habit freezes its streak**
      Acceptance: after DELETE (archive), further elapsed time plus a reconciliation pass does not change `current_streak`.
      Done: `services/streak.py: reconcile()` (guards on `archived_at`, used later by Phase 8's job); tests in `tests/services/test_streak_reconcile.py`.

## Phase 6 — Today & stats

- [x] **`GET /today`**
      Acceptance: returns exactly the non-archived habits due today (via `services/schedule.py`) with correct status and `current_streak`, reading the Habit row directly — assert `recompute()`/`apply_checkin()` is never called for this endpoint.
      Done: `services/today.py`, `api/v1/today.py`; tests in `tests/api/test_today_and_stats.py`. Found and fixed a real but unrelated flaky test along the way: `test_access_token_rejects_tampered_token` tampered the JWT's last base64 character, which can land on "don't-care" padding bits that decode to identical signature bytes — fixed to tamper an interior character instead (verified stable across 20 runs).
- [x] **`GET /habits/{id}/stats`**
      Acceptance: returns `current_streak`/`longest_streak` matching the Habit row.
      Done: tests in `tests/api/test_today_and_stats.py`.

## Phase 7 — Quantifiable habits

- [x] **`target_value`/`value` handling on check-in**
      Acceptance: `value < target_value` is stored but does not count as "done" for streak purposes; `value >= target_value` does.
      Done: this was already built into `services/streak.py: _qualifies()` while implementing Phase 5 (needed there for `recompute()`'s correctness) and unit-tested in `tests/services/test_streak_recompute.py`. This item added the API-level confirmation in `tests/api/test_entries_quantifiable.py` (below/at/above target).

## Phase 8 — Background jobs

- [x] **Nightly reconciliation task** (`jobs/scheduler.py`)
      Acceptance: given a habit whose expected next period has fully elapsed with no entry, invoking the task function directly (not on a real clock) calls `recompute()` and `current_streak` drops accordingly.
      Done: `jobs/scheduler.py: run_nightly_reconciliation()` (built on Phase 5's `reconcile()`) + `create_scheduler()` APScheduler wiring; tests in `tests/jobs/`.
- [x] **Notification selection logic** (`services/notifications.py`)
      Acceptance (unit): given habits due today with no entry yet, the "who to notify" function returns the correct user/habit set; SMTP send is mocked, not exercised for real.
      Done: `services/notifications.py: get_pending_reminders()` / `send_reminder_email()` (kept as separate functions so delivery is trivially mockable); tests in `tests/services/test_notifications.py`.

## Phase 9 — Settings

- [x] **`GET`/`PATCH /settings`**
      Acceptance: PATCH updates `timezone`/`day_start_hour`/notification prefs and GET reflects them; an invalid timezone string → 422.
      Done: `schemas/settings.py` (pydantic validator against `zoneinfo`), `services/settings.py`, `api/v1/settings.py`; tests in `tests/api/test_settings.py`.

## Phase 10 — Export/Import

- [x] **`GET /export`**
      Acceptance: dump contains all of the caller's habits/schedules/entries and nothing from another user; streak fields are excluded from the payload.
      Done: `schemas/export_import.py`, `services/export_import.py: export_data()`; tests in `tests/api/test_export_import.py`. Resolved REQUIREMENTS.md's flagged open decision (conflict policy): skip-duplicates, matched on habit name + entry `(habit, local_date)`.
- [x] **`POST /import`**
      Acceptance: importing a dump creates habits/entries, skips exact duplicates per the documented policy and reports a skipped count; each imported habit's counters match a fresh `recompute()` afterward.
      Done: `services/export_import.py: import_data()` (one `recompute()` per touched habit, not a replay of `apply_checkin()` per entry); tests in `tests/api/test_export_import.py`.

## Phase 11 — Cross-cutting hardening

- [x] **CORS middleware**
      Acceptance: a request from an allowed origin receives the correct `Access-Control-Allow-Origin` header; a disallowed origin does not.
      Done: `core/config.py: cors_allowed_origins_list` (env-configurable, deny-all by default per REQUIREMENTS.md), wired in `main.py`; tests in `tests/test_cors.py`.
- [x] **Rate limiting on `/auth/login` and `/habits/{id}/entries`**
      Acceptance: exceeding the configured rate → 429; requests under the limit succeed normally.
      Done: `core/rate_limit.py` (slowapi), limits of 10/minute (login) and 20/minute (check-ins) — picked generously above any legitimate multi-check-in flow in this test suite; tests in `tests/api/test_rate_limiting.py`. Added an autouse `limiter.reset()` fixture in `conftest.py` — without it, the Limiter's in-memory counters are a process-lifetime singleton and would leak across unrelated tests.

## Phase 12 — Deployment

- [x] **Dockerfile + docker-compose with a mounted SQLite volume**
      Acceptance: `docker compose up` serves the API; a container restart preserves data written before the restart.
      Done: `Dockerfile` (python:3.12-slim — the container isn't bound by this dev environment's Python 3.9 limitation), `docker-compose.yml`, `.env.example`. Actually verified end-to-end against a real Docker daemon in this environment (not just written-and-hoped): built the image, `docker compose up`, registered a user + created a habit + checked in via curl through the live container, restarted the container (`docker compose restart`) and separately did a full `down`+`up` recreation — in both cases, re-querying the habit showed identical `current_streak`/`longest_streak`/`created_at`, confirming the named volume actually persists the SQLite file. Verification stack torn down afterward (`docker compose down -v` + image removed) — nothing left running.
