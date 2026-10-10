"""Shared helpers for the live hackathon-directory connectors.

Devpost, Devfolio, MLH and lablab.ai all read a public listing, drop in-person
events and hand online/hybrid ones to the harvest. This module holds what they
share: the fetch wrappers with the bot-wall rule, date and title helpers, and a
small base class carrying the ``blocked`` flag.

Bot-wall rule: a CAPTCHA / WAF challenge is **never** worked around. The
connector stops, flags itself ``blocked`` and returns an empty page; the next
attempt is the next harvest window.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.ingestion.fetcher import FetchedDocument, FetchError, FetchPolicy, fetch_url
from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
    FetchRequest,
)

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; DevRadarBot/0.2; "
    "+https://github.com/bagusardin25/DevRadar)"
)

JSON_CONTENT_TYPES = ("application/json", "text/json", "text/plain", "text/html")
HTML_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml")

_BLOCK_STATUS = re.compile(r"HTTP (403|405|429|503)")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_WALL_TITLE = re.compile(
    r"verification|captcha|attention required|just a moment|access denied",
    re.IGNORECASE,
)
_WALL_MARKERS = ("awswaf", "cf-chl")
_TITLE_TOKENS = frozenset({"the"})
_YEAR_TOKEN = re.compile(r"^20\d\d$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class SourceBlocked(Exception):  # noqa: N818 (name fixed by the connector spec)
    """The source answered with a bot check / WAF challenge instead of data."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# --------------------------------------------------------------------------- #
# Bot-wall detection and fetching
# --------------------------------------------------------------------------- #


def bot_wall_reason(text: str) -> str | None:
    """Return why ``text`` looks like a bot-check page, else ``None``."""
    head = text[:4096]
    lowered = head.lower()
    for marker in _WALL_MARKERS:
        if marker in lowered:
            return f"marker:{marker}"
    match = _TITLE.search(head)
    if match and _WALL_TITLE.search(match.group(1)):
        return f"title:{match.group(1).strip()[:60]}"
    return None


def block_reason_for_error(exc: BaseException) -> str | None:
    """Return a block reason when ``exc`` is a WAF-style HTTP failure."""
    match = _BLOCK_STATUS.search(str(exc))
    if match and isinstance(exc, FetchError):
        return f"http_{match.group(1)}"
    return None


def _is_html(content_type: str | None) -> bool:
    return (content_type or "").split(";")[0].strip().lower().startswith("text/html")


async def _fetch(
    url: str, *, max_bytes: int, types: tuple[str, ...]
) -> FetchedDocument:
    policy = FetchPolicy(
        timeout_seconds=20.0,
        max_bytes=max_bytes,
        allowed_content_type_prefixes=types,
        user_agent=USER_AGENT,
    )
    try:
        return await fetch_url(url, policy)
    except FetchError as exc:
        reason = block_reason_for_error(exc)
        if reason is not None:
            raise SourceBlocked(reason) from exc
        raise


async def fetch_json(url: str, max_bytes: int) -> Any:
    """GET ``url`` and decode JSON. Raises :class:`SourceBlocked` on a bot wall."""
    doc = await _fetch(url, max_bytes=max_bytes, types=JSON_CONTENT_TYPES)
    text = doc.body.decode("utf-8", errors="replace")
    if _is_html(doc.content_type):
        raise SourceBlocked(bot_wall_reason(text) or "html_for_json")
    reason = bot_wall_reason(text)
    if reason is not None:
        raise SourceBlocked(reason)
    return json.loads(text)


async def fetch_text(url: str, max_bytes: int) -> str:
    """GET ``url`` as text. Raises :class:`SourceBlocked` on a bot wall."""
    doc = await _fetch(url, max_bytes=max_bytes, types=HTML_CONTENT_TYPES)
    text = doc.body.decode("utf-8", errors="replace")
    reason = bot_wall_reason(text)
    if reason is not None:
        raise SourceBlocked(reason)
    return text


# --------------------------------------------------------------------------- #
# Dates and titles
# --------------------------------------------------------------------------- #


def parse_instant(value: Any) -> datetime | None:
    """Parse a unix timestamp or ISO string (``$D`` prefix allowed) to UTC."""
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            seconds = float(value)
            if seconds > 1e11:  # milliseconds
                seconds /= 1000.0
            return datetime.fromtimestamp(seconds, tz=UTC)
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value).strip()
            if text.startswith("$D"):
                text = text[2:]
            if not text:
                return None
            parsed = datetime.fromisoformat(text)
    except (ValueError, OverflowError, OSError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso_utc(value: Any) -> str | None:
    """Normalise a unix int/float or ISO string (``$D`` prefix allowed) to UTC."""
    parsed = parse_instant(value)
    if parsed is None:
        return None
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def title_key(title: str | None) -> str:
    """Comparison key for cross-source title dedupe."""
    folded = unicodedata.normalize("NFKD", title or "")
    ascii_text = "".join(ch for ch in folded if not unicodedata.combining(ch))
    words = _NON_ALNUM.sub(" ", ascii_text.lower()).split()
    kept = [
        word
        for word in words
        if word not in _TITLE_TOKENS and not _YEAR_TOKEN.match(word)
    ]
    return " ".join(kept)


def ranges_overlap(
    a_start: Any,
    a_end: Any,
    b_start: Any,
    b_end: Any,
    slack_days: int = 1,
) -> bool:
    """True when two date ranges overlap, with ``slack_days`` of tolerance."""
    a0, b0 = parse_instant(a_start), parse_instant(b_start)
    if a0 is None or b0 is None:
        return False
    a1 = parse_instant(a_end) or a0
    b1 = parse_instant(b_end) or b0
    slack = timedelta(days=slack_days)
    return a0 - slack <= b1 and b0 - slack <= a1


# --------------------------------------------------------------------------- #
# Connector base
# --------------------------------------------------------------------------- #

HttpGet = Callable[[str], Awaitable[Any]]


class DirectoryConnector:
    """Common state and helpers for directory connectors."""

    name = ""
    connector_type = ""

    def __init__(
        self,
        fixtures: list[dict[str, Any]] | None = None,
        *,
        http_get: HttpGet | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._fixtures = None if fixtures is None else list(fixtures)
        self._http_get = http_get
        self._now_fn = now
        self.blocked = False
        self.degraded: str | None = None

    def now(self) -> datetime:
        return self._now_fn() if self._now_fn is not None else datetime.now(UTC)

    async def fetch_detail(self, candidate: DiscoveryCandidate) -> FetchRequest:
        return FetchRequest(url=candidate.url, metadata={"connector": self.name})

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        raise NotImplementedError

    # -- fetching ---------------------------------------------------------- #

    async def load_json(self, url: str, max_bytes: int) -> Any:
        if self._http_get is None:
            return await fetch_json(url, max_bytes)
        try:
            payload = await self._http_get(url)
        except SourceBlocked:
            raise
        except Exception as exc:
            reason = block_reason_for_error(exc)
            if reason is not None:
                raise SourceBlocked(reason) from exc
            raise
        if isinstance(payload, str):
            reason = bot_wall_reason(payload)
            if reason is not None:
                raise SourceBlocked(reason)
            if payload.lstrip().startswith("<"):
                raise SourceBlocked("html_for_json")
            return json.loads(payload)
        return payload

    async def load_text(self, url: str, max_bytes: int) -> str:
        if self._http_get is None:
            return await fetch_text(url, max_bytes)
        try:
            payload = await self._http_get(url)
        except SourceBlocked:
            raise
        except Exception as exc:
            reason = block_reason_for_error(exc)
            if reason is not None:
                raise SourceBlocked(reason) from exc
            raise
        if not isinstance(payload, str):
            raise TypeError("expected an HTML string")
        reason = bot_wall_reason(payload)
        if reason is not None:
            raise SourceBlocked(reason)
        return payload

    # -- outcomes ---------------------------------------------------------- #

    def block(self, url: str, reason: str) -> DiscoveryPage:
        self.blocked = True
        logger.warning(
            "source_blocked",
            extra={"source": self.name, "url": url, "reason": reason},
        )
        return DiscoveryPage(items=[], next_cursor=None)

    def failed(
        self, url: str, exc: BaseException, *, degrade: bool = True
    ) -> DiscoveryPage:
        if degrade:
            self.degraded = f"{self.name}_directory_failed"
        logger.warning(
            f"{self.name}_directory_failed",
            extra={"url": url, "error": f"{type(exc).__name__}: {exc}"},
        )
        return DiscoveryPage(items=[], next_cursor=None)

    def skipped(self, reason: str, row_id: Any) -> None:
        logger.info(
            f"{self.name}_row_skipped",
            extra={"reason": reason, "id": None if row_id is None else str(row_id)},
        )

    # -- shared row filters ------------------------------------------------ #

    def ended(self, ends_at: str | None) -> bool:
        """True when a known end date is already in the past."""
        if ends_at is None:
            return False
        parsed = parse_instant(ends_at)
        return parsed is not None and parsed < self.now()


def matches_query(title: str | None, query_text: str | None) -> bool:
    needle = (query_text or "").strip().lower()
    return not needle or needle in (title or "").lower()
