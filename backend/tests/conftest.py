"""Shared test fixtures for the DevRadar backend test suite."""

from collections.abc import AsyncIterator

import httpx
import pytest

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Test settings with default development values."""
    return Settings(
        app_env="test",
        database_url="postgresql+asyncpg://devradar:devradar@127.0.0.1:5434/devradar",
        redis_url="redis://127.0.0.1:6379/0",
    )


@pytest.fixture
def settings_no_db() -> Settings:
    """Settings with an invalid database URL for failure testing."""
    return Settings(
        app_env="test",
        database_url="postgresql+asyncpg://invalid:invalid@127.0.0.1:59999/nonexistent",
        redis_url="redis://127.0.0.1:6379/0",
    )


@pytest.fixture
def settings_no_redis() -> Settings:
    """Settings with an invalid Redis URL for failure testing."""
    return Settings(
        app_env="test",
        database_url="postgresql+asyncpg://devradar:devradar@127.0.0.1:5434/devradar",
        redis_url="redis://127.0.0.1:59999/0",
    )


@pytest.fixture
async def app(settings: Settings):
    """Create a test FastAPI application with valid settings."""
    application = create_app(settings)
    yield application


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP test client with all services available."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c


@pytest.fixture
async def client_no_db(settings_no_db: Settings) -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP test client with PostgreSQL unavailable."""
    application = create_app(settings_no_db)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://testserver",
    ) as c:
        yield c


@pytest.fixture
async def client_no_redis(settings_no_redis: Settings) -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP test client with Redis unavailable."""
    application = create_app(settings_no_redis)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://testserver",
    ) as c:
        yield c
