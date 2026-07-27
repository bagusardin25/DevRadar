"""OpenAI LLM provider unit tests (mocked — no live API)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.ingestion.llm_provider import (
    DisabledLLMProvider,
    ExtractionRequest,
    OpenAILLMProvider,
    _parse_json_content,
    build_llm_provider,
)


def _settings(**kwargs: str) -> Settings:
    """Build Settings from kwargs only (ignore local .env for unit tests)."""
    data = {
        "llm_provider": "disabled",
        "llm_model": "gpt-4o-mini",
        "llm_api_key": "",
        **kwargs,
    }
    return Settings.model_validate(data)


class TestParseJsonContent:
    def test_plain_object(self) -> None:
        assert _parse_json_content('{"title": "Hi"}') == {"title": "Hi"}

    def test_strips_markdown_fence(self) -> None:
        raw = '```json\n{"title": "Fenced"}\n```'
        assert _parse_json_content(raw) == {"title": "Fenced"}

    def test_rejects_non_object(self) -> None:
        with pytest.raises(ValueError, match="not a JSON object"):
            _parse_json_content("[1, 2]")


class TestBuildLlmProvider:
    def test_disabled_by_default(self) -> None:
        settings = _settings(llm_provider="disabled", llm_api_key="sk-test")
        assert isinstance(build_llm_provider(settings), DisabledLLMProvider)

    def test_openai_without_key_falls_back_disabled(self) -> None:
        settings = _settings(llm_provider="openai", llm_api_key="")
        assert isinstance(build_llm_provider(settings), DisabledLLMProvider)

    def test_openai_with_key(self) -> None:
        settings = _settings(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_key="sk-test-key",
        )
        provider = build_llm_provider(settings)
        assert isinstance(provider, OpenAILLMProvider)

    def test_unknown_provider_disabled(self) -> None:
        settings = _settings(llm_provider="anthropic", llm_api_key="x")
        assert isinstance(build_llm_provider(settings), DisabledLLMProvider)


class TestOpenAILLMProvider:
    @pytest.mark.asyncio
    async def test_extract_json_calls_chat_completions(self) -> None:
        message = SimpleNamespace(content='{"title": "From OpenAI", "mode": "online"}')
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(
            prompt_tokens=1_200,
            completion_tokens=100,
            total_tokens=1_300,
            prompt_tokens_details=SimpleNamespace(cached_tokens=200),
        )
        response = SimpleNamespace(
            choices=[choice],
            usage=usage,
            model="gpt-4o-mini-2024-07-18",
            service_tier="default",
        )

        mock_create = AsyncMock(return_value=response)
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        mock_client.close = AsyncMock()

        with patch(
            "openai.AsyncOpenAI", return_value=mock_client
        ) as mock_ctor:
            provider = OpenAILLMProvider(api_key="sk-test", model="gpt-4o-mini")
            result = await provider.extract_json(
                ExtractionRequest(
                    listing_kind="hackathon",
                    text="MegaHack online prize $10k deadline 2026-09-01",
                    url="https://example.com/hack",
                    schema_version="1.0.0",
                )
            )

        mock_ctor.assert_called_once()
        assert result.payload["title"] == "From OpenAI"
        assert result.payload["mode"] == "online"
        assert result.usage is not None
        assert result.usage.prompt_tokens == 1_200
        assert result.usage.cached_prompt_tokens == 200
        assert result.usage.completion_tokens == 100
        assert result.usage.total_tokens == 1_300
        assert str(result.usage.estimated_cost_usd()) == "0.00022500"
        kwargs = mock_create.await_args.kwargs
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["response_format"] == {"type": "json_object"}
        assert kwargs["temperature"] == 0
        assert any(m["role"] == "system" for m in kwargs["messages"])
        user_msg = next(m for m in kwargs["messages"] if m["role"] == "user")
        assert "https://example.com/hack" in user_msg["content"]
        mock_client.close.assert_awaited()

    @pytest.mark.asyncio
    async def test_empty_completion_raises(self) -> None:
        message = SimpleNamespace(content=None)
        choice = SimpleNamespace(message=message)
        response = SimpleNamespace(choices=[choice])
        mock_create = AsyncMock(return_value=response)
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        mock_client.close = AsyncMock()

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            provider = OpenAILLMProvider(api_key="sk-test", model="gpt-4o-mini")
            with pytest.raises(ValueError, match="Empty"):
                await provider.extract_json(
                    ExtractionRequest(
                        listing_kind="ai_offer",
                        text="free credits",
                        url="https://example.com/offer",
                        schema_version="1.0.0",
                    )
                )

    def test_empty_api_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            OpenAILLMProvider(api_key="", model="gpt-4o-mini")
