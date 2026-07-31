"""Router behaviour: rotation, failover, skipping, and the deadline."""

from __future__ import annotations

import httpx
import pytest

from app.llm.adapter import ChatRequest
from app.llm.breaker import CircuitBreaker
from app.llm.errors import AllProvidersFailedError, NoProviderAvailableError, ProviderHTTPError
from app.llm.limiter import LLMRateLimiter
from app.llm.registry import ProviderSpec
from app.llm.router import LLMRouter
from app.llm.state import MemoryState
from tests.llm.conftest import (
    Clock,
    RecordingTransport,
    error_response,
    make_spec,
    no_sleep,
    ok_response,
)

EXTRACT = ChatRequest(operation="extraction", system="s", user="u")


def _router(
    specs: list[ProviderSpec],
    transport: RecordingTransport,
    *,
    clock: Clock | None = None,
    state: MemoryState | None = None,
    strategy: str = "weighted",
    max_attempts: int = 4,
    deadline_seconds: float = 90.0,
) -> tuple[LLMRouter, httpx.AsyncClient]:
    clock = clock or Clock()
    client = transport.client()
    router = LLMRouter(
        specs,
        strategy=strategy,
        max_attempts=max_attempts,
        deadline_seconds=deadline_seconds,
        state=state if state is not None else MemoryState(clock=clock),
        client=client,
        clock=clock,
        sleep=no_sleep,
    )
    return router, client


class TestHappyPath:
    async def test_first_healthy_provider_serves(self) -> None:
        transport = RecordingTransport({"groq": ok_response('{"title": "Routed"}')})
        router, client = _router([make_spec("groq")], transport)

        async with client:
            result = await router.chat_json(EXTRACT)

        assert result.payload == {"title": "Routed"}
        assert result.provider == "groq"
        assert result.attempts == 1
        assert result.fallback_from == []

    async def test_usage_records_the_provider_that_served(self) -> None:
        transport = RecordingTransport({"groq": ok_response()})
        router, client = _router([make_spec("groq")], transport)

        async with client:
            result = await router.chat_json(EXTRACT)

        assert result.usage is not None
        assert result.usage.provider == "groq"
        assert result.usage.operation == "extraction"
        assert result.usage.total_tokens == 120
        # A free tier prices at zero rather than reading as unknown.
        assert result.usage.estimated_cost_usd() == 0

    async def test_no_provider_for_the_operation(self) -> None:
        transport = RecordingTransport({})
        router, client = _router([make_spec("groq", operations=("extraction",))], transport)

        async with client:
            with pytest.raises(NoProviderAvailableError):
                await router.chat_json(ChatRequest(operation="review", system="s", user="u"))


class TestFailover:
    async def test_exhausted_quota_moves_to_the_next_provider(self) -> None:
        # The case this whole system exists for: OpenAI's balance runs out.
        transport = RecordingTransport(
            {
                "openai": error_response(429, code="insufficient_quota", message="no budget"),
                "groq": ok_response('{"title": "From Groq"}'),
            }
        )
        specs = [make_spec("openai", priority=10), make_spec("groq", priority=20)]
        router, client = _router(specs, transport)

        async with client:
            result = await router.chat_json(EXTRACT)

        assert result.provider == "groq"
        assert result.fallback_from == ["openai"]
        assert result.attempts == 2
        assert result.usage is not None
        assert result.usage.fallback_from == ("openai",)

    async def test_quota_failure_opens_the_circuit_for_later_calls(self) -> None:
        clock = Clock()
        state = MemoryState(clock=clock)
        transport = RecordingTransport(
            {
                "openai": error_response(429, code="insufficient_quota"),
                "groq": ok_response(),
            }
        )
        specs = [make_spec("openai", priority=10), make_spec("groq", priority=20)]
        router, client = _router(specs, transport, clock=clock, state=state)

        async with client:
            await router.chat_json(EXTRACT)
            await router.chat_json(EXTRACT)

        # The second call must not touch the provider we already know is dry.
        assert transport.hits("openai") == 1
        assert transport.hits("groq") == 2

    async def test_server_error_retries_once_then_fails_over(self) -> None:
        transport = RecordingTransport(
            {"gemini": error_response(503, message="unavailable"), "groq": ok_response()}
        )
        specs = [make_spec("gemini", priority=10), make_spec("groq", priority=20)]
        router, client = _router(specs, transport)

        async with client:
            result = await router.chat_json(EXTRACT)

        assert transport.hits("gemini") == 2  # original + one inline retry
        assert result.provider == "groq"

    async def test_short_retry_after_is_waited_out_in_place(self) -> None:
        transport = RecordingTransport(
            {
                "groq": [
                    error_response(429, code="rate_limit_exceeded", retry_after=1),
                    ok_response('{"title": "Second try"}'),
                ]
            }
        )
        router, client = _router([make_spec("groq")], transport)

        async with client:
            result = await router.chat_json(EXTRACT)

        assert result.provider == "groq"
        assert result.payload == {"title": "Second try"}

    async def test_unparseable_json_fails_over(self) -> None:
        transport = RecordingTransport(
            {"groq": ok_response("not json at all"), "gemini": ok_response('{"ok": true}')}
        )
        specs = [make_spec("groq", priority=10), make_spec("gemini", priority=20)]
        router, client = _router(specs, transport)

        async with client:
            result = await router.chat_json(EXTRACT)

        assert result.provider == "gemini"

    async def test_every_provider_failing_raises(self) -> None:
        transport = RecordingTransport(
            {
                "groq": error_response(500),
                "gemini": error_response(500),
            }
        )
        specs = [make_spec("groq", priority=10), make_spec("gemini", priority=20)]
        router, client = _router(specs, transport)

        async with client:
            with pytest.raises(AllProvidersFailedError) as excinfo:
                await router.chat_json(EXTRACT)

        assert "groq" in str(excinfo.value)
        assert "gemini" in str(excinfo.value)


class TestFatalRequests:
    async def test_malformed_request_does_not_burn_the_chain(self) -> None:
        # A 400 is our bug; every provider would reject it identically.
        transport = RecordingTransport(
            {"groq": error_response(400, message="invalid parameter"), "gemini": ok_response()}
        )
        specs = [make_spec("groq", priority=10), make_spec("gemini", priority=20)]
        router, client = _router(specs, transport)

        async with client:
            with pytest.raises(ProviderHTTPError):
                await router.chat_json(EXTRACT)

        assert transport.hits("gemini") == 0

    async def test_oversized_context_still_fails_over(self) -> None:
        transport = RecordingTransport(
            {
                "cerebras": error_response(
                    400, message="This model's maximum context length is 8192 tokens"
                ),
                "gemini": ok_response(),
            }
        )
        specs = [make_spec("cerebras", priority=10), make_spec("gemini", priority=20)]
        router, client = _router(specs, transport)

        async with client:
            result = await router.chat_json(EXTRACT)

        assert result.provider == "gemini"


class TestJsonModeDowngrade:
    async def test_rejected_response_format_retries_one_step_weaker(self) -> None:
        def handler(call_index: int) -> httpx.Response:
            if call_index == 0:
                return error_response(
                    400, code="invalid_request", message="response_format is not supported"
                )
            return ok_response('{"title": "Downgraded"}')

        transport = RecordingTransport({"cerebras": handler})
        router, client = _router([make_spec("cerebras", json_mode="json_schema")], transport)

        async with client:
            result = await router.chat_json(EXTRACT)

        assert result.payload == {"title": "Downgraded"}
        assert "response_format" not in transport.calls[1][1] or transport.calls[1][1][
            "response_format"
        ] == {"type": "json_object"}


class TestSkipping:
    async def test_open_circuit_is_skipped_without_an_http_call(self) -> None:
        clock = Clock()
        state = MemoryState(clock=clock)
        breaker = CircuitBreaker(state, clock=clock)
        await breaker.record_failure("openai", cooldown_seconds=3_600)

        transport = RecordingTransport({"openai": ok_response(), "groq": ok_response()})
        specs = [make_spec("openai", priority=10), make_spec("groq", priority=20)]
        router, client = _router(specs, transport, clock=clock, state=state)

        async with client:
            result = await router.chat_json(EXTRACT)

        assert result.provider == "groq"
        assert transport.hits("openai") == 0
        assert result.attempts == 1  # a skip is not an attempt

    async def test_spent_rate_window_is_skipped_without_an_http_call(self) -> None:
        clock = Clock()
        state = MemoryState(clock=clock)
        spent = make_spec("groq", priority=10, rpm=2)
        limiter = LLMRateLimiter(state, clock=clock)
        for _ in range(2):
            await limiter.try_acquire(spent)

        transport = RecordingTransport({"groq": ok_response(), "gemini": ok_response()})
        router, client = _router(
            [spent, make_spec("gemini", priority=20)], transport, clock=clock, state=state
        )

        async with client:
            result = await router.chat_json(EXTRACT)

        assert result.provider == "gemini"
        assert transport.hits("groq") == 0

    async def test_token_use_is_recorded_against_the_daily_budget(self) -> None:
        clock = Clock()
        state = MemoryState(clock=clock)
        spec = make_spec("cerebras", tpd=1_000_000)
        transport = RecordingTransport({"cerebras": ok_response()})
        router, client = _router([spec], transport, clock=clock, state=state)

        async with client:
            await router.chat_json(EXTRACT)

        usage = await LLMRateLimiter(state, clock=clock).usage(spec)
        assert usage.tpd_used == 120


class TestBudgets:
    async def test_attempt_cap_stops_the_walk(self) -> None:
        transport = RecordingTransport({name: error_response(500) for name in "abcd"})
        specs = [make_spec(name, priority=10 + index) for index, name in enumerate("abcd")]
        router, client = _router(specs, transport, max_attempts=2)

        async with client:
            with pytest.raises(AllProvidersFailedError) as excinfo:
                await router.chat_json(EXTRACT)

        assert "attempt_budget_spent" in str(excinfo.value)
        assert len(transport.calls) == 4  # two providers, each retried once

    async def test_deadline_stops_the_walk(self) -> None:
        clock = Clock()

        def slow(_call_index: int) -> httpx.Response:
            clock.advance(40)
            return error_response(500)

        transport = RecordingTransport({name: slow for name in ("a", "b", "c")})
        specs = [make_spec(name, priority=10 + index) for index, name in enumerate("abc")]
        router, client = _router(specs, transport, clock=clock, deadline_seconds=90.0)

        async with client:
            with pytest.raises(AllProvidersFailedError) as excinfo:
                await router.chat_json(EXTRACT)

        assert "deadline_spent" in str(excinfo.value)


class TestRotation:
    async def test_weighted_rotation_spreads_calls_across_a_tier(self) -> None:
        clock = Clock()
        state = MemoryState(clock=clock)
        transport = RecordingTransport(
            {"groq": ok_response(), "gemini": ok_response(), "cerebras": ok_response()}
        )
        specs = [
            make_spec("groq", priority=10),
            make_spec("gemini", priority=10),
            make_spec("cerebras", priority=10),
        ]
        router, client = _router(specs, transport, clock=clock, state=state)

        async with client:
            for _ in range(6):
                await router.chat_json(EXTRACT)

        assert transport.hits("groq") == 2
        assert transport.hits("gemini") == 2
        assert transport.hits("cerebras") == 2

    async def test_weight_biases_the_share(self) -> None:
        clock = Clock()
        state = MemoryState(clock=clock)
        transport = RecordingTransport({"groq": ok_response(), "mistral": ok_response()})
        specs = [
            make_spec("groq", priority=10, weight=3),
            make_spec("mistral", priority=10, weight=1),
        ]
        router, client = _router(specs, transport, clock=clock, state=state)

        async with client:
            for _ in range(8):
                await router.chat_json(EXTRACT)

        assert transport.hits("groq") == 6
        assert transport.hits("mistral") == 2

    async def test_priority_strategy_keeps_a_fixed_order(self) -> None:
        clock = Clock()
        state = MemoryState(clock=clock)
        transport = RecordingTransport({"groq": ok_response(), "gemini": ok_response()})
        specs = [make_spec("groq", priority=10), make_spec("gemini", priority=10)]
        router, client = _router(specs, transport, clock=clock, state=state, strategy="priority")

        async with client:
            for _ in range(4):
                await router.chat_json(EXTRACT)

        assert transport.hits("gemini") == 4  # sorted by name inside the tier
        assert transport.hits("groq") == 0

    async def test_tiers_are_honoured_before_rotation(self) -> None:
        clock = Clock()
        state = MemoryState(clock=clock)
        transport = RecordingTransport({"groq": ok_response(), "openai": ok_response()})
        specs = [make_spec("groq", priority=10), make_spec("openai", priority=20)]
        router, client = _router(specs, transport, clock=clock, state=state)

        async with client:
            for _ in range(3):
                await router.chat_json(EXTRACT)

        assert transport.hits("groq") == 3
        assert transport.hits("openai") == 0
