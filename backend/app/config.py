"""Typed environment configuration using pydantic-settings."""

from __future__ import annotations

import json
import os
from typing import Annotated, Any, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # App
    app_env: str = "development"
    api_base_path: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"
    # NoDecode: allow plain comma-separated env values (not only JSON arrays).
    # pydantic-settings otherwise json.loads list fields before validators run.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Database
    database_url: str = "postgresql+asyncpg://devradar:devradar@127.0.0.1:5434/devradar"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Object Storage
    # backend: local | s3 | memory
    object_storage_backend: str = "local"
    object_storage_local_path: str = "./data/raw"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "devradar-raw"
    object_storage_access_key: str = "local-development-only"
    object_storage_secret_key: str = "local-development-only"
    object_storage_region: str = "us-east-1"

    # Fetch policy defaults
    fetch_timeout_seconds: float = 20.0
    fetch_max_bytes: int = 5_242_880  # 5 MiB
    fetch_max_redirects: int = 5

    # Security
    # Number of proxies in front of the app. 0 ignores X-Forwarded-For (correct
    # when directly exposed); set to 1 behind a single load balancer. Trusting
    # the header without this makes IP rate limits trivially bypassable.
    trusted_proxy_hops: int = 0
    session_secret: str = "replace-with-at-least-32-random-bytes"
    email_encryption_key: str = "replace-with-a-valid-key"
    email_hmac_key: str = "replace-with-at-least-32-random-bytes"

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    admin_github_ids: Annotated[list[str], NoDecode] = []

    # Email (console | resend | smtp)
    email_provider: str = "console"
    email_from: str = "alerts@example.test"
    resend_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = True

    # Operator outbound webhook (optional — Discord/n8n/etc.)
    # When set, scan_matches POSTs JSON for newly published matching listings.
    webhook_url: str = ""
    webhook_secret: str = ""  # optional HMAC-SHA256 in X-DevRadar-Signature
    # Optional JSON object of alert filters, e.g. {"kind":"hackathon","onlyClosingSoon":true}
    webhook_filter_json: str = ""

    # LLM (structured extraction only — not OpenAI web_search)
    # LLM_PROVIDER=openai | disabled
    llm_provider: str = "disabled"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""  # or set OPENAI_API_KEY (see validator)

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
        """Parse JSON arrays, comma-separated strings, or lists into list[str]."""
        if isinstance(v, (int, float)):
            return [str(v)]
        if isinstance(v, str):
            text = v.strip()
            if not text:
                return []
            # Prefer JSON when the value looks like an array (common for deploy envs).
            if text.startswith("["):
                try:
                    decoded = json.loads(text)
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, list):
                    return [str(item).strip() for item in decoded if str(item).strip()]
            return [item.strip() for item in text.split(",") if item.strip()]
        if isinstance(v, list):
            return [str(item) for item in v]
        return []

    @model_validator(mode="after")
    def fill_openai_api_key_alias(self) -> Self:
        """Allow OPENAI_API_KEY as an alias for LLM_API_KEY."""
        if not (self.llm_api_key or "").strip():
            alias = os.environ.get("OPENAI_API_KEY", "").strip()
            if alias:
                self.llm_api_key = alias
        return self


def get_settings() -> Settings:
    """Create and return application settings."""
    return Settings()
