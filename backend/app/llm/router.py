"""Provider router: rotation, failover, and the deadline that bounds them.

One routed call walks the priority tiers in order. Inside a tier providers are
rotated by weight, so ordinary traffic spreads across the free tiers instead of
hammering whichever one happens to be first. A provider is skipped without an
HTTP request when its circuit is open or its rate window is spent; it is
dropped from the chain when it fails in a way another provider could survive.

The whole walk is bounded by a single deadline. Without it, six providers at
thirty seconds each would leave a Celery task hanging for minutes on the way to
the same fallback the caller already has.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace

import httpx

from app.llm.adapter import ChatRequest, ChatResult, complete
from app.llm.breaker import CircuitBreaker
from app.llm.capabilities import JsonMode, downgrade
from app.llm.errors import AllProvidersFailedError, NoProviderAvailableError, ProviderHTTPError
from app.llm.json_parse import parse_json_object
from app.llm.limiter import LLMRateLimiter
from app.llm.policy import Decision, Verdict, classify_exception, classify_status
from app.llm.registry import ProviderSpec, providers_for
from app.llm.state import KEY_PREFIX, KeyValueState, open_state
from app.llm_usage import LLMCallUsage

logger = logging.getLogger(__name__)

DEFAULT_DEADLINE_SECONDS = 90.0
DEFAULT_MAX_ATTEMPTS = 4

# Starting an attempt with less than this left cannot produce anything useful.
_MIN_ATTEMPT_SECONDS = 5.0
# Small by design: Celery already retries the surrounding task.
_BACKOFF_SECONDS = 0.3
_MAX_JSON_DOWNGRADES = 2
_ROTATION_TTL = 3_600

# A 400 naming the response format is our request being wrong for this
# provider, not a malformed prompt — the weaker JSON mode usually works.
_FORMAT_MARKERS = (
    "response_format",
    "json_schema",
    "json_object",
    "structured output",
    "structured_outputs",
)


@dataclass(slots=True)
class RoutedResult:
    """A parsed JSON answer plus how the router got there."""

    payload: dict[str, object]
    usage: LLMCallUsage | None
    provider: str
    attempts: int
    latency_ms: int
    fallback_from: list[str] = field(default_factory=list)


class _AttemptFailedError(Exception):
    """Internal: one provider is done; the verdict says what happens next."""

    def __init__(self, verdict: Verdict, cause: Exception) -> None:
        self.verdict = verdict
        self.cause = cause
        super().__init__(str(cause))


class LLMRouter:
    """Routes one JSON completion across the configured providers."""

    def __init__(
        self,
        specs: list[ProviderSpec],
        *,
        redis_url: str = "",
        strategy: str = "weighted",
        deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        state: KeyValueState | None = None,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._specs = list(specs)
        self._redis_url = redis_url
        self._strategy = strategy if strategy in {"weighted", "priority"} else "weighted"
        self._deadline = deadline_seconds
        self._max_attempts = max(1, max_attempts)
        self._state = state
        self._client = client
        self._clock = clock
        self._sleep = sleep

    @property
    def specs(self) -> list[ProviderSpec]:
        return list(self._specs)

    def serves(self, operation: str) -> bool:
        return any(spec.serves(operation) for spec in self._specs)

    async def chat_json(self, request: ChatRequest) -> RoutedResult:
        """Return the first provider's parsed JSON answer, or raise."""
        tiers = providers_for(self._specs, request.operation)
        if not tiers:
            raise NoProviderAvailableError(request.operation)

        started = self._clock()
        deadline = started + self._deadline
        trail: list[str] = []
        fallback_from: list[str] = []
        attempts = 0

        async with self._open_state() as state, self._open_client() as client:
            limiter = LLMRateLimiter(state, clock=self._clock)
            breaker = CircuitBreaker(state, clock=self._clock)

            for tier in tiers:
                for spec in await self._order(state, tier, request.operation):
                    if attempts >= self._max_attempts:
                        trail.append("attempt_budget_spent")
                        raise AllProvidersFailedError(request.operation, trail)
                    if deadline - self._clock() <= _MIN_ATTEMPT_SECONDS:
                        trail.append("deadline_spent")
                        raise AllProvidersFailedError(request.operation, trail)

                    skip = await self._skip_reason(spec, breaker, limiter)
                    if skip is not None:
                        trail.append(f"{spec.name}:{skip}")
                        continue

                    attempts += 1
                    try:
                        payload, result = await self._attempt(
                            client, spec, request, deadline=deadline
                        )
                    except _AttemptFailedError as failure:
                        if failure.verdict.decision is Decision.FATAL:
                            # Malformed request: every provider would reject it.
                            logger.warning(
                                "llm_request_rejected",
                                extra={
                                    "provider": spec.name,
                                    "operation": request.operation,
                                    "reason": failure.verdict.reason,
                                },
                            )
                            raise failure.cause from None
                        await breaker.record_failure(
                            spec.name,
                            cooldown_seconds=failure.verdict.cooldown_seconds,
                        )
                        trail.append(f"{spec.name}:{failure.verdict.reason}")
                        fallback_from.append(spec.name)
                        logger.warning(
                            "llm_provider_failed",
                            extra={
                                "provider": spec.name,
                                "operation": request.operation,
                                "reason": failure.verdict.reason,
                                "cooldown_seconds": failure.verdict.cooldown_seconds,
                            },
                        )
                        continue

                    await breaker.record_success(spec.name)
                    latency_ms = int((self._clock() - started) * 1000)
                    usage = LLMCallUsage.from_openai_response(
                        result.raw,
                        operation=request.operation,
                        requested_model=spec.model,
                        provider=spec.name,
                    )
                    if usage is not None:
                        await limiter.record_tokens(spec, usage.total_tokens)
                        usage = replace(
                            usage,
                            attempts=attempts,
                            latency_ms=latency_ms,
                            fallback_from=tuple(fallback_from),
                        )

                    logger.info(
                        "llm_route_selected",
                        extra={
                            "provider": spec.name,
                            "model": spec.model,
                            "operation": request.operation,
                            "attempts": attempts,
                            "latency_ms": latency_ms,
                        },
                    )
                    return RoutedResult(
                        payload=payload,
                        usage=usage,
                        provider=spec.name,
                        attempts=attempts,
                        latency_ms=latency_ms,
                        fallback_from=fallback_from,
                    )

        logger.warning(
            "llm_all_failed",
            extra={"operation": request.operation, "attempts": attempts, "trail": trail},
        )
        raise AllProvidersFailedError(request.operation, trail)

    # --- one provider -------------------------------------------------------

    async def _attempt(
        self,
        client: httpx.AsyncClient,
        spec: ProviderSpec,
        request: ChatRequest,
        *,
        deadline: float,
    ) -> tuple[dict[str, object], ChatResult]:
        """Call one provider, allowing one inline retry and JSON downgrades."""
        json_mode: JsonMode = spec.capabilities.json_mode
        downgrades = 0
        retried = False

        while True:
            try:
                result = await complete(
                    client,
                    spec,
                    request,
                    json_mode=json_mode,
                    timeout=self._timeout_for(spec, deadline),
                )
                return parse_json_object(result.content), result
            except Exception as exc:
                verdict = self._classify(exc)

                weaker = self._weaker_mode(exc, verdict, json_mode, downgrades)
                if weaker is not None:
                    logger.info(
                        "llm_json_mode_downgraded",
                        extra={"provider": spec.name, "from": json_mode, "to": weaker},
                    )
                    json_mode = weaker
                    downgrades += 1
                    continue

                if (
                    verdict.decision is Decision.RETRY_SAME
                    and not retried
                    and deadline - self._clock() > _MIN_ATTEMPT_SECONDS
                ):
                    retried = True
                    await self._sleep(self._backoff(verdict))
                    continue

                if verdict.decision is Decision.RETRY_SAME:
                    # Out of inline retries: hand the provider over to failover.
                    verdict = Verdict(
                        Decision.FAILOVER,
                        verdict.reason,
                        cooldown_seconds=verdict.cooldown_seconds,
                    )
                raise _AttemptFailedError(verdict, exc) from exc

    @staticmethod
    def _classify(exc: Exception) -> Verdict:
        if isinstance(exc, ProviderHTTPError):
            return classify_status(
                exc.status,
                code=exc.code,
                message=exc.message,
                retry_after=exc.retry_after,
            )
        return classify_exception(exc)

    @staticmethod
    def _weaker_mode(
        exc: Exception, verdict: Verdict, json_mode: JsonMode, downgrades: int
    ) -> JsonMode | None:
        """The next JSON mode to try when a provider rejected this one."""
        if verdict.decision is not Decision.FATAL or downgrades >= _MAX_JSON_DOWNGRADES:
            return None
        if not isinstance(exc, ProviderHTTPError):
            return None
        haystack = f"{exc.code} {exc.message}".lower()
        if not any(marker in haystack for marker in _FORMAT_MARKERS):
            return None
        return downgrade(json_mode)

    @staticmethod
    def _backoff(verdict: Verdict) -> float:
        if verdict.retry_after_seconds > 0:
            return verdict.retry_after_seconds
        return _BACKOFF_SECONDS * (0.5 + random.random())

    def _timeout_for(self, spec: ProviderSpec, deadline: float) -> httpx.Timeout:
        remaining = max(deadline - self._clock(), _MIN_ATTEMPT_SECONDS)
        return httpx.Timeout(
            min(spec.read_timeout, remaining),
            connect=min(spec.connect_timeout, remaining),
        )

    # --- selection ----------------------------------------------------------

    async def _skip_reason(
        self,
        spec: ProviderSpec,
        breaker: CircuitBreaker,
        limiter: LLMRateLimiter,
    ) -> str | None:
        if await breaker.is_open(spec.name):
            return "circuit_open"
        return await limiter.try_acquire(spec)

    async def _order(
        self, state: KeyValueState, tier: list[ProviderSpec], operation: str
    ) -> list[ProviderSpec]:
        """Rotate a priority tier by weight; ties fall back to a stable order."""
        if len(tier) == 1 or self._strategy == "priority":
            return list(tier)

        expanded = [spec for spec in tier for _ in range(spec.weight)]
        key = f"{KEY_PREFIX}:rr:{operation}:{tier[0].priority_for(operation)}"
        cursor = await state.incr(key, ttl=_ROTATION_TTL)
        start = (cursor - 1) % len(expanded)
        rotated = expanded[start:] + expanded[:start]

        seen: set[str] = set()
        order: list[ProviderSpec] = []
        for spec in rotated:
            if spec.name not in seen:
                seen.add(spec.name)
                order.append(spec)
        return order

    # --- resources ----------------------------------------------------------

    @asynccontextmanager
    async def _open_state(self) -> AsyncIterator[KeyValueState]:
        if self._state is not None:
            yield self._state
            return
        async with open_state(self._redis_url) as state:
            yield state

    @asynccontextmanager
    async def _open_client(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._client is not None:
            yield self._client
            return
        async with httpx.AsyncClient() as client:
            yield client
