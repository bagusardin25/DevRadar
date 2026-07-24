"""LLM provider abstraction for structured extraction only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import Settings


@dataclass(slots=True)
class ExtractionRequest:
    """Request sent to an LLM provider (never logged with full prompt in prod)."""

    listing_kind: str
    text: str
    url: str
    schema_version: str
    max_chars: int = 12_000


class LLMProvider(Protocol):
    async def extract_json(self, request: ExtractionRequest) -> dict[str, object]: ...


class DisabledLLMProvider:
    """Default: no LLM calls; extractor stays rule-only."""

    async def extract_json(self, request: ExtractionRequest) -> dict[str, object]:
        return {}


class EchoLLMProvider:
    """Test double that returns a fixed payload or raises."""

    def __init__(
        self,
        payload: dict[str, object] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or {}
        self.error = error
        self.calls: list[ExtractionRequest] = []

    async def extract_json(self, request: ExtractionRequest) -> dict[str, object]:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return dict(self.payload)


def build_llm_provider(settings: Settings) -> LLMProvider:
    provider = (settings.llm_provider or "disabled").lower()
    if provider in {"", "disabled", "none", "off"}:
        return DisabledLLMProvider()
    # Future: OpenAI / SpaceXAI adapters when Task 7+ enables real extraction.
    # Keep a safe fallback so misconfiguration never crashes the pipeline.
    return DisabledLLMProvider()
