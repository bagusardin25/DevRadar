"""Redis-backed admin sessions with CSRF tokens."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import asdict, dataclass
from typing import Protocol

import redis.asyncio as aioredis

from app.config import Settings

SESSION_COOKIE = "devradar_admin_session"
CSRF_HEADER = "X-CSRF-Token"
SESSION_TTL_SECONDS = 8 * 3600  # 8 hours inactivity window
OAUTH_STATE_TTL_SECONDS = 600
SESSION_KEY_PREFIX = "devradar:admin:session:"
OAUTH_STATE_PREFIX = "devradar:admin:oauth:"


@dataclass(slots=True)
class AdminIdentity:
    subject: str  # OAuth `sub` — stable account identifier
    email: str
    admin_user_id: str
    csrf_token: str
    session_id: str


@dataclass(slots=True)
class SessionRecord:
    subject: str
    email: str
    admin_user_id: str
    csrf_token: str
    created_at: float
    last_seen_at: float

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> SessionRecord:
        data = json.loads(raw)
        return cls(**data)


@dataclass(slots=True)
class OAuthPending:
    code_verifier: str
    created_at: float

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> OAuthPending:
        data = json.loads(raw)
        return cls(**data)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionStore(Protocol):
    async def create_session(
        self,
        *,
        subject: str,
        email: str,
        admin_user_id: str,
    ) -> tuple[str, AdminIdentity]:
        """Return (raw_session_token, identity)."""
        ...

    async def get_session(self, raw_token: str) -> AdminIdentity | None: ...

    async def touch_session(self, raw_token: str) -> None: ...

    async def revoke_session(self, raw_token: str) -> None: ...

    async def save_oauth_state(self, state: str, code_verifier: str) -> None: ...

    async def pop_oauth_state(self, state: str) -> OAuthPending | None: ...


class RedisSessionStore:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    def _client(self) -> aioredis.Redis[str]:
        return aioredis.from_url(self._redis_url, decode_responses=True)

    async def _close(self, r: aioredis.Redis[str]) -> None:
        aclose = getattr(r, "aclose", None)
        if aclose is not None:
            await aclose()
        else:
            await r.close()

    async def create_session(
        self,
        *,
        subject: str,
        email: str,
        admin_user_id: str,
    ) -> tuple[str, AdminIdentity]:
        raw = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        now = time.time()
        record = SessionRecord(
            subject=subject,
            email=email,
            admin_user_id=admin_user_id,
            csrf_token=csrf,
            created_at=now,
            last_seen_at=now,
        )
        r = self._client()
        try:
            await r.set(
                f"{SESSION_KEY_PREFIX}{hash_token(raw)}",
                record.to_json(),
                ex=SESSION_TTL_SECONDS,
            )
        finally:
            await self._close(r)
        identity = AdminIdentity(
            subject=subject,
            email=email,
            admin_user_id=admin_user_id,
            csrf_token=csrf,
            session_id=hash_token(raw),
        )
        return raw, identity

    async def get_session(self, raw_token: str) -> AdminIdentity | None:
        r = self._client()
        try:
            raw = await r.get(f"{SESSION_KEY_PREFIX}{hash_token(raw_token)}")
            if not raw:
                return None
            rec = SessionRecord.from_json(raw)
            if time.time() - rec.last_seen_at > SESSION_TTL_SECONDS:
                await r.delete(f"{SESSION_KEY_PREFIX}{hash_token(raw_token)}")
                return None
            return AdminIdentity(
                subject=rec.subject,
                email=rec.email,
                admin_user_id=rec.admin_user_id,
                csrf_token=rec.csrf_token,
                session_id=hash_token(raw_token),
            )
        finally:
            await self._close(r)

    async def touch_session(self, raw_token: str) -> None:
        r = self._client()
        try:
            key = f"{SESSION_KEY_PREFIX}{hash_token(raw_token)}"
            raw = await r.get(key)
            if not raw:
                return
            rec = SessionRecord.from_json(raw)
            rec.last_seen_at = time.time()
            await r.set(key, rec.to_json(), ex=SESSION_TTL_SECONDS)
        finally:
            await self._close(r)

    async def revoke_session(self, raw_token: str) -> None:
        r = self._client()
        try:
            await r.delete(f"{SESSION_KEY_PREFIX}{hash_token(raw_token)}")
        finally:
            await self._close(r)

    async def save_oauth_state(self, state: str, code_verifier: str) -> None:
        r = self._client()
        try:
            pending = OAuthPending(code_verifier=code_verifier, created_at=time.time())
            await r.set(
                f"{OAUTH_STATE_PREFIX}{state}",
                pending.to_json(),
                ex=OAUTH_STATE_TTL_SECONDS,
            )
        finally:
            await self._close(r)

    async def pop_oauth_state(self, state: str) -> OAuthPending | None:
        r = self._client()
        try:
            key = f"{OAUTH_STATE_PREFIX}{state}"
            raw = await r.get(key)
            if not raw:
                return None
            await r.delete(key)
            return OAuthPending.from_json(raw)
        finally:
            await self._close(r)


class InMemorySessionStore:
    """Test double for sessions and OAuth state."""

    def __init__(self) -> None:
        self.sessions: dict[str, SessionRecord] = {}
        self.oauth: dict[str, OAuthPending] = {}

    async def create_session(
        self,
        *,
        subject: str,
        email: str,
        admin_user_id: str,
    ) -> tuple[str, AdminIdentity]:
        raw = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        now = time.time()
        rec = SessionRecord(
            subject=subject,
            email=email,
            admin_user_id=admin_user_id,
            csrf_token=csrf,
            created_at=now,
            last_seen_at=now,
        )
        self.sessions[hash_token(raw)] = rec
        return raw, AdminIdentity(
            subject=subject,
            email=email,
            admin_user_id=admin_user_id,
            csrf_token=csrf,
            session_id=hash_token(raw),
        )

    async def get_session(self, raw_token: str) -> AdminIdentity | None:
        rec = self.sessions.get(hash_token(raw_token))
        if not rec:
            return None
        if time.time() - rec.last_seen_at > SESSION_TTL_SECONDS:
            del self.sessions[hash_token(raw_token)]
            return None
        return AdminIdentity(
            subject=rec.subject,
            email=rec.email,
            admin_user_id=rec.admin_user_id,
            csrf_token=rec.csrf_token,
            session_id=hash_token(raw_token),
        )

    async def touch_session(self, raw_token: str) -> None:
        rec = self.sessions.get(hash_token(raw_token))
        if rec:
            rec.last_seen_at = time.time()

    async def revoke_session(self, raw_token: str) -> None:
        self.sessions.pop(hash_token(raw_token), None)

    async def save_oauth_state(self, state: str, code_verifier: str) -> None:
        self.oauth[state] = OAuthPending(code_verifier=code_verifier, created_at=time.time())

    async def pop_oauth_state(self, state: str) -> OAuthPending | None:
        return self.oauth.pop(state, None)


def cookie_secure(settings: Settings) -> bool:
    """Prefer Settings.cookie_secure (True only when APP_ENV=production)."""
    return settings.cookie_secure


def session_cookie_kwargs(settings: Settings) -> dict[str, object]:
    return {
        "key": SESSION_COOKIE,
        "httponly": True,
        "secure": cookie_secure(settings),
        "samesite": "lax",
        "max_age": SESSION_TTL_SECONDS,
        "path": "/",
    }
