"""Token usage accounting and conservative cost estimates.

Costs stay deliberately conservative: a model or tier we have no rate for
produces usage metrics with no cost estimate, rather than a confident wrong
number. Free-tier providers are the one place we assert a price — zero — so
routing extraction away from OpenAI does not turn the cost dashboard into
nulls.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

_ONE_MILLION = Decimal("1000000")
_COST_QUANTUM = Decimal("0.00000001")
_PRICING_VERSION = "2026-07-27"


@dataclass(frozen=True, slots=True)
class TokenPrice:
    input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal


# Source: https://developers.openai.com/api/docs/pricing (verified 2026-07-27).
# Keep this deliberately small. Unknown models or service tiers produce usage
# metrics without a cost estimate instead of silently applying the wrong rate.
_PROVIDER_PRICES: dict[tuple[str, str, str], TokenPrice] = {
    ("openai", "gpt-4o-mini", "default"): TokenPrice(
        input_per_million=Decimal("0.15"),
        cached_input_per_million=Decimal("0.075"),
        output_per_million=Decimal("0.60"),
    ),
    ("openai", "gpt-4o-mini", "priority"): TokenPrice(
        input_per_million=Decimal("0.25"),
        cached_input_per_million=Decimal("0.125"),
        output_per_million=Decimal("1.00"),
    ),
}

# Providers DevRadar uses on their free tiers (docs/LLM_MULTIPROVIDER_PLAN.md).
# Calls routed to these cost nothing, so they price at exactly zero instead of
# reading as "unknown". Move a provider onto a paid plan and you must add its
# per-model rates to _PROVIDER_PRICES and drop it from this set — otherwise the
# spend it generates stays invisible.
_FREE_TIER_PROVIDERS = frozenset(
    {"gemini", "groq", "cerebras", "openrouter", "mistral", "cloudflare"}
)

_ZERO = Decimal("0")


def _non_negative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _canonical_model(model: str) -> str:
    value = (model or "").strip().lower()
    if value == "gpt-4o-mini" or value.startswith("gpt-4o-mini-"):
        return "gpt-4o-mini"
    return value


def _canonical_provider(provider: str) -> str:
    value = (provider or "").strip().lower()
    return "openai" if value in {"oai", ""} else value


def _read_attr(value: object, name: str, default: object = None) -> object:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


@dataclass(frozen=True, slots=True)
class LLMCallUsage:
    operation: str
    provider: str
    model: str
    service_tier: str
    prompt_tokens: int
    cached_prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    # Routing metadata — defaults describe a direct, first-try call so existing
    # single-provider call sites and stored snapshots stay valid.
    attempts: int = 1
    latency_ms: int = 0
    fallback_from: tuple[str, ...] = ()

    @classmethod
    def from_openai_response(
        cls,
        response: object,
        *,
        operation: str,
        requested_model: str,
        provider: str = "openai",
    ) -> LLMCallUsage | None:
        usage = _read_attr(response, "usage")
        if usage is None:
            return None
        prompt_tokens = _non_negative_int(_read_attr(usage, "prompt_tokens"))
        completion_tokens = _non_negative_int(
            _read_attr(usage, "completion_tokens")
        )
        total_tokens = _non_negative_int(_read_attr(usage, "total_tokens"))
        prompt_details = _read_attr(usage, "prompt_tokens_details")
        cached_tokens = _non_negative_int(
            _read_attr(prompt_details, "cached_tokens") if prompt_details else 0
        )
        cached_tokens = min(cached_tokens, prompt_tokens)
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        return cls(
            operation=operation,
            provider=_canonical_provider(provider),
            model=str(_read_attr(response, "model", requested_model) or requested_model),
            service_tier=str(_read_attr(response, "service_tier", "default") or "default"),
            prompt_tokens=prompt_tokens,
            cached_prompt_tokens=cached_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    @classmethod
    def from_snapshot(cls, value: object) -> LLMCallUsage | None:
        if not isinstance(value, dict):
            return None
        model = str(value.get("model") or "").strip()
        operation = str(value.get("operation") or "").strip()
        if not model or not operation:
            return None
        fallback_from = value.get("fallbackFrom")
        return cls(
            operation=operation,
            provider=str(value.get("provider") or "openai"),
            model=model,
            service_tier=str(value.get("serviceTier") or "default"),
            prompt_tokens=_non_negative_int(value.get("promptTokens")),
            cached_prompt_tokens=_non_negative_int(value.get("cachedPromptTokens")),
            completion_tokens=_non_negative_int(value.get("completionTokens")),
            total_tokens=_non_negative_int(value.get("totalTokens")),
            attempts=max(1, _non_negative_int(value.get("attempts") or 1)),
            latency_ms=_non_negative_int(value.get("latencyMs")),
            fallback_from=(
                tuple(str(item) for item in fallback_from)
                if isinstance(fallback_from, list)
                else ()
            ),
        )

    def estimated_cost_usd(self) -> Decimal | None:
        provider = _canonical_provider(self.provider)
        tier = self.service_tier.lower().strip()
        if tier in {"", "standard"}:
            tier = "default"
        price = _PROVIDER_PRICES.get((provider, _canonical_model(self.model), tier))
        if price is None:
            # A known free tier costs nothing; anything else is genuinely
            # unpriced and must not be guessed at.
            return _ZERO if provider in _FREE_TIER_PROVIDERS else None
        cached = min(self.cached_prompt_tokens, self.prompt_tokens)
        uncached = self.prompt_tokens - cached
        cost = (
            Decimal(uncached) * price.input_per_million
            + Decimal(cached) * price.cached_input_per_million
            + Decimal(self.completion_tokens) * price.output_per_million
        ) / _ONE_MILLION
        return cost.quantize(_COST_QUANTUM)

    def to_snapshot(self) -> dict[str, Any]:
        cost = self.estimated_cost_usd()
        return {
            "operation": self.operation,
            "provider": self.provider,
            "model": self.model,
            "serviceTier": self.service_tier,
            "promptTokens": self.prompt_tokens,
            "cachedPromptTokens": self.cached_prompt_tokens,
            "completionTokens": self.completion_tokens,
            "totalTokens": self.total_tokens,
            "estimatedCostUsd": format(cost, "f") if cost is not None else None,
            "attempts": self.attempts,
            "latencyMs": self.latency_ms,
            "fallbackFrom": list(self.fallback_from),
        }


@dataclass(slots=True)
class LLMJsonResult:
    payload: dict[str, object]
    usage: LLMCallUsage | None = None


def summarize_llm_usage(usages: Iterable[LLMCallUsage | None]) -> dict[str, Any]:
    calls = [usage for usage in usages if usage is not None]
    costs = [usage.estimated_cost_usd() for usage in calls]
    pricing_complete = all(cost is not None for cost in costs)
    total_cost = sum((cost for cost in costs if cost is not None), Decimal("0"))
    return {
        "currency": "USD",
        "estimated": True,
        "pricingVersion": _PRICING_VERSION,
        "pricingComplete": pricing_complete,
        # Which providers actually served this pipeline run, in call order.
        "providers": list(dict.fromkeys(usage.provider for usage in calls)),
        "promptTokens": sum(usage.prompt_tokens for usage in calls),
        "cachedPromptTokens": sum(usage.cached_prompt_tokens for usage in calls),
        "completionTokens": sum(usage.completion_tokens for usage in calls),
        "totalTokens": sum(usage.total_tokens for usage in calls),
        "estimatedCostUsd": (
            format(total_cost.quantize(_COST_QUANTUM), "f")
            if pricing_complete
            else None
        ),
        "calls": [usage.to_snapshot() for usage in calls],
    }
