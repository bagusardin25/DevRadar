"""Commudle directory connector.

Commudle's hackathon directory is backed by a public JSON feed:
``https://json.commudle.com/api/v2/hackathons/public/all_hackathons`` with
``when=future`` (only ``future`` and ``past`` work) and cursor paging
(``data.page_info.{has_next_page,end_cursor}``, ``after=<end_cursor>``). Items
sit in ``data.page[].data``.

Judgement calls:

* Public URL: ``https://www.commudle.com/communities/{community.slug}/hackathons/{slug}``
  (confirmed against Commudle's own hackathon sitemap). Rows without a community
  slug are skipped, because the bare ``/hackathons/{slug}`` form is not served.
* ``hackathon_location_type`` is ``online`` / ``offline`` / ``hybrid``; offline
  rows are dropped.
* Dates are ISO strings with an offset (``+01:00``); they are normalised to UTC.
  ``registration_ends_at`` is ``None`` (the feed has no registration deadline).
* ``total_prize_amount`` is a currency map such as ``{"INR": 100000}``;
  ``prize_value`` is only set for a ``USD`` entry, otherwise the raw map goes
  to ``prize_text``.

Offline tests pass ``fixtures`` (raw ``data.page[].data`` rows) or ``http_get``.
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

COMMUDLE_API = "https://json.commudle.com/api/v2/hackathons/public/all_hackathons"
PUBLIC_BASE = "https://www.commudle.com/communities/"
PAGE_LIMIT = 20
MAX_PAGES = 5
MAX_BYTES = 2_097_152

_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_CURSOR = re.compile(r"^[A-Za-z0-9_=-]{1,512}$")
_MODES = {"online": "online", "hybrid": "hybrid"}


def _directory_url(after: str | None) -> str:
    params = [("when", "future"), ("limit", str(PAGE_LIMIT))]
    if after:
        params.append(("after", after))
    return f"{COMMUDLE_API}?{urlencode(params)}"


class CommudleConnector(DirectoryConnector):
    name = "commudle"
    connector_type = "commudle"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._seen: set[str] = set()
        self._pages_walked = 0

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        if self._fixtures is not None:
            return self._discover_fixtures(query, cursor)
        if cursor is None:
            self._seen = set()  # a fresh walk
            self._pages_walked = 0
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
        after = cursor if cursor and _CURSOR.match(cursor) else None
        url = _directory_url(after)
        try:
            payload = await self.load_json(url, MAX_BYTES)
        except SourceBlocked as blocked:
            return self.block(url, blocked.reason)
        except Exception as exc:
            return self.failed(url, exc)

        data = payload.get("data") if isinstance(payload, dict) else None
        entries = data.get("page") if isinstance(data, dict) else None
        if not isinstance(data, dict) or not isinstance(entries, list):
            return self.failed(url, ValueError("unexpected Commudle payload shape"))

        rows = [
            entry["data"]
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("data"), dict)
        ]
        items = self._parse_rows(rows, query)

        self._pages_walked += 1
        info = data.get("page_info")
        info = info if isinstance(info, dict) else {}
        end_cursor = info.get("end_cursor")
        if (
            entries
            and info.get("has_next_page") is True
            and isinstance(end_cursor, str)
            and _CURSOR.match(end_cursor)
            and self._pages_walked < MAX_PAGES
        ):
            next_cursor: str | None = end_cursor
        else:
            next_cursor = None
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
        row_id = row.get("id")
        title = str(row.get("name") or "").strip()
        if row_id is None or isinstance(row_id, bool) or not title:
            self.skipped("missing_id_or_title", row_id)
            return None

        mode = _MODES.get(str(row.get("hackathon_location_type") or "").strip().lower())
        if mode is None:
            return None  # offline / unknown: online-only discover

        community = row.get("community")
        community_slug = (
            str(community.get("slug") or "").strip() if isinstance(community, dict) else ""
        )
        slug = str(row.get("slug") or "").strip()
        if not _SLUG.match(slug) or not _SLUG.match(community_slug):
            self.skipped("bad_slug", row_id)
            return None

        starts_raw, ends_raw = row.get("start_date"), row.get("end_date")
        starts_at, ends_at = iso_utc(starts_raw), iso_utc(ends_raw)
        if (starts_raw is not None and starts_at is None) or (
            ends_raw is not None and ends_at is None
        ):
            self.skipped("bad_dates", row_id)
            return None
        if self.ended(ends_at):
            return None

        prize_value, prize_text = self._prize(row.get("total_prize_amount"))
        organization = (
            str(community["name"]).strip()
            if isinstance(community, dict) and community.get("name")
            else None
        )
        theme = str(row.get("hackathon_theme") or "").strip()
        url = f"{PUBLIC_BASE}{community_slug}/hackathons/{slug}"
        metadata: dict[str, Any] = {
            "source": self.name,
            "mode": mode,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "prize_value": prize_value,
            "organization": organization,
            "location": "Online" if mode == "online" else "Hybrid",
            "themes": [theme] if theme else [],
            "directory_url": url,
            "registration_ends_at": None,
        }
        if prize_text is not None:
            metadata["prize_text"] = prize_text
        return DiscoveryCandidate(
            external_id=str(row_id), url=url, title=title, metadata=metadata
        )

    @staticmethod
    def _prize(raw: Any) -> tuple[int | None, str | None]:
        if not isinstance(raw, dict):
            return None, None
        amounts = {
            str(code).upper(): float(value)
            for code, value in raw.items()
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value > 0
        }
        if not amounts:
            return None, None
        if set(amounts) == {"USD"}:
            return int(amounts["USD"]), None
        text = ", ".join(f"{value:g} {code}" for code, value in sorted(amounts.items()))
        return None, text
