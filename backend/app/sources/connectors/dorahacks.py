"""DoraHacks directory connector.

DoraHacks' hub page is driven by a public JSON endpoint,
``/api/v1/hub/hackathons`` (``{count, next, previous, results[]}``). It has no
status filter and lists newest first, so we filter ended rows ourselves and stop
paging as soon as a whole page is already over.

Judgement calls:

* ``venue_form`` is ``Virtual`` / ``IRL`` (and possibly ``Hybrid``). Anything
  that is not clearly virtual or hybrid is treated as in-person and dropped.
* ``timeline_start`` / ``timeline_end`` are unix seconds; ``ends_at`` is
  ``timeline_end``.
* ``prize_value`` is only set when ``bonus_token`` is USD, USDC or USDT.
  Any other token (ETH, SOL, ...) leaves it ``None`` and the raw amount goes to
  ``prize_text``.
* ``registration_ends_at`` is always ``None``: the list payload has no
  registration deadline (``timeline_pre_register`` is not one).
* Rows without a ``uname`` have no known public slug and are skipped.

Offline tests pass ``fixtures`` (raw result rows) or ``http_get``.
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

DORAHACKS_API = "https://dorahacks.io/api/v1/hub/hackathons"
PUBLIC_BASE = "https://dorahacks.io/hackathon/"
PAGE_SIZE = 24
MAX_PAGES = 5
MAX_BYTES = 2_097_152

_UNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_USD_TOKENS = frozenset({"USD", "USDC", "USDT"})


def _directory_url(page: int) -> str:
    query = urlencode([("page", str(page)), ("page_size", str(PAGE_SIZE))])
    return f"{DORAHACKS_API}?{query}"


def _mode(venue_form: Any) -> str | None:
    text = str(venue_form or "").strip().lower()
    if text in {"virtual", "online"}:
        return "online"
    if text == "hybrid":
        return "hybrid"
    return None


class DoraHacksConnector(DirectoryConnector):
    name = "dorahacks"
    connector_type = "dorahacks"

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
        try:
            page = max(1, int(cursor or 1))
        except ValueError:
            page = 1
        url = _directory_url(page)
        try:
            payload = await self.load_json(url, MAX_BYTES)
        except SourceBlocked as blocked:
            return self.block(url, blocked.reason)
        except Exception as exc:
            return self.failed(url, exc)

        rows = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(payload, dict) or not isinstance(rows, list):
            return self.failed(url, ValueError("unexpected DoraHacks payload shape"))

        items = self._parse_rows(rows, query)
        has_next = bool(payload.get("next"))
        # Newest-first: once a whole page is over, later pages only get older.
        all_ended = bool(rows) and all(self._row_ended(row) for row in rows)
        if rows and has_next and not all_ended and page < MAX_PAGES:
            next_cursor: str | None = str(page + 1)
        else:
            next_cursor = None
        return DiscoveryPage(items=items, next_cursor=next_cursor)

    # -- rows -------------------------------------------------------------- #

    def _row_ended(self, row: Any) -> bool:
        if not isinstance(row, dict):
            return False
        return self.ended(iso_utc(row.get("timeline_end")))

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
        title = str(row.get("title") or "").strip()
        if row_id is None or isinstance(row_id, bool) or not title:
            self.skipped("missing_id_or_title", row_id)
            return None

        mode = _mode(row.get("venue_form"))
        if mode is None:
            return None  # in-person (or unknown): online-only discover

        uname = str(row.get("uname") or "").strip()
        if not _UNAME.match(uname):
            self.skipped("missing_or_bad_uname", row_id)
            return None

        starts_raw, ends_raw = row.get("timeline_start"), row.get("timeline_end")
        starts_at, ends_at = iso_utc(starts_raw), iso_utc(ends_raw)
        if (starts_raw is not None and starts_at is None) or (
            ends_raw is not None and ends_at is None
        ):
            self.skipped("bad_dates", row_id)
            return None
        if self.ended(ends_at):
            return None

        prize_value, prize_text = self._prize(row)
        owner = row.get("owner")
        organization = (
            str(owner["name"]).strip()
            if isinstance(owner, dict) and owner.get("name")
            else None
        )
        tags = row.get("tags")
        themes = (
            [part.strip() for part in tags.split(",") if part.strip()]
            if isinstance(tags, str)
            else []
        )
        venue = row.get("venue_name")
        location = str(venue).strip() if venue else "Online"
        url = f"{PUBLIC_BASE}{uname}"
        metadata: dict[str, Any] = {
            "source": self.name,
            "mode": mode,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "prize_value": prize_value,
            "organization": organization,
            "location": location or "Online",
            "themes": themes,
            "directory_url": url,
            "registration_ends_at": None,
        }
        if prize_text is not None:
            metadata["prize_text"] = prize_text
        return DiscoveryCandidate(
            external_id=str(row_id), url=url, title=title, metadata=metadata
        )

    @staticmethod
    def _prize(row: dict[str, Any]) -> tuple[int | None, str | None]:
        amount = row.get("bonus_price")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            return None, None
        if amount <= 0:
            return None, None
        token = str(row.get("bonus_token") or "").strip()
        if token.upper() in _USD_TOKENS:
            return int(amount), None
        return None, f"{amount:g} {token}".strip()
