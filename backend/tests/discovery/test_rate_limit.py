"""Live discovery rate limiting — Redis-backed in production, dict in tests."""

from __future__ import annotations

from typing import Any

import pytest
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.service import (
    RATE_LIMIT_MAX,
    RATE_LIMIT_WINDOW,
    LiveDiscoveryService,
)
from app.errors import RateLimitError


class FakeRedis:
    """Minimal stand-in for the counters the limiter actually uses."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.expiries: dict[str, int] = {}
        self.close_calls = 0

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, ttl: int) -> None:
        self.expiries[key] = ttl

    async def aclose(self) -> None:
        self.close_calls += 1


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    fake = FakeRedis()

    def _from_url(*_args: Any, **_kwargs: Any) -> FakeRedis:
        return fake

    monkeypatch.setattr(aioredis, "from_url", _from_url)
    return fake


def _service(
    session: AsyncSession,
    *,
    store: dict[str, list[float]] | None = None,
) -> LiveDiscoveryService:
    return LiveDiscoveryService(
        session,
        "test-session-secret-at-least-32-chars!!",
        redis_url="redis://unused-because-patched/0",
        rate_limit_store=store,
    )


class TestDiscoveryRateLimit:
    async def test_counts_in_redis_when_no_in_process_store(
        self, session: AsyncSession, fake_redis: FakeRedis
    ) -> None:
        svc = _service(session)
        await svc._enforce_rate_limit("ip-hash-a")

        assert fake_redis.counters == {"devradar:rl:discovery:ip-hash-a": 1}
        # TTL is set on first hit so the window actually expires.
        assert fake_redis.expiries == {
            "devradar:rl:discovery:ip-hash-a": RATE_LIMIT_WINDOW
        }

    async def test_ttl_set_once_not_refreshed_on_every_hit(
        self, session: AsyncSession, fake_redis: FakeRedis
    ) -> None:
        svc = _service(session)
        for _ in range(3):
            await svc._enforce_rate_limit("ip-hash-b")

        # A sliding TTL would let a steady drip of requests never expire.
        assert fake_redis.counters["devradar:rl:discovery:ip-hash-b"] == 3
        assert len(fake_redis.expiries) == 1

    async def test_rejects_past_the_cap(
        self, session: AsyncSession, fake_redis: FakeRedis
    ) -> None:
        svc = _service(session)
        for _ in range(RATE_LIMIT_MAX):
            await svc._enforce_rate_limit("ip-hash-c")

        with pytest.raises(RateLimitError):
            await svc._enforce_rate_limit("ip-hash-c")

    async def test_quota_is_per_client(
        self, session: AsyncSession, fake_redis: FakeRedis
    ) -> None:
        svc = _service(session)
        for _ in range(RATE_LIMIT_MAX):
            await svc._enforce_rate_limit("ip-hash-noisy")

        # A different client is unaffected by the noisy one.
        await svc._enforce_rate_limit("ip-hash-quiet")

    async def test_connection_released_even_when_rejected(
        self, session: AsyncSession, fake_redis: FakeRedis
    ) -> None:
        svc = _service(session)
        for _ in range(RATE_LIMIT_MAX):
            await svc._enforce_rate_limit("ip-hash-d")
        with pytest.raises(RateLimitError):
            await svc._enforce_rate_limit("ip-hash-d")

        # Every call, including the rejected one, must close its client.
        assert fake_redis.close_calls == RATE_LIMIT_MAX + 1

    async def test_in_process_store_bypasses_redis(
        self, session: AsyncSession, fake_redis: FakeRedis
    ) -> None:
        store: dict[str, list[float]] = {}
        svc = _service(session, store=store)

        for _ in range(RATE_LIMIT_MAX):
            await svc._enforce_rate_limit("ip-hash-e")
        with pytest.raises(RateLimitError):
            await svc._enforce_rate_limit("ip-hash-e")

        assert fake_redis.counters == {}
        assert len(store["ip-hash-e"]) == RATE_LIMIT_MAX
