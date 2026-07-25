"""Shared HTTP policy and safe fetch helper for live discovery.

Every outbound request in a discovery run goes through here so the SSRF guard,
size caps and User-Agent stay consistent between seed resolution (feeds) and
detail fetches (individual opportunity pages).
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.ingestion.fetcher import FetchedDocument, FetchError, FetchPolicy, fetch_url
from app.ingestion.ssrf import SSRFError

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; DevRadarBot/0.2; "
    "+https://github.com/bagusardin25/DevRadar)"
)

ALLOWED_CONTENT_TYPE_PREFIXES = (
    "text/html",
    "text/plain",
    "text/markdown",
    "application/xhtml",
    "application/xml",
    "text/xml",
    "application/json",
    "application/rss",
    "application/atom",
)


def build_fetch_policy(settings: Settings) -> FetchPolicy:
    """Fetch policy shared by feed and detail requests."""
    return FetchPolicy(
        timeout_seconds=float(settings.fetch_timeout_seconds),
        max_bytes=int(settings.fetch_max_bytes),
        max_redirects=int(settings.fetch_max_redirects),
        allowed_content_type_prefixes=ALLOWED_CONTENT_TYPE_PREFIXES,
        user_agent=USER_AGENT,
    )


async def fetch_document(url: str, policy: FetchPolicy) -> FetchedDocument | None:
    """Fetch a URL, returning None when the response is unusable.

    A single dead link must never fail the whole discovery run, so blocked,
    timed-out and error responses are logged and skipped.
    """
    try:
        doc = await fetch_url(url, policy)
    except (SSRFError, FetchError) as exc:
        logger.info(
            "discovery_fetch_rejected",
            extra={"url": url, "error": f"{type(exc).__name__}: {exc}"},
        )
        return None
    except Exception as exc:  # network stack surprises must not kill the run
        logger.warning(
            "discovery_fetch_failed",
            extra={"url": url, "error": f"{type(exc).__name__}: {exc}"},
        )
        return None

    if doc.not_modified:
        return None
    if doc.status_code >= 400:
        logger.info(
            "discovery_fetch_http_error",
            extra={"url": url, "status": doc.status_code},
        )
        return None
    return doc


def decode_body(doc: FetchedDocument) -> str:
    """Best-effort text decode for feed parsing."""
    return doc.body.decode("utf-8", errors="replace")
