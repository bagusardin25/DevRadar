"""Shared counter store for router state (rate limits, breakers, rotation).

Redis is required in real deployments: Celery runs several workers, so an
in-process token bucket would undercount as soon as concurrency exceeds one.
``MemoryState`` exists for tests and for single-process development without a
Redis instance — it is explicitly not safe across processes.

The surface is deliberately tiny (counters with a TTL, plus one string key) so
both backends stay trivial to reason about.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, Protocol

KEY_PREFIX = "devradar:llm"


class KeyValueState(Protocol):
    """Counter and string operations the router needs."""

    async def incr(self, key: str, *, amount: int = 1, ttl: int) -> int: ...

    async def get_int(self, key: str) -> int: ...

    async def get_text(self, key: str) -> str | None: ...

    async def set_text(self, key: str, value: str, *, ttl: int) -> None: ...

    async def delete(self, key: str) -> None: ...


class MemoryState:
    """Process-local state for tests and single-process development."""

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._values: dict[str, tuple[str, float]] = {}

    def _live(self, key: str) -> str | None:
        entry = self._values.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at <= self._clock():
            del self._values[key]
            return None
        return value

    async def incr(self, key: str, *, amount: int = 1, ttl: int) -> int:
        current = self._live(key)
        total = (int(current) if current is not None else 0) + amount
        expires_at = (
            self._values[key][1] if current is not None else self._clock() + ttl
        )
        self._values[key] = (str(total), expires_at)
        return total

    async def get_int(self, key: str) -> int:
        value = self._live(key)
        return int(value) if value is not None else 0

    async def get_text(self, key: str) -> str | None:
        return self._live(key)

    async def set_text(self, key: str, value: str, *, ttl: int) -> None:
        self._values[key] = (value, self._clock() + ttl)

    async def delete(self, key: str) -> None:
        self._values.pop(key, None)


class RedisState:
    """Redis-backed state shared by every API process and Celery worker."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def incr(self, key: str, *, amount: int = 1, ttl: int) -> int:
        total = int(await self._client.incrby(key, amount))
        if total == amount:
            # First write in this window — attach the expiry once.
            await self._client.expire(key, ttl)
        return total

    async def get_int(self, key: str) -> int:
        value = await self._client.get(key)
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    async def get_text(self, key: str) -> str | None:
        value = await self._client.get(key)
        return None if value is None else str(value)

    async def set_text(self, key: str, value: str, *, ttl: int) -> None:
        await self._client.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)


@asynccontextmanager
async def open_state(redis_url: str) -> AsyncIterator[KeyValueState]:
    """Open router state for the duration of one routed call."""
    import redis.asyncio as aioredis

    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        yield RedisState(client)
    finally:
        aclose = getattr(client, "aclose", None)
        if aclose is not None:
            await aclose()
        else:
            await client.close()
