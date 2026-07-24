"""API tests for admin GitHub OAuth and sessions."""

from __future__ import annotations

import httpx
import pytest

from app.auth.github import FakeGitHubOAuthClient, GitHubUser
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
        admin_github_ids=["111"],
        frontend_url="http://localhost:5173",
        cors_origins=["http://localhost:5173"],
        github_client_id="test-client",
        github_client_secret="test-secret",
    )


@pytest.fixture
def session_store() -> InMemorySessionStore:
    return InMemorySessionStore()


@pytest.fixture
def oauth() -> FakeGitHubOAuthClient:
    return FakeGitHubOAuthClient(
        users_by_code={
            "good-code": GitHubUser(id="111", login="allowlisted-admin"),
            "bad-user-code": GitHubUser(id="999", login="intruder"),
        }
    )


@pytest.fixture
async def api_client(
    settings: Settings,
    session_store: InMemorySessionStore,
    oauth: FakeGitHubOAuthClient,
):
    app = create_app(settings)
    app.state.session_store = session_store
    app.state.github_oauth = oauth
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        yield client, session_store, oauth


class TestGitHubOAuth:
    async def test_start_returns_authorize_url_with_pkce(self, api_client) -> None:
        client, store, oauth = api_client
        response = await client.get("/api/v1/admin/auth/github/start")
        assert response.status_code == 200
        body = response.json()
        assert "authorizeUrl" in body
        assert "state" in body
        assert "code_challenge" in oauth.last_authorize_params
        assert body["state"] in store.oauth

    async def test_callback_allowlisted_sets_session_cookie(self, api_client) -> None:
        client, store, _ = api_client
        start = await client.get("/api/v1/admin/auth/github/start")
        state = start.json()["state"]
        response = await client.get(
            "/api/v1/admin/auth/github/callback",
            params={"code": "good-code", "state": state},
        )
        assert response.status_code == 302
        assert "admin_auth=ok" in response.headers["location"]
        assert SESSION_COOKIE in response.cookies
        cookie = response.cookies[SESSION_COOKIE]
        # Cookie flags via set-cookie header
        set_cookie = response.headers.get("set-cookie", "")
        assert "HttpOnly" in set_cookie or "httponly" in set_cookie.lower()
        identity = await store.get_session(cookie)
        assert identity is not None
        assert identity.github_id == "111"
        assert identity.login == "allowlisted-admin"

    async def test_callback_rejects_non_allowlisted(self, api_client) -> None:
        client, _, _ = api_client
        start = await client.get("/api/v1/admin/auth/github/start")
        state = start.json()["state"]
        response = await client.get(
            "/api/v1/admin/auth/github/callback",
            params={"code": "bad-user-code", "state": state},
        )
        # Forbidden during callback — problem response (not redirect)
        assert response.status_code == 403

    async def test_callback_rejects_invalid_state(self, api_client) -> None:
        client, _, _ = api_client
        response = await client.get(
            "/api/v1/admin/auth/github/callback",
            params={"code": "good-code", "state": "unknown-state"},
        )
        assert response.status_code == 401

    async def test_me_requires_session(self, api_client) -> None:
        client, _, _ = api_client
        response = await client.get("/api/v1/admin/auth/me")
        assert response.status_code == 401

    async def test_me_returns_csrf(self, api_client) -> None:
        client, _, _ = api_client
        start = await client.get("/api/v1/admin/auth/github/start")
        state = start.json()["state"]
        cb = await client.get(
            "/api/v1/admin/auth/github/callback",
            params={"code": "good-code", "state": state},
        )
        cookie = cb.cookies[SESSION_COOKIE]
        me = await client.get(
            "/api/v1/admin/auth/me",
            cookies={SESSION_COOKIE: cookie},
        )
        assert me.status_code == 200
        body = me.json()
        assert body["login"] == "allowlisted-admin"
        assert body["csrfToken"]

    async def test_logout_requires_csrf(self, api_client) -> None:
        client, store, _ = api_client
        start = await client.get("/api/v1/admin/auth/github/start")
        state = start.json()["state"]
        cb = await client.get(
            "/api/v1/admin/auth/github/callback",
            params={"code": "good-code", "state": state},
        )
        cookie = cb.cookies[SESSION_COOKIE]
        # Missing CSRF
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
        start = await client.get("/api/v1/admin/auth/github/start")
        state = start.json()["state"]
        cb = await client.get(
            "/api/v1/admin/auth/github/callback",
            params={"code": "good-code", "state": state},
        )
        cookie = cb.cookies[SESSION_COOKIE]
        # Force expiry
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
        start = await client.get("/api/v1/admin/auth/github/start")
        state = start.json()["state"]
        cb = await client.get(
            "/api/v1/admin/auth/github/callback",
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
