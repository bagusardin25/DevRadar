"""Redis-backed and in-process alert signup rate-limit tests."""

from __future__ import annotations

from typing import Any

import pytest
import redis.asyncio as aioredis

from app.alerts.rate_limit import (
    CLIENT_LIMIT,
    EMAIL_LIMIT,
    WINDOW_SECONDS,
    AlertSignupRateLimiter,
)
from app.errors import RateLimitError


class FakeRedis:
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

    def from_url(*_args: Any, **_kwargs: Any) -> FakeRedis:
        return fake

    monkeypatch.setattr(aioredis, "from_url", from_url)
    return fake


class TestAlertSignupRateLimiter:
    async def test_redis_keys_are_hashed_identifiers_only(self, fake_redis: FakeRedis) -> None:
        limiter = AlertSignupRateLimiter("redis://unused/0")
        await limiter.enforce("client-hash", "email-hash")

        assert fake_redis.counters == {
            "devradar:rl:alerts:client:client-hash": 1,
            "devradar:rl:alerts:email:email-hash": 1,
        }
        assert set(fake_redis.expiries.values()) == {WINDOW_SECONDS}
        assert fake_redis.close_calls == 1

    async def test_email_limit_blocks_and_closes_redis(self, fake_redis: FakeRedis) -> None:
        limiter = AlertSignupRateLimiter("redis://unused/0")
        for _ in range(EMAIL_LIMIT):
            await limiter.enforce("client-hash", "email-hash")

        with pytest.raises(RateLimitError, match="for this email") as exc_info:
            await limiter.enforce("client-hash", "email-hash")

        assert exc_info.value.headers == {"Retry-After": str(WINDOW_SECONDS)}
        assert fake_redis.close_calls == EMAIL_LIMIT + 1

    async def test_client_limit_covers_rotating_emails(self) -> None:
        store: dict[str, list[float]] = {}
        limiter = AlertSignupRateLimiter("redis://unused/0", rate_limit_store=store)

        for index in range(CLIENT_LIMIT):
            await limiter.enforce("client-hash", f"email-hash-{index}")

        with pytest.raises(RateLimitError, match="from this client"):
            await limiter.enforce("client-hash", "email-hash-over")
