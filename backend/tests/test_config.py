"""Development vs production settings separation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def _settings(**kwargs: object) -> Settings:
    """Build Settings without reading the developer's backend/.env."""
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def _production_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "app_env": "production",
        "frontend_url": "https://app.example.com",
        "cors_origins": "https://app.example.com",
        "database_url": "postgresql+asyncpg://app:s3cret-long-pass@db:5432/devradar",
        "redis_url": "redis://redis:6379/0",
        "session_secret": "prod-session-secret-at-least-32-chars-long!!",
        "email_encryption_key": "prod-email-encryption-key-16+",
        "email_hmac_key": "prod-email-hmac-key-at-least-32-chars-long!!",
        "oauth_redirect_base_url": "https://api.example.com",
        "object_storage_backend": "local",
        "llm_provider": "disabled",
    }
    base.update(overrides)
    return base


def test_development_allows_compose_defaults() -> None:
    settings = _settings(
        app_env="development",
        database_url="postgresql+asyncpg://devradar:devradar@127.0.0.1:5434/devradar",
        session_secret="replace-with-at-least-32-random-bytes",
    )
    assert settings.is_development
    assert not settings.is_production
    assert settings.cookie_secure is False
    assert settings.sql_echo is True


def test_test_env_does_not_require_production_hardening() -> None:
    settings = _settings(app_env="test")
    assert settings.is_test
    assert settings.cookie_secure is False
    assert settings.sql_echo is False


def test_app_env_is_normalized() -> None:
    settings = _settings(
        app_env="Production",
        **{k: v for k, v in _production_kwargs().items() if k != "app_env"},
    )
    assert settings.app_env == "production"
    assert settings.is_production


def test_production_accepts_hardened_config() -> None:
    settings = _settings(**_production_kwargs())
    assert settings.is_production
    assert settings.cookie_secure is True
    assert settings.sql_echo is False


def test_production_rejects_placeholder_secrets() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(
            **_production_kwargs(
                session_secret="replace-with-at-least-32-random-bytes",
            )
        )
    assert "SESSION_SECRET" in str(exc.value)


def test_production_rejects_compose_database_url() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(
            **_production_kwargs(
                database_url=(
                    "postgresql+asyncpg://devradar:devradar@127.0.0.1:5434/devradar"
                ),
            )
        )
    assert "DATABASE_URL" in str(exc.value)


def test_production_requires_https_oauth_and_frontend() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(
            **_production_kwargs(
                oauth_redirect_base_url="http://api.example.com",
                frontend_url="http://app.example.com",
            )
        )
    msg = str(exc.value)
    assert "OAUTH_REDIRECT_BASE_URL" in msg or "FRONTEND_URL" in msg


def test_production_rejects_memory_object_storage() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(**_production_kwargs(object_storage_backend="memory"))
    assert "OBJECT_STORAGE_BACKEND" in str(exc.value)


def test_production_hides_openapi_docs() -> None:
    from app.main import create_app

    app = create_app(_settings(**_production_kwargs()))
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/docs" not in paths
    assert "/openapi.json" not in paths
    assert "/health/live" in paths


def test_development_exposes_openapi_docs() -> None:
    from app.main import create_app

    app = create_app(_settings(app_env="development"))
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/docs" in paths
    assert "/openapi.json" in paths
