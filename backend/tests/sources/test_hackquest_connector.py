"""Offline contract tests for the HackQuest directory connector.

HackQuest's robots.txt disallows ``/api/``, so the connector only ever reads the
public HTML page. The fixture is a trimmed copy of that page: the hackathon rows
travel in two React Server Component flight chunks, split mid-value like the
real stream. Rows are mutated in test code (``_html``), never in the fixture.
"""

from __future__ import annotations

import copy
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.ingestion.fetcher import FetchError
from app.sources.connectors.base import ConnectorQuery, DiscoveryCandidate
from app.sources.connectors.hackquest import (
    HACKQUEST_URL,
    HackQuestConnector,
    extract_hackathon_rows,
    prize_fields,
)
from app.sources.connectors.lablab import decode_rsc_text

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "directories"
NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)

DUBAI = "https://www.hackquest.io/hackathons/Arbitrum-Open-House-Dubai-Online-Buildathon"
JAKARTA = "https://www.hackquest.io/hackathons/Ethereum-Jakarta-Hackathon-2026"
SINGAPORE = "https://www.hackquest.io/hackathons/Arbitrum-Open-House-Singapore-Online-Buildathon"

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


def _fixture_html() -> str:
    return _read("hackquest_hackathons.html")


def _fixture_rows() -> list[dict[str, Any]]:
    text, _pushes = decode_rsc_text(_fixture_html())
    rows = extract_hackathon_rows(text)
    assert rows is not None
    return copy.deepcopy(rows)


def _html(mutate: Callable[[list[dict[str, Any]]], None] | None = None) -> str:
    """The fixture page, re-encoded after ``mutate`` changed its rows."""
    if mutate is None:
        return _fixture_html()
    rows = _fixture_rows()
    mutate(rows)
    flight = '16:{"data":[],"total":0}\n2b:' + json.dumps({"data": rows, "total": len(rows)})
    return (
        "<html><head><title>Explore Hackathons - HackQuest</title></head><body>"
        "<script>self.__next_f.push(" + json.dumps([1, flight]) + ")</script>"
        "</body></html>"
    )


def _connector(html: str, calls: list[str] | None = None) -> HackQuestConnector:
    async def http_get(url: str) -> str:
        if calls is not None:
            calls.append(url)
        return html

    return HackQuestConnector(http_get=http_get, now=_now)


def _by_url(items: list[DiscoveryCandidate]) -> dict[str, DiscoveryCandidate]:
    return {item.url: item for item in items}


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


def test_extracts_rows_split_across_flight_chunks() -> None:
    html = _fixture_html()
    assert html.count("self.__next_f.push([1,") == 2  # one value, two chunks
    text, pushes = decode_rsc_text(html)
    assert pushes == 2
    rows = extract_hackathon_rows(text)
    assert rows is not None
    assert [row["alias"] for row in rows][0] == "Arbitrum-Open-House-Dubai-Online-Buildathon"
    assert len(rows) == 3
    # The empty ``{"data": []}`` placeholder in the stream is skipped over.
    assert extract_hackathon_rows('x:{"data":[],"total":0}\n') is None


async def test_parses_the_embedded_slice_from_the_html_page_only() -> None:
    calls: list[str] = []
    page = await _connector(_html(), calls).discover(_query())

    assert calls == ["https://www.hackquest.io/hackathons"]
    assert not any("/api/" in call for call in calls)  # robots.txt disallows /api/
    assert page.next_cursor is None

    # Singapore closed submissions on 2026-10-04: dropped as ended.
    by_url = _by_url(page.items)
    assert set(by_url) == {DUBAI, JAKARTA}
    for item in page.items:
        assert set(item.metadata) == REQUIRED_KEYS
        assert item.metadata["source"] == "hackquest"
        assert item.metadata["directory_url"] == item.url

    dubai = by_url[DUBAI]
    assert dubai.title == "Arbitrum Open House Dubai: Online Buildathon"
    assert dubai.external_id == "9dfcd5f7-f644-458a-8448-88d22ed098ff"
    assert dubai.metadata["mode"] == "online"
    assert dubai.metadata["location"] == "Online"
    assert dubai.metadata["organization"] == "Arbitrum Foundation"
    assert dubai.metadata["prize_value"] == 30000
    assert dubai.metadata["prize_text"] == "30000 USD"
    assert dubai.metadata["themes"] == ["Arbitrum"]  # the "All" tech stack is dropped
    assert dubai.metadata["starts_at"] == "2026-11-16T16:01:00Z"  # submissionOpen
    assert dubai.metadata["ends_at"] == "2026-12-06T16:01:00Z"  # submissionClose
    assert dubai.metadata["registration_ends_at"] == "2026-12-05T16:01:00Z"

    jakarta = by_url[JAKARTA]
    assert jakarta.metadata["mode"] == "hybrid"
    assert jakarta.metadata["location"] == "Hybrid"
    assert jakarta.metadata["prize_value"] == 1650
    assert jakarta.metadata["themes"] == ["Solidity", "Ethereum"]


async def test_rows_decoded_from_json_escapes_round_trip() -> None:
    def mutate(rows: list[dict[str, Any]]) -> None:
        rows[0]["name"] = "Café “Buildathon” — Online"

    page = await _connector(_html(mutate)).discover(_query())
    assert page.items[0].title == "Café “Buildathon” — Online"


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #


async def test_in_person_rows_are_dropped() -> None:
    def mutate(rows: list[dict[str, Any]]) -> None:
        rows[0]["info"]["mode"] = "OFFLINE"
        rows[1]["info"]["mode"] = "IN_PERSON"

    page = await _connector(_html(mutate)).discover(_query())
    assert page.items == []  # Singapore is over, the other two are in person


async def test_ended_rows_are_dropped_and_missing_close_falls_back() -> None:
    page = await _connector(_html()).discover(_query())
    assert SINGAPORE not in {item.url for item in page.items}

    def mutate(rows: list[dict[str, Any]]) -> None:
        rows[0]["timeline"]["submissionClose"] = None
        rows[0]["timeline"]["rewardTime"] = "2026-10-01T00:00:00.000Z"  # fallback is over
        rows[1]["timeline"]["submissionClose"] = "2026-10-09T00:00:00.000Z"

    gone = await _connector(_html(mutate)).discover(_query())
    assert gone.items == []


async def test_row_filters(caplog: pytest.LogCaptureFixture) -> None:
    def mutate(rows: list[dict[str, Any]]) -> None:
        rows[0]["info"]["mode"] = "HOLOGRAM"  # unknown mode -> skipped
        rows[1]["alias"] = "../escape"  # unsafe alias -> skipped
        rows[2]["info"]["mode"] = "ONLINE"
        rows[2]["timeline"]["submissionClose"] = "2026-12-31T00:00:00.000Z"
        rows[2]["status"] = "draft"  # unpublished -> dropped quietly
        rows.append(copy.deepcopy(rows[2]) | {"status": "publish", "id": "dup-1"})
        rows.append(copy.deepcopy(rows[2]) | {"status": "publish", "id": "dup-1"})
        rows.append(copy.deepcopy(rows[2]) | {"status": "publish", "id": "bad-date"})
        rows[-1]["timeline"]["submissionOpen"] = "garbage"

    with caplog.at_level(logging.INFO):
        page = await _connector(_html(mutate)).discover(_query())
    assert [item.external_id for item in page.items] == ["dup-1"]  # id-deduplicated
    reasons = {r.reason for r in caplog.records if r.getMessage() == "hackquest_row_skipped"}
    assert reasons == {"unknown_mode", "missing_id_title_or_bad_alias", "bad_dates"}


async def test_query_text_filters_by_title() -> None:
    page = await _connector(_html()).discover(_query(query_text="jakarta"))
    assert [item.url for item in page.items] == [JAKARTA]
    assert (await _connector(_html()).discover(_query(query_text="zzz"))).items == []


# --------------------------------------------------------------------------- #
# Prize
# --------------------------------------------------------------------------- #


def test_prize_is_numeric_only_for_clear_dollar_currencies() -> None:
    def row(total: Any, *currencies: str) -> dict[str, Any]:
        return {
            "totalRewards": total,
            "rewards": [{"totalRewards": 1, "currency": c} for c in currencies],
        }

    assert prize_fields(row("30000", "USD")) == (30000, "30000 USD")
    assert prize_fields(row("115000", "USDC", "USDC")) == (115000, "115000 USDC")
    assert prize_fields(row("2500.5", "USDT")) == (2500.5, "2500.5 USDT")
    assert prize_fields(row("5000", "USD", "USDC")) == (5000, "5000 USD/USDC")
    # Anything else keeps only the raw text.
    assert prize_fields(row("1000", "EUR")) == (None, "1000 EUR")
    assert prize_fields(row("1000", "USD", "EUR")) == (None, "1000 EUR/USD")
    assert prize_fields(row("1000")) == (None, "1000")
    assert prize_fields(row("0", "USD")) == (None, "0 USD")
    assert prize_fields(row("lots", "USD")) == (None, "lots USD")
    assert prize_fields({}) == (None, None)
    # Without a top-level total the per-reward sum is used.
    summed = {
        "rewards": [
            {"totalRewards": 40, "currency": "USD"},
            {"totalRewards": 2, "currency": "USD"},
        ]
    }
    assert prize_fields(summed) == (42, "42 USD")


async def test_non_dollar_prize_end_to_end() -> None:
    def mutate(rows: list[dict[str, Any]]) -> None:
        rows[0]["totalRewards"] = "4000"
        rows[0]["rewards"] = [{"totalRewards": 4000, "currency": "EUR"}]

    page = await _connector(_html(mutate)).discover(_query())
    dubai = _by_url(page.items)[DUBAI]
    assert dubai.metadata["prize_value"] is None
    assert dubai.metadata["prize_text"] == "4000 EUR"


# --------------------------------------------------------------------------- #
# Fixture mode
# --------------------------------------------------------------------------- #


async def test_fixture_mode_paginates_by_offset() -> None:
    connector = HackQuestConnector(fixtures=_fixture_rows(), now=_now)
    small = ConnectorQuery(module="hackathon", result_cap=1)
    first = await connector.discover(small)
    assert len(first.items) == 1 and first.next_cursor == "1"
    second = await connector.discover(small, first.next_cursor)
    assert len(second.items) == 1 and second.next_cursor is None
    assert first.items[0].url != second.items[0].url


# --------------------------------------------------------------------------- #
# Failure modes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("trigger", ["waf_page", "http_405", "http_429"])
async def test_bot_wall_flags_blocked_and_returns_empty(
    trigger: str, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str] = []

    async def http_get(url: str) -> str:
        calls.append(url)
        if trigger.startswith("http_"):
            raise FetchError(f"HTTP {trigger[5:]} for {url}")
        return _read("waf_challenge.html")

    connector = HackQuestConnector(http_get=http_get, now=_now)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is True
    assert connector.degraded is None
    assert calls == [HACKQUEST_URL]  # no retry, never the API
    records = [r for r in caplog.records if r.getMessage() == "source_blocked"]
    assert len(records) == 1 and records[0].source == "hackquest"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "breakage", ["renamed_key", "truncated", "no_pushes", "bad_rows", "empty_data"]
)
async def test_shape_change_degrades(
    breakage: str, caplog: pytest.LogCaptureFixture
) -> None:
    html = _fixture_html()
    if breakage == "renamed_key":
        html = html.replace(r'\"alias\"', r'\"aliax\"')
    elif breakage == "truncated":
        # The last chunk never arrived: the array is cut off mid-row.
        html = html[: html.rindex("<script>")] + "</body></html>"
    elif breakage == "no_pushes":
        html = "<html><body><h1>Redesigned without RSC</h1></body></html>"
    elif breakage == "bad_rows":
        html = html.replace(r'\"name\"', r'\"nam3\"')
    else:
        html = _html(lambda rows: rows.clear())
    connector = _connector(html)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is False
    assert connector.degraded == "hackquest_payload_missing"
    assert any(r.getMessage() == "hackquest_payload_missing" for r in caplog.records)


async def test_network_errors_degrade_without_blocking() -> None:
    async def boom(url: str) -> str:
        raise FetchError(f"HTTP 500 for {url}")

    connector = HackQuestConnector(http_get=boom, now=_now)
    page = await connector.discover(_query())
    assert page.items == [] and connector.blocked is False
    assert connector.degraded == "hackquest_directory_failed"


async def test_oversized_decoded_stream_degrades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.sources.connectors import hackquest

    monkeypatch.setattr(hackquest, "MAX_DECODED_CHARS", 200)
    connector = _connector(_fixture_html())
    page = await connector.discover(_query())
    assert page.items == []
    assert connector.degraded == "hackquest_payload_missing"


async def test_fetch_detail_points_at_the_event_page() -> None:
    connector = _connector(_fixture_html())
    page = await connector.discover(_query())
    request = await connector.fetch_detail(page.items[0])
    assert request.url == page.items[0].url
    assert request.metadata == {"connector": "hackquest"}
    assert connector.name == connector.connector_type == "hackquest"
