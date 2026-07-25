"""Resolve the caller's IP for abuse controls."""

from __future__ import annotations

from fastapi import Request

FALLBACK_IP = "0.0.0.0"


def client_ip(request: Request, trusted_proxy_hops: int = 0) -> str:
    """Best-effort client IP, used only as a rate-limit bucket key.

    Every hop appends to `X-Forwarded-For`, so entries are trustworthy only as
    far back as the infrastructure we control; anything further left was
    supplied by the caller and is free-form. Reading the left-most entry — the
    obvious-looking choice — hands anonymous callers an unlimited quota, since
    a fresh fake value per request lands in a fresh bucket.

    So we count `trusted_proxy_hops` entries back from the right. The default of
    0 ignores the header entirely and uses the socket peer, which is correct
    when the app is exposed directly; set it to the number of proxies actually
    in front of the app (1 for a single load balancer).
    """
    peer = request.client.host if request.client and request.client.host else None
    if trusted_proxy_hops <= 0:
        return peer or FALLBACK_IP

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer or FALLBACK_IP

    parts = [p.strip() for p in forwarded.split(",") if p.strip()]
    index = len(parts) - trusted_proxy_hops
    if index < 0:
        # Chain is shorter than configured, so the deployment does not match
        # `trusted_proxy_hops`. The peer is the only value we can still trust.
        return peer or FALLBACK_IP
    return parts[index]
