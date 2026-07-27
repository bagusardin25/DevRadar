"""Google OAuth (authorization code + PKCE) for admin login."""

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

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

# Route served by app.api.admin.auth, appended after API_BASE_PATH.
CALLBACK_PATH = "/admin/auth/google/callback"
LOCAL_API_ORIGIN = "http://localhost:8000"


@dataclass(frozen=True, slots=True)
class GoogleUser:
    id: str  # Google `sub` — stable, immutable account identifier.
    email: str
    email_verified: bool = False
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


class GoogleOAuthClient(Protocol):
    async def build_authorize_url(self, state: str, code_challenge: str) -> str: ...

    async def exchange_code(self, code: str, code_verifier: str) -> GoogleUser: ...


class HttpGoogleOAuthClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _redirect_uri(self) -> str:
        """Build the callback URL Google must redirect back to.

        OAUTH_REDIRECT_BASE_URL is the API's own public origin — required outside
        local development, and it must be the SAME host the frontend runs on so
        the session cookie set here travels back (localhost != 127.0.0.1).
        """
        base = self._settings.api_base_path.rstrip("/")
        origin = self._settings.oauth_redirect_base_url.strip().rstrip("/")
        if origin:
            if not origin.startswith(("http://", "https://")):
                raise ValidationError(
                    detail="OAUTH_REDIRECT_BASE_URL must include a scheme, "
                    "e.g. https://api.example.com"
                )
            return f"{origin}{base}{CALLBACK_PATH}"
        if self._settings.is_production:
            raise ValidationError(
                detail="OAUTH_REDIRECT_BASE_URL must be set in production: the public "
                "origin of this API, matching the Authorized redirect URI registered "
                "on the Google OAuth client (e.g. https://api.example.com)"
            )
        return f"{LOCAL_API_ORIGIN}{base}{CALLBACK_PATH}"

    async def build_authorize_url(self, state: str, code_challenge: str) -> str:
        if not self._settings.google_client_id:
            raise ValidationError(detail="Google OAuth is not configured")
        params = {
            "client_id": self._settings.google_client_id,
            "redirect_uri": self._redirect_uri(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            # Always show the account chooser so switching admin accounts is easy.
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str) -> GoogleUser:
        if not self._settings.google_client_id or not self._settings.google_client_secret:
            raise ValidationError(detail="Google OAuth is not configured")
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "grant_type": "authorization_code",
                    "client_id": self._settings.google_client_id,
                    "client_secret": self._settings.google_client_secret,
                    "code": code,
                    "redirect_uri": self._redirect_uri(),
                    "code_verifier": code_verifier,
                },
            )
            if token_resp.status_code >= 400:
                raise UnauthorizedError(detail="Google token exchange failed")
            access_token = token_resp.json().get("access_token")
            if not access_token:
                raise UnauthorizedError(detail="Google token exchange failed")

            user_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_resp.status_code >= 400:
                raise UnauthorizedError(detail="Failed to load Google profile")
            data = user_resp.json()
            sub = data.get("sub")
            email = data.get("email")
            if not sub or not email:
                raise UnauthorizedError(detail="Google profile missing sub/email")
            return GoogleUser(
                id=str(sub),
                email=str(email),
                email_verified=bool(data.get("email_verified", False)),
                name=data.get("name"),
            )


class FakeGoogleOAuthClient:
    """Test double: maps authorization codes to fixed users."""

    def __init__(
        self,
        users_by_code: dict[str, GoogleUser] | None = None,
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
            f"{GOOGLE_AUTHORIZE_URL}?"
            f"client_id={self.client_id}&state={state}"
            f"&code_challenge={code_challenge}&code_challenge_method=S256"
        )

    async def exchange_code(self, code: str, code_verifier: str) -> GoogleUser:
        if not code_verifier:
            raise UnauthorizedError(detail="Missing PKCE verifier")
        user = self.users_by_code.get(code)
        if user is None:
            raise UnauthorizedError(detail="Invalid authorization code")
        return user


def assert_allowlisted(email: str, email_verified: bool, settings: Settings) -> None:
    """Admit only allowlisted, verified Google email addresses.

    Matching is case-insensitive on the email. A Google account whose email is
    not verified is rejected: an unverified address is not proof of ownership.
    """
    allow = {e.strip().lower() for e in settings.admin_google_emails if e.strip()}
    if not allow:
        raise ForbiddenError(
            detail="Admin allowlist is empty: set ADMIN_GOOGLE_EMAILS to allowed emails"
        )
    if not email_verified:
        raise ForbiddenError(
            detail=f"Google email '{email}' is not verified"
        )
    if email.strip().lower() not in allow:
        raise ForbiddenError(
            detail=f"Google account '{email}' is not allowlisted in ADMIN_GOOGLE_EMAILS"
        )
