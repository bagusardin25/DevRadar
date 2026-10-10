"""Offline contract tests for the ETHGlobal directory connector.

The fixture is a trimmed real ``/events`` page (12 rows, the RSC payload split
over two ``self.__next_f.push`` chunks). Every real row is either physical or
finished, so online/hybrid rows are produced by mutating rows in test code.
"""

from __future__ import annotations

import copy
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.ingestion.fetcher import FetchError
from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.ethglobal import EthglobalConnector, extract_events

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "directories"
NOW = datetime(2026, 10, 10, tzinfo=UTC)
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


def _now() -> datetime:
    return NOW


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _query(**kwargs: Any) -> ConnectorQuery:
    return ConnectorQuery(module="hackathon", result_cap=40, **kwargs)


def _rows() -> list[dict[str, Any]]:
    rows = extract_events(_read("ethglobal_events.html"))
    assert rows is not None
    return copy.deepcopy(rows)


def _by_slug(rows: list[dict[str, Any]], slug: str) -> dict[str, Any]:
    return next(row for row in rows if row["slug"] == slug)


def _page(rows: list[dict[str, Any]]) -> str:
    """Rebuild an RSC page around ``rows``, split mid-array like the real one."""
    text = '6:["$","$L27",null,{"events":' + json.dumps(rows) + ',"filters":{}}]\n'
    cut = len(text) // 2
    scripts = "".join(
        f"<script>self.__next_f.push({json.dumps([1, chunk])})</script>"
        for chunk in (text[:cut], text[cut:])
    )
    return f"<html><body>{scripts}</body></html>"


def _connector(html: str, calls: list[str] | None = None) -> EthglobalConnector:
    async def http_get(url: str) -> str:
        if calls is not None:
            calls.append(url)
        return html

    return EthglobalConnector(http_get=http_get, now=_now)


def _open_hackathon(**overrides: Any) -> dict[str, Any]:
    row = _by_slug(_rows(), "mumbai")  # the one real future hackathon (physical)
    row.update(medium="virtual", city=None)
    row.update(overrides)
    return row


def test_extracts_events_from_split_rsc_chunks() -> None:
    html = _read("ethglobal_events.html")
    assert html.count("self.__next_f.push(") == 3
    rows = extract_events(html)
    assert rows is not None and len(rows) == 12
    assert {row["medium"] for row in rows} == {"physical", "virtual"}
    assert {row["type"] for row in rows} == {"hackathon", "summit", "cafe"}


async def test_real_snapshot_has_no_open_online_hackathon() -> None:
    calls: list[str] = []
    connector = _connector(_read("ethglobal_events.html"), calls)
    page = await connector.discover(_query())
    # ETHGlobal Mumbai is physical; ETHOnline 2026 / Open Agents / HackMoney 2026
    # are finished; summits and cowork "cafe" events are not hackathons.
    assert page.items == [] and page.next_cursor is None
    assert calls == ["https://ethglobal.com/events"]
    assert connector.degraded is None and connector.blocked is False


async def test_online_row_maps_to_candidate() -> None:
    row = _open_hackathon()
    page = await _connector(_page([row])).discover(_query())
    assert len(page.items) == 1
    item = page.items[0]
    assert item.external_id == str(row["id"])
    assert item.url == "https://ethglobal.com/events/mumbai"
    assert item.title == "ETHGlobal Mumbai"
    assert set(item.metadata) == METADATA_KEYS
    assert item.metadata["source"] == "ethglobal"
    assert item.metadata["mode"] == "online"
    assert item.metadata["location"] == "Online"
    assert item.metadata["organization"] == "ETHGlobal"
    assert item.metadata["starts_at"] == "2026-11-05T00:00:00Z"
    assert item.metadata["ends_at"] == "2026-11-07T00:00:00Z"
    assert item.metadata["registration_ends_at"] == "2026-11-03T18:29:00Z"
    assert item.metadata["prize_value"] is None
    assert item.metadata["themes"] == []
    assert item.metadata["directory_url"] == item.url


async def test_hybrid_row_keeps_city_and_physical_is_dropped() -> None:
    hybrid = _open_hackathon(medium="hybrid", city=_by_slug(_rows(), "mumbai")["city"])
    physical = _open_hackathon(id=999, slug="somewhere", name="Somewhere", medium="physical")
    page = await _connector(_page([hybrid, physical])).discover(_query())
    assert [(i.url, i.metadata["mode"], i.metadata["location"]) for i in page.items] == [
        ("https://ethglobal.com/events/mumbai", "hybrid", "Mumbai")
    ]


async def test_only_hackathons_that_are_still_running_are_kept() -> None:
    rows = [
        _open_hackathon(id=1, slug="keep", name="Keep"),
        _open_hackathon(id=2, slug="summit", name="Summit", type="summit"),
        _open_hackathon(id=3, slug="cafe", name="Cafe", type="cafe"),
        _open_hackathon(id=4, slug="over", name="Over", endTime="2026-10-01T00:00:00.000Z"),
        _open_hackathon(id=5, slug="done", name="Done", status="finished"),
        _open_hackathon(id=6, slug="cancelled", name="Cancelled", status="cancelled"),
        _open_hackathon(id=7, slug="live", name="Live", status="live", endTime=None),
    ]
    page = await _connector(_page(rows)).discover(_query())
    assert [item.external_id for item in page.items] == ["1", "7"]
    assert page.items[1].metadata["ends_at"] is None


async def test_unknown_medium_bad_dates_and_bad_slug_are_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rows = [
        _open_hackathon(id=1, slug="mystery", name="Mystery", medium="metaverse"),
        _open_hackathon(id=2, slug="baddate", name="Bad date", startTime="soon"),
        _open_hackathon(id=3, slug="../escape", name="Escape"),
        _open_hackathon(id=4, slug="ok", name="Fine"),
    ]
    with caplog.at_level(logging.INFO):
        page = await _connector(_page(rows)).discover(_query())
    assert [item.external_id for item in page.items] == ["4"]
    reasons = {r.reason for r in caplog.records if r.getMessage() == "ethglobal_row_skipped"}  # type: ignore[attr-defined]
    assert reasons == {"unknown_mode", "bad_dates", "missing_title_or_bad_slug"}


async def test_query_text_filters_by_title() -> None:
    rows = [
        _open_hackathon(id=1, slug="alpha", name="ETHOnline Alpha"),
        _open_hackathon(id=2, slug="beta", name="Superhack Beta"),
    ]
    connector = _connector(_page(rows))
    page = await connector.discover(_query(query_text="superhack"))
    assert [item.external_id for item in page.items] == ["2"]


async def test_duplicate_rows_are_deduped() -> None:
    row = _open_hackathon()
    page = await _connector(_page([row, copy.deepcopy(row)])).discover(_query())
    assert len(page.items) == 1


@pytest.mark.parametrize("breakage", ["renamed_key", "truncated", "no_pushes", "bad_rows"])
async def test_shape_change_degrades_instead_of_raising(
    breakage: str, caplog: pytest.LogCaptureFixture
) -> None:
    html = _read("ethglobal_events.html")
    if breakage == "renamed_key":
        html = html.replace('\\"events\\":', '\\"eventList\\":')
    elif breakage == "truncated":
        html = html[: html.rindex("<script>")] + "</body></html>"
    elif breakage == "no_pushes":
        html = "<html><body><h1>Redesigned without RSC</h1></body></html>"
    else:
        html = html.replace('\\"slug\\"', '\\"slugx\\"')
    connector = _connector(html)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.degraded == "ethglobal_payload_missing"
    assert connector.blocked is False
    assert any(r.getMessage() == "ethglobal_payload_missing" for r in caplog.records)


def test_decoded_size_bound() -> None:
    html = _read("ethglobal_events.html")
    assert extract_events(html) is not None
    assert extract_events(html, max_chars=200) is None


@pytest.mark.parametrize("trigger", ["waf_page", "http_405"])
async def test_bot_check_returns_empty_and_blocks(
    trigger: str, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str] = []

    async def http_get(url: str) -> str:
        calls.append(url)
        if trigger == "http_405":
            raise FetchError(f"HTTP 405 for {url}")
        return _read("waf_challenge.html")

    connector = EthglobalConnector(http_get=http_get, now=_now)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is True and connector.degraded is None
    assert len(calls) == 1
    records = [r for r in caplog.records if r.getMessage() == "source_blocked"]
    assert len(records) == 1 and records[0].source == "ethglobal"  # type: ignore[attr-defined]


async def test_plain_http_error_is_a_failure_not_a_block() -> None:
    async def http_get(url: str) -> str:
        raise FetchError(f"HTTP 500 for {url}")

    connector = EthglobalConnector(http_get=http_get, now=_now)
    page = await connector.discover(_query())
    assert page.items == [] and connector.blocked is False
    assert connector.degraded == "ethglobal_directory_failed"


async def test_fixture_mode_paginates_by_offset() -> None:
    rows = [
        _open_hackathon(id=1, slug="one", name="One"),
        _open_hackathon(id=2, slug="two", name="Two"),
    ]
    connector = EthglobalConnector(fixtures=rows, now=_now)
    small = ConnectorQuery(module="hackathon", result_cap=1)
    first = await connector.discover(small)
    assert [i.external_id for i in first.items] == ["1"] and first.next_cursor == "1"
    second = await connector.discover(small, first.next_cursor)
    assert [i.external_id for i in second.items] == ["2"] and second.next_cursor is None


def test_connector_identity() -> None:
    connector = EthglobalConnector()
    assert connector.name == "ethglobal" and connector.connector_type == "ethglobal"
