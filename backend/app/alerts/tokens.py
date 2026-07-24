"""Opaque tokens stored only as hashes."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def confirmation_expiry(now: datetime | None = None, hours: int = 24) -> datetime:
    now = now or datetime.now(UTC)
    return now + timedelta(hours=hours)
