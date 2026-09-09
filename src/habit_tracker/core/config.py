from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HABIT_TRACKER_")

    database_url: str = "sqlite+aiosqlite:///./habit_tracker.db"

    # JWT / auth. jwt_secret_key has an insecure default so local dev and
    # tests work out of the box — real deployments MUST override it via
    # HABIT_TRACKER_JWT_SECRET_KEY (see ARCHITECTURE.md's Docker section).
    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Email delivery (ARCHITECTURE.md: user supplies their own SMTP
    # credentials — no provider hardcoded). Unset by default; real
    # delivery requires overriding these via env vars at deployment time.
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "habit-tracker@example.com"

    # CORS — a frontend origin isn't finalized yet (REQUIREMENTS.md), so
    # this is built in but empty (deny-all) by default; deployments set an
    # env-configurable comma-separated allowed-origins list.
    cors_allowed_origins: str = ""

    @property
    def cors_allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()
