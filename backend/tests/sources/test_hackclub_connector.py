"""Offline contract tests for the Hack Club directory connector.

The connector prefers the open JSON events API and falls back to the
``__NEXT_DATA__`` payload embedded in the home page. Both fixtures are trimmed
real responses stored in ``tests/fixtures/directories``; rows are mutated in
test code, never in the fixtures.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.ingestion.fetcher import FetchError
from app.sources.connectors.base import ConnectorQuery, DiscoveryCandidate
from app.sources.connectors.hackclub import (
    HACKCLUB_API,
    HACKCLUB_PAGE,
    HackClubConnector,
    extract_embedded_events,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "directories"
NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)

REQUIRED_KEYS = {
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


def _now() -> datetime:
    return NOW


def _query(**kwargs: Any) -> ConnectorQuery:
    return ConnectorQuery(module="hackathon", result_cap=40, **kwargs)


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _api_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(_read("hackclub_upcoming.json"))
    return copy.deepcopy(rows)


def _page_html(mutate: Callable[[list[dict[str, Any]]], None] | None = None) -> str:
    html = _read("hackclub_hackathons.html")
    if mutate is None:
        return html
    events = extract_embedded_events(html)
    assert events is not None
    mutate(events)
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    assert match is not None
    data = json.loads(match.group(1))
    data["props"]["pageProps"]["events"] = events
    return html.replace(match.group(1), json.dumps(data))


def _connector(
    *,
    api: Any = None,
    page: str | None = None,
    calls: list[str] | None = None,
) -> HackClubConnector:
    """``api`` is the raw API answer (or an exception); ``page`` the home page."""

    async def http_get(url: str) -> Any:
        if calls is not None:
            calls.append(url)
        if url == HACKCLUB_API:
            if isinstance(api, Exception):
                raise api
            return api
        if url == HACKCLUB_PAGE:
            if page is None:
                raise AssertionError("the home page should not have been fetched")
            return page
        raise AssertionError(f"unexpected URL {url}")

    return HackClubConnector(http_get=http_get, now=_now)


def _by_url(items: list[DiscoveryCandidate]) -> dict[str, DiscoveryCandidate]:
    return {item.url: item for item in items}


# --------------------------------------------------------------------------- #
# JSON API
# --------------------------------------------------------------------------- #


async def test_parses_the_json_api() -> None:
    calls: list[str] = []
    page = await _connector(api=_api_rows(), calls=calls).discover(_query())

    assert calls == ["https://hackathons.hackclub.com/api/events/upcoming/"]
    assert page.next_cursor is None
    by_url = _by_url(page.items)
    assert set(by_url) == {
        "https://pixelforgejam.org/",
        "https://www.cosmohacks.com/",
        "https://earth.firstcommit.xyz",
    }
    for item in page.items:
        assert set(item.metadata) == REQUIRED_KEYS
        assert item.metadata["source"] == "hackclub"
        assert item.metadata["mode"] == "online"
        assert item.metadata["location"] == "Online"
        assert item.metadata["prize_value"] is None
        assert item.metadata["registration_ends_at"] is None
        assert item.metadata["directory_url"] == "https://hackathons.hackclub.com/"

    pixel = by_url["https://pixelforgejam.org/"]
    assert pixel.title == "Pixel Forge Mega Jam"
    assert pixel.external_id == "0n1IKx"
    assert pixel.metadata["starts_at"] == "2026-11-28T09:30:00Z"
    assert pixel.metadata["ends_at"] == "2026-12-08T09:30:00Z"


async def test_in_person_rows_are_dropped() -> None:
    rows = _api_rows()
    in_person = [r for r in rows if not r["virtual"] and not r["hybrid"]]
    assert in_person  # the fixture really contains in-person events
    page = await _connector(api=rows).discover(_query())
    assert not ({r["website"] for r in in_person} & {item.url for item in page.items})
    assert {item.metadata["mode"] for item in page.items} == {"online"}


async def test_hybrid_rows_are_kept_with_their_place() -> None:
    rows = _api_rows()
    row = next(r for r in rows if not r["virtual"])
    row["hybrid"] = True
    page = await _connector(api=rows).discover(_query())
    hybrid = _by_url(page.items)[row["website"]]
    assert hybrid.metadata["mode"] == "hybrid"
    expected = ", ".join(p for p in (row["city"], row["state"], row["country"]) if p)
    assert hybrid.metadata["location"] == f"Hybrid, {expected}"

    row["city"] = row["state"] = row["country"] = None
    bare = await _connector(api=rows).discover(_query())
    assert _by_url(bare.items)[row["website"]].metadata["location"] == "Hybrid"


async def test_ended_rows_are_dropped() -> None:
    rows = _api_rows()
    ended = next(r for r in rows if r["virtual"])
    ended["end"] = "2026-10-01T00:00:00.000Z"
    page = await _connector(api=rows).discover(_query())
    assert ended["website"] not in {item.url for item in page.items}
    assert len(page.items) == 2


async def test_themes_are_empty_and_organization_follows_the_data() -> None:
    rows = _api_rows()
    page = await _connector(api=rows).discover(_query())
    assert all(item.metadata["themes"] == [] for item in page.items)  # no "high-school" guess
    assert all(item.metadata["organization"] is None for item in page.items)

    next(r for r in rows if r["virtual"])["hack_club_event"] = True
    marked = await _connector(api=rows).discover(_query())
    assert [i.metadata["organization"] for i in marked.items].count("Hack Club") == 1


async def test_row_filters(caplog: pytest.LogCaptureFixture) -> None:
    rows = [r for r in _api_rows() if r["virtual"]]
    assert len(rows) == 3
    del rows[0]["virtual"], rows[0]["hybrid"]  # unknown mode -> skipped
    rows[1]["website"] = "javascript:alert(1)"  # unsafe -> skipped
    rows[2]["end"] = "garbage"  # bad date -> skipped
    rows.append(copy.deepcopy(rows[2]) | {"end": "2027-01-01T00:00:00.000Z"})
    rows.append(copy.deepcopy(rows[-1]))  # repeated id
    with caplog.at_level(logging.INFO):
        page = await _connector(api=rows).discover(_query())
    assert [item.external_id for item in page.items] == [rows[2]["id"]]
    reasons = {r.reason for r in caplog.records if r.getMessage() == "hackclub_row_skipped"}
    assert reasons == {"unknown_mode", "missing_id_title_or_website", "bad_dates"}


async def test_query_text_filters_by_title() -> None:
    page = await _connector(api=_api_rows()).discover(_query(query_text="cosmo"))
    assert [item.title for item in page.items] == ["Cosmo Hacks"]
    assert (await _connector(api=_api_rows()).discover(_query(query_text="zzz"))).items == []


async def test_empty_api_list_is_not_a_failure() -> None:
    calls: list[str] = []
    connector = _connector(api=[], calls=calls)
    page = await connector.discover(_query())
    assert page.items == [] and connector.degraded is None
    assert calls == [HACKCLUB_API]  # no fallback for a valid, empty answer


async def test_api_answer_as_a_json_string() -> None:
    page = await _connector(api=_read("hackclub_upcoming.json")).discover(_query())
    assert len(page.items) == 3


# --------------------------------------------------------------------------- #
# Embedded fallback
# --------------------------------------------------------------------------- #


def test_extracts_embedded_events() -> None:
    events = extract_embedded_events(_read("hackclub_hackathons.html"))
    assert events is not None and len(events) == 15
    assert {(e["virtual"], e["hybrid"]) for e in events} == {
        (True, False),
        (False, True),
        (False, False),
    }
    assert extract_embedded_events("<html>nothing</html>") is None
    assert extract_embedded_events('<script id="__NEXT_DATA__">{broken</script>') is None
    assert extract_embedded_events('<script id="__NEXT_DATA__">{"props":{}}</script>') is None


@pytest.mark.parametrize(
    "api",
    [
        FetchError("HTTP 404 for https://hackathons.hackclub.com/api/events/upcoming/"),
        {"events": []},  # wrong shape
        "{not json",
        "<html><head><title>Welcome</title></head><body>app shell</body></html>",
    ],
)
async def test_falls_back_to_the_embedded_page(api: Any) -> None:
    calls: list[str] = []
    connector = _connector(api=api, page=_page_html(), calls=calls)
    page = await connector.discover(_query())

    assert calls == [HACKCLUB_API, HACKCLUB_PAGE]
    assert connector.blocked is False and connector.degraded is None
    # Past events in the page are dropped as ended; in-person ones are dropped.
    assert [item.title for item in page.items] == [
        "Banana Hacks",
        "Build for Earth",
        "Pixel Forge Mega Jam",
        "Cosmo Hacks",
    ]
    assert all(item.metadata["mode"] == "online" for item in page.items)
    assert all(item.metadata["themes"] == [] for item in page.items)


async def test_embedded_hybrid_and_ended_hybrid() -> None:
    def mutate(events: list[dict[str, Any]]) -> None:
        for event in events:
            if event["name"] == "Brilliant Move":
                event["end"] = "2026-11-01T00:00:00.000Z"  # hybrid, now upcoming

    page = await _connector(api=FetchError("HTTP 404"), page=_page_html(mutate)).discover(
        _query()
    )
    modes = {item.title: item.metadata["mode"] for item in page.items}
    assert modes["Brilliant Move"] == "hybrid"
    assert "Hack the Skies" not in modes  # the other hybrid event is over


# --------------------------------------------------------------------------- #
# Failure modes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("trigger", ["waf_page", "http_405", "http_429"])
async def test_bot_wall_on_the_api_blocks_without_fallback(
    trigger: str, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str] = []
    api: Any = (
        _read("waf_challenge.html")
        if trigger == "waf_page"
        else FetchError(f"HTTP {trigger[5:]} for {HACKCLUB_API}")
    )
    connector = _connector(api=api, calls=calls)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is True and connector.degraded is None
    assert calls == [HACKCLUB_API]  # a wall is never worked around
    records = [r for r in caplog.records if r.getMessage() == "source_blocked"]
    assert len(records) == 1 and records[0].source == "hackclub"  # type: ignore[attr-defined]


async def test_bot_wall_on_the_fallback_page_blocks() -> None:
    calls: list[str] = []
    connector = _connector(
        api=FetchError("HTTP 500"), page=_read("waf_challenge.html"), calls=calls
    )
    page = await connector.discover(_query())
    assert page.items == [] and connector.blocked is True
    assert calls == [HACKCLUB_API, HACKCLUB_PAGE]


@pytest.mark.parametrize(
    "page_html",
    [
        "<html><body>no payload here</body></html>",
        '<script id="__NEXT_DATA__" type="application/json">{not json</script>',
        '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>',
    ],
)
async def test_broken_payload_everywhere_degrades(
    page_html: str, caplog: pytest.LogCaptureFixture
) -> None:
    connector = _connector(api={"unexpected": True}, page=page_html)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is False
    assert connector.degraded == "hackclub_payload_missing"
    assert any(r.getMessage() == "hackclub_payload_missing" for r in caplog.records)


async def test_network_failure_on_both_sources_degrades() -> None:
    async def boom(url: str) -> str:
        raise FetchError(f"HTTP 500 for {url}")

    connector = HackClubConnector(http_get=boom, now=_now)
    page = await connector.discover(_query())
    assert page.items == [] and connector.blocked is False
    assert connector.degraded == "hackclub_directory_failed"


async def test_fixture_mode_paginates_by_offset() -> None:
    connector = HackClubConnector(fixtures=_api_rows(), now=_now)
    small = ConnectorQuery(module="hackathon", result_cap=2)
    first = await connector.discover(small)
    assert len(first.items) == 2 and first.next_cursor == "2"
    second = await connector.discover(small, first.next_cursor)
    assert len(second.items) == 1 and second.next_cursor is None
    assert first.items[0].url != second.items[0].url


async def test_fetch_detail_points_at_the_event_website() -> None:
    connector = _connector(api=_api_rows())
    page = await connector.discover(_query())
    request = await connector.fetch_detail(page.items[0])
    assert request.url == page.items[0].url
    assert request.metadata == {"connector": "hackclub"}
    assert connector.name == connector.connector_type == "hackclub"
