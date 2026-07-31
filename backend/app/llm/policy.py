"""Failure classification — the rule that decides retry vs failover vs abort.

The distinction that matters most: a rate limit and an exhausted balance are
both HTTP 429, but they need opposite handling. A rate limit clears in seconds;
an exhausted quota does not clear until the provider's window resets. Treating
the second as the first makes the router hammer a dead provider until the
deadline expires, which is the usual reason a fallback chain never fires.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import httpx

# A 429 that clears within this many seconds is worth waiting out in place.
# Anything longer is cheaper to serve from a different provider.
INLINE_RETRY_AFTER_MAX_SECONDS = 5.0

DEFAULT_RATE_COOLDOWN_SECONDS = 60
QUOTA_COOLDOWN_SECONDS = 3_600  # balance or period quota exhausted
PAYMENT_COOLDOWN_SECONDS = 21_600  # 402 needs an operator, not a retry
DISABLED_COOLDOWN_SECONDS = 86_400  # revoked key or model that no longer exists

# Provider-specific codes that mean "you have no budget left", as opposed to
# "you are going too fast". OpenAI uses insufficient_quota; the rest mostly
# surface billing wording or a bare 402.
_QUOTA_CODES = frozenset(
    {
        "insufficient_quota",
        "quota_exceeded",
        "billing_hard_limit_reached",
        "credit_limit_reached",
        "account_deactivated",
    }
)

_QUOTA_MARKERS = (
    "insufficient_quota",
    "exceeded your current quota",
    "billing",
    "credit balance",
    "out of credits",
)

# A 400/413 caused by an oversized prompt is not a bug in our request shape —
# another provider with a bigger context window may well accept it.
_CONTEXT_MARKERS = (
    "context length",
    "context_length",
    "maximum context",
    "too many tokens",
    "reduce the length",
    "input is too long",
    "string too long",
)


class Decision(StrEnum):
    """What the router should do next."""

    RETRY_SAME = "retry_same"
    FAILOVER = "failover"
    FATAL = "fatal"


@dataclass(frozen=True, slots=True)
class Verdict:
    """Outcome of classifying one failed attempt."""

    decision: Decision
    reason: str
    cooldown_seconds: int = 0
    retry_after_seconds: float = 0.0


def _contains(haystack: str, needles: tuple[str, ...]) -> bool:
    lowered = haystack.lower()
    return any(needle in lowered for needle in needles)


def _is_quota(code: str, message: str) -> bool:
    if code.strip().lower() in _QUOTA_CODES:
        return True
    return _contains(message, _QUOTA_MARKERS)


def classify_status(
    status: int,
    *,
    code: str = "",
    message: str = "",
    retry_after: float | None = None,
) -> Verdict:
    """Classify a non-2xx provider response."""
    if status == 429:
        return _classify_rate_limited(code, message, retry_after)

    if status == 402:
        return Verdict(
            Decision.FAILOVER,
            "payment_required",
            cooldown_seconds=PAYMENT_COOLDOWN_SECONDS,
        )

    if status in {401, 403}:
        return Verdict(
            Decision.FAILOVER,
            "auth_rejected",
            cooldown_seconds=DISABLED_COOLDOWN_SECONDS,
        )

    if status == 404:
        # Free model IDs are withdrawn without notice, most visibly on
        # OpenRouter. Retrying the same model will never start working.
        return Verdict(
            Decision.FAILOVER,
            "model_not_found",
            cooldown_seconds=DISABLED_COOLDOWN_SECONDS,
        )

    if status in {408, 409, 425}:
        return Verdict(Decision.RETRY_SAME, f"transient_{status}")

    if status == 413 or (status in {400, 422} and _contains(message, _CONTEXT_MARKERS)):
        return Verdict(Decision.FAILOVER, "context_too_large")

    if status in {400, 422}:
        # Our request is malformed. Every other provider would reject it too,
        # so burning the rest of the chain on it wastes the deadline.
        return Verdict(Decision.FATAL, f"bad_request_{status}")

    if status >= 500:
        return Verdict(Decision.RETRY_SAME, f"server_error_{status}")

    return Verdict(Decision.FAILOVER, f"unexpected_status_{status}")


def _classify_rate_limited(code: str, message: str, retry_after: float | None) -> Verdict:
    if _is_quota(code, message):
        return Verdict(
            Decision.FAILOVER,
            "quota_exhausted",
            cooldown_seconds=QUOTA_COOLDOWN_SECONDS,
        )

    if retry_after is not None and retry_after <= INLINE_RETRY_AFTER_MAX_SECONDS:
        return Verdict(
            Decision.RETRY_SAME,
            "rate_limited_short",
            retry_after_seconds=retry_after,
        )

    cooldown = int(retry_after) if retry_after else DEFAULT_RATE_COOLDOWN_SECONDS
    return Verdict(Decision.FAILOVER, "rate_limited", cooldown_seconds=cooldown)


def classify_exception(exc: BaseException) -> Verdict:
    """Classify a transport-level or response-shape failure."""
    if isinstance(exc, httpx.TimeoutException):
        return Verdict(Decision.RETRY_SAME, "timeout")
    if isinstance(exc, httpx.TransportError):
        return Verdict(
            Decision.FAILOVER,
            "transport_error",
            cooldown_seconds=DEFAULT_RATE_COOLDOWN_SECONDS,
        )
    return Verdict(Decision.FAILOVER, f"invalid_response_{type(exc).__name__}")
