"""Adversarial request-boundary tests that do not require endpoint work."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from app.config import Settings
from app.main import create_app


@pytest.fixture
async def limited_client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    application = create_app(
        settings.model_copy(update={"max_request_body_bytes": 16_384})
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        yield client


class TestRequestBodyLimit:
    async def test_rejects_declared_oversized_body(self, limited_client) -> None:
        response = await limited_client.post(
            "/api/v1/alerts",
            content=b"x" * 16_385,
            headers={"content-type": "application/json", "x-trace-id": "stress-fixed"},
        )
        assert response.status_code == 413
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.headers["x-trace-id"] == "stress-fixed"

    async def test_rejects_chunked_body_without_content_length(
        self, limited_client
    ) -> None:
        async def chunks() -> AsyncIterator[bytes]:
            yield b'{"email":"dev@example.com","padding":"'
            yield b"x" * 16_385
            yield b'"}'

        response = await limited_client.post(
            "/api/v1/alerts",
            content=chunks(),
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 413

    async def test_replaces_pathological_trace_id(self, limited_client) -> None:
        response = await limited_client.get(
            "/health/live",
            headers={"x-trace-id": "x" * 129},
        )
        assert response.status_code == 200
        assert response.headers["x-trace-id"] != "x" * 129
        assert len(response.headers["x-trace-id"]) == 36


class TestPublicParameterLimits:
    async def test_rejects_oversized_search_before_database_work(
        self, limited_client
    ) -> None:
        response = await limited_client.get(
            "/api/v1/search",
            params={"q": "q" * 201},
        )
        assert response.status_code == 422

    async def test_rejects_too_many_ai_offer_tags(self, limited_client) -> None:
        response = await limited_client.get(
            "/api/v1/ai-offers",
            params={"tags": ",".join(f"tag{i}" for i in range(11))},
        )
        assert response.status_code == 422

    async def test_rejects_oversized_tracking_token(self, limited_client) -> None:
        response = await limited_client.get(f"/api/v1/submissions/{'x' * 129}")
        assert response.status_code == 422

    async def test_rejects_oversized_alert_token(self, limited_client) -> None:
        response = await limited_client.get(
            "/api/v1/alerts/confirm",
            params={"token": "x" * 257},
        )
        assert response.status_code == 422
