"""Admin auth orchestration: OAuth callback, session cookies, CSRF/Origin."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.google import (
    GoogleOAuthClient,
    GoogleUser,
    HttpGoogleOAuthClient,
    assert_allowlisted,
    generate_pkce_pair,
    generate_state,
)
from app.auth.models import AdminUser
from app.auth.sessions import (
    CSRF_HEADER,
    SESSION_COOKIE,
    AdminIdentity,
    SessionStore,
    session_cookie_kwargs,
)
from app.config import Settings
from app.errors import ForbiddenError, UnauthorizedError, ValidationError


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        store: SessionStore,
        oauth: GoogleOAuthClient | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._store = store
        self._oauth = oauth or HttpGoogleOAuthClient(settings)

    async def start_google_oauth(self) -> tuple[str, str]:
        """Return (authorize_url, state)."""
        state = generate_state()
        verifier, challenge = generate_pkce_pair()
        await self._store.save_oauth_state(state, verifier)
        url = await self._oauth.build_authorize_url(state, challenge)
        return url, state

    async def complete_google_oauth(
        self,
        *,
        code: str,
        state: str,
        response: Response,
    ) -> AdminIdentity:
        if not code or not state:
            raise ValidationError(detail="Missing OAuth code or state")
        pending = await self._store.pop_oauth_state(state)
        if pending is None:
            raise UnauthorizedError(detail="Invalid or expired OAuth state")

        user = await self._oauth.exchange_code(code, pending.code_verifier)
        assert_allowlisted(user.email, user.email_verified, self._settings)
        admin_user = await self._upsert_admin(user)
        raw_token, identity = await self._store.create_session(
            subject=user.id,
            email=user.email,
            admin_user_id=str(admin_user.id),
        )
        self._set_session_cookie(response, raw_token)
        return identity

    async def logout(self, request: Request, response: Response) -> None:
        raw = request.cookies.get(SESSION_COOKIE)
        if raw:
            await self._store.revoke_session(raw)
        response.delete_cookie(SESSION_COOKIE, path="/")

    async def require_admin(
        self,
        request: Request,
        *,
        require_csrf: bool = False,
    ) -> AdminIdentity:
        raw = request.cookies.get(SESSION_COOKIE)
        if not raw:
            raise UnauthorizedError(detail="Not authenticated")
        identity = await self._store.get_session(raw)
        if identity is None:
            raise UnauthorizedError(detail="Session expired or invalid")

        if require_csrf:
            self._validate_origin(request)
            csrf = request.headers.get(CSRF_HEADER)
            if not csrf or csrf != identity.csrf_token:
                raise ForbiddenError(detail="CSRF validation failed")

        await self._store.touch_session(raw)
        return identity

    async def _upsert_admin(self, user: GoogleUser) -> AdminUser:
        result = await self._session.execute(
            select(AdminUser).where(AdminUser.subject == user.id)
        )
        admin = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if admin is None:
            admin = AdminUser(
                subject=user.id,
                email=user.email,
                active=True,
                allowlist_matched=True,
                last_login_at=now,
            )
            self._session.add(admin)
        else:
            if not admin.active:
                raise ForbiddenError(detail="Admin account is disabled")
            admin.email = user.email
            admin.allowlist_matched = True
            admin.last_login_at = now
        await self._session.flush()
        return admin

    def _set_session_cookie(self, response: Response, raw_token: str) -> None:
        kwargs = session_cookie_kwargs(self._settings)
        response.set_cookie(value=raw_token, **kwargs)  # type: ignore[arg-type]

    def _validate_origin(self, request: Request) -> None:
        origin = request.headers.get("origin")
        if origin is None:
            # Same-site navigations / non-browser clients may omit Origin;
            # still require CSRF header. Optionally check Referer.
            referer = request.headers.get("referer")
            if referer:
                origin = f"{urlparse(referer).scheme}://{urlparse(referer).netloc}"
            else:
                return
        allowed = set(self._settings.cors_origins)
        allowed.add(self._settings.frontend_url.rstrip("/"))
        # Normalize trailing slash
        allowed = {a.rstrip("/") for a in allowed}
        if origin.rstrip("/") not in allowed:
            raise ForbiddenError(detail="Origin not allowed")


def resolve_session_store(request: Request, settings: Settings) -> SessionStore:
    store = getattr(request.app.state, "session_store", None)
    if store is not None:
        return store  # type: ignore[no-any-return]
    from app.auth.sessions import RedisSessionStore

    return RedisSessionStore(settings.redis_url)


def resolve_google_oauth(request: Request, settings: Settings) -> GoogleOAuthClient:
    oauth = getattr(request.app.state, "google_oauth", None)
    if oauth is not None:
        return oauth  # type: ignore[no-any-return]
    return HttpGoogleOAuthClient(settings)
