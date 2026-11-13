"""Hack Club hackathons directory connector.

``hackathons.hackclub.com`` publishes an open events API (linked from the
site's own footer as "Events API"): ``/api/events/upcoming/`` returns a JSON
list of upcoming events. Note the trailing slash: without it the host answers
``308``. The home page embeds the same rows (plus past ones) in its Next.js
``__NEXT_DATA__`` script; that parse is the fallback when the API is
unavailable or changes shape.

Mode: ``virtual`` -> online, ``hybrid`` -> hybrid, everything else is in
person and dropped. The listing is a single page: no paging.

Offline tests pass ``fixtures`` (raw event rows) or ``http_get``.
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

logger = logging.getLogger(__name__)

HACKCLUB_HOST = "https://hackathons.hackclub.com"
HACKCLUB_API = f"{HACKCLUB_HOST}/api/events/upcoming/"
HACKCLUB_PAGE = f"{HACKCLUB_HOST}/"
MAX_API_BYTES = 2_097_152
MAX_PAGE_BYTES = 3_145_728

_HTTP_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)
_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


def extract_embedded_events(page_html: str) -> list[dict[str, Any]] | None:
    """Return ``props.pageProps.events`` from the page, or ``None`` on any failure."""
    match = _NEXT_DATA.search(page_html)
    if match is None:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    props = data.get("props") if isinstance(data, dict) else None
    page_props = props.get("pageProps") if isinstance(props, dict) else None
    events = page_props.get("events") if isinstance(page_props, dict) else None
    if not isinstance(events, list):
        return None
    return events


def _mode_from(row: dict[str, Any]) -> str | None:
    virtual, hybrid = row.get("virtual"), row.get("hybrid")
    if not isinstance(virtual, bool) and not isinstance(hybrid, bool):
        return None
    if hybrid is True:
        return "hybrid"
    if virtual is True:
        return "online"
    return "in_person"


class HackClubConnector(DirectoryConnector):
    name = "hackclub"
    connector_type = "hackclub"

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        if self._fixtures is not None:
            return self._discover_fixtures(query, cursor)
        return await self._discover_live(query)

    # -- fixtures ---------------------------------------------------------- #

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

    # -- live -------------------------------------------------------------- #

    async def _discover_live(self, query: ConnectorQuery) -> DiscoveryPage:
        rows: list[Any] | None = None
        try:
            payload = await self.load_json(HACKCLUB_API, MAX_API_BYTES)
        except SourceBlocked as blocked:
            if blocked.reason != "html_for_json":
                return self.block(HACKCLUB_API, blocked.reason)
            logger.info("hackclub_api_html", extra={"url": HACKCLUB_API})
        except Exception as exc:
            logger.warning(
                "hackclub_api_failed",
                extra={"url": HACKCLUB_API, "error": f"{type(exc).__name__}: {exc}"},
            )
        else:
            if isinstance(payload, list):
                rows = payload
            else:
                logger.warning("hackclub_api_shape", extra={"url": HACKCLUB_API})

        if rows is None:
            try:
                page_html = await self.load_text(HACKCLUB_PAGE, MAX_PAGE_BYTES)
            except SourceBlocked as blocked:
                return self.block(HACKCLUB_PAGE, blocked.reason)
            except Exception as exc:
                return self.failed(HACKCLUB_PAGE, exc)
            rows = extract_embedded_events(page_html)
            if rows is None:
                logger.warning("hackclub_payload_missing", extra={"url": HACKCLUB_PAGE})
                self.degraded = "hackclub_payload_missing"
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
        row_id = row.get("id")
        title = str(row.get("name") or "").strip()
        website = str(row.get("website") or "").strip()
        if not row_id or not title or not _HTTP_URL.match(website):
            self.skipped("missing_id_title_or_website", row_id)
            return None

        mode = _mode_from(row)
        if mode is None:
            self.skipped("unknown_mode", row_id)
            return None
        if mode == "in_person":
            return None  # online-only discover

        starts_raw, ends_raw = row.get("start"), row.get("end")
        starts_at, ends_at = iso_utc(starts_raw), iso_utc(ends_raw)
        if (starts_raw is not None and starts_at is None) or (
            ends_raw is not None and ends_at is None
        ):
            self.skipped("bad_dates", row_id)
            return None
        if self.ended(ends_at):
            return None

        if mode == "online":
            location = "Online"
        else:
            place = ", ".join(
                str(part).strip()
                for part in (row.get("city"), row.get("state"), row.get("country"))
                if part
            )
            location = f"Hybrid, {place}" if place else "Hybrid"

        # The listing never labels rows with a theme: whether an event is a
        # high-school one is not stated per row, so ``themes`` stays empty.
        return DiscoveryCandidate(
            external_id=str(row_id),
            url=website,
            title=title,
            metadata={
                "source": self.name,
                "mode": mode,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "prize_value": None,
                "prize_text": None,
                "organization": "Hack Club" if row.get("hack_club_event") is True else None,
                "location": location,
                "themes": [],
                "directory_url": HACKCLUB_PAGE,
                "registration_ends_at": None,
            },
        )
