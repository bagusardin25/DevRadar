"""Offline contract tests for the live directory connectors.

Every connector is exercised through an injected ``http_get`` against trimmed
real responses stored in ``tests/fixtures/directories``. Degraded and digital
rows are mutated here in test code, never written into the fixtures.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.ingestion.fetcher import FetchedDocument, FetchError
from app.sources.connectors import directory_common
from app.sources.connectors.base import ConnectorQuery, DiscoveryCandidate
from app.sources.connectors.devfolio import DevfolioConnector
from app.sources.connectors.devpost import DevpostConnector, parse_period_dates
from app.sources.connectors.directory_common import (
    SourceBlocked,
    fetch_json,
    fetch_text,
    iso_utc,
    ranges_overlap,
)
from app.sources.connectors.lablab import LablabConnector, extract_sorted_events
from app.sources.connectors.mlh import MLHConnector, extract_inertia_page, seasons_to_read

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "directories"
NOW = datetime(2026, 10, 10, tzinfo=UTC)


def _now() -> datetime:
    return NOW


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _query(**kwargs: Any) -> ConnectorQuery:
    return ConnectorQuery(module="hackathon", result_cap=40, **kwargs)


async def _walk(connector: Any, max_pages: int = 30) -> list[DiscoveryCandidate]:
    items: list[DiscoveryCandidate] = []
    cursor: str | None = None
    for _ in range(max_pages):
        page = await connector.discover(_query(), cursor)
        items += page.items
        cursor = page.next_cursor
        if not cursor:
            break
    return items


def _devfolio_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(_read("devfolio_application_open.json"))
    return payload


def _devfolio_connector(
    responses: dict[str, dict[str, Any]], calls: list[str]
) -> DevfolioConnector:
    """``responses`` maps a phase to the JSON returned for it (page 1 and 2)."""

    async def http_get(url: str) -> dict[str, Any]:
        calls.append(url)
        phase = re.search(r"filter=(\w+)", url)
        assert phase is not None
        return responses.get(phase.group(1), {"result": [], "count": 0, "pages": 1})

    return DevfolioConnector(http_get=http_get, now=_now)


def _mlh_html(mutate: Any = None) -> str:
    html = _read("mlh_2027_events.html")
    if mutate is None:
        return html
    page = extract_inertia_page(html)
    assert page is not None
    mutate(page["props"]["upcomingEvents"])
    body = json.dumps(page)
    return re.sub(
        r'(<script data-page="app"[^>]*>).*?(</script>)',
        lambda m: m.group(1) + body + m.group(2),
        html,
        flags=re.DOTALL,
    )


def _mlh_connector(
    html: str, calls: list[str] | None = None, *, now: datetime = NOW
) -> MLHConnector:
    async def http_get(url: str) -> str:
        if calls is not None:
            calls.append(url)
        return html

    return MLHConnector(http_get=http_get, now=lambda: now)


def _lablab_connector(html: str, calls: list[str] | None = None) -> LablabConnector:
    async def http_get(url: str) -> str:
        if calls is not None:
            calls.append(url)
        return html

    return LablabConnector(http_get=http_get, now=_now)


# --------------------------------------------------------------------------- #
# Devfolio
# --------------------------------------------------------------------------- #


async def test_devfolio_parses_sample() -> None:
    calls: list[str] = []
    connector = _devfolio_connector({"application_open": _devfolio_payload()}, calls)
    page = await connector.discover(_query())
    assert [item.title for item in page.items] == ["Winter of Code 2026", "hackodisha-6.0"]
    first = page.items[0]
    assert first.url == "https://winter-of-code-4.devfolio.co/"
    assert first.metadata["location"] == "Online"
    assert first.metadata["mode"] == "online"
    assert first.metadata["source"] == "devfolio"
    assert first.metadata["prize_value"] is None
    assert first.metadata["themes"] == ["No Restrictions"]
    assert first.metadata["starts_at"] == "2026-10-14T18:30:00Z"
    assert first.metadata["registration_ends_at"] == "2026-10-13T18:30:00.000Z"
    assert page.next_cursor == "live:1"  # one page only: on to the next phase
    assert len(calls) == 1


async def test_devfolio_phases_and_uuid_dedupe() -> None:
    row = _devfolio_payload()["result"][1]
    calls: list[str] = []
    connector = _devfolio_connector(
        {
            "application_open": {"result": [row], "count": 1, "pages": 1},
            "live": {"result": [copy.deepcopy(row)], "count": 1, "pages": 1},
        },
        calls,
    )
    items = await _walk(connector)
    assert len(items) == 1
    assert all("limit=50" in url for url in calls)
    phases = [re.search(r"filter=(\w+)", url).group(1) for url in calls]  # type: ignore[union-attr]
    assert phases == ["application_open", "live", "upcoming"]


async def test_devfolio_stops_at_pages() -> None:
    rows = _devfolio_payload()["result"]
    calls: list[str] = []
    connector = _devfolio_connector(
        {
            "upcoming": {"result": [rows[1]], "count": 2, "pages": 2},
        },
        calls,
    )
    cursor: str | None = "upcoming:1"
    seen = 0
    while cursor:
        page = await connector.discover(_query(), cursor)
        seen += 1
        cursor = page.next_cursor
    assert seen == 2
    assert len(calls) == 2
    assert cursor is None


async def test_devfolio_caps_pages_per_phase() -> None:
    row = _devfolio_payload()["result"][1]
    calls: list[str] = []
    connector = _devfolio_connector(
        {"live": {"result": [row], "count": 999, "pages": 99}}, calls
    )
    cursor: str | None = "live:1"
    while cursor and cursor.startswith("live"):
        cursor = (await connector.discover(_query(), cursor)).next_cursor
    assert len(calls) == 5
    assert cursor == "upcoming:1"


async def test_devfolio_degraded_rows(caplog: pytest.LogCaptureFixture) -> None:
    rows = copy.deepcopy(_devfolio_payload()["result"][:2])
    del rows[0]["is_online"]  # unknown mode -> skipped
    rows[1]["hackathon_setting"]["subdomain"] = "Bad_Sub!"  # unsafe host -> skipped
    rows[1]["slug"] = "Bad Slug"
    calls: list[str] = []
    connector = _devfolio_connector(
        {"application_open": {"result": rows, "count": 2, "pages": 1}}, calls
    )
    with caplog.at_level(logging.INFO):
        page = await connector.discover(_query())
    assert page.items == []
    assert {r.reason for r in caplog.records if r.getMessage() == "devfolio_row_skipped"} == {
        "unknown_mode",
        "bad_subdomain",
    }

    # A payload that is not a dict / has no result list degrades to nothing.
    async def list_payload(_url: str) -> Any:
        return ["not", "a", "dict"]

    degraded = await DevfolioConnector(http_get=list_payload, now=_now).discover(_query())
    assert degraded.items == [] and degraded.next_cursor is None

    async def boom(_url: str) -> Any:
        raise RuntimeError("network down")

    failed = await DevfolioConnector(http_get=boom, now=_now).discover(_query())
    assert failed.items == [] and failed.next_cursor is None


async def test_devfolio_drops_in_person_and_ended_rows() -> None:
    rows = copy.deepcopy(_devfolio_payload()["result"])
    rows[0]["ends_at"] = "2026-10-01T00:00:00.000Z"  # online but already over
    connector = _devfolio_connector(
        {"application_open": {"result": rows, "count": 4, "pages": 1}}, []
    )
    page = await connector.discover(_query())
    # winter-of-code ended, qhack-india and tum are in person: only hackodisha remains.
    assert [item.url for item in page.items] == ["https://hackodisha-6a.devfolio.co/"]


async def test_devfolio_fixture_mode_paginates_by_offset() -> None:
    connector = DevfolioConnector(fixtures=_devfolio_payload()["result"], now=_now)
    first = await connector.discover(ConnectorQuery(module="hackathon", result_cap=1))
    assert len(first.items) == 1 and first.next_cursor == "1"
    second = await connector.discover(
        ConnectorQuery(module="hackathon", result_cap=1), first.next_cursor
    )
    assert len(second.items) == 1 and second.next_cursor is None
    assert first.items[0].url != second.items[0].url


# --------------------------------------------------------------------------- #
# MLH
# --------------------------------------------------------------------------- #


async def test_mlh_parses_inertia_payload() -> None:
    calls: list[str] = []
    page = await _mlh_connector(_mlh_html(), calls).discover(_query())
    assert calls == ["https://www.mlh.com/seasons/2027/events"]
    assert len(page.items) == 3
    assert page.next_cursor is None
    html_rows = extract_inertia_page(_mlh_html())["props"]["upcomingEvents"]  # type: ignore[index]
    websites = {row["websiteUrl"] for row in html_rows}
    for item in page.items:
        assert item.url in websites
        assert item.metadata["mode"] == "hybrid"
        assert item.metadata["source"] == "mlh"
        assert item.metadata["league"] == "MLH"
        assert item.metadata["directory_url"].startswith("https://www.mlh.com/events/")
        assert item.metadata["prize_value"] is None
        assert item.metadata["starts_at"].endswith("Z")


async def test_mlh_digital_is_online_physical_dropped(caplog: pytest.LogCaptureFixture) -> None:
    def mutate(events: list[dict[str, Any]]) -> None:
        events[0]["formatType"] = "digital"
        events[1]["formatType"] = "mystery"  # unknown -> skipped, not an error

    with caplog.at_level(logging.INFO):
        page = await _mlh_connector(_mlh_html(mutate)).discover(_query())
    assert Counter(item.metadata["mode"] for item in page.items) == {"online": 1, "hybrid": 1}
    assert "physical" not in {item.metadata["mode"] for item in page.items}
    assert any(r.getMessage() == "mlh_row_skipped" for r in caplog.records)


async def test_mlh_drops_ended_and_closed_events() -> None:
    def mutate(events: list[dict[str, Any]]) -> None:
        events[0]["endsAt"] = "2026-10-01T00:00:00Z"
        events[1]["status"] = "finished"

    page = await _mlh_connector(_mlh_html(mutate)).discover(_query())
    assert len(page.items) == 1


async def test_mlh_falls_back_to_directory_page_without_website() -> None:
    def mutate(events: list[dict[str, Any]]) -> None:
        events[0]["websiteUrl"] = "javascript:alert(1)"

    page = await _mlh_connector(_mlh_html(mutate)).discover(_query())
    first = page.items[0]
    assert first.url == "https://www.mlh.com/events/" + first.metadata["directory_url"].split(
        "/events/"
    )[1].split("/")[0]


def test_mlh_season_selection() -> None:
    assert seasons_to_read(datetime(2026, 10, 10, tzinfo=UTC)) == [2027]
    assert seasons_to_read(datetime(2026, 6, 1, tzinfo=UTC)) == [2026, 2027]
    assert seasons_to_read(datetime(2027, 1, 15, tzinfo=UTC)) == [2027]
    assert seasons_to_read(datetime(2026, 8, 1, tzinfo=UTC)) == [2027]


async def test_mlh_failing_season_is_skipped() -> None:
    calls: list[str] = []
    html = _mlh_html()

    async def http_get(url: str) -> str:
        calls.append(url)
        if "/2026/" in url:
            raise FetchError("HTTP 404 for " + url)
        return html

    connector = MLHConnector(http_get=http_get, now=lambda: datetime(2026, 6, 1, tzinfo=UTC))
    first = await connector.discover(_query())
    assert first.items == [] and first.next_cursor == "2027:1"
    second = await connector.discover(_query(), first.next_cursor)
    assert len(second.items) == 3 and second.next_cursor is None
    assert [url.split("/seasons/")[1] for url in calls] == ["2026/events", "2027/events"]


async def test_mlh_missing_payload_degrades(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        page = await _mlh_connector("<html><body>no payload here</body></html>").discover(
            _query()
        )
    assert page.items == [] and page.next_cursor is None
    assert any(r.getMessage() == "mlh_payload_missing" for r in caplog.records)

    broken = '<script data-page="app" type="application/json">{not json</script>'
    assert (await _mlh_connector(broken).discover(_query())).items == []


async def test_mlh_entity_escaped_payload_is_decoded() -> None:
    import html as html_lib

    html = _mlh_html()
    body = re.search(r'data-page="app"[^>]*>(.*?)</script>', html, re.DOTALL).group(1)  # type: ignore[union-attr]
    escaped = html.replace(body, html_lib.escape(body, quote=True))
    assert body.startswith("{") and escaped != html
    page = await _mlh_connector(escaped).discover(_query())
    assert len(page.items) == 3


async def test_mlh_legacy_fixture_mode() -> None:
    mlh = MLHConnector(
        fixtures=[
            {"url": "https://mlh.io/e1", "title": "E1", "mode": "online"},
            {"url": "https://mlh.io/e2", "title": "E2"},
        ]
    )
    page = await mlh.discover(ConnectorQuery(module="hackathon", result_cap=1))
    assert [(i.external_id, i.url, i.title, i.metadata) for i in page.items] == [
        ("https://mlh.io/e1", "https://mlh.io/e1", "E1", {"mode": "online", "source": "mlh"})
    ]
    assert page.next_cursor == "1"
    last = await mlh.discover(ConnectorQuery(module="hackathon", result_cap=1), "1")
    assert last.items[0].metadata["mode"] == "online" and last.next_cursor is None


# --------------------------------------------------------------------------- #
# lablab.ai
# --------------------------------------------------------------------------- #


def test_lablab_extracts_split_rsc_payload() -> None:
    html = _read("lablab_ai_hackathons.html")
    assert html.count("self.__next_f.push(") == 3
    rows = extract_sorted_events(html)
    assert rows is not None
    assert len(rows) == 5
    assert {row["eventType"] for row in rows} == {"ONLINE", "HYBRID", "ONSITE"}


async def test_lablab_maps_and_filters() -> None:
    calls: list[str] = []
    page = await _lablab_connector(_read("lablab_ai_hackathons.html"), calls).discover(_query())
    assert calls == ["https://lablab.ai/ai-hackathons"]
    assert page.next_cursor is None
    assert len(page.items) == 3
    assert Counter(item.metadata["mode"] for item in page.items) == {"online": 1, "hybrid": 2}
    by_url = {item.url: item for item in page.items}
    online = by_url["https://lablab.ai/event/amd-lablab-ai-academy-challenge"]
    assert online.title == "AMD AI League"
    assert online.metadata["prize_value"] is None
    assert online.metadata["organization"] == "lablab.ai"
    assert online.metadata["location"] == "Online"
    assert online.metadata["participants"] == 4963
    assert online.metadata["starts_at"] == "2026-09-01T19:00:00Z"
    hybrid = by_url["https://lablab.ai/event/vultr-hackathon"]
    assert hybrid.metadata["location"] == "Hybrid"
    assert all(item.metadata["prize_value"] is None for item in page.items)


async def test_lablab_row_filters(caplog: pytest.LogCaptureFixture) -> None:
    rows = extract_sorted_events(_read("lablab_ai_hackathons.html"))
    assert rows is not None
    rows = copy.deepcopy(rows)
    rows[0]["deletedAt"] = "2026-10-01T00:00:00.000Z"  # soft-deleted
    rows[1]["type"] = "WORKSHOP"
    rows[2]["eventType"] = "SOMETHING_NEW"  # unknown mode -> skipped
    rows[3]["endAt"] = None  # no end date -> kept
    rows[4]["slug"] = "../escape"
    connector = LablabConnector(fixtures=rows, now=_now)
    with caplog.at_level(logging.INFO):
        page = await connector.discover(_query())
    assert [item.external_id for item in page.items] == [rows[3]["id"]]
    reasons = {r.reason for r in caplog.records if r.getMessage() == "lablab_row_skipped"}
    assert reasons == {"unknown_mode", "missing_title_or_bad_slug"}


@pytest.mark.parametrize("breakage", ["renamed_key", "truncated", "no_pushes", "bad_rows"])
async def test_lablab_shape_change_degrades(
    breakage: str, caplog: pytest.LogCaptureFixture
) -> None:
    html = _read("lablab_ai_hackathons.html")
    if breakage == "renamed_key":
        html = html.replace("sortedEvents", "sortedEvent")
    elif breakage == "truncated":
        # The last RSC chunk never arrived: the array is cut off mid-row.
        html = html[: html.rindex("<script>")] + "</body></html>"
    elif breakage == "no_pushes":
        html = "<html><body><h1>Redesigned without RSC</h1></body></html>"
    else:
        html = html.replace("slug", "slugx")
    with caplog.at_level(logging.WARNING):
        page = await _lablab_connector(html).discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert any(r.getMessage() == "lablab_payload_missing" for r in caplog.records)


def test_lablab_decoded_size_bound() -> None:
    html = _read("lablab_ai_hackathons.html")
    assert extract_sorted_events(html) is not None
    assert extract_sorted_events(html, max_chars=200) is None


# --------------------------------------------------------------------------- #
# Bot walls
# --------------------------------------------------------------------------- #


def _connector_for_block(kind: str, http_get: Any) -> Any:
    connector_cls = {
        "devpost": DevpostConnector,
        "devfolio": DevfolioConnector,
        "mlh": MLHConnector,
        "lablab": LablabConnector,
    }[kind]
    return connector_cls(http_get=http_get, now=_now)


@pytest.mark.parametrize("trigger", ["waf_page", "http_405"])
@pytest.mark.parametrize("kind", ["devpost", "devfolio", "mlh", "lablab"])
async def test_bot_check_returns_empty_and_blocks(
    kind: str, trigger: str, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str] = []

    async def http_get(url: str) -> str:
        calls.append(url)
        if trigger == "http_405":
            raise FetchError(f"HTTP 405 for {url}")
        return _read("waf_challenge.html")

    connector = _connector_for_block(kind, http_get)
    assert connector.blocked is False
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is True
    assert len(calls) == 1  # no retry inside the same run
    records = [r for r in caplog.records if r.getMessage() == "source_blocked"]
    assert len(records) == 1
    assert records[0].source == kind  # type: ignore[attr-defined]
    assert records[0].url == calls[0]  # type: ignore[attr-defined]
    assert records[0].reason  # type: ignore[attr-defined]


async def test_json_source_answering_with_html_is_blocked() -> None:
    async def http_get(_url: str) -> str:
        return "<html><head><title>Welcome</title></head><body>hi</body></html>"

    connector = DevfolioConnector(http_get=http_get, now=_now)
    page = await connector.discover(_query())
    assert page.items == [] and connector.blocked is True


async def test_other_http_errors_are_failures_not_blocks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def http_get(url: str) -> str:
        raise FetchError(f"HTTP 500 for {url}")

    connector = LablabConnector(http_get=http_get, now=_now)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and connector.blocked is False
    assert any(r.getMessage() == "lablab_directory_failed" for r in caplog.records)


def _document(body: str, content_type: str) -> FetchedDocument:
    return FetchedDocument(
        url="https://example.test/",
        final_url="https://example.test/",
        status_code=200,
        content_type=content_type,
        body=body.encode(),
    )


async def test_live_fetch_helpers_apply_the_bot_wall_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result: dict[str, Any] = {}

    async def fake_fetch_url(url: str, policy: Any) -> FetchedDocument:
        result["policy"] = policy
        outcome = result["outcome"]
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, FetchedDocument)
        return outcome

    monkeypatch.setattr(directory_common, "fetch_url", fake_fetch_url)

    result["outcome"] = _document('{"ok": true}', "application/json")
    assert await fetch_json("https://example.test/", 1000) == {"ok": True}
    assert result["policy"].user_agent.startswith("Mozilla/5.0 (compatible; DevRadarBot")
    assert result["policy"].max_bytes == 1000

    result["outcome"] = _document(_read("waf_challenge.html"), "text/html; charset=utf-8")
    with pytest.raises(SourceBlocked):
        await fetch_json("https://example.test/", 1000)
    with pytest.raises(SourceBlocked):
        await fetch_text("https://example.test/", 1000)

    result["outcome"] = _document("<html><title>Dashboard</title></html>", "text/html")
    with pytest.raises(SourceBlocked, match="html_for_json"):
        await fetch_json("https://example.test/", 1000)
    assert "Dashboard" in await fetch_text("https://example.test/", 1000)

    result["outcome"] = FetchError("HTTP 429 for https://example.test/")
    with pytest.raises(SourceBlocked):
        await fetch_text("https://example.test/", 1000)

    result["outcome"] = FetchError("HTTP 404 for https://example.test/")
    with pytest.raises(FetchError):
        await fetch_text("https://example.test/", 1000)


# --------------------------------------------------------------------------- #
# Devpost delta and shared helpers
# --------------------------------------------------------------------------- #


def test_devpost_parse_period_dates() -> None:
    assert parse_period_dates("Sep 03 - 25, 2026") == (
        "2026-09-03T00:00:00Z",
        "2026-09-25T23:59:59Z",
    )
    assert parse_period_dates("Aug 21 - Oct 02, 2026") == (
        "2026-08-21T00:00:00Z",
        "2026-10-02T23:59:59Z",
    )
    assert parse_period_dates("Aug 29, 2026") == (
        "2026-08-29T00:00:00Z",
        "2026-08-29T23:59:59Z",
    )
    assert parse_period_dates("Dec 17, 2025 - Feb 09, 2026") == (
        "2025-12-17T00:00:00Z",
        "2026-02-09T23:59:59Z",
    )
    for garbage in (None, "", "TBA", "Feb 31, 2026", "Oct 20 - 05, 2026", "soon-ish", 42):
        assert parse_period_dates(garbage) == (None, None)


async def test_devpost_candidates_carry_dates_and_blocked_flag() -> None:
    async def http_get(_url: str) -> dict[str, Any]:
        return {
            "hackathons": [
                {
                    "id": 1,
                    "title": "Online Only",
                    "url": "https://online.devpost.com/",
                    "displayed_location": {"icon": "globe", "location": "Online"},
                    "submission_period_dates": "Sep 03 - 25, 2026",
                }
            ],
            "meta": {"total_count": 1, "per_page": 40},
        }

    connector = DevpostConnector(http_get=http_get)
    page = await connector.discover(_query())
    meta = page.items[0].metadata
    assert (meta["starts_at"], meta["ends_at"]) == (
        "2026-09-03T00:00:00Z",
        "2026-09-25T23:59:59Z",
    )
    assert meta["submission_period_dates"] == "Sep 03 - 25, 2026"
    assert meta["mode"] == "online"
    assert connector.blocked is False


def test_iso_utc_accepts_unix_and_iso_and_rsc_dates() -> None:
    assert iso_utc(1_791_590_400) == "2026-10-10T00:00:00Z"
    assert iso_utc(1_791_590_400_000) == "2026-10-10T00:00:00Z"
    assert iso_utc("2026-10-30T03:30:00.000Z") == "2026-10-30T03:30:00Z"
    assert iso_utc("$D2026-10-10T08:00:00+08:00") == "2026-10-10T00:00:00Z"
    assert iso_utc("2026-10-10T00:00:00") == "2026-10-10T00:00:00Z"
    for bad in (None, "", "not a date", True):
        assert iso_utc(bad) is None


def test_ranges_overlap_with_slack() -> None:
    assert ranges_overlap("2026-10-01T00:00:00Z", "2026-10-12T00:00:00Z",
                          "2026-10-09T00:00:00Z", "2026-10-11T00:00:00Z")
    # Adjacent by a day counts as overlapping; a week apart does not.
    assert ranges_overlap("2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z",
                          "2026-10-03T00:00:00Z", "2026-10-04T00:00:00Z")
    assert not ranges_overlap("2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z",
                              "2026-10-09T00:00:00Z", "2026-10-10T00:00:00Z")
    # A missing start never matches; a missing end collapses to the start.
    assert not ranges_overlap(None, None, "2026-10-09T00:00:00Z", None)
    assert ranges_overlap("2026-10-09T00:00:00Z", None, "2026-10-09T12:00:00Z", None)
