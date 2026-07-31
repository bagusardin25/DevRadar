"""LLM provider abstraction for structured extraction only (no web search)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from app.config import Settings
from app.llm.adapter import ChatRequest
from app.llm.json_parse import parse_json_object as _parse_json_content
from app.llm.router import LLMRouter
from app.llm_usage import LLMCallUsage, LLMJsonResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExtractionRequest:
    """Request sent to an LLM provider (never log full prompt text in prod)."""

    listing_kind: str
    text: str
    url: str
    schema_version: str
    max_chars: int = 12_000


class LLMProvider(Protocol):
    async def extract_json(self, request: ExtractionRequest) -> LLMJsonResult: ...


class DisabledLLMProvider:
    """Default: no LLM calls; extractor stays rule-only."""

    async def extract_json(self, request: ExtractionRequest) -> LLMJsonResult:
        return LLMJsonResult(payload={})


class EchoLLMProvider:
    """Test double that returns a fixed payload or raises."""

    def __init__(
        self,
        payload: dict[str, object] | None = None,
        *,
        error: Exception | None = None,
        usage: LLMCallUsage | None = None,
    ) -> None:
        self.payload = payload or {}
        self.error = error
        self.usage = usage
        self.calls: list[ExtractionRequest] = []

    async def extract_json(self, request: ExtractionRequest) -> LLMJsonResult:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return LLMJsonResult(payload=dict(self.payload), usage=self.usage)


_HACKATHON_SCHEMA_HINT = """
Return a JSON object with optional keys only (omit unknowns):
title, description, organizer, registration_open_at, registration_deadline,
submission_deadline, mode (online|hybrid|in_person), location,
eligible_countries (string[]), eligibility (string[]), team_min, team_max,
prize_value (number), prize_currency (ISO code), technologies (string[]),
official_url, effort_estimate, tags (string[]), raw_notes.
Dates must be ISO-8601 UTC if present (e.g. 2026-08-25T23:59:00+00:00).
"""

_AI_OFFER_SCHEMA_HINT = """
Return a JSON object with optional keys only (omit unknowns):
title, description, product_name, provider, offer_type
(free_credits|free_tier|trial|student_program|open_source_program|
hackathon_credits|promo_code|free_model|self_hosted_weights),
offer_value, target_users (string[]), requirements (string[]),
starts_at, expires_at (null if permanent/unknown), supported_regions (string[]),
official_terms_url, claim_url, official_url, tags (string[]), raw_notes.
Dates must be ISO-8601 UTC if present.
"""


def _system_prompt(listing_kind: str, schema_version: str) -> str:
    schema = _HACKATHON_SCHEMA_HINT if listing_kind == "hackathon" else _AI_OFFER_SCHEMA_HINT
    return (
        "You extract structured fields for DevRadar opportunity listings. "
        "Use ONLY the provided page text and URL. Do not invent deadlines, "
        "prizes, or URLs not supported by the text. Do not browse the web. "
        "Respond with a single JSON object, no markdown.\n"
        f"listing_kind={listing_kind}\nschema_version={schema_version}\n"
        f"{schema}"
    )


def _user_content(url: str, body: str) -> str:
    return f"Source URL: {url}\n\nPage text:\n{body if body.strip() else '(empty)'}\n"


class OpenAILLMProvider:
    """OpenAI Chat Completions JSON extraction — no web_search tool."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is empty")
        self._api_key = api_key
        self._model = model or "gpt-4o-mini"
        self._timeout = timeout_seconds

    async def extract_json(self, request: ExtractionRequest) -> LLMJsonResult:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout)
        body = (request.text or "")[: request.max_chars]
        user_content = _user_content(request.url, body)
        logger.info(
            "openai_extract_start",
            extra={
                "model": self._model,
                "listing_kind": request.listing_kind,
                "text_chars": len(body),
                # never log api key or full page body
            },
        )
        try:
            response = await client.chat.completions.create(
                model=self._model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": _system_prompt(
                            request.listing_kind, request.schema_version
                        ),
                    },
                    {"role": "user", "content": user_content},
                ],
            )
        finally:
            await client.close()

        choice = response.choices[0].message.content if response.choices else None
        if not choice:
            raise ValueError("Empty OpenAI completion")
        return LLMJsonResult(
            payload=_parse_json_content(choice),
            usage=LLMCallUsage.from_openai_response(
                response,
                operation="extraction",
                requested_model=self._model,
            ),
        )


class RoutedLLMProvider:
    """Extraction across several providers, with failover and rotation.

    Errors propagate: ``Extractor`` already treats a provider failure as
    "keep the rule-based fields", which stays the right outcome once every
    provider in the chain has been tried.
    """

    def __init__(self, router: LLMRouter) -> None:
        self._router = router

    async def extract_json(self, request: ExtractionRequest) -> LLMJsonResult:
        body = (request.text or "")[: request.max_chars]
        logger.info(
            "routed_extract_start",
            extra={
                "listing_kind": request.listing_kind,
                "text_chars": len(body),
                # never log api keys or the full page body
            },
        )
        result = await self._router.chat_json(
            ChatRequest(
                operation="extraction",
                system=_system_prompt(request.listing_kind, request.schema_version),
                user=_user_content(request.url, body),
                schema_name="devradar_extraction",
            )
        )
        return LLMJsonResult(payload=result.payload, usage=result.usage)


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Build the configured LLM provider (defaults to disabled).

    Multi-provider routing wins when enabled and a provider serves extraction;
    otherwise the single-provider path below is used unchanged.
    """
    from app.llm.factory import build_router

    router = build_router(settings)
    if router is not None and router.serves("extraction"):
        return RoutedLLMProvider(router)

    provider = (settings.llm_provider or "disabled").lower().strip()
    if provider in {"", "disabled", "none", "off"}:
        return DisabledLLMProvider()

    if provider in {"openai", "oai"}:
        api_key = (settings.llm_api_key or "").strip()
        if not api_key:
            logger.warning(
                "llm_openai_missing_key",
                extra={"hint": "Set LLM_API_KEY or keep LLM_PROVIDER=disabled"},
            )
            return DisabledLLMProvider()
        model = (settings.llm_model or "gpt-4o-mini").strip()
        return OpenAILLMProvider(api_key=api_key, model=model)

    logger.warning("llm_unknown_provider", extra={"provider": provider})
    return DisabledLLMProvider()


def create_extractor(settings: Settings) -> Any:
    """Convenience: Extractor wired to settings LLM provider."""
    from app.ingestion.extractor import Extractor

    return Extractor(build_llm_provider(settings))
