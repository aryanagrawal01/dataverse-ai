"""Application configuration via environment variables (12-factor).

All tunables live here; nothing else in the codebase reads os.environ.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    app_name: str = "DataVerse AI"
    environment: Literal["dev", "staging", "prod"] = "dev"
    secret_key: str = Field(
        default="dev-secret-change-me",
        description="Signs session tokens. MUST be overridden outside dev.",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- Database ---
    database_url: str = "sqlite:///./data/dataverse.db"

    # --- Storage ---
    storage_backend: Literal["local", "s3"] = "local"
    storage_path: Path = Path("./data/artifacts")
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # --- Limits & quotas ---
    max_upload_mb: int = 100
    user_quota_mb: int = 500
    session_ttl_minutes: int = 60
    login_max_failures: int = 5
    login_lockout_minutes: int = 15

    # --- LLM ---
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_budget_usd_per_project: float = 0.25
    llm_timeout_seconds: int = 45

    # --- Feature flags ---
    enable_chat: bool = True
    enable_forecasting: bool = True
    enable_insights: bool = True

    @field_validator("secret_key")
    @classmethod
    def _warn_default_secret(cls, v: str) -> str:
        return v

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def validate_for_environment(self) -> None:
        """Fail fast on unsafe prod configuration. Called at app startup."""
        if self.is_prod and self.secret_key == "dev-secret-change-me":
            msg = "SECRET_KEY must be set in production"
            raise RuntimeError(msg)
        if self.is_prod and self.database_url.startswith("sqlite"):
            msg = "SQLite is not supported in production; set DATABASE_URL"
            raise RuntimeError(msg)


@lru_cache
def get_settings() -> Settings:
    return Settings()
