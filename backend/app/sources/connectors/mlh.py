"""Major League Hacking events connector.

Live mode reads the MLH season page, which embeds an Inertia.js JSON payload
(``<script data-page="app">``); ``props.upcomingEvents`` lists every upcoming
event of the season in one request. Digital and hybrid events are returned;
physical ones are dropped.

The original fixture mode (rows of ``url`` / ``title`` / ``mode``) is kept for
legacy tests: ``MLHConnector(fixtures=[...])``.
"""

from __future__ import annotations

import html
import json
import logging
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
)
from app.sources.connectors.directory_common import (
    DirectoryConnector,
    HttpGet,
    SourceBlocked,
    iso_utc,
    matches_query,
)

logger = logging.getLogger(__name__)

MLH_HOST = "https://www.mlh.com"
MAX_BYTES = 4_194_304
LIVE_STATUSES = frozenset({"pending", "in_progress"})

_HTTP_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_DATA_PAGE = re.compile(
    r"<script[^>]*\bdata-page=\"app\"[^>]*>(.*?)</script>", re.DOTALL
)


def seasons_to_read(now: datetime) -> list[int]:
    """MLH seasons run roughly Aug-Jul and are named for the year they end in.

    From May through July the next season is usually announced already, so it
    is read as well.
    """
    season = now.year + 1 if now.month >= 8 else now.year
    seasons = [season]
    if 5 <= now.month <= 7:
        seasons.append(season + 1)
    return seasons


def extract_inertia_page(page_html: str) -> dict[str, Any] | None:
    """Return the decoded Inertia page object, or ``None`` when absent."""
    match = _DATA_PAGE.search(page_html)
    if match is None:
        return None
    raw = match.group(1).strip()
    if raw.startswith("{&"):
        raw = html.unescape(raw)
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _mode_from_format(format_type: Any) -> str | None:
    text = str(format_type or "").strip().lower()
    if text == "digital":
        return "online"
    if "hybrid" in text:
        return "hybrid"
    if text == "physical":
        return "in_person"
    return None


class MLHConnector(DirectoryConnector):
    name = "mlh"
    connector_type = "mlh"

    def __init__(
        self,
        fixtures: list[dict[str, Any]] | None = None,
        *,
        http_get: HttpGet | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(fixtures, http_get=http_get, now=now)

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        if self._fixtures is not None:
            return self._discover_legacy_fixtures(query, cursor)
        return await self._discover_live(query, cursor)

    # -- legacy fixtures (unchanged behaviour) ----------------------------- #

    def _discover_legacy_fixtures(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        fixtures = self._fixtures or []
        start = int(cursor or 0)
        cap = query.result_cap
        page = fixtures[start : start + cap]
        items = [
            DiscoveryCandidate(
                external_id=str(f.get("id") or f["url"]),
                url=f["url"],
                title=f.get("title"),
                metadata={"mode": f.get("mode", "online"), "source": "mlh"},
            )
            for f in page
        ]
        nxt = str(start + cap) if start + cap < len(fixtures) else None
        return DiscoveryPage(items=items, next_cursor=nxt)

    # -- live -------------------------------------------------------------- #

    async def _discover_live(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        seasons = seasons_to_read(self.now())
        season = seasons[0]
        if cursor:
            try:
                season = int(cursor.partition(":")[0])
            except ValueError:
                season = seasons[0]
        following = [s for s in seasons if s > season]
        next_cursor = f"{following[0]}:1" if following else None

        url = f"{MLH_HOST}/seasons/{season}/events"
        try:
            page_html = await self.load_text(url, MAX_BYTES)
        except SourceBlocked as blocked:
            return self.block(url, blocked.reason)
        except Exception as exc:
            # e.g. a 404 before the next season is announced: skip this season.
            self.failed(url, exc)
            return DiscoveryPage(items=[], next_cursor=next_cursor)

        page = extract_inertia_page(page_html)
        props = page.get("props") if page else None
        events = props.get("upcomingEvents") if isinstance(props, dict) else None
        if not isinstance(events, list):
            logger.warning(
                "mlh_payload_missing",
                extra={"url": url, "found_page": page is not None},
            )
            return DiscoveryPage(items=[], next_cursor=next_cursor)

        items: list[DiscoveryCandidate] = []
        for row in events:
            if not isinstance(row, dict):
                continue
            item = self._candidate_from_row(row)
            if item is not None and matches_query(item.title, query.query_text):
                items.append(item)
        return DiscoveryPage(items=items, next_cursor=next_cursor)

    def _candidate_from_row(self, row: dict[str, Any]) -> DiscoveryCandidate | None:
        row_id = row.get("id")
        if row.get("status") not in LIVE_STATUSES:
            return None
        title = str(row.get("name") or "").strip()
        slug = str(row.get("slug") or "").strip()
        website = str(row.get("websiteUrl") or "").strip()
        if not _HTTP_URL.match(website):
            website = ""
        url = website or (f"{MLH_HOST}/events/{slug}" if slug else "")
        if not row_id or not title or not url:
            self.skipped("missing_id_title_or_url", row_id)
            return None

        mode = _mode_from_format(row.get("formatType"))
        if mode is None:
            self.skipped("unknown_mode", row_id)
            return None
        if mode == "in_person":
            return None  # online-only discover

        starts_raw, ends_raw = row.get("startsAt"), row.get("endsAt")
        starts_at, ends_at = iso_utc(starts_raw), iso_utc(ends_raw)
        if (starts_raw is not None and starts_at is None) or (
            ends_raw is not None and ends_at is None
        ):
            self.skipped("bad_dates", row_id)
            return None
        if self.ended(ends_at):
            return None

        path = str(row.get("url") or "")
        directory_url = (
            f"{MLH_HOST}{path}"
            if path.startswith("/events/")
            else (f"{MLH_HOST}/events/{slug}" if slug else None)
        )
        return DiscoveryCandidate(
            external_id=str(row_id),
            url=url,
            title=title,
            metadata={
                "source": self.name,
                "mode": mode,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "prize_value": None,
                "organization": None,
                "league": "MLH",
                "location": str(row.get("location") or "").strip(),
                "region": row.get("region"),
                "themes": [],
                "directory_url": directory_url,
            },
        )
