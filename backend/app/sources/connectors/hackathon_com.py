"""hackathon.com directory connector.

``https://www.hackathon.com/online`` is server-rendered (Marko). Each event is
a ``div.hero`` card carrying the title, an ``/event/<slug>`` link, topic tags,
a location (``Online`` for the online listing) and *day + month only* dates
(``Starts 02 Nov`` / ``Ends 02 Dec``). A ``ht-highlights__list`` strip repeats
the start date with a year (``2nd November 2026``) and an inline ``$MC=...``
script ships the same events as JSON (``eventType``, ``organizerName``, ...).

Year inference (the cards have none):

* the end date is the next occurrence on/after ``now - 30 days`` (so a freshly
  ended event is still dated correctly and then dropped by the ended filter);
* the start date is the latest occurrence on/before that end date, which rolls
  a ``28 Dec -> 03 Jan`` event across New Year correctly;
* when the highlight strip gives the start with a year, that year wins and the
  end is the first occurrence on/after the start.

The ``/online`` page only server-renders its highlight cards (the rest of the
search is client-side), so a harvest sees a handful of events. Pagination links
(``?page=N``) are followed when present, bounded by ``MAX_PAGES``.

The JSON is optional enrichment: it drops non-hackathon ``eventType`` rows
(``Event``, ``Conference`` ...) and supplies the organiser. Without it the
cards alone are enough.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlsplit

from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
)
from app.sources.connectors.directory_common import (
    DirectoryConnector,
    SourceBlocked,
    matches_query,
)

logger = logging.getLogger(__name__)

HOST = "https://www.hackathon.com"
LISTING_URL = f"{HOST}/online"
EVENT_URL = f"{HOST}/event/{{slug}}"
MAX_BYTES = 2_097_152
MAX_PAGES = 3
LOOKBACK_DAYS = 30

_EVENT_SLUG = re.compile(r"/event/([A-Za-z0-9][A-Za-z0-9._-]{0,200})(?:[/?#]|$)")
_LONG_DATE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\.?,?\s+(\d{4})")
# Result-list cards show only a start, e.g. "28 Sep - 08:00 AM".
_CARD_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\b")
_MC_MARKER = "$MC=(window.$MC||[]).concat("
_NON_HACKATHON_TYPES = frozenset(
    {"event", "conference", "meetup", "webinar", "workshop", "summit", "talk"}
)
_MODE_TAGS = frozenset({"virtual", "online", "hybrid"})
_MONTHS = {
    name: number
    for number, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        start=1,
    )
}


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #


def parse_month(text: str | None) -> int | None:
    """Month number from ``Nov`` / ``November`` / ``nov.``; ``None`` otherwise."""
    key = (text or "").strip().lower()[:3]
    return _MONTHS.get(key) if key.isalpha() else None


def parse_day(text: str | None) -> int | None:
    match = re.match(r"^\s*(\d{1,2})(?:st|nd|rd|th)?\s*$", text or "")
    return int(match.group(1)) if match else None


def _on_or_after(month: int, day: int, floor: date) -> date | None:
    for year in range(floor.year, floor.year + 6):  # 29 Feb needs a leap year
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= floor:
            return candidate
    return None


def _on_or_before(month: int, day: int, ceiling: date) -> date | None:
    for year in range(ceiling.year, ceiling.year - 6, -1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate <= ceiling:
            return candidate
    return None


def infer_range(
    start: tuple[int, int] | None,
    end: tuple[int, int] | None,
    today: date,
    anchor: date | None = None,
) -> tuple[date | None, date | None]:
    """Resolve ``(month, day)`` pairs without a year to concrete dates.

    ``start`` / ``end`` are ``(month, day)``. ``anchor`` is a start date whose
    year is known. See the module docstring for the rule.
    """
    floor = today - timedelta(days=LOOKBACK_DAYS)
    if anchor is not None and start is not None:
        return anchor, (_on_or_after(end[0], end[1], anchor) if end else None)
    if end is not None:
        end_date = _on_or_after(end[0], end[1], floor)
        if end_date is None:
            return None, None
        start_date = _on_or_before(start[0], start[1], end_date) if start else None
        return start_date, end_date
    if start is not None:
        return _on_or_after(start[0], start[1], floor), None
    return None, None


def parse_long_date(text: str | None) -> date | None:
    """``2nd November 2026`` -> ``date(2026, 11, 2)``."""
    match = _LONG_DATE.search(text or "")
    if match is None:
        return None
    month = parse_month(match.group(2))
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(1)))
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #


@dataclass
class Listing:
    """What one listing page holds: cards, highlight dates, JSON rows, links."""

    cards: list[dict[str, Any]] = field(default_factory=list)
    long_dates: dict[str, date] = field(default_factory=dict)
    json_rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    links: list[str] = field(default_factory=list)


class _ListingParser(HTMLParser):
    """Collects event cards and ``ht-highlights__item`` date buttons.

    Two card layouts are served: the highlights ``div.hero`` (start and end
    day/month) and the result-list ``div.ht-event-card`` (start only). Both
    become the same card dict.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.listing = Listing()
        self._card: dict[str, Any] | None = None
        self._item: dict[str, str] = {}
        self._capture: tuple[str, str] | None = None  # (tag, field)
        self._buffer: list[str] = []
        self._side = ""
        self._location_depth = 0
        self._location_parts: list[str] = []

    # -- helpers ----------------------------------------------------------- #

    def _start_capture(self, tag: str, name: str) -> None:
        self._capture = (tag, name)
        self._buffer = []

    def _commit(self, name: str) -> None:
        text = " ".join("".join(self._buffer).split())
        card = self._card
        if name == "item_name":
            self._item["name"] = text
        elif name == "item_date":
            self._item["date"] = text
            title, when = self._item.get("name"), parse_long_date(text)
            if title and when is not None:
                self.listing.long_dates[title] = when
        elif card is not None:
            if name == "title":
                card["title"] = text
            elif name == "topic" and text:
                card["topics"].append(text)
            elif name in ("start_day", "start_month", "end_day", "end_month"):
                card[name] = text
            elif name == "card_date":
                match = _CARD_DATE.search(text)
                if match is not None:
                    card["start_day"], card["start_month"] = match.group(1), match.group(2)

    # -- parser hooks ------------------------------------------------------ #

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        href = attributes.get("href")
        if tag == "a" and href:
            self.listing.links.append(href)

        if tag == "div" and self._location_depth:
            self._location_depth += 1
        if tag == "div" and ("hero" in classes or "ht-event-card" in classes):
            self._card = {
                "title": "",
                "href": "",
                "topics": [],
                "location": "",
                "start_day": "",
                "start_month": "",
                "end_day": "",
                "end_month": "",
            }
            self.listing.cards.append(self._card)
            self._side = ""
            return
        if tag == "button" and "ht-highlights__item" in classes:
            self._item = {}
        elif tag == "span" and "ht-highlights__item__name" in classes:
            self._start_capture(tag, "item_name")
        elif tag == "span" and "ht-highlights__item__date" in classes:
            self._start_capture(tag, "item_date")

        if self._card is None:
            return
        if tag == "a" and classes & {"hero__title", "ht-event-card__title"}:
            self._card["href"] = href or ""
            self._start_capture(tag, "title")
        elif tag == "a" and "ht-event-topics__tag" in classes:
            self._start_capture(tag, "topic")
        elif tag == "div" and classes & {"hero__key-info__location", "ht-event-card__location"}:
            self._location_depth = 1
            self._location_parts = []
        elif tag == "div" and "ht-event-card__date" in classes:
            self._start_capture(tag, "card_date")
        elif tag == "div" and "date--start" in classes:
            self._side = "start"
        elif tag == "div" and "date--end" in classes:
            self._side = "end"
        elif tag == "div" and "date__day" in classes and self._side:
            self._start_capture(tag, f"{self._side}_day")
        elif tag == "div" and "date__month" in classes and self._side:
            self._start_capture(tag, f"{self._side}_month")

    def handle_endtag(self, tag: str) -> None:
        if self._capture is not None and self._capture[0] == tag:
            name = self._capture[1]
            self._capture = None
            self._commit(name)
        if tag == "div" and self._location_depth:
            self._location_depth -= 1
            if self._location_depth == 0 and self._card is not None:
                self._card["location"] = ", ".join(self._location_parts)

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._buffer.append(data)
        if self._location_depth:
            text = " ".join(data.split())
            if text:
                self._location_parts.append(text)


def _json_rows(page_html: str) -> dict[str, dict[str, Any]]:
    """Events from the inline ``$MC`` JSON, keyed by slug (best effort)."""
    rows: dict[str, dict[str, Any]] = {}
    decoder = json.JSONDecoder()
    start = 0
    while True:
        index = page_html.find(_MC_MARKER, start)
        if index < 0:
            return rows
        start = index + len(_MC_MARKER)
        try:
            value, _end = decoder.raw_decode(page_html, start)
        except ValueError:
            continue
        outer = value.get("o") if isinstance(value, dict) else None
        widgets = outer.get("w") if isinstance(outer, dict) else None
        if not isinstance(widgets, list):
            continue
        for widget in widgets:
            props = widget[2] if isinstance(widget, list) and len(widget) > 2 else None
            if not isinstance(props, dict):
                continue
            for entries in props.values():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if isinstance(entry, dict) and isinstance(entry.get("slug"), str):
                        rows[entry["slug"]] = entry


def parse_listing(page_html: str) -> Listing | None:
    """Parse one listing page; ``None`` when no event card could be read."""
    parser = _ListingParser()
    try:
        parser.feed(page_html)
        parser.close()
    except Exception:
        logger.warning("hackathon_com_parse_error", exc_info=True)
        return None
    listing = parser.listing
    if not any(
        card["title"] and _EVENT_SLUG.search(card["href"]) for card in listing.cards
    ):
        return None
    listing.json_rows = _json_rows(page_html)
    return listing


def next_page_number(links: list[str], current: int) -> int | None:
    """The page number ``current + 1`` when a ``?page=`` link to it exists."""
    wanted = str(current + 1)
    for href in links:
        parts = urlsplit(href)
        if parts.path.rstrip("/") not in ("", "/online", "/online/"):
            continue
        if parse_qs(parts.query).get("page") == [wanted]:
            return current + 1
    return None


# --------------------------------------------------------------------------- #
# Connector
# --------------------------------------------------------------------------- #


def _page_url(page: int) -> str:
    return LISTING_URL if page <= 1 else f"{LISTING_URL}?page={page}"


class HackathonComConnector(DirectoryConnector):
    name = "hackathon_com"
    connector_type = "hackathon_com"

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

    def _discover_fixtures(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        """Fixtures are card dicts shaped like the parser's output."""
        assert self._fixtures is not None
        start = int(cursor or 0)
        cap = max(1, query.result_cap)
        self._seen = set()
        items = self._parse_cards(self._fixtures, {}, {}, query)
        page = items[start : start + cap]
        next_cursor = str(start + cap) if start + cap < len(items) else None
        return DiscoveryPage(items=page, next_cursor=next_cursor)

    async def _discover_live(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        try:
            page = max(1, min(int(cursor or 1), MAX_PAGES))
        except ValueError:
            page = 1
        url = _page_url(page)
        try:
            page_html = await self.load_text(url, MAX_BYTES)
        except SourceBlocked as blocked:
            return self.block(url, blocked.reason)
        except Exception as exc:
            return self.failed(url, exc)

        listing = parse_listing(page_html)
        if listing is None:
            logger.warning(
                "hackathon_com_payload_missing",
                extra={"url": url, "has_event_links": "/event/" in page_html},
            )
            self.degraded = "hackathon_com_payload_missing"
            return DiscoveryPage(items=[], next_cursor=None)

        items = self._parse_cards(
            listing.cards, listing.long_dates, listing.json_rows, query
        )
        following = next_page_number(listing.links, page) if page < MAX_PAGES else None
        return DiscoveryPage(
            items=items, next_cursor=None if following is None else str(following)
        )

    # -- rows -------------------------------------------------------------- #

    def _parse_cards(
        self,
        cards: list[Any],
        long_dates: dict[str, date],
        json_rows: dict[str, dict[str, Any]],
        query: ConnectorQuery,
    ) -> list[DiscoveryCandidate]:
        items: list[DiscoveryCandidate] = []
        undated = 0
        dated = 0  # cards that got as far as the date check
        for card in cards:
            if not isinstance(card, dict):
                continue
            outcome = self._candidate_from_card(card, long_dates, json_rows)
            if outcome == "undated":
                undated += 1
                continue
            if outcome == "ended" or isinstance(outcome, DiscoveryCandidate):
                dated += 1
            if not isinstance(outcome, DiscoveryCandidate):
                continue
            if outcome.external_id in self._seen:
                continue
            if not matches_query(outcome.title, query.query_text):
                continue
            self._seen.add(outcome.external_id)
            items.append(outcome)
        if undated and not dated:
            # Every eligible card lost its dates: the card markup has changed.
            logger.warning("hackathon_com_dates_missing", extra={"cards": len(cards)})
            self.degraded = "hackathon_com_dates_missing"
        return items

    def _candidate_from_card(
        self,
        card: dict[str, Any],
        long_dates: dict[str, date],
        json_rows: dict[str, dict[str, Any]],
    ) -> DiscoveryCandidate | str | None:
        """A candidate, ``"dropped"`` / ``"ended"`` (filtered), ``"undated"`` or ``None``."""
        title = str(card.get("title") or "").strip()
        slug_match = _EVENT_SLUG.search(str(card.get("href") or ""))
        if not title or slug_match is None:
            self.skipped("missing_title_or_event_link", title or card.get("href"))
            return None
        slug = slug_match.group(1)

        extra = json_rows.get(slug, {})
        if extra.get("deleted") is True:
            return "dropped"
        event_type = str(extra.get("eventType") or "").strip().lower()
        if event_type in _NON_HACKATHON_TYPES:
            self.skipped("not_hackathon", slug)
            return "dropped"

        topics = [str(t) for t in card.get("topics") or [] if str(t).strip()]
        mode = _mode(card, topics, extra)
        if mode is None:
            self.skipped("unknown_mode", slug)
            return "dropped"
        if mode == "in_person":
            return "dropped"  # online-only discover

        start_md = _month_day(card.get("start_month"), card.get("start_day"))
        end_md = _month_day(card.get("end_month"), card.get("end_day"))
        if start_md is None and end_md is None:
            self.skipped("missing_dates", slug)
            return "undated"
        start, end = infer_range(
            start_md, end_md, self.now().date(), long_dates.get(title)
        )
        if start is None and end is None:
            self.skipped("bad_dates", slug)
            return "dropped"
        starts_at = None if start is None else f"{start.isoformat()}T00:00:00Z"
        ends_at = None if end is None else f"{end.isoformat()}T23:59:59Z"
        if self.ended(ends_at):
            return "ended"

        organizer = str(extra.get("organizerName") or "").strip()
        themes = [t for t in topics if t.lower() not in _MODE_TAGS]
        url = EVENT_URL.format(slug=slug)
        return DiscoveryCandidate(
            external_id=slug,
            url=url,
            title=title,
            metadata={
                "source": self.name,
                "mode": mode,
                "starts_at": starts_at,
                "ends_at": ends_at,
                # The cards list no prize; ``prizes`` is empty in the JSON.
                "prize_value": None,
                "prize_text": None,
                "organization": organizer or None,
                "location": "Online" if mode == "online" else "Hybrid",
                "themes": themes,
                "directory_url": url,
                "registration_ends_at": None,
            },
        )


def _month_day(month: Any, day: Any) -> tuple[int, int] | None:
    parsed_month, parsed_day = parse_month(str(month or "")), parse_day(str(day or ""))
    if parsed_month is None or parsed_day is None:
        return None
    return parsed_month, parsed_day


def _mode(card: dict[str, Any], topics: list[str], extra: dict[str, Any]) -> str | None:
    tags = {t.lower() for t in topics}
    location = str(card.get("location") or "").strip().lower()
    kind = str(extra.get("type") or "").strip().lower()
    if "hybrid" in tags or kind == "hybrid":
        return "hybrid"
    if location:  # the card is the primary source; the JSON only fills gaps
        return "online" if location == "online" else "in_person"
    if extra.get("online") is True or kind in ("digital", "online"):
        return "online"
    if extra.get("online") is False or kind in ("physical", "onsite", "in_person"):
        return "in_person"
    if tags & {"virtual", "online"}:
        return "online"
    return None
