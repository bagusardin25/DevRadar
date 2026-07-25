"""Shared test fixtures for the DevRadar backend test suite.

The suite runs against a dedicated database (``<dev db>_test`` by default), never
the developer's catalogue. This matters because some tests commit rows and
``tests/integration/test_migrations.py`` drops the whole schema — pointed at a
dev database that silently destroys seeded data.

Override with ``TEST_DATABASE_URL`` if you need a different target.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
import pytest

from app.config import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_EXTENSIONS = ("pg_trgm", "citext", "uuid-ossp")


def _derive_test_url(url: str) -> str:
    parts = urlsplit(url)
    name = parts.path.lstrip("/") or "devradar"
    if name.endswith("_test"):
        return url
    return urlunsplit(
        (parts.scheme, parts.netloc, f"/{name}_test", parts.query, parts.fragment)
    )


# Resolve the configured (dev) URL once, then redirect everything that follows.
# get_settings() is uncached and env vars outrank .env, so this override applies
# to every Settings() built afterwards — including inside app code and alembic.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or _derive_test_url(
    Settings().database_url
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.main import create_app  # noqa: E402  (must follow the env override)


def _asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _provision_test_database() -> None:
    import asyncpg

    parts = urlsplit(_asyncpg_dsn(TEST_DATABASE_URL))
    db_name = parts.path.lstrip("/")
    admin_dsn = urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))

    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if not exists:
            # Identifier cannot be parameterised; db_name is derived from config.
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()

    conn = await asyncpg.connect(_asyncpg_dsn(TEST_DATABASE_URL))
    try:
        for ext in REQUIRED_EXTENSIONS:
            await conn.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')
    finally:
        await conn.close()


def pytest_sessionstart(session: pytest.Session) -> None:
    """Create and migrate the test database before any test connects."""
    asyncio.run(_provision_test_database())
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to migrate test database {TEST_DATABASE_URL}:\n"
            f"{result.stdout}\n{result.stderr}"
        )


@pytest.fixture
def settings() -> Settings:
    """Test settings pointed at the dedicated test database."""
    return Settings(
        app_env="test",
        database_url=TEST_DATABASE_URL,
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
        database_url=TEST_DATABASE_URL,
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
