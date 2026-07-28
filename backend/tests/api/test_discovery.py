"""Live discovery API tests."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from app.config import Settings
from app.discovery.enqueue import InMemoryDiscoveryEnqueue
from app.main import create_app


@pytest.fixture
def enqueue() -> InMemoryDiscoveryEnqueue:
    return InMemoryDiscoveryEnqueue()


@pytest.fixture
async def client(enqueue: InMemoryDiscoveryEnqueue):
    app = create_app(
        Settings(session_secret="test-session-secret-at-least-32-chars!!")
    )
    app.state.discovery_rate_limit_store = {}
    app.state.discovery_enqueue = enqueue
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
            json={"query": "a", "confirmLiveDiscovery": True},
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

    async def test_new_run_is_dispatched_to_the_worker(
        self, client, enqueue: InMemoryDiscoveryEnqueue
    ) -> None:
        r = await client.post(
            "/api/v1/discovery-runs",
            json={
                "query": f"dispatch {uuid4().hex[:8]}",
                "confirmLiveDiscovery": True,
            },
        )
        assert r.status_code == 202
        assert enqueue.calls == [r.json()["id"]]

    async def test_cached_run_is_not_dispatched_twice(
        self, client, enqueue: InMemoryDiscoveryEnqueue
    ) -> None:
        payload = {
            "query": f"cached {uuid4().hex[:8]}",
            "confirmLiveDiscovery": True,
            "connectors": ["official_site"],
        }
        await client.post("/api/v1/discovery-runs", json=payload)
        await client.post("/api/v1/discovery-runs", json=payload)
        assert len(enqueue.calls) == 1

    async def test_unknown_module_rejected(self, client) -> None:
        r = await client.post(
            "/api/v1/discovery-runs",
            json={
                "query": "ai hackathon",
                "confirmLiveDiscovery": True,
                "module": "not_a_module",
            },
        )
        assert r.status_code == 422

    async def test_connector_payload_is_bounded(self, client) -> None:
        too_many = await client.post(
            "/api/v1/discovery-runs",
            json={
                "query": "ai hackathon",
                "confirmLiveDiscovery": True,
                "connectors": ["official_site", "rss", "github", "x"],
            },
        )
        assert too_many.status_code == 422

        oversized = await client.post(
            "/api/v1/discovery-runs",
            json={
                "query": "ai hackathon",
                "confirmLiveDiscovery": True,
                "connectors": ["x" * 51],
            },
        )
        assert oversized.status_code == 422

    async def test_status_exposes_progress_counters(self, client) -> None:
        r = await client.post(
            "/api/v1/discovery-runs",
            json={
                "query": f"counters {uuid4().hex[:8]}",
                "confirmLiveDiscovery": True,
            },
        )
        st = await client.get(f"/api/v1/discovery-runs/{r.json()['id']}")
        body = st.json()
        # Queued run has not done any work yet — and says so.
        assert body["candidates"] == 0
        assert body["fetched"] == 0
        assert body["published"] == 0
        assert body["finishedAt"] is None
