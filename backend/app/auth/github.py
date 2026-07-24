"""GitHub OAuth (authorization code + PKCE) for admin login."""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.errors import ForbiddenError, UnauthorizedError, ValidationError

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


@dataclass(frozen=True, slots=True)
class GitHubUser:
    id: str
    login: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class OAuthStart:
    authorize_url: str
    state: str
    code_verifier: str


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using S256."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_urlsafe(24)


class GitHubOAuthClient(Protocol):
    async def build_authorize_url(self, state: str, code_challenge: str) -> str: ...

    async def exchange_code(self, code: str, code_verifier: str) -> GitHubUser: ...


class HttpGitHubOAuthClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _redirect_uri(self) -> str:
        # Callback is served by this API (local default; reverse-proxy in prod).
        base = self._settings.api_base_path.rstrip("/")
        if self._settings.app_env == "production":
            origin = self._settings.frontend_url.rstrip("/").replace("5173", "8000")
            return f"{origin}{base}/admin/auth/github/callback"
        return f"http://127.0.0.1:8000{base}/admin/auth/github/callback"

    async def build_authorize_url(self, state: str, code_challenge: str) -> str:
        if not self._settings.github_client_id:
            raise ValidationError(detail="GitHub OAuth is not configured")
        params = {
            "client_id": self._settings.github_client_id,
            "redirect_uri": self._redirect_uri(),
            "scope": "read:user",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str) -> GitHubUser:
        if not self._settings.github_client_id or not self._settings.github_client_secret:
            raise ValidationError(detail="GitHub OAuth is not configured")
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self._settings.github_client_id,
                    "client_secret": self._settings.github_client_secret,
                    "code": code,
                    "redirect_uri": self._redirect_uri(),
                    "code_verifier": code_verifier,
                },
            )
            if token_resp.status_code >= 400:
                raise UnauthorizedError(detail="GitHub token exchange failed")
            token_body = token_resp.json()
            access_token = token_body.get("access_token")
            if not access_token:
                raise UnauthorizedError(detail="GitHub token exchange failed")

            user_resp = await client.get(
                GITHUB_USER_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            if user_resp.status_code >= 400:
                raise UnauthorizedError(detail="Failed to load GitHub user")
            data = user_resp.json()
            return GitHubUser(
                id=str(data["id"]),
                login=str(data["login"]),
                name=data.get("name"),
            )


class FakeGitHubOAuthClient:
    """Test double: maps authorization codes to fixed users."""

    def __init__(
        self,
        users_by_code: dict[str, GitHubUser] | None = None,
        *,
        client_id: str = "test-client",
    ) -> None:
        self.users_by_code = users_by_code or {}
        self.client_id = client_id
        self.last_authorize_params: dict[str, str] = {}

    async def build_authorize_url(self, state: str, code_challenge: str) -> str:
        self.last_authorize_params = {
            "state": state,
            "code_challenge": code_challenge,
            "client_id": self.client_id,
        }
        return (
            f"https://github.com/login/oauth/authorize?"
            f"client_id={self.client_id}&state={state}"
            f"&code_challenge={code_challenge}&code_challenge_method=S256"
        )

    async def exchange_code(self, code: str, code_verifier: str) -> GitHubUser:
        if not code_verifier:
            raise UnauthorizedError(detail="Missing PKCE verifier")
        user = self.users_by_code.get(code)
        if user is None:
            raise UnauthorizedError(detail="Invalid authorization code")
        return user


def assert_allowlisted(github_id: str, settings: Settings) -> None:
    allow = set(settings.admin_github_ids)
    if not allow:
        raise ForbiddenError(detail="Admin allowlist is empty")
    if github_id not in allow:
        raise ForbiddenError(detail="GitHub user is not allowlisted")
