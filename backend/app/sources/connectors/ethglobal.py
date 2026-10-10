"""ETHGlobal directory connector.

``https://ethglobal.com/events`` is a Next.js page whose event list travels in
React Server Component flight data (``self.__next_f.push([1, "..."])``) as a
``"events":[...]`` prop. The chunk decoder is shared with the lablab.ai
connector. Each row carries ``name, slug, type, medium, status, startTime,
endTime, city, signupDeadline``; the listing holds no prize information.

Only ``type == "hackathon"`` rows are kept (summits, meetups and cowork "cafe"
events are not hackathons). ``medium`` is ``virtual`` / ``physical`` (and, by
extension, ``hybrid``): physical rows are dropped, unknown values are skipped.
Every step validates its shape and degrades to an empty page (flagging
``degraded``) instead of raising.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
)
from app.sources.connectors.directory_common import (
    DirectoryConnector,
    SourceBlocked,
    iso_utc,
    matches_query,
)
from app.sources.connectors.lablab import MAX_DECODED_CHARS, decode_rsc_text

logger = logging.getLogger(__name__)

ETHGLOBAL_URL = "https://ethglobal.com/events"
EVENT_URL = "https://ethglobal.com/events/{slug}"
MAX_BYTES = 6_291_456  # the listing is ~1.8 MB because every row ships its styles

_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_KEY = '"events":'
_SKIPPED_STATUSES = frozenset({"finished", "cancelled", "canceled"})


def extract_events(
    page_html: str, *, max_chars: int = MAX_DECODED_CHARS
) -> list[dict[str, Any]] | None:
    """Return the ``events`` rows embedded in the page, or ``None`` on any failure."""
    text, _pushes = decode_rsc_text(page_html, max_chars)
    if len(text) > max_chars:
        return None
    return _events_from_text(text)


def _events_from_text(text: str) -> list[dict[str, Any]] | None:
    decoder = json.JSONDecoder()
    start = 0
    while True:
        index = text.find(_KEY, start)
        if index < 0:
            return None
        start = index + len(_KEY)
        try:
            value, _end = decoder.raw_decode(text, start)
        except ValueError:
            continue
        if not isinstance(value, list):
            continue
        rows = [
            row
            for row in value
            if isinstance(row, dict) and "slug" in row and "name" in row
        ]
        if rows:
            return rows


def _mode_from_medium(medium: Any) -> str | None:
    text = str(medium or "").strip().lower().replace("-", "_")
    if text in ("virtual", "online"):
        return "online"
    if text == "hybrid":
        return "hybrid"
    if text in ("physical", "in_person", "inperson", "onsite"):
        return "in_person"
    return None


def _city_name(row: dict[str, Any]) -> str | None:
    city = row.get("city")
    name = city.get("name") if isinstance(city, dict) else None
    return name.strip() if isinstance(name, str) and name.strip() else None


class EthglobalConnector(DirectoryConnector):
    name = "ethglobal"
    connector_type = "ethglobal"

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        if self._fixtures is not None:
            return self._discover_fixtures(query, cursor)
        return await self._discover_live(query)

    def _discover_fixtures(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        assert self._fixtures is not None
        start = int(cursor or 0)
        cap = max(1, query.result_cap)
        items = self._parse_rows(self._fixtures, query)
        page = items[start : start + cap]
        next_cursor = str(start + cap) if start + cap < len(items) else None
        return DiscoveryPage(items=page, next_cursor=next_cursor)

    async def _discover_live(self, query: ConnectorQuery) -> DiscoveryPage:
        try:
            page_html = await self.load_text(ETHGLOBAL_URL, MAX_BYTES)
        except SourceBlocked as blocked:
            return self.block(ETHGLOBAL_URL, blocked.reason)
        except Exception as exc:
            return self.failed(ETHGLOBAL_URL, exc)

        text, pushes = decode_rsc_text(page_html)
        rows = None if len(text) > MAX_DECODED_CHARS else _events_from_text(text)
        if rows is None:
            logger.warning(
                "ethglobal_payload_missing",
                extra={
                    "pushes": pushes,
                    "decoded_len": len(text),
                    "found_key": _KEY in text,
                },
            )
            self.degraded = "ethglobal_payload_missing"
            return DiscoveryPage(items=[], next_cursor=None)
        return DiscoveryPage(items=self._parse_rows(rows, query), next_cursor=None)

    # -- rows -------------------------------------------------------------- #

    def _parse_rows(
        self, rows: list[Any], query: ConnectorQuery
    ) -> list[DiscoveryCandidate]:
        items: list[DiscoveryCandidate] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = self._candidate_from_row(row)
            if item is None or item.external_id in seen:
                continue
            if not matches_query(item.title, query.query_text):
                continue
            seen.add(item.external_id)
            items.append(item)
        return items

    def _candidate_from_row(self, row: dict[str, Any]) -> DiscoveryCandidate | None:
        if str(row.get("type") or "").strip().lower() != "hackathon":
            return None
        row_id = row.get("id") if row.get("id") is not None else row.get("slug")
        if str(row.get("status") or "").strip().lower() in _SKIPPED_STATUSES:
            return None

        title = str(row.get("name") or "").strip()
        slug = str(row.get("slug") or "").strip()
        if not title or not _SLUG.match(slug):
            self.skipped("missing_title_or_bad_slug", row_id)
            return None

        mode = _mode_from_medium(row.get("medium"))
        if mode is None:
            self.skipped("unknown_mode", row_id)
            return None
        if mode == "in_person":
            return None  # online-only discover

        starts_raw, ends_raw = row.get("startTime"), row.get("endTime")
        starts_at, ends_at = iso_utc(starts_raw), iso_utc(ends_raw)
        if (starts_raw is not None and starts_at is None) or (
            ends_raw is not None and ends_at is None
        ):
            self.skipped("bad_dates", row_id)
            return None
        if self.ended(ends_at):
            return None

        city = _city_name(row)
        url = EVENT_URL.format(slug=slug)
        return DiscoveryCandidate(
            external_id=str(row_id),
            url=url,
            title=title,
            metadata={
                "source": self.name,
                "mode": mode,
                "starts_at": starts_at,
                "ends_at": ends_at,
                # The listing carries no prize data.
                "prize_value": None,
                "prize_text": None,
                "organization": "ETHGlobal",
                "location": "Online" if mode == "online" else (city or "Hybrid"),
                "themes": [],
                "directory_url": url,
                "registration_ends_at": iso_utc(row.get("signupDeadline")),
            },
        )
