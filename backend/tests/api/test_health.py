"""Tests for health check endpoints."""

import httpx


class TestHealthLive:
    """Tests for GET /health/live."""

    async def test_returns_ok_status(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health/live")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"

    async def test_returns_json_content_type(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health/live")
        assert "application/json" in response.headers["content-type"]

    async def test_propagates_trace_id(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health/live")
        assert "x-trace-id" in response.headers
        trace_id = response.headers["x-trace-id"]
        assert len(trace_id) > 0

    async def test_uses_provided_trace_id(self, client: httpx.AsyncClient) -> None:
        custom_trace = "test-trace-12345"
        response = await client.get(
            "/health/live",
            headers={"X-Trace-Id": custom_trace},
        )
        assert response.headers["x-trace-id"] == custom_trace

    async def test_stable_json_body_structure(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health/live")
        body = response.json()
        assert set(body.keys()) == {"status"}


class TestHealthReady:
    """Tests for GET /health/ready."""

    async def test_returns_ok_when_services_available(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get("/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"]["postgres"] == "ok"
        assert body["checks"]["redis"] == "ok"

    async def test_returns_503_when_postgres_down(
        self, client_no_db: httpx.AsyncClient
    ) -> None:
        """When PostgreSQL is unavailable, readiness should fail."""
        response = await client_no_db.get("/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["checks"]["postgres"] != "ok"

    async def test_returns_503_when_redis_down(
        self, client_no_redis: httpx.AsyncClient
    ) -> None:
        """When Redis is unavailable, readiness should fail."""
        response = await client_no_redis.get("/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["checks"]["redis"] != "ok"

    async def test_ready_propagates_trace_id(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get("/health/ready")
        assert "x-trace-id" in response.headers

    async def test_stable_json_structure(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get("/health/ready")
        body = response.json()
        assert set(body.keys()) == {"status", "checks"}
        assert set(body["checks"].keys()) == {"postgres", "redis"}
