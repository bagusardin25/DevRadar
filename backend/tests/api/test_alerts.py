"""API tests for alert endpoints."""

from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.main import create_app


@pytest.fixture
async def client():
    settings = Settings(
        session_secret="test-session-secret-at-least-32-chars!!",
        email_hmac_key="test-hmac-key-at-least-32-characters!!",
        email_encryption_key="test-email-encryption-key-material",
    )
    app = create_app(settings)
    app.state.alert_rate_limit_store = {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=False,
    ) as c:
        yield c


class TestAlertsAPI:
    async def test_create_alert(self, client) -> None:
        r = await client.post(
            "/api/v1/alerts",
            json={"email": "dev@example.com", "filters": {"q": "hackathon"}},
        )
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "pending_confirmation"
        assert r.headers["X-RateLimit-Limit"] == "5"

    async def test_honeypot(self, client) -> None:
        r = await client.post(
            "/api/v1/alerts",
            json={
                "email": "dev@example.com",
                "filters": {},
                "website": "http://bot",
            },
        )
        assert r.status_code == 403

    async def test_confirm_invalid_token(self, client) -> None:
        r = await client.get("/api/v1/alerts/confirm", params={"token": "nope"})
        assert r.status_code == 404

    async def test_limits_confirmation_spam_per_recipient(self, client) -> None:
        for _ in range(3):
            response = await client.post(
                "/api/v1/alerts",
                json={"email": "target@example.com", "filters": {}},
            )
            assert response.status_code == 202
        blocked = await client.post(
            "/api/v1/alerts",
            json={"email": "target@example.com", "filters": {}},
        )
        assert blocked.status_code == 429

    async def test_rejects_pathological_filter_payload(self, client) -> None:
        response = await client.post(
            "/api/v1/alerts",
            json={"email": "dev@example.com", "filters": {"q": "x" * 201}},
        )
        assert response.status_code == 422

    async def test_rejects_unknown_cadence(self, client) -> None:
        response = await client.post(
            "/api/v1/alerts",
            json={"email": "dev@example.com", "cadence": "every-second"},
        )
        assert response.status_code == 422
