"""API tests for admin Google OAuth and sessions."""

from __future__ import annotations

import httpx
import pytest

from app.auth.google import FakeGoogleOAuthClient, GoogleUser
from app.auth.sessions import (
    CSRF_HEADER,
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    InMemorySessionStore,
)
from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        admin_google_emails=["admin@example.com"],
        frontend_url="http://localhost:5173",
        cors_origins=["http://localhost:5173"],
        google_client_id="test-client",
        google_client_secret="test-secret",
    )


@pytest.fixture
def session_store() -> InMemorySessionStore:
    return InMemorySessionStore()


@pytest.fixture
def oauth() -> FakeGoogleOAuthClient:
    return FakeGoogleOAuthClient(
        users_by_code={
            "good-code": GoogleUser(
                id="108234", email="admin@example.com", email_verified=True
            ),
            "bad-user-code": GoogleUser(
                id="999", email="intruder@example.com", email_verified=True
            ),
            "unverified-code": GoogleUser(
                id="108234", email="admin@example.com", email_verified=False
            ),
        }
    )


@pytest.fixture
async def api_client(
    settings: Settings,
    session_store: InMemorySessionStore,
    oauth: FakeGoogleOAuthClient,
):
    app = create_app(settings)
    app.state.session_store = session_store
    app.state.google_oauth = oauth
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        yield client, session_store, oauth


class TestGoogleOAuth:
    async def test_start_returns_authorize_url_with_pkce(self, api_client) -> None:
        client, store, oauth = api_client
        response = await client.get("/api/v1/admin/auth/google/start")
        assert response.status_code == 200
        body = response.json()
        assert "authorizeUrl" in body
        assert "state" in body
        assert "code_challenge" in oauth.last_authorize_params
        assert body["state"] in store.oauth

    async def test_callback_allowlisted_sets_session_cookie(self, api_client) -> None:
        client, store, _ = api_client
        start = await client.get("/api/v1/admin/auth/google/start")
        state = start.json()["state"]
        response = await client.get(
            "/api/v1/admin/auth/google/callback",
            params={"code": "good-code", "state": state},
        )
        assert response.status_code == 302
        assert "admin_auth=ok" in response.headers["location"]
        assert SESSION_COOKIE in response.cookies
        cookie = response.cookies[SESSION_COOKIE]
        set_cookie = response.headers.get("set-cookie", "")
        assert "HttpOnly" in set_cookie or "httponly" in set_cookie.lower()
        identity = await store.get_session(cookie)
        assert identity is not None
        assert identity.subject == "108234"
        assert identity.email == "admin@example.com"

    async def test_callback_rejects_non_allowlisted(self, api_client) -> None:
        client, _, _ = api_client
        start = await client.get("/api/v1/admin/auth/google/start")
        state = start.json()["state"]
        response = await client.get(
            "/api/v1/admin/auth/google/callback",
            params={"code": "bad-user-code", "state": state},
        )
        assert response.status_code == 403

    async def test_callback_rejects_unverified_email(self, api_client) -> None:
        client, _, _ = api_client
        start = await client.get("/api/v1/admin/auth/google/start")
        state = start.json()["state"]
        response = await client.get(
            "/api/v1/admin/auth/google/callback",
            params={"code": "unverified-code", "state": state},
        )
        assert response.status_code == 403

    async def test_callback_rejects_invalid_state(self, api_client) -> None:
        client, _, _ = api_client
        response = await client.get(
            "/api/v1/admin/auth/google/callback",
            params={"code": "good-code", "state": "unknown-state"},
        )
        assert response.status_code == 401

    async def test_me_requires_session(self, api_client) -> None:
        client, _, _ = api_client
        response = await client.get("/api/v1/admin/auth/me")
        assert response.status_code == 401

    async def test_me_returns_csrf(self, api_client) -> None:
        client, _, _ = api_client
        start = await client.get("/api/v1/admin/auth/google/start")
        state = start.json()["state"]
        cb = await client.get(
            "/api/v1/admin/auth/google/callback",
            params={"code": "good-code", "state": state},
        )
        cookie = cb.cookies[SESSION_COOKIE]
        me = await client.get(
            "/api/v1/admin/auth/me",
            cookies={SESSION_COOKIE: cookie},
        )
        assert me.status_code == 200
        body = me.json()
        assert body["email"] == "admin@example.com"
        assert body["subject"] == "108234"
        assert body["csrfToken"]

    async def test_logout_requires_csrf(self, api_client) -> None:
        client, store, _ = api_client
        start = await client.get("/api/v1/admin/auth/google/start")
        state = start.json()["state"]
        cb = await client.get(
            "/api/v1/admin/auth/google/callback",
            params={"code": "good-code", "state": state},
        )
        cookie = cb.cookies[SESSION_COOKIE]
        bad = await client.post(
            "/api/v1/admin/auth/logout",
            cookies={SESSION_COOKIE: cookie},
        )
        assert bad.status_code == 403

        me = await client.get(
            "/api/v1/admin/auth/me",
            cookies={SESSION_COOKIE: cookie},
        )
        csrf = me.json()["csrfToken"]
        ok = await client.post(
            "/api/v1/admin/auth/logout",
            cookies={SESSION_COOKIE: cookie},
            headers={
                CSRF_HEADER: csrf,
                "Origin": "http://localhost:5173",
            },
        )
        assert ok.status_code == 200
        assert await store.get_session(cookie) is None

    async def test_session_expiry(self, api_client, session_store: InMemorySessionStore) -> None:
        client, store, _ = api_client
        start = await client.get("/api/v1/admin/auth/google/start")
        state = start.json()["state"]
        cb = await client.get(
            "/api/v1/admin/auth/google/callback",
            params={"code": "good-code", "state": state},
        )
        cookie = cb.cookies[SESSION_COOKIE]
        key = __import__("app.auth.sessions", fromlist=["hash_token"]).hash_token(cookie)
        rec = store.sessions[key]
        rec.last_seen_at -= SESSION_TTL_SECONDS + 10
        me = await client.get(
            "/api/v1/admin/auth/me",
            cookies={SESSION_COOKIE: cookie},
        )
        assert me.status_code == 401

    async def test_origin_check_on_mutation(self, api_client) -> None:
        client, _, _ = api_client
        start = await client.get("/api/v1/admin/auth/google/start")
        state = start.json()["state"]
        cb = await client.get(
            "/api/v1/admin/auth/google/callback",
            params={"code": "good-code", "state": state},
        )
        cookie = cb.cookies[SESSION_COOKIE]
        me = await client.get(
            "/api/v1/admin/auth/me",
            cookies={SESSION_COOKIE: cookie},
        )
        csrf = me.json()["csrfToken"]
        bad_origin = await client.post(
            "/api/v1/admin/auth/logout",
            cookies={SESSION_COOKIE: cookie},
            headers={
                CSRF_HEADER: csrf,
                "Origin": "https://evil.example",
            },
        )
        assert bad_origin.status_code == 403
