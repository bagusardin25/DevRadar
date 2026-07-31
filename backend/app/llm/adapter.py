"""OpenAI-compatible chat-completions adapter.

All six providers in the plan expose ``POST {base_url}/chat/completions`` with
the OpenAI request shape, so one adapter over httpx covers them. Provider
differences are flags on ``Capabilities``, not separate client classes.

Deliberately plain httpx rather than the ``openai`` SDK: httpx is already a
dependency, the ingestion pipeline already uses it, and a single shared client
avoids the per-call connect/close cycle the previous OpenAI-only code paid.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.llm.capabilities import JsonMode
from app.llm.errors import ProviderHTTPError, ProviderResponseError
from app.llm.registry import ProviderSpec

logger = logging.getLogger(__name__)

# Enough for the extraction and review payloads; keeps a runaway model from
# burning a whole daily token budget on one call.
DEFAULT_MAX_OUTPUT_TOKENS = 2_048


@dataclass(slots=True)
class ChatRequest:
    """A provider-neutral JSON completion request."""

    operation: str
    system: str
    user: str
    schema_name: str = "devradar_response"
    json_schema: dict[str, Any] | None = None
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS


@dataclass(slots=True)
class ChatResult:
    """A successful completion, plus the raw body for usage accounting."""

    content: str
    model: str
    finish_reason: str
    raw: dict[str, Any] = field(default_factory=dict)


def build_payload(
    spec: ProviderSpec,
    request: ChatRequest,
    *,
    json_mode: JsonMode,
) -> dict[str, Any]:
    """Assemble the request body for one provider and JSON mode."""
    payload: dict[str, Any] = {
        "model": spec.model,
        "messages": [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.user},
        ],
        "max_tokens": request.max_output_tokens,
    }

    if spec.capabilities.supports_temperature:
        payload["temperature"] = 0

    if json_mode == "json_schema" and request.json_schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": request.schema_name,
                "schema": request.json_schema,
                "strict": True,
            },
        }
    elif json_mode in {"json_schema", "json_object"}:
        # No schema to enforce (or the provider only does the weaker mode);
        # json_object still guarantees parseable output.
        payload["response_format"] = {"type": "json_object"}
    # json_mode == "prompt": nothing to add. The system prompt already demands
    # a bare JSON object and json_parse repairs the usual wrappers.

    return payload


def build_headers(spec: ProviderSpec) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {spec.api_key}",
        "Content-Type": "application/json",
        **spec.capabilities.extra_headers,
    }


async def complete(
    client: httpx.AsyncClient,
    spec: ProviderSpec,
    request: ChatRequest,
    *,
    json_mode: JsonMode,
    timeout: httpx.Timeout,
) -> ChatResult:
    """Call one provider once. Raises ProviderHTTPError / ProviderResponseError."""
    response = await client.post(
        f"{spec.base_url}/chat/completions",
        json=build_payload(spec, request, json_mode=json_mode),
        headers=build_headers(spec),
        timeout=timeout,
    )

    if response.status_code >= 400:
        code, message = _error_fields(response)
        raise ProviderHTTPError(
            spec.name,
            response.status_code,
            code=code,
            message=message,
            retry_after=_retry_after(response),
        )

    return _read_result(spec, response)


def _read_result(spec: ProviderSpec, response: httpx.Response) -> ChatResult:
    try:
        body = response.json()
    except ValueError as exc:
        raise ProviderResponseError(spec.name, "response body is not JSON") from exc
    if not isinstance(body, dict):
        raise ProviderResponseError(spec.name, "response body is not a JSON object")

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderResponseError(spec.name, "response has no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderResponseError(spec.name, "malformed choice")

    finish_reason = str(first.get("finish_reason") or "")
    if finish_reason == "length":
        # Truncated JSON often still parses while silently losing fields, so
        # this has to fail loudly rather than be accepted as a result.
        raise ProviderResponseError(spec.name, "completion truncated (finish_reason=length)")

    message = first.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ProviderResponseError(spec.name, "empty completion")

    return ChatResult(
        content=content,
        model=str(body.get("model") or spec.model),
        finish_reason=finish_reason,
        raw=body,
    )


def _error_fields(response: httpx.Response) -> tuple[str, str]:
    """Pull a code and message out of the several error shapes in use."""
    try:
        body = response.json()
    except ValueError:
        return "", response.text[:500]
    if not isinstance(body, dict):
        return "", str(body)[:500]

    error = body.get("error")
    if isinstance(error, dict):
        # OpenAI/Groq/Mistral use `code`; Gemini's compat layer uses `status`.
        code = error.get("code") or error.get("status") or error.get("type") or ""
        return str(code), str(error.get("message") or "")[:500]
    if isinstance(error, str):
        return "", error[:500]

    detail = body.get("detail") or body.get("message") or ""
    return "", str(detail)[:500]


def _retry_after(response: httpx.Response) -> float | None:
    """Seconds from Retry-After. HTTP-date form is ignored rather than guessed."""
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        value = float(raw.strip())
    except ValueError:
        return None
    return value if value >= 0 else None
