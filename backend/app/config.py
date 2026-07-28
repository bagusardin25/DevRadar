"""Typed environment configuration using pydantic-settings.

Development defaults are safe for local seed-demo use (Compose credentials,
placeholder secrets, OpenAPI docs on). Production (`APP_ENV=production`) is
stricter: unique secrets, no Compose default DB password, required OAuth
callback origin, and no accidental open docs surface.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Annotated, Any, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.api.limits import MAX_REQUEST_BODY_BYTES

logger = logging.getLogger(__name__)

# Known template / CI placeholders that must never ship as live production secrets.
_PLACEHOLDER_SECRETS = frozenset(
    {
        "replace-with-at-least-32-random-bytes",
        "replace-with-a-valid-key",
        "ci-session-secret-at-least-32-chars-long",
        "ci-email-encryption-key-material",
        "ci-email-hmac-key-at-least-32-chars",
        "local-development-only",
        "devradar123",
        "changeme",
        "secret",
        "password",
    }
)

_COMPOSE_DEFAULT_DB_MARKERS = (
    "devradar:devradar@",
    "postgres:postgres@",
    "user:password@",
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # App — development | test | production (normalized to lowercase)
    app_env: str = "development"
    api_base_path: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"
    # NoDecode: allow plain comma-separated env values (not only JSON arrays).
    # pydantic-settings otherwise json.loads list fields before validators run.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Database
    database_url: str = "postgresql+asyncpg://devradar:devradar@127.0.0.1:5434/devradar"

    # Redis
    redis_url: str = "redis://127.0.0.1:6379/0"

    # Object Storage
    # backend: local | s3 | memory
    object_storage_backend: str = "local"
    object_storage_local_path: str = "./data/raw"
    object_storage_endpoint: str = "http://127.0.0.1:9000"
    object_storage_bucket: str = "devradar-raw"
    object_storage_access_key: str = "devradar"
    object_storage_secret_key: str = "devradar123"
    object_storage_region: str = "us-east-1"

    # Fetch policy defaults
    fetch_timeout_seconds: float = 20.0
    fetch_max_bytes: int = 5_242_880  # 5 MiB
    fetch_max_redirects: int = 5

    # Public HTTP request policy. This is enforced for both Content-Length and
    # streamed/chunked bodies, so running Uvicorn without a reverse proxy does
    # not leave JSON endpoints open to unbounded buffering.
    max_request_body_bytes: int = MAX_REQUEST_BODY_BYTES

    # Security
    # Number of proxies in front of the app. 0 ignores X-Forwarded-For (correct
    # when directly exposed); set to 1 behind a single load balancer. Trusting
    # the header without this makes IP rate limits trivially bypassable.
    trusted_proxy_hops: int = 0
    session_secret: str = "replace-with-at-least-32-random-bytes"
    email_encryption_key: str = "replace-with-a-valid-key"
    email_hmac_key: str = "replace-with-at-least-32-random-bytes"

    # Google OAuth (admin login)
    google_client_id: str = ""
    google_client_secret: str = ""
    admin_google_emails: Annotated[list[str], NoDecode] = []
    # Public origin of THIS API (scheme + host [+ port]), used to build the OAuth
    # callback URL. Must match an Authorized redirect URI on the Google OAuth
    # client, and share the frontend's host so the session cookie is returned.
    # Empty falls back to the local dev API in non-production.
    oauth_redirect_base_url: str = ""

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

    # AI initial review — a CodeRabbit-style pre-review attached to the admin
    # queue for community submissions. Uses the deterministic verifier by
    # default; enriched with an LLM narrative when LLM_PROVIDER=openai + key.
    ai_review_enabled: bool = True

    # X/Twitter
    x_bearer_token: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Environment helpers -------------------------------------------------

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def cookie_secure(self) -> bool:
        """Session cookies require HTTPS only in production."""
        return self.is_production

    @property
    def sql_echo(self) -> bool:
        """Log SQL only during local development (never in test/production)."""
        return self.is_development

    # --- Validators ----------------------------------------------------------

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, v: Any) -> str:
        text = str(v or "development").strip().lower()
        if text not in {"development", "test", "production"}:
            raise ValueError(
                f"APP_ENV must be development, test, or production (got {v!r})"
            )
        return text

    @field_validator("max_request_body_bytes")
    @classmethod
    def validate_request_body_limit(cls, v: int) -> int:
        if v < 16_384:
            raise ValueError("MAX_REQUEST_BODY_BYTES must be at least 16384")
        return v

    @field_validator("cors_origins", "admin_google_emails", mode="before")
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

    @field_validator("admin_google_emails", mode="after")
    @classmethod
    def normalize_admin_emails(cls, v: list[str]) -> list[str]:
        """Lowercase, de-duplicate, and drop entries that are not email-shaped.

        Matching happens on the verified Google email (see auth.google), so the
        allowlist stores canonical lowercased addresses. Malformed entries are
        dropped rather than trusted so a typo cannot widen access.
        """
        seen: set[str] = set()
        emails: list[str] = []
        dropped: list[str] = []
        for item in v:
            candidate = item.strip().lower()
            if "@" in candidate and "." in candidate.split("@")[-1]:
                if candidate not in seen:
                    seen.add(candidate)
                    emails.append(candidate)
            elif candidate:
                dropped.append(item)
        if dropped:
            logger.warning(
                "Ignoring malformed ADMIN_GOOGLE_EMAILS entries: %s. Use full email "
                "addresses, e.g. you@example.com.",
                ", ".join(dropped),
            )
        return emails

    @model_validator(mode="after")
    def fill_openai_api_key_alias(self) -> Self:
        """Allow OPENAI_API_KEY as an alias for LLM_API_KEY."""
        if not (self.llm_api_key or "").strip():
            alias = os.environ.get("OPENAI_API_KEY", "").strip()
            if alias:
                self.llm_api_key = alias
        return self

    @model_validator(mode="after")
    def harden_production(self) -> Self:
        """Refuse unsafe defaults when APP_ENV=production.

        Development and test keep Compose-friendly defaults so seed-demo and CI
        stay zero-config. Production must set unique secrets and real endpoints.
        """
        if not self.is_production:
            return self

        problems: list[str] = []

        def _secret_ok(name: str, value: str, *, min_len: int = 32) -> None:
            text = (value or "").strip()
            if len(text) < min_len:
                problems.append(f"{name} must be at least {min_len} characters")
            if text.lower() in _PLACEHOLDER_SECRETS or text in _PLACEHOLDER_SECRETS:
                problems.append(f"{name} must not use a documented placeholder value")

        _secret_ok("SESSION_SECRET", self.session_secret)
        _secret_ok("EMAIL_HMAC_KEY", self.email_hmac_key)
        # Fernet keys are often 44-char urlsafe base64; require non-placeholder length ≥16.
        _secret_ok("EMAIL_ENCRYPTION_KEY", self.email_encryption_key, min_len=16)

        if any(marker in self.database_url for marker in _COMPOSE_DEFAULT_DB_MARKERS):
            problems.append(
                "DATABASE_URL must not use local Compose default credentials "
                "(e.g. devradar:devradar) in production"
            )

        if not self.oauth_redirect_base_url.strip():
            problems.append(
                "OAUTH_REDIRECT_BASE_URL is required in production "
                "(public API origin, e.g. https://api.example.com)"
            )
        elif not self.oauth_redirect_base_url.strip().startswith("https://"):
            problems.append(
                "OAUTH_REDIRECT_BASE_URL must use https:// in production"
            )

        if not self.frontend_url.strip().startswith("https://"):
            problems.append("FRONTEND_URL must use https:// in production")

        if any(o.strip() == "*" for o in self.cors_origins):
            problems.append("CORS_ORIGINS must not be wildcard (*) in production")
        if not self.cors_origins:
            problems.append("CORS_ORIGINS must list at least one allowed origin")

        if self.object_storage_backend == "memory":
            problems.append(
                "OBJECT_STORAGE_BACKEND=memory is for tests only; use local or s3"
            )
        if (
            self.object_storage_backend == "s3"
            and (self.object_storage_secret_key or "").strip() in _PLACEHOLDER_SECRETS
        ):
            problems.append(
                "OBJECT_STORAGE_SECRET_KEY must be set to a real key when using s3"
            )

        if self.llm_provider == "openai" and not (self.llm_api_key or "").strip():
            problems.append("LLM_API_KEY is required when LLM_PROVIDER=openai")

        if problems:
            raise ValueError(
                "Invalid production configuration:\n- " + "\n- ".join(problems)
            )
        return self


def get_settings() -> Settings:
    """Create and return application settings."""
    return Settings()
