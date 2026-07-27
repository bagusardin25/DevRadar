"""OpenAI review provider tests (mocked; no live API calls)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai_review.llm import OpenAIReviewLLM, ReviewLLMRequest


@pytest.mark.asyncio
async def test_review_json_returns_payload_and_actual_usage() -> None:
    message = SimpleNamespace(
        content='{"recommendation":"approve","confidence":88,"summary":"Grounded."}'
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(
            prompt_tokens=750,
            completion_tokens=50,
            total_tokens=800,
            prompt_tokens_details=SimpleNamespace(cached_tokens=250),
        ),
        model="gpt-4o-mini-2024-07-18",
        service_tier="default",
    )
    mock_create = AsyncMock(return_value=response)
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    mock_client.close = AsyncMock()

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        provider = OpenAIReviewLLM(api_key="sk-test", model="gpt-4o-mini")
        result = await provider.review_json(
            ReviewLLMRequest(
                listing_kind="hackathon",
                title="Grounded Hack",
                url="https://example.com/hack",
                extracted_fields={"mode": "online"},
                verification={"status": "needs_review"},
            )
        )

    assert result.payload["recommendation"] == "approve"
    assert result.usage is not None
    assert result.usage.operation == "review"
    assert result.usage.prompt_tokens == 750
    assert result.usage.cached_prompt_tokens == 250
    assert result.usage.total_tokens == 800
    assert str(result.usage.estimated_cost_usd()) == "0.00012375"
    mock_client.close.assert_awaited_once()
