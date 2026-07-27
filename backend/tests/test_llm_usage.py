"""Actual token accounting and conservative price estimation."""

from __future__ import annotations

from app.llm_usage import LLMCallUsage, summarize_llm_usage


def _usage(
    *,
    operation: str = "extraction",
    model: str = "gpt-4o-mini",
    service_tier: str = "default",
    prompt: int = 2_000,
    cached: int = 500,
    completion: int = 250,
) -> LLMCallUsage:
    return LLMCallUsage(
        operation=operation,
        provider="openai",
        model=model,
        service_tier=service_tier,
        prompt_tokens=prompt,
        cached_prompt_tokens=cached,
        completion_tokens=completion,
        total_tokens=prompt + completion,
    )


def test_default_tier_cost_separates_cached_input() -> None:
    usage = _usage()

    assert str(usage.estimated_cost_usd()) == "0.00041250"
    assert usage.to_snapshot()["estimatedCostUsd"] == "0.00041250"


def test_unknown_model_or_tier_never_guesses_price() -> None:
    unknown_model = _usage(model="future-model")
    automatic_tier = _usage(service_tier="auto")
    other_provider = _usage()
    other_provider = LLMCallUsage(
        operation=other_provider.operation,
        provider="other",
        model=other_provider.model,
        service_tier=other_provider.service_tier,
        prompt_tokens=other_provider.prompt_tokens,
        cached_prompt_tokens=other_provider.cached_prompt_tokens,
        completion_tokens=other_provider.completion_tokens,
        total_tokens=other_provider.total_tokens,
    )

    assert unknown_model.estimated_cost_usd() is None
    assert automatic_tier.estimated_cost_usd() is None
    assert other_provider.estimated_cost_usd() is None

    summary = summarize_llm_usage([unknown_model])
    assert summary["pricingComplete"] is False
    assert summary["estimatedCostUsd"] is None
    assert summary["totalTokens"] == 2_250


def test_aggregate_two_model_calls() -> None:
    extraction = _usage()
    review = _usage(
        operation="review",
        prompt=1_000,
        cached=0,
        completion=100,
    )

    summary = summarize_llm_usage([extraction, review, None])

    assert summary["pricingVersion"] == "2026-07-27"
    assert summary["pricingComplete"] is True
    assert summary["promptTokens"] == 3_000
    assert summary["cachedPromptTokens"] == 500
    assert summary["completionTokens"] == 350
    assert summary["totalTokens"] == 3_350
    assert summary["estimatedCostUsd"] == "0.00062250"
    assert len(summary["calls"]) == 2
