"""Devpost directory connector.

Offline tests pass ``fixtures``. Production harvest (no fixtures) calls
Devpost's public listing API — the same JSON the website uses — filtered to
**online** + open/upcoming hackathons.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlencode

from app.ingestion.fetcher import FetchPolicy, fetch_url
from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
    FetchRequest,
)

logger = logging.getLogger(__name__)

DEVPOST_API = "https://devpost.com/api/hackathons"
# Devpost silently caps ``per_page`` at 40 (asking for 50 returns 40 rows and
# ``meta.per_page == 40``), so never ask for more.
DEVPOST_MAX_PER_PAGE = 40
USER_AGENT = (
    "Mozilla/5.0 (compatible; DevRadarBot/0.2; "
    "+https://github.com/bagusardin25/DevRadar)"
)

_PRIZE_VALUE = re.compile(r"([\d,]+)")

HttpGet = Callable[[str], Awaitable[dict[str, Any]]]


def is_online_listing(row: dict[str, Any]) -> bool:
    """True when the directory row is an online / virtual event."""
    location = row.get("displayed_location")
    if isinstance(location, dict):
        icon = str(location.get("icon") or "").strip().lower()
        if icon == "globe":
            return True
        text = str(location.get("location") or "").strip().lower()
    else:
        text = str(location or "").strip().lower()
    return "online" in text or "virtual" in text or "remote" in text


def parse_prize_amount(raw: object) -> int | None:
    """Pull an integer prize from Devpost's HTML-ish ``prize_amount`` field."""
    text = re.sub(r"<[^>]+>", "", str(raw or ""))
    match = _PRIZE_VALUE.search(text.replace(",", ""))
    if match is None:
        match = _PRIZE_VALUE.search(text)
    if match is None:
        return None
    digits = match.group(1).replace(",", "")
    try:
        value = int(digits)
    except ValueError:
        return None
    return value if value > 0 else None


def _directory_url(*, page: int, per_page: int) -> str:
    query = urlencode(
        [
            ("challenge_type[]", "online"),
            ("status[]", "open"),
            ("status[]", "upcoming"),
            ("page", str(max(1, page))),
            ("per_page", str(max(1, min(per_page, DEVPOST_MAX_PER_PAGE)))),
        ]
    )
    return f"{DEVPOST_API}?{query}"


class DevpostConnector:
    name = "devpost"
    connector_type = "devpost"

    def __init__(
        self,
        fixtures: list[dict[str, Any]] | None = None,
        *,
        http_get: HttpGet | None = None,
    ) -> None:
        self._fixtures = list(fixtures or [])
        self._http_get = http_get

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        if self._fixtures:
            return self._discover_fixtures(query, cursor)
        return await self._discover_live(query, cursor)

    async def fetch_detail(self, candidate: DiscoveryCandidate) -> FetchRequest:
        return FetchRequest(url=candidate.url, metadata={"connector": self.name})

    def _discover_fixtures(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        start = int(cursor or 0)
        cap = query.result_cap
        # Fixtures without a location stay (legacy test rows). Rows that *do*
        # declare an in-person location are dropped so harvest tests can mix.
        filtered = [
            row
            for row in self._fixtures
            if (
                not query.query_text
                or query.query_text.lower() in (row.get("title") or "").lower()
            )
            and (not _has_location(row) or is_online_listing(row))
        ]
        page = filtered[start : start + cap]
        items = [_candidate_from_row(row) for row in page]
        next_cursor = str(start + cap) if start + cap < len(filtered) else None
        return DiscoveryPage(items=items, next_cursor=next_cursor)

    async def _discover_live(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        page = int(cursor or 1)
        per_page = max(1, min(int(query.result_cap or 20), DEVPOST_MAX_PER_PAGE))
        url = _directory_url(page=page, per_page=per_page)
        try:
            payload = await self._load_directory(url)
        except Exception as exc:
            logger.warning(
                "devpost_directory_failed",
                extra={"url": url, "error": f"{type(exc).__name__}: {exc}"},
            )
            return DiscoveryPage(items=[], next_cursor=None)

        rows = payload.get("hackathons") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return DiscoveryPage(items=[], next_cursor=None)

        items: list[DiscoveryCandidate] = []
        needle = (query.query_text or "").strip().lower()
        for row in rows:
            if not isinstance(row, dict):
                continue
            if not is_online_listing(row):
                continue
            title = str(row.get("title") or "")
            if needle and needle not in title.lower():
                continue
            item = _candidate_from_row(row)
            if item is not None:
                items.append(item)

        meta_raw = payload.get("meta")
        meta: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
        total = int(meta.get("total_count") or 0)
        # Page arithmetic must use the page size Devpost actually served, not
        # the one we asked for, or the last page(s) are silently skipped.
        served = int(meta.get("per_page") or 0) or per_page
        fetched_through = (page - 1) * served + len(rows)
        next_cursor = (
            str(page + 1) if rows and total and fetched_through < total else None
        )
        return DiscoveryPage(items=items, next_cursor=next_cursor)

    async def _load_directory(self, url: str) -> dict[str, Any]:
        if self._http_get is not None:
            return await self._http_get(url)
        policy = FetchPolicy(
            timeout_seconds=20.0,
            max_bytes=1_048_576,
            allowed_content_type_prefixes=("application/json", "text/json", "text/plain"),
            user_agent=USER_AGENT,
        )
        doc = await fetch_url(url, policy)
        payload = json.loads(doc.body.decode("utf-8", errors="replace"))
        if not isinstance(payload, dict):
            raise ValueError("Devpost directory did not return a JSON object")
        return payload


def _has_location(row: dict[str, Any]) -> bool:
    location = row.get("displayed_location")
    if isinstance(location, dict):
        return bool(location.get("location") or location.get("icon"))
    return bool(location)


def _candidate_from_row(row: dict[str, Any]) -> DiscoveryCandidate | None:
    url = str(row.get("url") or "").strip()
    if not url:
        return None
    prize = parse_prize_amount(row.get("prize_amount"))
    location = row.get("displayed_location")
    location_text = ""
    if isinstance(location, dict):
        location_text = str(location.get("location") or "")
    themes = [
        str(theme.get("name"))
        for theme in (row.get("themes") or [])
        if isinstance(theme, dict) and theme.get("name")
    ]
    return DiscoveryCandidate(
        external_id=str(row.get("id") or url),
        url=url,
        title=str(row.get("title") or "") or None,
        metadata={
            "source": "devpost",
            "mode": "online",
            "organization": row.get("organization_name"),
            "open_state": row.get("open_state"),
            "submission_period_dates": row.get("submission_period_dates"),
            "time_left_to_submission": row.get("time_left_to_submission"),
            "prize_value": prize,
            "themes": themes,
            "location": location_text,
        },
    )
