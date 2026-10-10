"""Unstop directory connector.

Unstop exposes a public search API (``robots.txt`` allows ``/api/public/*``):
``/api/public/opportunity/search-result?opportunity=hackathons&oppstatus=open``.
Rows live in ``data.data[]`` and ``data.last_page`` bounds the paging. Unstop is
huge and mostly Indian college events, so only ``region`` ``online`` / ``hybrid``
rows survive.

Date fields Unstop provides (verified live): ``end_date`` (the event's last
date) and ``regnRequirements.start_regn_dt`` / ``end_regn_dt`` (registration
window). The list payload has **no event start date**, so ``starts_at`` is
``None``; ``ends_at`` is ``end_date`` and ``registration_ends_at`` is
``end_regn_dt``.

Prizes: ``prize_value`` is only set when every cash prize is in USD
(``currencyCode`` ``USD``); the amount is the "total prize pool" row when
present, otherwise the sum of the ranked prizes. Rupee (and any other) prizes
leave it ``None`` and the raw text goes to ``prize_text``.

Offline tests pass ``fixtures`` (raw rows) or ``http_get``.
"""

from __future__ import annotations

import logging
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

UNSTOP_API = "https://unstop.com/api/public/opportunity/search-result"
UNSTOP_BASE = "https://unstop.com/"
PER_PAGE = 15
MAX_PAGES = 5
MAX_BYTES = 3_145_728

_ONLINE_REGIONS = {"online": "online", "hybrid": "hybrid"}
_THEME_FILTER_TYPES = frozenset({"category", "domain"})
_CURRENCY_ICONS = {
    "fa-rupee": "INR",
    "fa-dollar": "USD",
    "fa-euro": "EUR",
    "fa-gbp": "GBP",
}


def _directory_url(page: int) -> str:
    query = urlencode(
        [
            ("opportunity", "hackathons"),
            ("oppstatus", "open"),
            ("page", str(page)),
            ("per_page", str(PER_PAGE)),
        ]
    )
    return f"{UNSTOP_API}?{query}"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _currency(prize: dict[str, Any]) -> str:
    code = prize.get("currencyCode")
    if isinstance(code, str) and code.strip():
        return code.strip().upper()
    return _CURRENCY_ICONS.get(str(prize.get("currency") or ""), "")


class UnstopConnector(DirectoryConnector):
    name = "unstop"
    connector_type = "unstop"

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

        data = payload.get("data") if isinstance(payload, dict) else None
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(data, dict) or not isinstance(rows, list):
            return self.failed(url, ValueError("unexpected Unstop payload shape"))

        items = self._parse_rows(rows, query)
        last_page = data.get("last_page")
        total_pages = (
            last_page
            if isinstance(last_page, int) and not isinstance(last_page, bool)
            else 1
        )
        if rows and page < total_pages and page < MAX_PAGES:
            next_cursor: str | None = str(page + 1)
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
        title = str(row.get("title") or "").strip()
        if row_id is None or isinstance(row_id, bool) or not title:
            self.skipped("missing_id_or_title", row_id)
            return None

        mode = _ONLINE_REGIONS.get(str(row.get("region") or "").strip().lower())
        if mode is None:
            return None  # offline / unknown region: online-only discover

        url = self._public_url(row)
        if url is None:
            self.skipped("missing_url", row_id)
            return None

        ends_raw = row.get("end_date")
        ends_at = iso_utc(ends_raw)
        if ends_raw is not None and ends_at is None:
            self.skipped("bad_dates", row_id)
            return None
        if self.ended(ends_at):
            return None

        regn = row.get("regnRequirements")
        regn = regn if isinstance(regn, dict) else {}
        registration_ends_at = iso_utc(regn.get("end_regn_dt"))

        organisation = row.get("organisation")
        organization = (
            str(organisation["name"]).strip()
            if isinstance(organisation, dict) and organisation.get("name")
            else None
        )
        themes = [
            str(flt["name"]).strip()
            for flt in (row.get("filters") or [])
            if isinstance(flt, dict)
            and flt.get("type") in _THEME_FILTER_TYPES
            and flt.get("name")
        ]
        prize_value, prize_text = self._prize(row.get("prizes"))
        metadata: dict[str, Any] = {
            "source": self.name,
            "mode": mode,
            "starts_at": None,
            "ends_at": ends_at,
            "prize_value": prize_value,
            "organization": organization,
            "location": "Online" if mode == "online" else "Hybrid",
            "themes": themes,
            "directory_url": url,
            "registration_ends_at": registration_ends_at,
        }
        if prize_text is not None:
            metadata["prize_text"] = prize_text
        return DiscoveryCandidate(
            external_id=str(row_id), url=url, title=title, metadata=metadata
        )

    @staticmethod
    def _public_url(row: dict[str, Any]) -> str | None:
        for key in ("public_url", "seo_url"):
            value = str(row.get(key) or "").strip()
            if not value:
                continue
            if value.startswith(UNSTOP_BASE):
                return value
            if "://" in value or value.startswith("//"):
                continue  # never follow a foreign host
            return UNSTOP_BASE + value.lstrip("/")
        return None

    @staticmethod
    def _prize(prizes: Any) -> tuple[int | None, str | None]:
        if not isinstance(prizes, list):
            return None, None
        cash: list[tuple[str, float, str]] = []  # (rank, amount, currency)
        for prize in prizes:
            if not isinstance(prize, dict):
                continue
            amount = _number(prize.get("cash"))
            if amount is None or amount <= 0:
                continue
            cash.append((str(prize.get("rank") or ""), amount, _currency(prize)))
        if not cash:
            return None, None
        currencies = {currency for _, _, currency in cash}
        pools = [amount for rank, amount, _ in cash if "pool" in rank.lower()]
        total = max(pools) if pools else sum(amount for _, amount, _ in cash)
        if currencies == {"USD"}:
            return int(total), None
        label = "/".join(sorted(c for c in currencies if c)) or "unknown currency"
        return None, f"{total:g} {label}"
