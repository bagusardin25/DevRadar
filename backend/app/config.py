"""Typed environment configuration using pydantic-settings."""

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # App
    app_env: str = "development"
    api_base_path: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Database
    database_url: str = "postgresql+asyncpg://devradar:devradar@127.0.0.1:5434/devradar"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Object Storage
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "devradar-raw"
    object_storage_access_key: str = "local-development-only"
    object_storage_secret_key: str = "local-development-only"
    object_storage_region: str = "us-east-1"

    # Security
    session_secret: str = "replace-with-at-least-32-random-bytes"
    email_encryption_key: str = "replace-with-a-valid-key"
    email_hmac_key: str = "replace-with-at-least-32-random-bytes"

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    admin_github_ids: list[str] = []

    # Email
    email_provider: str = "console"
    email_from: str = "alerts@example.test"

    # LLM
    llm_provider: str = "disabled"
    llm_model: str = ""
    llm_api_key: str = ""

    # X/Twitter
    x_bearer_token: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("cors_origins", "admin_github_ids", mode="before")
    @classmethod
    def parse_comma_separated_list(cls, v: Any) -> list[str]:
        """Parse comma-separated strings into lists."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, list):
            return [str(item) for item in v]
        return []


def get_settings() -> Settings:
    """Create and return application settings."""
    return Settings()
