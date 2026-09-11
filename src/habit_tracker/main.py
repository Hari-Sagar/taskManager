from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from habit_tracker.api.v1.router import api_router
from habit_tracker.core.config import settings
from habit_tracker.core.rate_limit import limiter

# Order here is display order in the docs UI — grouped in the sequence
# you'd actually use the API: register/log in, set up habits, check in,
# check today's status, then the less-common settings/backup endpoints.
tags_metadata = [
    {"name": "auth", "description": "Register, log in, and manage session tokens."},
    {"name": "habits", "description": "Create and manage habits, including streak stats."},
    {"name": "entries", "description": "Check in (or edit/undo a check-in) for a habit."},
    {"name": "today", "description": "What's due today and its status, in one call."},
    {"name": "settings", "description": "Timezone, day-boundary, and notification preferences."},
    {"name": "export-import", "description": "Back up or restore your habits and history as JSON."},
]

app = FastAPI(
    title="Habit Tracker",
    description="Create habits, check in daily, and track streaks.",
    version="0.1.0",
    openapi_tags=tags_metadata,
    # Both the default Swagger UI and the earlier separate ReDoc page are
    # replaced below by a single page at /docs (Scalar) — a modern look
    # like ReDoc's, but still fully interactive ("Try it out"), which
    # ReDoc can't do (it's read-only reference docs by design).
    docs_url=None,
    redoc_url=None,
)


_SCALAR_HTML = """<!DOCTYPE html>
<html>
  <head>
    <title>Habit Tracker API</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body>
    <script id="api-reference" data-url="{openapi_url}"></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </body>
</html>
"""


@app.get("/docs", include_in_schema=False)
def docs() -> HTMLResponse:
    """The one interactive API reference page — register, get a token,
    authorize, and call every endpoint from here."""
    return HTMLResponse(_SCALAR_HTML.format(openapi_url=app.openapi_url))


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """Liveness check for deployment tooling — deliberately excluded from
    the docs UI, since it's infrastructure plumbing, not part of the API
    surface a client of this service would use."""
    return {"status": "ok"}
