"""SSRF protection: validate URLs and resolved IP addresses."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.errors import ValidationError
from app.submissions.url_policy import _BLOCKED_HOSTS, _METADATA_SUFFIXES, canonicalize_url

_BLOCKED_LITERAL_IPS = frozenset({"169.254.169.254", "fd00:ec2::254", "0.0.0.0", "::"})


class SSRFError(ValidationError):
    """URL blocked by outbound fetch policy."""

    def __init__(self, detail: str = "URL blocked by fetch policy") -> None:
        super().__init__(
            detail=detail,
            errors=[{"field": "url", "message": detail}],
        )


def assert_public_url(url: str) -> str:
    """Canonicalize and reject obviously unsafe targets. Returns canonical URL."""
    try:
        canonical = canonicalize_url(url)
    except ValidationError as exc:
        raise SSRFError(detail=str(exc)) from exc
    return canonical.canonical


def is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if str(ip) in _BLOCKED_LITERAL_IPS:
        return True
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def resolve_and_validate_host(host: str) -> list[str]:
    """DNS-resolve host and ensure every address is publicly routable.

    Returns resolved IP strings. Raises SSRFError if any address is blocked.
    """
    host = host.lower().rstrip(".")
    if host in _BLOCKED_HOSTS or any(host.endswith(s) for s in _METADATA_SUFFIXES):
        raise SSRFError(detail=f"Host not allowed: {host}")

    # Literal IP
    try:
        ip = ipaddress.ip_address(host)
        if is_blocked_ip(ip):
            raise SSRFError(detail=f"Blocked IP address: {host}")
        return [str(ip)]
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SSRFError(detail=f"DNS resolution failed for {host}") from exc

    resolved: list[str] = []
    for info in infos:
        sockaddr = info[4]
        addr = str(sockaddr[0])
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if is_blocked_ip(ip):
            raise SSRFError(detail=f"Resolved address blocked for {host}: {addr}")
        if addr not in resolved:
            resolved.append(addr)

    if not resolved:
        raise SSRFError(detail=f"No usable addresses for {host}")
    return resolved


def validate_url_for_fetch(url: str) -> tuple[str, str, list[str]]:
    """Full pre-fetch validation.

    Returns (canonical_url, host, resolved_ips).
    """
    canonical = assert_public_url(url)
    parsed = urlparse(canonical)
    host = (parsed.hostname or "").lower()
    if not host:
        raise SSRFError(detail="Missing host")
    ips = resolve_and_validate_host(host)
    return canonical, host, ips
