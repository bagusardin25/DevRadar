"""Hashing helpers for abuse identifiers and optional submitter email."""

from __future__ import annotations

import base64
import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings


def hash_ip(ip: str, secret: str) -> str:
    """HMAC-SHA256 of client IP using email/session secret material."""
    return hmac.new(
        secret.encode("utf-8"),
        ip.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_user_agent(user_agent: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        user_agent.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_email(email: str, hmac_key: str) -> str:
    normalized = email.strip().lower()
    return hmac.new(
        hmac_key.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@lru_cache(maxsize=4)
def _fernet_from_key(key_material: str) -> Fernet:
    """Derive a Fernet key from configured material (dev-friendly)."""
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_email(email: str, settings: Settings) -> str:
    f = _fernet_from_key(settings.email_encryption_key)
    return f.encrypt(email.strip().lower().encode("utf-8")).decode("ascii")


def decrypt_email(token: str, settings: Settings) -> str | None:
    try:
        f = _fernet_from_key(settings.email_encryption_key)
        return f.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def job_idempotency_key(canonical_url: str, bucket_hours: int = 24) -> str:
    """Stable job key for URL + coarse time bucket (UTC hour / window)."""
    import time

    # Floor to multi-hour buckets so retries within the window collapse.
    window = int(time.time()) // (bucket_hours * 3600)
    material = f"ingestion.fetch_submission|{canonical_url}|{window}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
