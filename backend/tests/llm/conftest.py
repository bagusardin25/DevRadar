"""Helpers for the LLM router tests — no live API and no Redis."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from app.llm.capabilities import Capabilities, JsonMode, defaults_for
from app.llm.registry import ProviderLimits, ProviderSpec


class Clock:
    """Controllable wall clock for window rollover and deadline tests."""

    def __init__(self, now: float = 1_772_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def no_sleep(_seconds: float) -> None:
    """Drop-in for asyncio.sleep so backoff does not slow the suite."""


def make_spec(
    name: str,
    *,
    priority: int = 10,
    priority_overrides: dict[str, int] | None = None,
    weight: int = 1,
    operations: Sequence[str] = ("extraction",),
    model: str = "test-model",
    json_mode: JsonMode | None = None,
    supports_temperature: bool | None = None,
    rpm: int | None = None,
    rpd: int | None = None,
    tpm: int | None = None,
    tpd: int | None = None,
    read_timeout: float = 30.0,
) -> ProviderSpec:
    """A spec whose base_url encodes the provider name as the host."""
    caps = defaults_for(name)
    caps = Capabilities(
        json_mode=json_mode if json_mode is not None else caps.json_mode,
        supports_temperature=(
            supports_temperature
            if supports_temperature is not None
            else caps.supports_temperature
        ),
        extra_headers=dict(caps.extra_headers),
    )
    return ProviderSpec(
        name=name,
        kind="openai_compat",
        base_url=f"https://{name}.test/v1",
        api_key=f"key-{name}",
        model=model,
        operations=frozenset(operations),
        priority=priority,
        priority_overrides=priority_overrides or {},
        weight=weight,
        capabilities=caps,
        limits=ProviderLimits(rpm=rpm, rpd=rpd, tpm=tpm, tpd=tpd),
        connect_timeout=5.0,
        read_timeout=read_timeout,
    )


def ok_response(
    content: str = '{"title": "Routed"}',
    *,
    model: str = "test-model",
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": model,
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": content}}
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        },
    )


def error_response(
    status: int,
    *,
    code: str = "",
    message: str = "boom",
    retry_after: float | None = None,
) -> httpx.Response:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    return httpx.Response(
        status,
        json={"error": {"code": code, "message": message}},
        headers=headers,
    )


class RecordingTransport:
    """Routes mock responses by provider name (the host of the base_url)."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self._routes = routes
        self.calls: list[tuple[str, dict[str, Any]]] = []

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self.transport)

    def hits(self, provider: str) -> int:
        return sum(1 for name, _ in self.calls if name == provider)

    def payload_for(self, provider: str) -> dict[str, Any]:
        for name, body in self.calls:
            if name == provider:
                return body
        raise AssertionError(f"{provider} was never called")

    def _handle(self, request: httpx.Request) -> httpx.Response:
        provider = (request.url.host or "").split(".")[0]
        self.calls.append((provider, json.loads(request.content.decode())))
        route = self._routes.get(provider)
        if route is None:
            return error_response(500, message=f"no route for {provider}")
        if callable(route):
            handler: Callable[[int], httpx.Response] = route
            return handler(self.hits(provider) - 1)
        if isinstance(route, list):
            index = min(self.hits(provider) - 1, len(route) - 1)
            return route[index]
        return route
