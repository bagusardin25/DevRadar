"""API tests for alert endpoints."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from app.config import Settings
from app.main import create_app


@pytest.fixture
def application():
    settings = Settings(
        session_secret="test-session-secret-at-least-32-chars!!",
        email_hmac_key="test-hmac-key-at-least-32-characters!!",
        email_encryption_key="test-email-encryption-key-material",
        email_provider="console",
    )
    app = create_app(settings)
    app.state.alert_rate_limit_store = {}
    return app


@pytest.fixture
async def client(application):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
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

    async def test_repeated_address_is_bounded(self, client) -> None:
        email = f"victim-{uuid4().hex[:8]}@example.com"
        payload = {"email": email, "filters": {"q": "hackathon"}}

        for _ in range(3):
            response = await client.post("/api/v1/alerts", json=payload)
            assert response.status_code == 202

        blocked = await client.post("/api/v1/alerts", json=payload)
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"] == "3600"
        assert blocked.json()["detail"] == "Too many alert requests for this email"

    async def test_email_limit_survives_case_and_filter_variants(self, client) -> None:
        email = f"variant-{uuid4().hex[:8]}@example.com"
        local_part = email.split("@", maxsplit=1)[0]
        variants = [email, email.upper(), f"{local_part}@EXAMPLE.COM"]

        for index, variant in enumerate(variants):
            response = await client.post(
                "/api/v1/alerts",
                json={"email": variant, "filters": {"q": f"topic-{index}"}},
            )
            assert response.status_code == 202

        blocked = await client.post(
            "/api/v1/alerts",
            json={"email": email.swapcase(), "filters": {"q": "another-topic"}},
        )
        assert blocked.status_code == 429
        assert blocked.json()["detail"] == "Too many alert requests for this email"

    async def test_client_cannot_bypass_limit_by_rotating_emails(self, client) -> None:
        for i in range(10):
            response = await client.post(
                "/api/v1/alerts",
                json={"email": f"target-{i}-{uuid4().hex[:6]}@example.com"},
            )
            assert response.status_code == 202

        blocked = await client.post(
            "/api/v1/alerts",
            json={"email": f"target-over-{uuid4().hex[:6]}@example.com"},
        )
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"] == "3600"
        assert blocked.json()["detail"] == "Too many alert requests from this client"
