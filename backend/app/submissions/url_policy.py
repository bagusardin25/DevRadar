"""URL canonicalization and SSRF-oriented submission policy."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.errors import ValidationError

_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata",
    }
)

_METADATA_SUFFIXES = (
    ".internal",
    ".localhost",
    ".local",
)


@dataclass(frozen=True, slots=True)
class CanonicalUrl:
    original: str
    canonical: str
    host: str
    scheme: str


def canonicalize_url(raw: str) -> CanonicalUrl:
    """Normalize a user-submitted URL or raise ValidationError."""
    if not raw or not raw.strip():
        raise ValidationError(
            detail="URL is required",
            errors=[{"field": "url", "message": "URL is required"}],
        )

    candidate = raw.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"

    try:
        parsed = urlparse(candidate)
    except ValueError as exc:
        raise ValidationError(
            detail="URL is malformed",
            errors=[{"field": "url", "message": "Malformed URL"}],
        ) from exc
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValidationError(
            detail="Only http and https URLs are supported",
            errors=[{"field": "url", "message": f"Unsupported scheme: {scheme or '(none)'}"}],
        )

    if parsed.username or parsed.password:
        raise ValidationError(
            detail="URLs must not include credentials",
            errors=[{"field": "url", "message": "Userinfo is not allowed"}],
        )

    try:
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise ValidationError(
            detail="URL host or port is invalid",
            errors=[{"field": "url", "message": "Invalid host or port"}],
        ) from exc
    if not host:
        raise ValidationError(
            detail="URL host is required",
            errors=[{"field": "url", "message": "Missing host"}],
        )

    if host in _BLOCKED_HOSTS or any(host.endswith(s) for s in _METADATA_SUFFIXES):
        raise ValidationError(
            detail="URL host is not allowed",
            errors=[{"field": "url", "message": "Private or local host blocked"}],
        )

    # Literal IP host checks (before DNS — submission stage).
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValidationError(
                detail="URL host is not allowed",
                errors=[{"field": "url", "message": "Private or local IP blocked"}],
            )
        # Cloud metadata common address
        if str(ip) in {"169.254.169.254", "fd00:ec2::254"}:
            raise ValidationError(
                detail="URL host is not allowed",
                errors=[{"field": "url", "message": "Metadata endpoint blocked"}],
            )
    except ValueError:
        # Not an IP literal — hostname path; still block obvious internal patterns.
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
            raise ValidationError(
                detail="URL host is not allowed",
                errors=[{"field": "url", "message": "Invalid IP host"}],
            ) from None

    # Drop default ports.
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        netloc = host
    elif port:
        netloc = f"{host}:{port}"
    else:
        netloc = host

    # Normalize path: ensure at least "/", collapse empty.
    path = parsed.path or "/"
    # Drop fragment; keep query sorted for stable canonical form.
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = urlencode(sorted(query_pairs))

    canonical = urlunparse((scheme, netloc, path, "", query, ""))
    return CanonicalUrl(original=raw.strip(), canonical=canonical, host=host, scheme=scheme)
