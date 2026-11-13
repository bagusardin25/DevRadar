"""Hack2skill directory connector.

Hack2skill's public event listing is served by a JSON API that the website
itself calls (``/api/v1/innovator/public/event/public-list``). It is paged
(``page`` / ``records``), filtered by a ``start`` / ``end`` window and carries
no prize or location text. ``robots.txt`` allows ``/`` and ``/event/``.

The API answers ``data`` as a plain list of rows (verified 2026-10-10); an
older shape with ``data.docs`` is accepted too. Rows are mapped, in-person
events are dropped, and online and hybrid ones are handed to the harvest.

Offline tests pass ``fixtures`` (raw API rows) or ``http_get``.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

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

logger = logging.getLogger(__name__)

HACK2SKILL_HOST = "https://hack2skill.com"
HACK2SKILL_API = f"{HACK2SKILL_HOST}/api/v1/innovator/public/event/public-list"
PAGE_SIZE = 9
MAX_PAGES = 12
WINDOW_DAYS = 365
MAX_BYTES = 1_048_576

_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_HTTP_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)

_MODES = {
    "ONLINE": "online",
    "VIRTUAL": "online",
    "HYBRID": "hybrid",
    "IN_PERSON": "in_person",
    "INPERSON": "in_person",
    "OFFLINE": "in_person",
    "ONSITE": "in_person",
    "ON_SITE": "in_person",
}


def _mode_from(value: Any) -> str | None:
    key = re.sub(r"[\s-]+", "_", str(value or "").strip().upper())
    return _MODES.get(key)


def _event_url(event_url: Any) -> str | None:
    """Absolute public page for an ``eventUrl`` (a slug or an absolute URL)."""
    text = str(event_url or "").strip()
    if not text:
        return None
    if _HTTP_URL.match(text):
        return text
    slug = text.strip("/")
    if slug.startswith("event/"):
        slug = slug[len("event/") :]
    if not _SLUG.match(slug):
        return None
    return f"{HACK2SKILL_HOST}/event/{slug}"


def _rows_from_payload(payload: Any) -> tuple[list[Any], int] | None:
    """Return ``(rows, total_pages)`` or ``None`` when the shape is unknown."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    rows = data.get("docs") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return None
    pages = payload.get("pages")
    if pages is None and isinstance(data, dict):
        pages = data.get("pages")
    total = pages if isinstance(pages, int) and not isinstance(pages, bool) else 1
    return rows, max(1, total)


class Hack2SkillConnector(DirectoryConnector):
    name = "hack2skill"
    connector_type = "hack2skill"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._seen: set[str] = set()

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        if self._fixtures is not None:
            return self._discover_fixtures(query, cursor)
        if cursor is None:
            self._seen = set()  # a fresh walk
        return await self._discover_live(query, cursor)

    # -- fixtures ---------------------------------------------------------- #

    def _discover_fixtures(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        assert self._fixtures is not None
        start = int(cursor or 0)
        cap = max(1, query.result_cap)
        self._seen = set()  # the whole fixture list is re-parsed on every call
        items = self._parse_rows(self._fixtures, query)
        page = items[start : start + cap]
        next_cursor = str(start + cap) if start + cap < len(items) else None
        return DiscoveryPage(items=page, next_cursor=next_cursor)

    # -- live -------------------------------------------------------------- #

    def _directory_url(self, page: int) -> str:
        now = self.now()
        window = now + timedelta(days=WINDOW_DAYS)
        params = urlencode(
            [
                ("page", str(page)),
                ("records", str(PAGE_SIZE)),
                ("search", ""),
                ("start", now.strftime("%Y-%m-%dT%H:%M:%S.000Z")),
                ("end", window.strftime("%Y-%m-%dT%H:%M:%S.000Z")),
            ]
        )
        return f"{HACK2SKILL_API}?{params}"

    async def _discover_live(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        try:
            page = max(1, int(cursor or 1))
        except ValueError:
            page = 1
        url = self._directory_url(page)
        try:
            payload = await self.load_json(url, MAX_BYTES)
        except SourceBlocked as blocked:
            return self.block(url, blocked.reason)
        except Exception as exc:
            return self.failed(url, exc)

        parsed = _rows_from_payload(payload)
        if parsed is None:
            return self.failed(url, ValueError("unexpected Hack2skill payload shape"))
        rows, total_pages = parsed

        items = self._parse_rows(rows, query)
        next_cursor = (
            str(page + 1) if rows and page < total_pages and page < MAX_PAGES else None
        )
        return DiscoveryPage(items=items, next_cursor=next_cursor)

    # -- rows -------------------------------------------------------------- #

    def _parse_rows(
        self, rows: list[Any], query: ConnectorQuery
    ) -> list[DiscoveryCandidate]:
        items: list[DiscoveryCandidate] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = self._candidate_from_row(row)
            if item is None:
                continue
            if not matches_query(item.title, query.query_text):
                continue
            if item.external_id in self._seen:
                continue
            self._seen.add(item.external_id)
            items.append(item)
        return items

    def _candidate_from_row(self, row: dict[str, Any]) -> DiscoveryCandidate | None:
        row_id = row.get("_id") or row.get("eventUrl")
        title = str(row.get("title") or "").strip()
        url = _event_url(row.get("eventUrl"))
        if not row_id or not title or url is None:
            self.skipped("missing_id_title_or_url", row_id)
            return None

        mode = _mode_from(row.get("mode"))
        if mode is None:
            self.skipped("unknown_mode", row_id)
            return None
        if mode == "in_person":
            return None  # online-only discover

        starts_raw = row.get("submissionStart") or row.get("registrationStart")
        ends_raw = row.get("submissionEnd") or row.get("registrationEnd")
        reg_end_raw = row.get("registrationEnd")
        starts_at, ends_at = iso_utc(starts_raw), iso_utc(ends_raw)
        registration_ends_at = iso_utc(reg_end_raw)
        if (
            (starts_raw is not None and starts_at is None)
            or (ends_raw is not None and ends_at is None)
            or (reg_end_raw is not None and registration_ends_at is None)
        ):
            self.skipped("bad_dates", row_id)
            return None
        if self.ended(ends_at):
            return None

        if mode == "online":
            location = "Online"
        else:
            place = ", ".join(
                str(part).strip() for part in (row.get("city"), row.get("country")) if part
            )
            location = f"Hybrid, {place}" if place else "Hybrid"

        return DiscoveryCandidate(
            external_id=str(row_id),
            url=url,
            title=title,
            metadata={
                "source": self.name,
                "mode": mode,
                "starts_at": starts_at,
                "ends_at": ends_at,
                # The listing exposes no prize field at all.
                "prize_value": None,
                "prize_text": None,
                "organization": None,
                "location": location,
                "themes": [],
                "directory_url": url,
                "registration_ends_at": registration_ends_at,
            },
        )
