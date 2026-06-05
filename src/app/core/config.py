"""Application configuration via Pydantic settings.

All values are sourced from environment variables (and a local `.env` file in
development). Settings are cached so the object is parsed once per process.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Predictive Maintenance API"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # --- Server ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_host: str = "0.0.0.0"
    frontend_port: int = 7860
    api_base_url: str = "http://localhost:8000"

    # --- PostgreSQL ---
    postgres_user: str = "pmuser"
    postgres_password: str = "pmpassword"
    postgres_db: str = "predictive_maintenance"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str | None = None

    # --- Security ---
    jwt_secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- OpenRouter / AI ---
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-2.5-pro"
    openrouter_fallback_model: str = "google/gemini-2.5-flash"
    openrouter_timeout_seconds: int = 60

    # --- Telemetry / Anomaly detection ---
    csv_chunk_size: int = 50_000
    isolation_forest_contamination: float = 0.02
    isolation_forest_n_estimators: int = 100
    model_dir: str = "./models"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        """Assemble the async SQLAlchemy DSN, preferring an explicit override."""
        if self.database_url:
            return self.database_url
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ai_enabled(self) -> bool:
        return bool(self.openrouter_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
