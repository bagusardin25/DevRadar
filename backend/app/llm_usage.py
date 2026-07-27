"""Token usage accounting and conservative OpenAI cost estimates."""

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
_OPENAI_PRICES: dict[tuple[str, str], TokenPrice] = {
    ("gpt-4o-mini", "default"): TokenPrice(
        input_per_million=Decimal("0.15"),
        cached_input_per_million=Decimal("0.075"),
        output_per_million=Decimal("0.60"),
    ),
    ("gpt-4o-mini", "priority"): TokenPrice(
        input_per_million=Decimal("0.25"),
        cached_input_per_million=Decimal("0.125"),
        output_per_million=Decimal("1.00"),
    ),
}


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

    @classmethod
    def from_openai_response(
        cls,
        response: object,
        *,
        operation: str,
        requested_model: str,
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
            provider="openai",
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
        return cls(
            operation=operation,
            provider=str(value.get("provider") or "openai"),
            model=model,
            service_tier=str(value.get("serviceTier") or "default"),
            prompt_tokens=_non_negative_int(value.get("promptTokens")),
            cached_prompt_tokens=_non_negative_int(value.get("cachedPromptTokens")),
            completion_tokens=_non_negative_int(value.get("completionTokens")),
            total_tokens=_non_negative_int(value.get("totalTokens")),
        )

    def estimated_cost_usd(self) -> Decimal | None:
        if self.provider.lower().strip() not in {"openai", "oai"}:
            return None
        tier = self.service_tier.lower().strip()
        if tier in {"", "standard"}:
            tier = "default"
        price = _OPENAI_PRICES.get((_canonical_model(self.model), tier))
        if price is None:
            return None
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
