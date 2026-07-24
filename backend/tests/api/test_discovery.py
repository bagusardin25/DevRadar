"""Live discovery API tests."""

from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.main import create_app


@pytest.fixture
async def client():
    app = create_app(
        Settings(session_secret="test-session-secret-at-least-32-chars!!")
    )
    app.state.discovery_rate_limit_store = {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c


class TestDiscoveryAPI:
    async def test_requires_opt_in(self, client) -> None:
        r = await client.post(
            "/api/v1/discovery-runs",
            json={"query": "ai hackathon", "confirmLiveDiscovery": False},
        )
        assert r.status_code == 422

    async def test_min_query_length(self, client) -> None:
        r = await client.post(
            "/api/v1/discovery-runs",
            json={"query": "ab", "confirmLiveDiscovery": True},
        )
        assert r.status_code == 422

    async def test_start_and_status(self, client) -> None:
        r = await client.post(
            "/api/v1/discovery-runs",
            json={
                "query": "online hackathon",
                "confirmLiveDiscovery": True,
                "resultCap": 5,
            },
        )
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "queued"
        run_id = body["id"]
        st = await client.get(f"/api/v1/discovery-runs/{run_id}")
        assert st.status_code == 200
        assert st.json()["verifiedListingIds"] == []

    async def test_cache_duplicate_request(self, client) -> None:
        payload = {
            "query": "unique discovery query xyz",
            "confirmLiveDiscovery": True,
            "connectors": ["devpost"],
        }
        r1 = await client.post("/api/v1/discovery-runs", json=payload)
        r2 = await client.post("/api/v1/discovery-runs", json=payload)
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json()["id"] == r2.json()["id"]
