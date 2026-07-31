"""Circuit breaker keeping dead providers out of the rotation.

Two ways a provider goes into cooldown:

* The failure itself says how long it is out — an exhausted quota, a 402, a
  revoked key. ``policy`` supplies that duration and the breaker honours it
  directly; there is no point counting to three first.
* Generic failures (bad response shape, transport errors) trip the breaker
  after a threshold, with the cooldown doubling on each repeat trip.

There is no separate half-open state: once the cooldown passes the provider is
eligible again, and the next failure simply doubles the next cooldown.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.llm.state import KEY_PREFIX, KeyValueState

FAILURE_THRESHOLD = 3
BASE_COOLDOWN_SECONDS = 60
MAX_COOLDOWN_SECONDS = 3_600
_COUNTER_TTL_SECONDS = 300


@dataclass(frozen=True, slots=True)
class BreakerState:
    """Consecutive failures, trip count, and when the cooldown ends."""

    failures: int = 0
    trips: int = 0
    open_until: float = 0.0

    def is_open(self, now: float) -> bool:
        return now < self.open_until


class CircuitBreaker:
    """Per-provider availability, shared across processes via Redis."""

    def __init__(
        self,
        state: KeyValueState,
        *,
        clock: Callable[[], float] = time.time,
        threshold: int = FAILURE_THRESHOLD,
    ) -> None:
        self._state = state
        self._clock = clock
        self._threshold = threshold

    async def state_of(self, provider: str) -> BreakerState:
        raw = await self._state.get_text(self._key(provider))
        if not raw:
            return BreakerState()
        parts = raw.split(":")
        if len(parts) != 3:
            return BreakerState()
        try:
            return BreakerState(
                failures=int(parts[0]), trips=int(parts[1]), open_until=float(parts[2])
            )
        except ValueError:
            return BreakerState()

    async def is_open(self, provider: str) -> bool:
        return (await self.state_of(provider)).is_open(self._clock())

    async def record_failure(self, provider: str, *, cooldown_seconds: int = 0) -> None:
        """Register a failover-worthy failure, opening the circuit when due."""
        now = self._clock()
        current = await self.state_of(provider)
        failures = current.failures + 1
        trips = current.trips
        open_until = current.open_until

        if cooldown_seconds > 0:
            trips += 1
            open_until = now + cooldown_seconds
            failures = 0
        elif failures >= self._threshold:
            trips += 1
            open_until = now + min(
                BASE_COOLDOWN_SECONDS * (2 ** (trips - 1)), MAX_COOLDOWN_SECONDS
            )
            failures = 0

        remaining = max(int(open_until - now), _COUNTER_TTL_SECONDS)
        await self._state.set_text(
            self._key(provider),
            f"{failures}:{trips}:{open_until}",
            ttl=remaining + 60,
        )

    async def record_success(self, provider: str) -> None:
        """Any success clears the failure count and the escalating cooldown."""
        await self._state.delete(self._key(provider))

    @staticmethod
    def _key(provider: str) -> str:
        return f"{KEY_PREFIX}:cb:{provider}"
