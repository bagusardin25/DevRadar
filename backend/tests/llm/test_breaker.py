"""Circuit breaker keeping dead providers out of the rotation."""

from __future__ import annotations

from app.llm.breaker import BASE_COOLDOWN_SECONDS, CircuitBreaker
from app.llm.policy import QUOTA_COOLDOWN_SECONDS
from app.llm.state import MemoryState
from tests.llm.conftest import Clock


def _breaker(clock: Clock) -> CircuitBreaker:
    return CircuitBreaker(MemoryState(clock=clock), clock=clock)


class TestExplicitCooldown:
    """When the failure says how long the provider is out, honour it."""

    async def test_quota_exhaustion_opens_immediately(self) -> None:
        clock = Clock()
        breaker = _breaker(clock)

        await breaker.record_failure("openai", cooldown_seconds=QUOTA_COOLDOWN_SECONDS)
        assert await breaker.is_open("openai") is True

    async def test_circuit_closes_once_the_cooldown_passes(self) -> None:
        clock = Clock()
        breaker = _breaker(clock)

        await breaker.record_failure("openai", cooldown_seconds=60)
        assert await breaker.is_open("openai") is True

        clock.advance(61)
        assert await breaker.is_open("openai") is False


class TestFailureThreshold:
    """Generic failures need to repeat before the provider is pulled."""

    async def test_stays_closed_below_the_threshold(self) -> None:
        clock = Clock()
        breaker = _breaker(clock)

        for _ in range(2):
            await breaker.record_failure("groq")
        assert await breaker.is_open("groq") is False

    async def test_trips_on_the_third_consecutive_failure(self) -> None:
        clock = Clock()
        breaker = _breaker(clock)

        for _ in range(3):
            await breaker.record_failure("groq")
        assert await breaker.is_open("groq") is True

        clock.advance(BASE_COOLDOWN_SECONDS + 1)
        assert await breaker.is_open("groq") is False

    async def test_cooldown_doubles_on_repeat_trips(self) -> None:
        clock = Clock()
        breaker = _breaker(clock)

        for _ in range(3):
            await breaker.record_failure("groq")
        clock.advance(BASE_COOLDOWN_SECONDS + 1)

        for _ in range(3):
            await breaker.record_failure("groq")
        # Second trip: 120s, so the first-trip duration is no longer enough.
        clock.advance(BASE_COOLDOWN_SECONDS + 1)
        assert await breaker.is_open("groq") is True

        clock.advance(BASE_COOLDOWN_SECONDS)
        assert await breaker.is_open("groq") is False


class TestRecovery:
    async def test_success_clears_the_failure_count(self) -> None:
        clock = Clock()
        breaker = _breaker(clock)

        await breaker.record_failure("groq")
        await breaker.record_failure("groq")
        await breaker.record_success("groq")
        await breaker.record_failure("groq")

        assert await breaker.is_open("groq") is False

    async def test_success_resets_the_escalating_cooldown(self) -> None:
        clock = Clock()
        breaker = _breaker(clock)

        for _ in range(3):
            await breaker.record_failure("groq")
        clock.advance(BASE_COOLDOWN_SECONDS + 1)
        await breaker.record_success("groq")

        for _ in range(3):
            await breaker.record_failure("groq")
        clock.advance(BASE_COOLDOWN_SECONDS + 1)
        assert await breaker.is_open("groq") is False

    async def test_unknown_provider_is_closed(self) -> None:
        breaker = _breaker(Clock())
        assert await breaker.is_open("never-seen") is False

    async def test_corrupt_state_is_treated_as_closed(self) -> None:
        clock = Clock()
        state = MemoryState(clock=clock)
        await state.set_text("devradar:llm:cb:groq", "garbage", ttl=300)

        breaker = CircuitBreaker(state, clock=clock)
        assert await breaker.is_open("groq") is False

    async def test_providers_are_isolated(self) -> None:
        clock = Clock()
        breaker = _breaker(clock)

        await breaker.record_failure("openai", cooldown_seconds=3_600)
        assert await breaker.is_open("openai") is True
        assert await breaker.is_open("groq") is False
