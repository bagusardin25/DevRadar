"""Devfolio directory connector.

Devfolio's website is driven by an undocumented JSON API. We read the three
phases that can still be joined (``application_open``, ``live``, ``upcoming``),
drop in-person events and hand online ones to the harvest.

Offline tests pass ``fixtures`` (raw API rows) or ``http_get``.
"""

from __future__ import annotations

import logging
import re
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

DEVFOLIO_API = "https://api.devfolio.co/api/hackathons"
PHASES = ("application_open", "live", "upcoming")
# ``limit`` is mandatory: without it one page is ~1,000 rows (~915 KB).
PAGE_LIMIT = 50
MAX_PAGES_PER_PHASE = 5
MAX_BYTES = 2_097_152

_SUBDOMAIN = re.compile(r"^[a-z0-9-]{1,63}$")


def _directory_url(phase: str, page: int) -> str:
    query = urlencode(
        [("filter", phase), ("page", str(page)), ("limit", str(PAGE_LIMIT))]
    )
    return f"{DEVFOLIO_API}?{query}"


class DevfolioConnector(DirectoryConnector):
    name = "devfolio"
    connector_type = "devfolio"

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

    async def _discover_live(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        phase_name, _, page_text = (cursor or f"{PHASES[0]}:1").partition(":")
        if phase_name not in PHASES:
            phase_name = PHASES[0]
        page = max(1, int(page_text or 1))
        url = _directory_url(phase_name, page)
        try:
            payload = await self.load_json(url, MAX_BYTES)
        except SourceBlocked as blocked:
            return self.block(url, blocked.reason)
        except Exception as exc:
            return self.failed(url, exc)

        rows = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return self.failed(url, ValueError("unexpected Devfolio payload shape"))

        items = self._parse_rows(rows, query)
        pages = payload.get("pages")
        total_pages = pages if isinstance(pages, int) and not isinstance(pages, bool) else 1
        if rows and page < total_pages and page < MAX_PAGES_PER_PHASE:
            next_cursor: str | None = f"{phase_name}:{page + 1}"
        else:
            index = PHASES.index(phase_name) + 1
            next_cursor = f"{PHASES[index]}:1" if index < len(PHASES) else None
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
        row_id = row.get("uuid") or row.get("slug")
        title = str(row.get("name") or "").strip()
        if not row_id or not title:
            self.skipped("missing_id_or_title", row_id)
            return None

        is_online = row.get("is_online")
        if not isinstance(is_online, bool):
            self.skipped("unknown_mode", row_id)
            return None
        if not is_online:
            return None  # in-person: online-only discover

        setting = row.get("hackathon_setting")
        setting = setting if isinstance(setting, dict) else {}
        subdomain = str(setting.get("subdomain") or row.get("slug") or "").strip()
        if not _SUBDOMAIN.match(subdomain):
            self.skipped("bad_subdomain", row_id)
            return None

        starts_raw, ends_raw = row.get("starts_at"), row.get("ends_at")
        starts_at, ends_at = iso_utc(starts_raw), iso_utc(ends_raw)
        if (starts_raw is not None and starts_at is None) or (
            ends_raw is not None and ends_at is None
        ):
            self.skipped("bad_dates", row_id)
            return None
        if self.ended(ends_at):
            return None

        brand = row.get("hackathon_brand")
        organization = (
            str(brand.get("name")) if isinstance(brand, dict) and brand.get("name") else None
        )
        themes = [
            str(theme["name"])
            for theme in (row.get("themes") or [])
            if isinstance(theme, dict) and theme.get("name")
        ]
        url = f"https://{subdomain}.devfolio.co/"
        return DiscoveryCandidate(
            external_id=str(row_id),
            url=url,
            title=title,
            metadata={
                "source": self.name,
                "mode": "online",
                "starts_at": starts_at,
                "ends_at": ends_at,
                "prize_value": None,
                "organization": organization,
                "location": "Online",
                "themes": themes,
                "directory_url": url,
                "registration_ends_at": setting.get("reg_ends_at"),
            },
        )
