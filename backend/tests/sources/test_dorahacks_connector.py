"""Offline contract tests for the DoraHacks directory connector."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ingestion.fetcher import FetchError
from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.dorahacks import MAX_PAGES, DoraHacksConnector

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "directories"
NOW = datetime(2026, 10, 10, tzinfo=UTC)
UNIX_NOW = int(NOW.timestamp())
DAY = 86_400


def _now() -> datetime:
    return NOW


def _query(**kwargs: Any) -> ConnectorQuery:
    return ConnectorQuery(module="hackathon", result_cap=40, **kwargs)


def _payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        (FIXTURES / "dorahacks_hub.json").read_text(encoding="utf-8")
    )
    return payload


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 9001,
        "uname": "test-hack",
        "title": "Test Hack",
        "owner": {"id": 1, "name": "Test Org"},
        "tags": "AI,Web3",
        "timeline_start": UNIX_NOW - DAY,
        "timeline_end": UNIX_NOW + 10 * DAY,
        "venue_form": "Virtual",
        "venue_name": None,
        "bonus_price": 1000,
        "bonus_token": "USD",
    }
    row.update(overrides)
    return row


def _connector(
    responses: list[Any], calls: list[str] | None = None
) -> DoraHacksConnector:
    queue = list(responses)

    async def http_get(url: str) -> Any:
        if calls is not None:
            calls.append(url)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, BaseException):
            raise item
        return item

    return DoraHacksConnector(http_get=http_get, now=_now)


def test_class_attributes() -> None:
    assert DoraHacksConnector.name == "dorahacks"
    assert DoraHacksConnector.connector_type == "dorahacks"


async def test_parses_online_rows_and_metadata() -> None:
    calls: list[str] = []
    connector = _connector([_payload()], calls)
    page = await connector.discover(_query())
    assert calls == ["https://dorahacks.io/api/v1/hub/hackathons?page=1&page_size=24"]
    by_slug = {item.url.rsplit("/", 1)[1]: item for item in page.items}
    assert set(by_slug) == {
        "weex-ai-wars2",
        "arc-microgrants",
        "bchblaze2026",
        "mdba-youth",
        "satnav",
    }
    arc = by_slug["arc-microgrants"]
    assert arc.external_id == "2238"
    assert arc.url == "https://dorahacks.io/hackathon/arc-microgrants"
    assert arc.metadata == {
        "source": "dorahacks",
        "mode": "online",
        "starts_at": "2026-09-16T10:00:00Z",
        "ends_at": "2026-10-15T03:59:00Z",
        "prize_value": 10000,
        "organization": "Circle",
        "location": "Online",
        "themes": ["Arc", "USDC", "Microgrants"],
        "directory_url": "https://dorahacks.io/hackathon/arc-microgrants",
        "registration_ends_at": None,
    }
    assert by_slug["satnav"].metadata["prize_value"] is None  # bonus_price 0
    assert connector.degraded is None
    assert connector.blocked is False


async def test_drops_in_person_ended_and_slugless_rows() -> None:
    page = await _connector([_payload()]).discover(_query())
    titles = " ".join(item.title for item in page.items)
    assert "Web3 for Social Good" not in titles  # IRL
    assert "BSA - EPFL" not in titles  # IRL
    assert "Agent Economy" not in titles and "agent-economy" not in titles  # ended
    assert all(item.metadata["mode"] in {"online", "hybrid"} for item in page.items)
    assert all(
        item.metadata["ends_at"] is None or item.metadata["ends_at"] > "2026-10-10"
        for item in page.items
    )
    # virtual rows with no uname have no public page and are skipped
    assert "Anna AI App Builder Program" not in titles
    assert "IITG.eth" not in titles


async def test_hybrid_kept_and_unknown_form_dropped() -> None:
    payload = {
        "next": None,
        "results": [
            _row(id=1, uname="hy", venue_form="Hybrid", venue_name="Hall A"),
            _row(id=2, uname="odd", venue_form="Somewhere"),
            _row(id=3, uname="irl", venue_form="IRL"),
        ],
    }
    page = await _connector([payload]).discover(_query())
    assert [item.external_id for item in page.items] == ["1"]
    assert page.items[0].metadata["mode"] == "hybrid"
    assert page.items[0].metadata["location"] == "Hall A"


async def test_prize_only_for_usd_like_tokens() -> None:
    payload = {
        "next": None,
        "results": [
            _row(id=1, uname="usdc", bonus_token="USDC", bonus_price=500),
            _row(id=2, uname="usdt", bonus_token="USDT", bonus_price=700),
            _row(id=3, uname="eth", bonus_token="ETH", bonus_price=12.5),
        ],
    }
    page = await _connector([payload]).discover(_query())
    by_id = {item.external_id: item.metadata for item in page.items}
    assert by_id["1"]["prize_value"] == 500
    assert by_id["2"]["prize_value"] == 700
    assert by_id["3"]["prize_value"] is None
    assert by_id["3"]["prize_text"] == "12.5 ETH"
    assert "prize_text" not in by_id["1"]


async def test_query_text_filter() -> None:
    page = await _connector([_payload()]).discover(_query(query_text="microgrants"))
    assert [item.title for item in page.items] == ["Arc Microgrants | Circle"]


async def test_paging_walks_pages_until_next_is_missing() -> None:
    calls: list[str] = []
    first = {"next": "x", "results": [_row(id=1, uname="a", title="A")]}
    second = {"next": None, "results": [_row(id=2, uname="b", title="B")]}
    connector = _connector([first, second], calls)
    page1 = await connector.discover(_query())
    assert page1.next_cursor == "2"
    page2 = await connector.discover(_query(), page1.next_cursor)
    assert page2.next_cursor is None
    assert [item.title for item in page1.items + page2.items] == ["A", "B"]
    assert calls[1].endswith("page=2&page_size=24")


async def test_paging_stops_once_a_whole_page_is_ended() -> None:
    ended = {
        "next": "x",
        "results": [_row(id=1, uname="old", timeline_end=UNIX_NOW - DAY)],
    }
    page = await _connector([ended]).discover(_query())
    assert page.items == []
    assert page.next_cursor is None


async def test_paging_is_bounded() -> None:
    live = {"next": "x", "results": [_row(id=1, uname="a")]}
    connector = _connector([live])
    page = await connector.discover(_query(), str(MAX_PAGES))
    assert page.next_cursor is None


async def test_dedupes_across_pages_but_resets_on_fresh_walk() -> None:
    payload = {"next": "x", "results": [_row(id=1, uname="a")]}
    connector = _connector([payload])
    first = await connector.discover(_query())
    again = await connector.discover(_query(), first.next_cursor)
    assert len(first.items) == 1
    assert again.items == []
    fresh = await connector.discover(_query())
    assert len(fresh.items) == 1


async def test_bot_wall_marks_blocked() -> None:
    wall = (FIXTURES / "waf_challenge.html").read_text(encoding="utf-8")
    connector = _connector([wall])
    page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is True
    assert connector.degraded is None


async def test_http_403_marks_blocked() -> None:
    connector = _connector([FetchError("HTTP 403 from dorahacks.io")])
    page = await connector.discover(_query())
    assert page.items == []
    assert connector.blocked is True


async def test_bad_payload_degrades() -> None:
    for bad in ({"results": "nope"}, ["not", "a", "dict"], {"unexpected": True}):
        connector = _connector([bad])
        page = await connector.discover(_query())
        assert page.items == [] and page.next_cursor is None
        assert connector.degraded == "dorahacks_directory_failed"
        assert connector.blocked is False


async def test_fetch_error_degrades() -> None:
    connector = _connector([RuntimeError("boom")])
    page = await connector.discover(_query())
    assert page.items == []
    assert connector.degraded == "dorahacks_directory_failed"


async def test_fixture_rows_with_cursor() -> None:
    rows = copy.deepcopy(_payload()["results"])
    connector = DoraHacksConnector(rows, now=_now)
    query = ConnectorQuery(module="hackathon", result_cap=2)
    first = await connector.discover(query)
    assert len(first.items) == 2
    assert first.next_cursor == "2"
    second = await connector.discover(query, first.next_cursor)
    assert len(second.items) == 2
    third = await connector.discover(query, second.next_cursor)
    assert [item.external_id for item in third.items] == ["1995"]
    assert third.next_cursor is None


async def test_fetch_detail_points_at_public_page() -> None:
    connector = _connector([_payload()])
    page = await connector.discover(_query())
    request = await connector.fetch_detail(page.items[0])
    assert request.url == page.items[0].url
    assert request.metadata == {"connector": "dorahacks"}
