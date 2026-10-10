"""Offline contract tests for the Unstop directory connector."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ingestion.fetcher import FetchError
from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.unstop import MAX_PAGES, UnstopConnector

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "directories"
NOW = datetime(2026, 10, 10, tzinfo=UTC)


def _now() -> datetime:
    return NOW


def _query(**kwargs: Any) -> ConnectorQuery:
    return ConnectorQuery(module="hackathon", result_cap=40, **kwargs)


def _payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        (FIXTURES / "unstop_open.json").read_text(encoding="utf-8")
    )
    return payload


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 5001,
        "public_url": "hackathons/test-hack-5001",
        "title": "Test Hack",
        "region": "online",
        "end_date": "2026-11-01T18:00:00+05:30",
        "regnRequirements": {"end_regn_dt": "2026-10-25T23:59:00+05:30"},
        "organisation": {"name": "Test Org"},
        "filters": [{"name": "Student", "type": "eligible"}, {"name": "AI", "type": "domain"}],
        "prizes": [],
    }
    row.update(overrides)
    return row


def _wrap(rows: list[dict[str, Any]], last_page: int = 1) -> dict[str, Any]:
    return {"data": {"data": rows, "last_page": last_page, "current_page": 1}}


def _connector(
    responses: list[Any], calls: list[str] | None = None
) -> UnstopConnector:
    queue = list(responses)

    async def http_get(url: str) -> Any:
        if calls is not None:
            calls.append(url)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, BaseException):
            raise item
        return item

    return UnstopConnector(http_get=http_get, now=_now)


def test_class_attributes() -> None:
    assert UnstopConnector.name == "unstop"
    assert UnstopConnector.connector_type == "unstop"


async def test_parses_online_and_hybrid_rows() -> None:
    calls: list[str] = []
    connector = _connector([_payload()], calls)
    page = await connector.discover(_query())
    assert calls == [
        "https://unstop.com/api/public/opportunity/search-result"
        "?opportunity=hackathons&oppstatus=open&page=1&per_page=15"
    ]
    assert [item.external_id for item in page.items] == [
        "1768744",
        "1766434",
        "1766226",
        "1768266",
        "1768758",
        "1768545",
    ]
    threws = page.items[1]
    assert threws.url == (
        "https://unstop.com/hackathons/threws-odyssey-2026-threws-the-research-world-1766434"
    )
    assert threws.metadata == {
        "source": "unstop",
        "mode": "online",
        "starts_at": None,
        "ends_at": "2026-11-15T12:30:00Z",
        "prize_value": None,
        "organization": "Threws - The Research World",
        "location": "Online",
        "themes": [],
        "directory_url": threws.url,
        "registration_ends_at": "2026-10-30T18:30:00Z",
        "prize_text": "150000 INR",
    }
    assert page.items[2].metadata["mode"] == "hybrid"
    assert page.next_cursor == "2"  # last_page is 18 in the fixture
    assert connector.degraded is None and connector.blocked is False


async def test_drops_offline_and_ended_rows() -> None:
    page = await _connector([_payload()]).discover(_query())
    titles = {item.title for item in page.items}
    assert "Sphinx 26" not in titles  # offline
    assert "Capture the Flag" not in titles  # online but ended in 2025
    assert "Google Code Jam" not in titles  # online but ended in 2022
    assert {item.metadata["mode"] for item in page.items} == {"online", "hybrid"}


async def test_url_building_and_foreign_hosts() -> None:
    rows = [
        _row(id=1, public_url="hackathons/rel-1"),
        _row(id=2, public_url=None, seo_url="https://unstop.com/hackathons/seo-2"),
        _row(id=3, public_url="https://evil.example/x", seo_url="/hackathons/fallback-3"),
        _row(id=4, public_url=None, seo_url=None),
    ]
    page = await _connector([_wrap(rows)]).discover(_query())
    urls = {item.external_id: item.url for item in page.items}
    assert urls == {
        "1": "https://unstop.com/hackathons/rel-1",
        "2": "https://unstop.com/hackathons/seo-2",
        "3": "https://unstop.com/hackathons/fallback-3",
    }


async def test_themes_come_from_category_and_domain_filters() -> None:
    page = await _connector([_wrap([_row()])]).discover(_query())
    assert page.items[0].metadata["themes"] == ["AI"]


async def test_prize_value_only_for_usd() -> None:
    usd = [
        {"rank": "Winner", "cash": 1000, "currency": "fa-dollar", "currencyCode": "USD"},
        {"rank": "Runner Up", "cash": 500, "currency": "fa-dollar", "currencyCode": "USD"},
    ]
    pool = [
        {"rank": "Total Prize Pool", "cash": 9000, "currency": "fa-dollar"},
        {"rank": "Winner", "cash": 5000, "currency": "fa-dollar"},
    ]
    inr = [{"rank": "Winner", "cash": 2500, "currency": "fa-rupee", "currencyCode": "INR"}]
    mixed = [
        {"rank": "Winner", "cash": 100, "currency": "fa-dollar"},
        {"rank": "Second", "cash": 100, "currency": "fa-rupee"},
    ]
    rows = [
        _row(id=1, prizes=usd),
        _row(id=2, prizes=pool),
        _row(id=3, prizes=inr),
        _row(id=4, prizes=mixed),
        _row(id=5, prizes=[{"rank": "Winner", "cash": None, "currency": "fa-rupee"}]),
    ]
    page = await _connector([_wrap(rows)]).discover(_query())
    by_id = {item.external_id: item.metadata for item in page.items}
    assert by_id["1"]["prize_value"] == 1500 and "prize_text" not in by_id["1"]
    assert by_id["2"]["prize_value"] == 9000
    assert by_id["3"]["prize_value"] is None and by_id["3"]["prize_text"] == "2500 INR"
    assert by_id["4"]["prize_value"] is None and "INR" in by_id["4"]["prize_text"]
    assert by_id["5"]["prize_value"] is None and "prize_text" not in by_id["5"]


async def test_ended_filter_with_mutated_row() -> None:
    rows = [
        _row(id=1, end_date="2026-10-09T23:00:00+05:30"),
        _row(id=2, end_date="2026-10-11T00:00:00+05:30"),
        _row(id=3, end_date=None),
    ]
    page = await _connector([_wrap(rows)]).discover(_query())
    assert [item.external_id for item in page.items] == ["2", "3"]
    assert page.items[1].metadata["ends_at"] is None


async def test_bad_dates_row_is_skipped() -> None:
    rows = [_row(id=1, end_date="not-a-date"), _row(id=2)]
    page = await _connector([_wrap(rows)]).discover(_query())
    assert [item.external_id for item in page.items] == ["2"]


async def test_query_text_filter() -> None:
    page = await _connector([_payload()]).discover(_query(query_text="odyssey"))
    assert [item.external_id for item in page.items] == ["1766434"]


async def test_paging_follows_last_page() -> None:
    calls: list[str] = []
    connector = _connector(
        [
            _wrap([_row(id=1, title="A")], last_page=2),
            _wrap([_row(id=2, title="B")], last_page=2),
        ],
        calls,
    )
    page1 = await connector.discover(_query())
    assert page1.next_cursor == "2"
    page2 = await connector.discover(_query(), page1.next_cursor)
    assert page2.next_cursor is None
    assert "page=2" in calls[1]
    assert [item.title for item in page1.items + page2.items] == ["A", "B"]


async def test_paging_is_bounded() -> None:
    connector = _connector([_wrap([_row(id=1)], last_page=400)])
    page = await connector.discover(_query(), str(MAX_PAGES))
    assert page.next_cursor is None


async def test_dedupes_across_pages_but_resets_on_fresh_walk() -> None:
    connector = _connector([_wrap([_row(id=1)], last_page=3)])
    first = await connector.discover(_query())
    again = await connector.discover(_query(), first.next_cursor)
    assert len(first.items) == 1 and again.items == []
    fresh = await connector.discover(_query())
    assert len(fresh.items) == 1


async def test_bot_wall_marks_blocked() -> None:
    wall = (FIXTURES / "waf_challenge.html").read_text(encoding="utf-8")
    connector = _connector([wall])
    page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is True
    assert connector.degraded is None


async def test_http_429_marks_blocked() -> None:
    connector = _connector([FetchError("HTTP 429 from unstop.com")])
    page = await connector.discover(_query())
    assert page.items == []
    assert connector.blocked is True


async def test_bad_payload_degrades() -> None:
    for bad in ({"data": {"data": "nope"}}, ["list"], {"data": None}, {"x": 1}):
        connector = _connector([bad])
        page = await connector.discover(_query())
        assert page.items == [] and page.next_cursor is None
        assert connector.degraded == "unstop_directory_failed"
        assert connector.blocked is False


async def test_fetch_error_degrades() -> None:
    connector = _connector([RuntimeError("boom")])
    page = await connector.discover(_query())
    assert page.items == []
    assert connector.degraded == "unstop_directory_failed"


async def test_fixture_rows_with_cursor() -> None:
    rows = copy.deepcopy(_payload()["data"]["data"])
    connector = UnstopConnector(rows, now=_now)
    query = ConnectorQuery(module="hackathon", result_cap=4)
    first = await connector.discover(query)
    assert len(first.items) == 4
    assert first.next_cursor == "4"
    second = await connector.discover(query, first.next_cursor)
    assert len(second.items) == 2
    assert second.next_cursor is None
