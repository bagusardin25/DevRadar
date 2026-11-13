"""Offline contract tests for the Commudle directory connector."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ingestion.fetcher import FetchError
from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.commudle import MAX_PAGES, CommudleConnector

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "directories"
NOW = datetime(2026, 10, 10, tzinfo=UTC)
LISTING = "https://json.commudle.com/api/v2/hackathons/public/all_hackathons"


def _now() -> datetime:
    return NOW


def _query(**kwargs: Any) -> ConnectorQuery:
    return ConnectorQuery(module="hackathon", result_cap=40, **kwargs)


def _payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        (FIXTURES / "commudle_future.json").read_text(encoding="utf-8")
    )
    return payload


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 700,
        "name": "Test Hack",
        "slug": "test-hack",
        "hackathon_theme": "",
        "hackathon_location_type": "online",
        "start_date": "2026-10-20T10:00:00.000+01:00",
        "end_date": "2026-10-21T10:00:00.000+01:00",
        "total_prize_amount": {},
        "status": "open",
        "community": {"name": "Test Community", "slug": "test-community"},
    }
    row.update(overrides)
    return row


def _wrap(
    rows: list[dict[str, Any]], *, has_next: bool = False, end_cursor: str = "CUR1"
) -> dict[str, Any]:
    return {
        "status": 200,
        "data": {
            "total": len(rows),
            "page_info": {"has_next_page": has_next, "end_cursor": end_cursor},
            "page": [{"cursor": f"c{row['id']}", "data": row} for row in rows],
        },
    }


def _connector(
    responses: list[Any], calls: list[str] | None = None
) -> CommudleConnector:
    queue = list(responses)

    async def http_get(url: str) -> Any:
        if calls is not None:
            calls.append(url)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, BaseException):
            raise item
        return item

    return CommudleConnector(http_get=http_get, now=_now)


def test_class_attributes() -> None:
    assert CommudleConnector.name == "commudle"
    assert CommudleConnector.connector_type == "commudle"


async def test_parses_fixture() -> None:
    calls: list[str] = []
    connector = _connector([_payload()], calls)
    page = await connector.discover(_query())
    assert calls == [f"{LISTING}?when=future&limit=20"]
    assert [item.external_id for item in page.items] == ["163", "157", "161"]
    first = page.items[0]
    assert first.title == "AHGV BUILDVERSE 2026"
    assert first.url == (
        "https://www.commudle.com/communities/hackgyanverse/hackathons/ahgv-buildverse-2026"
    )
    assert first.metadata == {
        "source": "commudle",
        "mode": "hybrid",
        "starts_at": "2026-10-24T03:30:00Z",
        "ends_at": "2026-10-24T11:30:00Z",
        "prize_value": None,
        "organization": "Hackgyanverse",
        "location": "Hybrid",
        "themes": [],
        "directory_url": first.url,
        "registration_ends_at": None,
    }
    assert page.items[2].metadata["prize_text"] == "100000 INR"
    assert page.next_cursor is None  # has_next_page is false in the fixture
    assert connector.degraded is None and connector.blocked is False


async def test_drops_offline_and_ended_rows() -> None:
    rows = [
        _row(id=1, slug="on", hackathon_location_type="online"),
        _row(id=2, slug="off", hackathon_location_type="offline"),
        _row(id=3, slug="hy", hackathon_location_type="hybrid"),
        _row(id=4, slug="old", end_date="2026-10-09T10:00:00.000+01:00"),
        _row(id=5, slug="odd", hackathon_location_type="metaverse"),
    ]
    page = await _connector([_wrap(rows)]).discover(_query())
    assert [item.external_id for item in page.items] == ["1", "3"]
    assert [item.metadata["mode"] for item in page.items] == ["online", "hybrid"]


async def test_dates_are_normalised_to_utc() -> None:
    page = await _connector([_wrap([_row()])]).discover(_query())
    metadata = page.items[0].metadata
    assert metadata["starts_at"] == "2026-10-20T09:00:00Z"
    assert metadata["ends_at"] == "2026-10-21T09:00:00Z"


async def test_prize_value_only_for_usd() -> None:
    rows = [
        _row(id=1, slug="usd", total_prize_amount={"USD": 2500}),
        _row(id=2, slug="inr", total_prize_amount={"INR": 50000}),
        _row(id=3, slug="mixed", total_prize_amount={"USD": 100, "INR": 200}),
        _row(id=4, slug="none", total_prize_amount={}),
        _row(id=5, slug="zero", total_prize_amount={"USD": 0}),
    ]
    page = await _connector([_wrap(rows)]).discover(_query())
    by_id = {item.external_id: item.metadata for item in page.items}
    assert by_id["1"]["prize_value"] == 2500 and "prize_text" not in by_id["1"]
    assert by_id["2"]["prize_value"] is None and by_id["2"]["prize_text"] == "50000 INR"
    assert by_id["3"]["prize_value"] is None and "100 USD" in by_id["3"]["prize_text"]
    assert by_id["4"]["prize_value"] is None and "prize_text" not in by_id["4"]
    assert by_id["5"]["prize_value"] is None and "prize_text" not in by_id["5"]


async def test_theme_and_missing_community() -> None:
    rows = [
        _row(id=1, slug="themed", hackathon_theme="Climate"),
        _row(id=2, slug="orphan", community=None),
        _row(id=3, slug="bad slug!"),
    ]
    page = await _connector([_wrap(rows)]).discover(_query())
    assert [item.external_id for item in page.items] == ["1"]
    assert page.items[0].metadata["themes"] == ["Climate"]


async def test_bad_dates_row_is_skipped() -> None:
    rows = [_row(id=1, end_date="garbage"), _row(id=2, slug="fine")]
    page = await _connector([_wrap(rows)]).discover(_query())
    assert [item.external_id for item in page.items] == ["2"]


async def test_query_text_filter() -> None:
    page = await _connector([_payload()]).discover(_query(query_text="sprint"))
    assert [item.title for item in page.items] == ["Hack Sprint"]


async def test_paging_uses_end_cursor() -> None:
    calls: list[str] = []
    connector = _connector(
        [
            _wrap([_row(id=1, slug="a", name="A")], has_next=True, end_cursor="ABC_-="),
            _wrap([_row(id=2, slug="b", name="B")], has_next=False),
        ],
        calls,
    )
    page1 = await connector.discover(_query())
    assert page1.next_cursor == "ABC_-="
    page2 = await connector.discover(_query(), page1.next_cursor)
    assert page2.next_cursor is None
    assert calls[1] == f"{LISTING}?when=future&limit=20&after=ABC_-%3D"
    assert [item.title for item in page1.items + page2.items] == ["A", "B"]


async def test_paging_is_bounded() -> None:
    connector = _connector([_wrap([_row(id=1)], has_next=True)])
    cursor: str | None = None
    pages = 0
    while pages < MAX_PAGES + 3:
        page = await connector.discover(_query(), cursor)
        pages += 1
        cursor = page.next_cursor
        if cursor is None:
            break
    assert pages == MAX_PAGES


async def test_hostile_cursor_is_not_sent() -> None:
    calls: list[str] = []
    connector = _connector([_wrap([_row()])], calls)
    await connector.discover(_query(), "x&when=past#frag")
    assert calls == [f"{LISTING}?when=future&limit=20"]


async def test_hostile_end_cursor_is_not_followed() -> None:
    connector = _connector([_wrap([_row()], has_next=True, end_cursor="a b&c")])
    page = await connector.discover(_query())
    assert page.next_cursor is None


async def test_dedupes_across_pages_but_resets_on_fresh_walk() -> None:
    connector = _connector([_wrap([_row(id=1)], has_next=True)])
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


async def test_http_503_marks_blocked() -> None:
    connector = _connector([FetchError("HTTP 503 from json.commudle.com")])
    page = await connector.discover(_query())
    assert page.items == []
    assert connector.blocked is True


async def test_bad_payload_degrades() -> None:
    for bad in ({"data": {"page": "nope"}}, ["list"], {"data": None}, {"x": 1}):
        connector = _connector([bad])
        page = await connector.discover(_query())
        assert page.items == [] and page.next_cursor is None
        assert connector.degraded == "commudle_directory_failed"
        assert connector.blocked is False


async def test_fetch_error_degrades() -> None:
    connector = _connector([RuntimeError("boom")])
    page = await connector.discover(_query())
    assert page.items == []
    assert connector.degraded == "commudle_directory_failed"


async def test_fixture_rows_with_cursor() -> None:
    rows = [entry["data"] for entry in copy.deepcopy(_payload()["data"]["page"])]
    connector = CommudleConnector(rows, now=_now)
    query = ConnectorQuery(module="hackathon", result_cap=2)
    first = await connector.discover(query)
    assert len(first.items) == 2 and first.next_cursor == "2"
    second = await connector.discover(query, first.next_cursor)
    assert [item.external_id for item in second.items] == ["161"]
    assert second.next_cursor is None
