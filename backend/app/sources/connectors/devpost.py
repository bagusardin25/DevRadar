"""Devpost directory connector.

Offline tests pass ``fixtures``. Production harvest (no fixtures) calls
Devpost's public listing API — the same JSON the website uses — filtered to
**online** + open/upcoming hackathons.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
)
from app.sources.connectors.directory_common import (
    USER_AGENT as USER_AGENT,
)
from app.sources.connectors.directory_common import (
    DirectoryConnector,
    HttpGet,
    SourceBlocked,
)

logger = logging.getLogger(__name__)

DEVPOST_API = "https://devpost.com/api/hackathons"
# Devpost silently caps ``per_page`` at 40 (asking for 50 returns 40 rows and
# ``meta.per_page == 40``), so never ask for more.
DEVPOST_MAX_PER_PAGE = 40
DEVPOST_MAX_BYTES = 1_048_576

_PRIZE_VALUE = re.compile(r"([\d,]+)")

_MONTHS = {
    name: number
    for number, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        start=1,
    )
}
_MON = r"([A-Za-z]{3})[a-z]*\.?"
_PERIOD_PATTERNS = (
    # Dec 17, 2025 - Feb 09, 2026
    re.compile(rf"^{_MON} (\d{{1,2}}), (\d{{4}}) - {_MON} (\d{{1,2}}), (\d{{4}})$"),
    # Aug 21 - Oct 02, 2026
    re.compile(rf"^{_MON} (\d{{1,2}}) - {_MON} (\d{{1,2}}), (\d{{4}})$"),
    # Sep 03 - 25, 2026
    re.compile(rf"^{_MON} (\d{{1,2}}) - (\d{{1,2}}), (\d{{4}})$"),
    # Aug 29, 2026
    re.compile(rf"^{_MON} (\d{{1,2}}), (\d{{4}})$"),
)


def parse_period_dates(text: object) -> tuple[str | None, str | None]:
    """Turn Devpost's ``submission_period_dates`` into ISO UTC start/end.

    Handles the four shapes Devpost serves; anything else (or an impossible /
    reversed range) returns ``(None, None)``. Start is 00:00:00Z of the first
    day, end is 23:59:59Z of the last day.
    """
    cleaned = re.sub(r"\s+", " ", str(text or "").replace("–", "-")).strip()
    if not cleaned:
        return None, None
    try:
        parts = _match_period(cleaned)
        if parts is None:
            return None, None
        start = datetime(parts[0], parts[1], parts[2], tzinfo=UTC)
        end = datetime(parts[3], parts[4], parts[5], 23, 59, 59, tzinfo=UTC)
    except (ValueError, KeyError):
        return None, None
    if end < start:
        return None, None
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")


def _match_period(text: str) -> tuple[int, int, int, int, int, int] | None:
    """Return (y1, m1, d1, y2, m2, d2) for a recognised period string."""

    def month(name: str) -> int:
        return _MONTHS[name.lower()]

    if m := _PERIOD_PATTERNS[0].match(text):
        a, b, c, d, e, f = m.groups()
        return int(c), month(a), int(b), int(f), month(d), int(e)
    if m := _PERIOD_PATTERNS[1].match(text):
        a, b, c, d, e = m.groups()
        return int(e), month(a), int(b), int(e), month(c), int(d)
    if m := _PERIOD_PATTERNS[2].match(text):
        a, b, c, d = m.groups()
        return int(d), month(a), int(b), int(d), month(a), int(c)
    if m := _PERIOD_PATTERNS[3].match(text):
        a, b, c = m.groups()
        return int(c), month(a), int(b), int(c), month(a), int(b)
    return None


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


class DevpostConnector(DirectoryConnector):
    name = "devpost"
    connector_type = "devpost"

    def __init__(
        self,
        fixtures: list[dict[str, Any]] | None = None,
        *,
        http_get: HttpGet | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        # ``now`` is accepted for a uniform constructor; Devpost's listing is
        # already filtered to open/upcoming events server-side.
        super().__init__(fixtures, http_get=http_get, now=now)
        self._fixtures = list(fixtures or [])

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        if self._fixtures:
            return self._discover_fixtures(query, cursor)
        return await self._discover_live(query, cursor)

    def _discover_fixtures(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        start = int(cursor or 0)
        cap = query.result_cap
        # Fixtures without a location stay (legacy test rows). Rows that *do*
        # declare an in-person location are dropped so harvest tests can mix.
        filtered = [
            row
            for row in self._fixtures or []
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
        except SourceBlocked as blocked:
            return self.block(url, blocked.reason)
        except Exception as exc:
            return self.failed(url, exc)

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
        payload = await self.load_json(url, DEVPOST_MAX_BYTES)
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
    period = row.get("submission_period_dates")
    starts_at, ends_at = parse_period_dates(period)
    return DiscoveryCandidate(
        external_id=str(row.get("id") or url),
        url=url,
        title=str(row.get("title") or "") or None,
        metadata={
            "source": "devpost",
            "mode": "online",
            "organization": row.get("organization_name"),
            "open_state": row.get("open_state"),
            "submission_period_dates": period,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "time_left_to_submission": row.get("time_left_to_submission"),
            "prize_value": prize,
            "themes": themes,
            "location": location_text,
            "directory_url": url,
        },
    )
