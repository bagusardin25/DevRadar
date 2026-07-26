"""API tests for POST/GET /api/v1/submissions."""

from __future__ import annotations

import time
from uuid import uuid4

import httpx
import pytest

from app.config import Settings
from app.main import create_app
from app.submissions.enqueue import InMemorySubmissionEnqueue


@pytest.fixture
def enqueue() -> InMemorySubmissionEnqueue:
    return InMemorySubmissionEnqueue()


@pytest.fixture
async def api_client(settings: Settings, enqueue: InMemorySubmissionEnqueue):
    application = create_app(settings)
    application.state.submission_enqueue = enqueue
    # Isolate rate limits from other tests that hit Redis.
    application.state.submission_rate_limit_store = {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        yield client, enqueue


def _body(**kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
        "url": f"https://example.com/events/{uuid4().hex[:8]}",
        "claimedType": "hackathon",
        "claimedTitle": "Community Hack",
        "formOpenedAt": time.time() - 10,
    }
    base.update(kwargs)
    return base


class TestCreateSubmission:
    async def test_accepts_valid_submission(self, api_client) -> None:
        client, enqueue = api_client
        response = await client.post("/api/v1/submissions", json=_body())
        assert response.status_code == 202
        body = response.json()
        assert "trackingId" in body
        assert body["status"] == "queued"
        assert body["duplicate"] is False
        # after_commit hook should have run via dependency
        assert len(enqueue.calls) == 1

    async def test_rejects_private_url(self, api_client) -> None:
        client, _ = api_client
        response = await client.post(
            "/api/v1/submissions",
            json=_body(url="http://127.0.0.1/secret"),
        )
        assert response.status_code == 422
        assert "application/problem+json" in response.headers["content-type"]

    async def test_rejects_honeypot(self, api_client) -> None:
        client, enqueue = api_client
        response = await client.post(
            "/api/v1/submissions",
            json=_body(website="http://bot.fill.me"),
        )
        assert response.status_code == 403
        assert enqueue.calls == []

    async def test_idempotency_key(self, api_client) -> None:
        client, enqueue = api_client
        key = f"key-{uuid4().hex}"
        # Randomise the URL so reruns don't collide with the 24h duplicate window
        # on the persistent test database.
        payload = _body(url=f"https://example.com/idem-api-{uuid4().hex[:8]}")
        r1 = await client.post(
            "/api/v1/submissions",
            json=payload,
            headers={"Idempotency-Key": key},
        )
        r2 = await client.post(
            "/api/v1/submissions",
            json=payload,
            headers={"Idempotency-Key": key},
        )
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json()["trackingId"] == r2.json()["trackingId"]
        # Only one enqueue
        assert len(enqueue.calls) == 1

    async def test_duplicate_url(self, api_client) -> None:
        client, enqueue = api_client
        url = f"https://example.com/dup-api-{uuid4().hex[:8]}"
        r1 = await client.post("/api/v1/submissions", json=_body(url=url))
        r2 = await client.post("/api/v1/submissions", json=_body(url=url))
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r2.json()["duplicate"] is True
        assert r2.json()["status"] == "duplicate"
        assert len(enqueue.calls) == 1

    async def test_rate_limit_headers_present(self, api_client) -> None:
        client, _ = api_client
        response = await client.post("/api/v1/submissions", json=_body())
        assert response.status_code == 202
        assert "X-RateLimit-Limit" in response.headers


class TestSubmissionStatus:
    async def test_get_status(self, api_client) -> None:
        client, _ = api_client
        created = await client.post("/api/v1/submissions", json=_body())
        tracking = created.json()["trackingId"]
        response = await client.get(f"/api/v1/submissions/{tracking}")
        assert response.status_code == 200
        body = response.json()
        assert body["trackingId"] == tracking
        assert body["status"] == "queued"
        assert "message" in body
        # Coarse: no IP / email fields
        assert "ipHash" not in body
        assert "email" not in body

    async def test_unknown_tracking(self, api_client) -> None:
        client, _ = api_client
        response = await client.get("/api/v1/submissions/missing-token-xyz")
        assert response.status_code == 404
