"""Admin visibility into LLM provider health and remaining budget."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest

from app.auth.google import FakeGoogleOAuthClient, GoogleUser
from app.auth.sessions import SESSION_COOKIE, InMemorySessionStore
from app.config import Settings
from app.llm.breaker import CircuitBreaker
from app.llm.limiter import LLMRateLimiter
from app.llm.registry import parse_provider_specs
from app.llm.state import MemoryState
from app.main import create_app

PROVIDERS = json.dumps(
    [
        {
            "name": "groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key_env": "TEST_GROQ_KEY",
            "model": "openai/gpt-oss-120b",
            "operations": ["extraction"],
            "priority": 10,
            "weight": 3,
            "limits": {"rpm": 30, "rpd": 1000},
        },
        {
            "name": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "TEST_OPENAI_KEY",
            "model": "gpt-4o-mini",
            "priority": {"review": 10, "extraction": 30},
        },
    ]
)


@pytest.fixture(autouse=True)
def _provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_GROQ_KEY", "gsk-test")
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-test")


def _settings(**overrides: object) -> Settings:
    data: dict[str, object] = {
        "app_env": "test",
        "admin_google_emails": ["admin@example.com"],
        "frontend_url": "http://localhost:5173",
        "cors_origins": ["http://localhost:5173"],
        "google_client_id": "test-client",
        "google_client_secret": "test-secret",
        "llm_routing_enabled": True,
        "llm_routing_strategy": "weighted",
        "llm_providers_json": PROVIDERS,
    }
    data.update(overrides)
    return Settings.model_validate(data)


async def _client(
    settings: Settings, state: MemoryState | None = None
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    app.state.session_store = InMemorySessionStore()
    app.state.google_oauth = FakeGoogleOAuthClient(
        users_by_code={
            "good-code": GoogleUser(
                id="llm-admin", email="admin@example.com", email_verified=True
            )
        }
    )
    if state is not None:
        app.state.llm_router_state = state
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        yield client


async def _login(client: httpx.AsyncClient) -> dict[str, str]:
    start = await client.get("/api/v1/admin/auth/google/start")
    callback = await client.get(
        "/api/v1/admin/auth/google/callback",
        params={"code": "good-code", "state": start.json()["state"]},
    )
    return {SESSION_COOKIE: callback.cookies[SESSION_COOKIE]}


class TestProviderStatus:
    async def test_requires_admin_authentication(self) -> None:
        async for client in _client(_settings(), MemoryState()):
            response = await client.get("/api/v1/admin/llm/providers")
            assert response.status_code == 401

    async def test_reports_configured_providers(self) -> None:
        state = MemoryState()
        async for client in _client(_settings(), state):
            cookies = await _login(client)
            response = await client.get("/api/v1/admin/llm/providers", cookies=cookies)

        assert response.status_code == 200
        body = response.json()
        assert body["routingEnabled"] is True
        assert body["strategy"] == "weighted"
        assert [p["name"] for p in body["providers"]] == ["groq", "openai"]

    async def test_shows_per_operation_priority(self) -> None:
        state = MemoryState()
        async for client in _client(_settings(), state):
            cookies = await _login(client)
            response = await client.get("/api/v1/admin/llm/providers", cookies=cookies)

        openai = next(p for p in response.json()["providers"] if p["name"] == "openai")
        assert openai["priority"] == {"extraction": 30, "review": 10}

    async def test_reports_remaining_budget_against_the_effective_ceiling(self) -> None:
        state = MemoryState()
        spec = next(s for s in parse_provider_specs(PROVIDERS) if s.name == "groq")
        limiter = LLMRateLimiter(state)
        for _ in range(4):
            await limiter.try_acquire(spec)

        async for client in _client(_settings(), state):
            cookies = await _login(client)
            response = await client.get("/api/v1/admin/llm/providers", cookies=cookies)

        groq = next(p for p in response.json()["providers"] if p["name"] == "groq")
        assert groq["rpm"]["limit"] == 30
        assert groq["rpm"]["effective"] == 27  # published limit used at 90%
        assert groq["rpm"]["used"] == 4
        assert groq["rpm"]["remaining"] == 23

    async def test_surfaces_an_open_circuit(self) -> None:
        state = MemoryState()
        await CircuitBreaker(state).record_failure("openai", cooldown_seconds=3_600)

        async for client in _client(_settings(), state):
            cookies = await _login(client)
            response = await client.get("/api/v1/admin/llm/providers", cookies=cookies)

        providers = {p["name"]: p for p in response.json()["providers"]}
        assert providers["openai"]["circuitOpen"] is True
        assert providers["groq"]["circuitOpen"] is False

    async def test_routing_disabled_reports_nothing_configured(self) -> None:
        settings = _settings(llm_routing_enabled=False)
        async for client in _client(settings, MemoryState()):
            cookies = await _login(client)
            response = await client.get("/api/v1/admin/llm/providers", cookies=cookies)

        body = response.json()
        assert body["routingEnabled"] is False
        assert body["providers"] == []
