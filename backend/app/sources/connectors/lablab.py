"""lablab.ai directory connector.

``https://lablab.ai/ai-hackathons`` is a Next.js page whose event list travels
inside React Server Component flight data (``self.__next_f.push([1, "..."])``).
We decode those chunks, find the ``sortedEvents`` array and map it. This is the
most fragile of the directory sources, so every step validates its shape and
degrades to an empty page (with a warning) instead of raising.
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

LABLAB_URL = "https://lablab.ai/ai-hackathons"
MAX_BYTES = 3_145_728
MAX_DECODED_CHARS = 8_000_000

_PUSH = re.compile(r"self\.__next_f\.push\((\[.*?\])\)</script>", re.DOTALL)
_SLUG = re.compile(r"^[a-z0-9-]+$")
_KEY = '"sortedEvents":'


def decode_rsc_text(page_html: str, max_chars: int = MAX_DECODED_CHARS) -> tuple[str, int]:
    """Concatenate the string chunks of every RSC push, in order.

    Returns ``(text, pushes)``. Chunks may split a value, so they must be
    joined before any JSON is located. Decoding stops once ``max_chars`` is
    exceeded.
    """
    pushes = 0
    parts: list[str] = []
    size = 0
    for match in _PUSH.finditer(page_html):
        pushes += 1
        try:
            chunk = json.loads(match.group(1))
        except ValueError:
            continue
        if not (
            isinstance(chunk, list)
            and len(chunk) == 2
            and chunk[0] == 1
            and isinstance(chunk[1], str)
        ):
            continue
        parts.append(chunk[1])
        size += len(chunk[1])
        if size > max_chars:
            logger.warning(
                "lablab_decoded_size_exceeded",
                extra={"decoded_len": size, "limit": max_chars},
            )
            return "".join(parts), pushes
    return "".join(parts), pushes


def extract_sorted_events(
    page_html: str, *, max_chars: int = MAX_DECODED_CHARS
) -> list[dict[str, Any]] | None:
    """Return the ``sortedEvents`` list from the page, or ``None`` on any failure."""
    text, _pushes = decode_rsc_text(page_html, max_chars)
    if len(text) > max_chars:
        return None
    return _events_from_text(text)


def _events_from_text(text: str) -> list[dict[str, Any]] | None:
    index = text.find(_KEY)
    if index < 0:
        return None
    try:
        value, _end = json.JSONDecoder().raw_decode(text, index + len(_KEY))
    except ValueError:
        return None
    if not isinstance(value, list):
        return None
    for row in value:
        if not (isinstance(row, dict) and "slug" in row and "name" in row):
            return None
    return value


def _mode_from_event_type(event_type: Any) -> str | None:
    return {"ONLINE": "online", "HYBRID": "hybrid", "ONSITE": "in_person"}.get(
        str(event_type or "").upper()
    )


def _tech_names(row: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("techs", "technologyList"):
        values = row.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            name = value.get("name") if isinstance(value, dict) else value
            if isinstance(name, str) and name.strip() and name not in names:
                names.append(name.strip())
    return names


class LablabConnector(DirectoryConnector):
    name = "lablab"
    connector_type = "lablab"
    _missing_end = 0

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
            page_html = await self.load_text(LABLAB_URL, MAX_BYTES)
        except SourceBlocked as blocked:
            return self.block(LABLAB_URL, blocked.reason)
        except Exception as exc:
            return self.failed(LABLAB_URL, exc)

        text, pushes = decode_rsc_text(page_html)
        rows = None if len(text) > MAX_DECODED_CHARS else _events_from_text(text)
        if rows is None:
            logger.warning(
                "lablab_payload_missing",
                extra={
                    "pushes": pushes,
                    "decoded_len": len(text),
                    "found_key": _KEY in text,
                },
            )
            self.degraded = "lablab_payload_missing"
            return DiscoveryPage(items=[], next_cursor=None)
        return DiscoveryPage(items=self._parse_rows(rows, query), next_cursor=None)

    # -- rows -------------------------------------------------------------- #

    def _parse_rows(
        self, rows: list[Any], query: ConnectorQuery
    ) -> list[DiscoveryCandidate]:
        items: list[DiscoveryCandidate] = []
        seen: set[str] = set()
        self._missing_end = 0
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
        if self._missing_end:
            # The listing holds ~144 past events: without an end date there is
            # no way to tell them from live ones, so they are never queued.
            logger.warning(
                "lablab_rows_missing_end",
                extra={"skipped": self._missing_end, "rows": len(rows)},
            )
        return items

    def _candidate_from_row(self, row: dict[str, Any]) -> DiscoveryCandidate | None:
        row_id = row.get("id") or row.get("slug")
        if row.get("type") not in (None, "HACKATHON"):
            return None
        if row.get("deletedAt"):
            return None

        title = str(row.get("name") or "").strip()
        slug = str(row.get("slug") or "").strip()
        if not title or not _SLUG.match(slug):
            self.skipped("missing_title_or_bad_slug", row_id)
            return None

        starts_raw, ends_raw = row.get("startAt"), row.get("endAt")
        starts_at, ends_at = iso_utc(starts_raw), iso_utc(ends_raw)
        if (starts_raw is not None and starts_at is None) or (
            ends_raw is not None and ends_at is None
        ):
            self.skipped("bad_dates", row_id)
            return None
        if ends_at is None:
            self._missing_end += 1
            return None
        if self.ended(ends_at):
            return None

        # ``status`` / ``approvalStatus`` read DRAFT on every row, so they are
        # deliberately not used as filters.
        mode = _mode_from_event_type(row.get("eventType"))
        if mode is None:
            self.skipped("unknown_mode", row_id)
            return None
        if mode == "in_person":
            return None  # online-only discover

        counts = row.get("_count")
        participants = counts.get("participants") if isinstance(counts, dict) else None
        url = f"https://lablab.ai/event/{slug}"
        return DiscoveryCandidate(
            external_id=str(row_id),
            url=url,
            title=title,
            metadata={
                "source": self.name,
                "mode": mode,
                "starts_at": starts_at,
                "ends_at": ends_at,
                # ``paymentAmount`` is a listing fee next to the Stripe fields,
                # not a prize, so no prize is reported.
                "prize_value": None,
                "organization": "lablab.ai",
                "location": "Online" if mode == "online" else "Hybrid",
                "themes": _tech_names(row),
                "directory_url": url,
                "participants": participants,
                "signup_active": row.get("signupActive"),
            },
        )
