"""Offline contract tests for the hackathon.com directory connector.

The fixture is the real ``/online`` page reduced to its ``<main>`` (four
highlight cards, the highlight date strip and the inline ``$MC`` JSON). The
cards carry day + month only, so the year-inference rule gets its own tests.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from app.ingestion.fetcher import FetchError
from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.hackathon_com import (
    HackathonComConnector,
    infer_range,
    next_page_number,
    parse_day,
    parse_listing,
    parse_long_date,
    parse_month,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "directories"
NOW = datetime(2026, 10, 10, tzinfo=UTC)
AI_BUILDERS = "ai-builders-challenge---north-america-6abbf8d772b8a910818d2070"
XYLEM = "xylem-global-student-innovation-challenge-2026-6aa862e261509030e7e6436f"
HUAWEI = "huawei-ireland-tech-arena-2026-6ac54367612836bf413df387"
METADATA_KEYS = {
    "source",
    "mode",
    "starts_at",
    "ends_at",
    "prize_value",
    "prize_text",
    "organization",
    "location",
    "themes",
    "directory_url",
    "registration_ends_at",
}


def _read() -> str:
    return (FIXTURES / "hackathon_com_online.html").read_text(encoding="utf-8")


def _query(**kwargs: Any) -> ConnectorQuery:
    return ConnectorQuery(module="hackathon", result_cap=40, **kwargs)


def _connector(
    html: str, calls: list[str] | None = None, *, now: datetime = NOW
) -> HackathonComConnector:
    async def http_get(url: str) -> str:
        if calls is not None:
            calls.append(url)
        return html

    return HackathonComConnector(http_get=http_get, now=lambda: now)


def _without_json(html: str) -> str:
    return re.sub(r"<script>\$MC=.*?</script>", "", html, flags=re.DOTALL)


def _without_strip(html: str) -> str:
    """Drop the highlight date strip, which carries the years."""
    return re.sub(
        r'<div class="ht-highlights__list container">.*?</div></section>',
        "</section>",
        html,
        flags=re.DOTALL,
    )


def _card(**overrides: Any) -> dict[str, Any]:
    card: dict[str, Any] = {
        "title": "Winter Jam",
        "href": "/event/winter-jam-abc123",
        "topics": ["Game"],
        "location": "Online",
        "start_day": "20",
        "start_month": "Dec",
        "end_day": "10",
        "end_month": "Jan",
    }
    card.update(overrides)
    return card


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


def test_parse_listing_reads_cards_strip_and_json() -> None:
    listing = parse_listing(_read())
    assert listing is not None
    assert [c["title"] for c in listing.cards] == [
        "AI Builders Challenge - North America",
        "IBM Z Day 2026",
        "Xylem Global Student Innovation Challenge 2026",
        "Huawei Ireland Tech Arena 2026",
    ]
    first = listing.cards[0]
    assert first["href"] == "/event/" + AI_BUILDERS
    assert (first["start_day"], first["start_month"]) == ("02", "Nov")
    assert (first["end_day"], first["end_month"]) == ("02", "Dec")
    assert first["location"] == "Online"
    assert first["topics"] == ["University", "Beginner friendly", "AI", "Student"]
    assert listing.long_dates["Xylem Global Student Innovation Challenge 2026"] == date(
        2026, 9, 28
    )
    assert listing.json_rows[AI_BUILDERS]["eventType"] == "Hackathon"
    assert listing.json_rows["ibm-z-day-2026-6a90a131d4372f7cdf912da6"]["eventType"] == "Event"


async def test_maps_online_and_hybrid_cards() -> None:
    calls: list[str] = []
    page = await _connector(_read(), calls).discover(_query())
    assert calls == ["https://www.hackathon.com/online"]
    assert page.next_cursor is None
    # IBM Z Day is an "Event" in the page JSON, not a hackathon.
    assert [item.external_id for item in page.items] == [AI_BUILDERS, XYLEM, HUAWEI]

    online, _xylem, hybrid = page.items
    assert online.url == "https://www.hackathon.com/event/" + AI_BUILDERS
    assert online.title == "AI Builders Challenge - North America"
    assert set(online.metadata) == METADATA_KEYS
    assert online.metadata["source"] == "hackathon_com"
    assert online.metadata["mode"] == "online" and online.metadata["location"] == "Online"
    assert online.metadata["organization"] == "IBM SkillsBuild"
    assert online.metadata["themes"] == ["University", "Beginner friendly", "AI", "Student"]
    assert online.metadata["prize_value"] is None
    assert online.metadata["starts_at"] == "2026-11-02T00:00:00Z"
    assert online.metadata["ends_at"] == "2026-12-02T23:59:59Z"
    assert online.metadata["directory_url"] == online.url
    assert hybrid.metadata["mode"] == "hybrid" and hybrid.metadata["location"] == "Hybrid"
    assert "Hybrid" not in hybrid.metadata["themes"]


async def test_works_without_json_or_date_strip() -> None:
    page = await _connector(_without_strip(_without_json(_read()))).discover(_query())
    # No JSON: IBM Z Day can no longer be told apart from a hackathon.
    assert len(page.items) == 4
    assert page.items[0].metadata["organization"] is None
    assert page.items[0].metadata["starts_at"] == "2026-11-02T00:00:00Z"
    assert page.items[0].metadata["ends_at"] == "2026-12-02T23:59:59Z"
    xylem = next(i for i in page.items if i.external_id == XYLEM)
    assert xylem.metadata["starts_at"] == "2026-09-28T00:00:00Z"


async def test_reads_the_result_list_layout() -> None:
    """The live page is sometimes served as ``ht-event-card`` rows (start only)."""
    html = (FIXTURES / "hackathon_com_result_list.html").read_text(encoding="utf-8")
    connector = _connector(html)
    page = await connector.discover(_query())

    assert connector.degraded is None
    by_id = {item.external_id: item for item in page.items}
    assert {XYLEM, HUAWEI, AI_BUILDERS} <= set(by_id)
    xylem = by_id[XYLEM]
    assert xylem.title == "Xylem Global Student Innovation Challenge 2026"
    assert xylem.metadata["mode"] == "online"
    assert xylem.metadata["starts_at"] == "2026-09-28T00:00:00Z"
    assert xylem.metadata["ends_at"] is None
    assert "Virtual" not in xylem.metadata["themes"]
    assert set(xylem.metadata) == METADATA_KEYS


async def test_in_person_and_ended_cards_are_dropped() -> None:
    html = _read().replace(
        "<a href=/online>Online</a>",
        "<a href=/city/paris>Paris</a>, <a href=/country/fr>France</a>",
        1,
    )
    page = await _connector(html).discover(_query())
    assert AI_BUILDERS not in {i.external_id for i in page.items}  # in person

    later = await _connector(_read(), now=datetime(2026, 12, 10, tzinfo=UTC)).discover(_query())
    assert later.items == []  # every window has closed by 10 Dec 2026


async def test_unknown_location_is_skipped(caplog: pytest.LogCaptureFixture) -> None:
    html = _read().replace("<a href=/online>Online</a>", "", 1)
    with caplog.at_level(logging.INFO):
        page = await _connector(html).discover(_query())
    # AI Builders has no location left, no mode tag, but its JSON says digital/online.
    assert AI_BUILDERS in {i.external_id for i in page.items}
    bare = _without_json(html)
    with caplog.at_level(logging.INFO):
        page = await _connector(bare).discover(_query())
    assert AI_BUILDERS not in {i.external_id for i in page.items}
    assert any(
        r.getMessage() == "hackathon_com_row_skipped" and r.reason == "unknown_mode"  # type: ignore[attr-defined]
        for r in caplog.records
    )


async def test_query_text_filters_by_title() -> None:
    page = await _connector(_read()).discover(_query(query_text="huawei"))
    assert [i.external_id for i in page.items] == [HUAWEI]


# --------------------------------------------------------------------------- #
# Year inference
# --------------------------------------------------------------------------- #


def test_infer_range_within_one_year() -> None:
    today = date(2026, 10, 10)
    assert infer_range((11, 2), (12, 2), today) == (date(2026, 11, 2), date(2026, 12, 2))
    assert infer_range((9, 28), (11, 20), today) == (date(2026, 9, 28), date(2026, 11, 20))
    assert infer_range((11, 18), (11, 18), today) == (date(2026, 11, 18), date(2026, 11, 18))


def test_infer_range_rolls_over_new_year() -> None:
    # 20 Dec -> 10 Jan seen in October: the end is 10 Jan 2027, the start 20 Dec 2026.
    assert infer_range((12, 20), (1, 10), date(2026, 10, 10)) == (
        date(2026, 12, 20),
        date(2027, 1, 10),
    )
    # Seen mid-event on 28 Dec the window is unchanged...
    assert infer_range((12, 20), (1, 10), date(2026, 12, 28)) == (
        date(2026, 12, 20),
        date(2027, 1, 10),
    )
    # ... and seen on 2 Jan (already in the new year) it still is.
    assert infer_range((12, 20), (1, 10), date(2027, 1, 2)) == (
        date(2026, 12, 20),
        date(2027, 1, 10),
    )
    # An event that was in January and is seen in late December is next January's.
    assert infer_range((1, 5), (1, 20), date(2026, 12, 28)) == (
        date(2027, 1, 5),
        date(2027, 1, 20),
    )


def test_infer_range_lookback_window() -> None:
    today = date(2026, 10, 10)
    # Ended 20 days ago: still this year (so the ended filter can drop it).
    assert infer_range((9, 1), (9, 20), today) == (date(2026, 9, 1), date(2026, 9, 20))
    # Started two months ago, ends soon: the start is not pushed to next year.
    assert infer_range((8, 20), (12, 1), today) == (date(2026, 8, 20), date(2026, 12, 1))
    # Ended 40 days ago: past the 30-day window, so it reads as next year's.
    assert infer_range((8, 20), (8, 31), today) == (date(2027, 8, 20), date(2027, 8, 31))


def test_infer_range_anchor_year_wins() -> None:
    anchor = date(2026, 12, 28)
    assert infer_range((12, 28), (1, 3), date(2026, 10, 10), anchor) == (
        anchor,
        date(2027, 1, 3),
    )
    assert infer_range((12, 28), None, date(2026, 10, 10), anchor) == (anchor, None)


def test_infer_range_edge_cases() -> None:
    today = date(2026, 10, 10)
    assert infer_range(None, None, today) == (None, None)
    assert infer_range((11, 2), None, today) == (date(2026, 11, 2), None)
    assert infer_range(None, (11, 2), today) == (None, date(2026, 11, 2))
    assert infer_range((2, 30), (3, 1), today)[1] == date(2027, 3, 1)  # bad start day
    # 29 Feb only exists in leap years: 2028 is the next one.
    assert infer_range((2, 29), (2, 29), today) == (date(2028, 2, 29), date(2028, 2, 29))
    assert infer_range((13, 1), (13, 2), today) == (None, None)


def test_date_text_helpers() -> None:
    assert parse_month("Nov") == 11 and parse_month("December") == 12
    assert parse_month("nov.") == 11
    assert parse_month("Foo") is None and parse_month("") is None and parse_month(None) is None
    assert parse_day("02") == 2 and parse_day("2nd") == 2 and parse_day(" 31 ") == 31
    assert parse_day("x") is None and parse_day("") is None
    assert parse_long_date("2nd November 2026") == date(2026, 11, 2)
    assert parse_long_date("14th October 2026") == date(2026, 10, 14)
    assert parse_long_date("31st February 2026") is None
    assert parse_long_date("soon") is None


async def test_new_year_window_through_the_connector() -> None:
    december = datetime(2026, 12, 28, tzinfo=UTC)
    connector = HackathonComConnector(fixtures=[_card()], now=lambda: december)
    page = await connector.discover(_query())
    meta = page.items[0].metadata
    assert (meta["starts_at"], meta["ends_at"]) == ("2026-12-20T00:00:00Z", "2027-01-10T23:59:59Z")

    january = datetime(2027, 1, 15, tzinfo=UTC)
    after = HackathonComConnector(fixtures=[_card()], now=lambda: january)
    # 10 Jan 2027 is 5 days past on 15 Jan: still dated 2027 and therefore ended.
    assert (await after.discover(_query())).items == []


# --------------------------------------------------------------------------- #
# Paging
# --------------------------------------------------------------------------- #


def test_next_page_number_requires_a_matching_link() -> None:
    assert next_page_number(["/online?page=2"], 1) == 2
    assert next_page_number(["https://www.hackathon.com/online?page=3"], 2) == 3
    assert next_page_number(["/online?page=3"], 1) is None
    assert next_page_number(["/theme/ai?page=2", "/event/x"], 1) is None
    assert next_page_number([], 1) is None


async def test_follows_page_links_with_a_bound() -> None:
    html = _read().replace(
        "</main>",
        "".join(f'<a href="/online?page={n}">{n}</a>' for n in (2, 3, 4)) + "</main>",
    )
    calls: list[str] = []
    connector = _connector(html, calls)
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(10):
        page = await connector.discover(_query(), cursor)
        seen += [item.external_id for item in page.items]
        cursor = page.next_cursor
        if cursor is None:
            break
    assert calls == [
        "https://www.hackathon.com/online",
        "https://www.hackathon.com/online?page=2",
        "https://www.hackathon.com/online?page=3",
    ]
    assert len(seen) == len(set(seen)) == 3  # the repeated page adds no duplicates
    # A fresh walk starts clean.
    assert len((await connector.discover(_query())).items) == 3


async def test_garbage_cursor_restarts_at_page_one() -> None:
    calls: list[str] = []
    await _connector(_read(), calls).discover(_query(), "banana")
    assert calls == ["https://www.hackathon.com/online"]


# --------------------------------------------------------------------------- #
# Failure modes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("breakage", ["no_cards", "renamed_title_class", "no_event_links"])
async def test_shape_change_degrades_instead_of_raising(
    breakage: str, caplog: pytest.LogCaptureFixture
) -> None:
    html = _read()
    if breakage == "no_cards":
        html = "<html><body><h1>Redesigned</h1></body></html>"
    elif breakage == "renamed_title_class":
        html = html.replace("hero__title", "hero__heading")
    else:
        html = html.replace("/event/", "/e/")
    connector = _connector(html)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.degraded == "hackathon_com_payload_missing"
    assert any(r.getMessage() == "hackathon_com_payload_missing" for r in caplog.records)


async def test_cards_without_dates_degrade(caplog: pytest.LogCaptureFixture) -> None:
    html = _read().replace("date__day", "date__d").replace("date__month", "date__m")
    connector = _connector(html)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == []
    assert connector.degraded == "hackathon_com_dates_missing"


async def test_malformed_markup_does_not_raise() -> None:
    html = "<html><body><div class=hero><a class=hero__title href=/event/x>Half"
    connector = _connector(html)
    page = await connector.discover(_query())
    assert page.items == [] and connector.degraded == "hackathon_com_payload_missing"


@pytest.mark.parametrize("trigger", ["waf_page", "http_405"])
async def test_bot_check_returns_empty_and_blocks(
    trigger: str, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str] = []

    async def http_get(url: str) -> str:
        calls.append(url)
        if trigger == "http_405":
            raise FetchError(f"HTTP 405 for {url}")
        return (FIXTURES / "waf_challenge.html").read_text(encoding="utf-8")

    connector = HackathonComConnector(http_get=http_get, now=lambda: NOW)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is True and connector.degraded is None
    assert len(calls) == 1
    records = [r for r in caplog.records if r.getMessage() == "source_blocked"]
    assert len(records) == 1 and records[0].source == "hackathon_com"  # type: ignore[attr-defined]


async def test_plain_http_error_is_a_failure_not_a_block() -> None:
    async def http_get(url: str) -> str:
        raise FetchError(f"HTTP 500 for {url}")

    connector = HackathonComConnector(http_get=http_get, now=lambda: NOW)
    page = await connector.discover(_query())
    assert page.items == [] and connector.blocked is False
    assert connector.degraded == "hackathon_com_directory_failed"


async def test_fixture_mode_paginates_by_offset() -> None:
    cards = [_card(), _card(title="Spring Jam", href="/event/spring-jam-def456")]
    connector = HackathonComConnector(fixtures=cards, now=lambda: NOW)
    small = ConnectorQuery(module="hackathon", result_cap=1)
    first = await connector.discover(small)
    assert [i.external_id for i in first.items] == ["winter-jam-abc123"]
    assert first.next_cursor == "1"
    second = await connector.discover(small, first.next_cursor)
    assert [i.external_id for i in second.items] == ["spring-jam-def456"]
    assert second.next_cursor is None


def test_connector_identity() -> None:
    connector = HackathonComConnector()
    assert connector.name == "hackathon_com" and connector.connector_type == "hackathon_com"
