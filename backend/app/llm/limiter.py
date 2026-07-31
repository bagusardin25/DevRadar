"""Pre-flight rate limiting against each provider's published free-tier limits.

Checking before dispatch matters more here than in a normal client: a rejected
request still counts against some providers' quotas, and burning a 429 tells us
nothing we did not already know from the counters.

Request budgets are incremented then checked (the same INCR/EXPIRE shape as
``alerts.rate_limit``). Token budgets can only be checked for prior exhaustion,
because the cost of a call is not known until the response arrives — the actual
token count is folded back in afterwards via ``record_tokens``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.llm.registry import ProviderSpec
from app.llm.state import KEY_PREFIX, KeyValueState

# Published limits are used at 90% so concurrent workers racing on the same
# window do not overshoot the real ceiling.
SAFETY_MARGIN = 0.9

_MINUTE_TTL = 120
_DAY_TTL = 90_000  # a little over 25h; the key name already carries the date


@dataclass(frozen=True, slots=True)
class LimitUsage:
    """Counters for one provider, for the admin status endpoint."""

    rpm_used: int
    rpd_used: int
    tpm_used: int
    tpd_used: int


def effective_limit(limit: int | None, *, margin: float = SAFETY_MARGIN) -> int | None:
    """Published limit reduced by the safety margin."""
    if limit is None:
        return None
    return max(1, int(limit * margin))


class LLMRateLimiter:
    """Fixed-window counters per provider, shared across processes via Redis."""

    def __init__(
        self,
        state: KeyValueState,
        *,
        clock: Callable[[], float] = time.time,
        margin: float = SAFETY_MARGIN,
    ) -> None:
        self._state = state
        self._clock = clock
        self._margin = margin

    async def try_acquire(self, spec: ProviderSpec) -> str | None:
        """Admit a call, or return the reason this provider must be skipped."""
        now = self._clock()
        limits = spec.limits

        # Token budgets first: they are read-only, so a rejection here does not
        # consume a request slot.
        if await self._is_exhausted(spec.name, "tpm", limits.tpm, self._minute(now)):
            return "tpm_exhausted"
        if await self._is_exhausted(spec.name, "tpd", limits.tpd, self._day(now)):
            return "tpd_exhausted"

        rpm_limit = effective_limit(limits.rpm, margin=self._margin)
        if rpm_limit is not None:
            key = self._key(spec.name, "rpm", self._minute(now))
            if await self._state.incr(key, ttl=_MINUTE_TTL) > rpm_limit:
                return "rpm_exhausted"

        rpd_limit = effective_limit(limits.rpd, margin=self._margin)
        if rpd_limit is not None:
            key = self._key(spec.name, "rpd", self._day(now))
            if await self._state.incr(key, ttl=_DAY_TTL) > rpd_limit:
                return "rpd_exhausted"

        return None

    async def record_tokens(self, spec: ProviderSpec, total_tokens: int) -> None:
        """Fold the real token cost back into the minute and day budgets."""
        if total_tokens <= 0:
            return
        now = self._clock()
        if spec.limits.tpm is not None:
            await self._state.incr(
                self._key(spec.name, "tpm", self._minute(now)),
                amount=total_tokens,
                ttl=_MINUTE_TTL,
            )
        if spec.limits.tpd is not None:
            await self._state.incr(
                self._key(spec.name, "tpd", self._day(now)),
                amount=total_tokens,
                ttl=_DAY_TTL,
            )

    async def usage(self, spec: ProviderSpec) -> LimitUsage:
        """Current window counters, for operator visibility."""
        now = self._clock()
        minute, day = self._minute(now), self._day(now)
        return LimitUsage(
            rpm_used=await self._state.get_int(self._key(spec.name, "rpm", minute)),
            rpd_used=await self._state.get_int(self._key(spec.name, "rpd", day)),
            tpm_used=await self._state.get_int(self._key(spec.name, "tpm", minute)),
            tpd_used=await self._state.get_int(self._key(spec.name, "tpd", day)),
        )

    async def _is_exhausted(
        self, provider: str, window: str, limit: int | None, bucket: str
    ) -> bool:
        ceiling = effective_limit(limit, margin=self._margin)
        if ceiling is None:
            return False
        used = await self._state.get_int(self._key(provider, window, bucket))
        return used >= ceiling

    @staticmethod
    def _key(provider: str, window: str, bucket: str) -> str:
        return f"{KEY_PREFIX}:rl:{provider}:{window}:{bucket}"

    @staticmethod
    def _minute(now: float) -> str:
        return str(int(now // 60))

    @staticmethod
    def _day(now: float) -> str:
        # Providers that publish a daily quota reset at 00:00 UTC.
        return time.strftime("%Y%m%d", time.gmtime(now))
