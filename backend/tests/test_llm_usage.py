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


def _routed(provider: str, **overrides: object) -> LLMCallUsage:
    base = _usage()
    data: dict[str, object] = {
        "operation": base.operation,
        "provider": provider,
        "model": base.model,
        "service_tier": base.service_tier,
        "prompt_tokens": base.prompt_tokens,
        "cached_prompt_tokens": base.cached_prompt_tokens,
        "completion_tokens": base.completion_tokens,
        "total_tokens": base.total_tokens,
    }
    data.update(overrides)
    return LLMCallUsage(**data)  # type: ignore[arg-type]


class TestFreeTierPricing:
    """Routing away from OpenAI must not turn the cost report into nulls."""

    def test_free_tier_providers_price_at_zero_not_unknown(self) -> None:
        for provider in ("groq", "gemini", "cerebras", "openrouter", "mistral", "cloudflare"):
            usage = _routed(provider, model="whatever-model-they-serve")
            assert usage.estimated_cost_usd() == 0, provider

    def test_a_free_call_keeps_the_summary_complete(self) -> None:
        summary = summarize_llm_usage([_routed("groq"), _usage()])

        assert summary["pricingComplete"] is True
        assert summary["estimatedCostUsd"] == "0.00041250"  # only the OpenAI call costs
        assert summary["providers"] == ["groq", "openai"]

    def test_an_unlisted_paid_provider_is_still_unknown(self) -> None:
        # Anything not in the free set and not priced must not be guessed at.
        assert _routed("anthropic").estimated_cost_usd() is None

    def test_oai_alias_is_priced_as_openai(self) -> None:
        assert str(_routed("oai").estimated_cost_usd()) == "0.00041250"


class TestRoutingMetadata:
    def test_snapshot_carries_the_failover_trail(self) -> None:
        usage = _routed(
            "groq", attempts=2, latency_ms=1_450, fallback_from=("openai",)
        )
        snapshot = usage.to_snapshot()

        assert snapshot["provider"] == "groq"
        assert snapshot["attempts"] == 2
        assert snapshot["latencyMs"] == 1_450
        assert snapshot["fallbackFrom"] == ["openai"]

    def test_snapshot_round_trips(self) -> None:
        usage = _routed("gemini", attempts=3, latency_ms=900, fallback_from=("groq", "openai"))
        restored = LLMCallUsage.from_snapshot(usage.to_snapshot())

        assert restored == usage

    def test_snapshots_written_before_routing_still_load(self) -> None:
        # Rows already in review_item.candidate_snapshot have none of the new keys.
        legacy = {
            "operation": "extraction",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "serviceTier": "default",
            "promptTokens": 2_000,
            "cachedPromptTokens": 500,
            "completionTokens": 250,
            "totalTokens": 2_250,
        }
        restored = LLMCallUsage.from_snapshot(legacy)

        assert restored is not None
        assert restored.attempts == 1
        assert restored.latency_ms == 0
        assert restored.fallback_from == ()
        assert str(restored.estimated_cost_usd()) == "0.00041250"
