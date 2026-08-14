"""Pre-flight rate limiting against published free-tier ceilings."""

from __future__ import annotations

from app.llm.limiter import LLMRateLimiter, effective_limit
from app.llm.state import MemoryState
from tests.llm.conftest import Clock, make_spec


def _limiter(clock: Clock) -> LLMRateLimiter:
    return LLMRateLimiter(MemoryState(clock=clock), clock=clock)


class TestSafetyMargin:
    def test_published_limits_are_used_at_ninety_percent(self) -> None:
        # Concurrent workers race on the same window, so leave headroom.
        assert effective_limit(30) == 27
        assert effective_limit(1000) == 900
        assert effective_limit(None) is None

    def test_tiny_limits_never_round_to_zero(self) -> None:
        assert effective_limit(1) == 1


class TestRequestWindows:
    async def test_rpm_admits_up_to_the_effective_ceiling(self) -> None:
        clock = Clock()
        limiter = _limiter(clock)
        spec = make_spec("groq", rpm=10)

        for _ in range(9):
            assert await limiter.try_acquire(spec) is None
        assert await limiter.try_acquire(spec) == "rpm_exhausted"

    async def test_minute_window_rolls_over(self) -> None:
        clock = Clock()
        limiter = _limiter(clock)
        spec = make_spec("groq", rpm=10)

        for _ in range(9):
            await limiter.try_acquire(spec)
        assert await limiter.try_acquire(spec) == "rpm_exhausted"

        clock.advance(60)
        assert await limiter.try_acquire(spec) is None

    async def test_daily_requests_survive_the_minute_rollover(self) -> None:
        clock = Clock()
        limiter = _limiter(clock)
        spec = make_spec("cerebras", rpd=10)

        for _ in range(9):
            assert await limiter.try_acquire(spec) is None
        clock.advance(120)
        assert await limiter.try_acquire(spec) == "rpd_exhausted"

    async def test_providers_have_independent_budgets(self) -> None:
        clock = Clock()
        limiter = _limiter(clock)
        groq = make_spec("groq", rpm=2)
        gemini = make_spec("gemini", rpm=2)

        assert await limiter.try_acquire(groq) is None
        assert await limiter.try_acquire(groq) == "rpm_exhausted"
        assert await limiter.try_acquire(gemini) is None

    async def test_unmetered_provider_is_always_admitted(self) -> None:
        clock = Clock()
        limiter = _limiter(clock)
        spec = make_spec("openai")

        for _ in range(50):
            assert await limiter.try_acquire(spec) is None


class TestTokenBudgets:
    async def test_daily_tokens_block_once_spent(self) -> None:
        clock = Clock()
        limiter = _limiter(clock)
        spec = make_spec("cerebras", tpd=1_000)

        assert await limiter.try_acquire(spec) is None
        await limiter.record_tokens(spec, 899)
        assert await limiter.try_acquire(spec) is None

        await limiter.record_tokens(spec, 1)
        assert await limiter.try_acquire(spec) == "tpd_exhausted"

    async def test_token_rejection_does_not_consume_a_request_slot(self) -> None:
        # Token budgets are checked before request counters are incremented.
        clock = Clock()
        limiter = _limiter(clock)
        spec = make_spec("cerebras", rpm=10, tpd=1_000)

        await limiter.record_tokens(spec, 900)
        assert await limiter.try_acquire(spec) == "tpd_exhausted"

        usage = await limiter.usage(spec)
        assert usage.rpm_used == 0

    async def test_minute_tokens_roll_over(self) -> None:
        clock = Clock()
        limiter = _limiter(clock)
        spec = make_spec("groq", tpm=1_000)

        await limiter.record_tokens(spec, 900)
        assert await limiter.try_acquire(spec) == "tpm_exhausted"

        clock.advance(60)
        assert await limiter.try_acquire(spec) is None

    async def test_usage_snapshot_reports_all_windows(self) -> None:
        clock = Clock()
        limiter = _limiter(clock)
        spec = make_spec("groq", rpm=10, rpd=100, tpm=1_000, tpd=10_000)

        await limiter.try_acquire(spec)
        await limiter.record_tokens(spec, 250)

        usage = await limiter.usage(spec)
        assert usage.rpm_used == 1
        assert usage.rpd_used == 1
        assert usage.tpm_used == 250
        assert usage.tpd_used == 250


class TestReviewReserve:
    async def test_extraction_stops_before_review_on_dual_role_provider(self) -> None:
        # rpd=10 → effective 9. 20% reserve = 1 slot. Extraction ceiling = 8.
        clock = Clock()
        limiter = LLMRateLimiter(MemoryState(clock=clock), clock=clock, reserve_ratio=0.2)
        gemini = make_spec("gemini", rpd=10, operations=("extraction", "review"))

        for _ in range(8):
            assert await limiter.try_acquire(gemini, operation="extraction") is None
        assert await limiter.try_acquire(gemini, operation="extraction") == "rpd_reserved"
        # The reserved slot is still there for the admin review path.
        assert await limiter.try_acquire(gemini, operation="review") is None

    async def test_reserve_does_not_apply_to_extraction_only_providers(self) -> None:
        clock = Clock()
        limiter = LLMRateLimiter(MemoryState(clock=clock), clock=clock, reserve_ratio=0.2)
        groq = make_spec("groq", rpd=10, operations=("extraction",))

        for _ in range(9):
            assert await limiter.try_acquire(groq, operation="extraction") is None
        assert await limiter.try_acquire(groq, operation="extraction") == "rpd_exhausted"

    async def test_reserve_rejection_does_not_consume_the_held_slot(self) -> None:
        clock = Clock()
        limiter = LLMRateLimiter(MemoryState(clock=clock), clock=clock, reserve_ratio=0.2)
        gemini = make_spec("gemini", rpd=10, operations=("extraction", "review"))

        for _ in range(8):
            await limiter.try_acquire(gemini, operation="extraction")
        await limiter.try_acquire(gemini, operation="extraction")  # reserved

        usage = await limiter.usage(gemini)
        assert usage.rpd_used == 8

    async def test_token_reserve_blocks_extraction_before_review(self) -> None:
        clock = Clock()
        limiter = LLMRateLimiter(MemoryState(clock=clock), clock=clock, reserve_ratio=0.2)
        gemini = make_spec("gemini", tpd=1_000, operations=("extraction", "review"))

        await limiter.record_tokens(gemini, 720)  # 90% of 1000 = 900; 20% of 900 = 180; ceil=720
        assert await limiter.try_acquire(gemini, operation="extraction") == "tpd_reserved"
        assert await limiter.try_acquire(gemini, operation="review") is None
