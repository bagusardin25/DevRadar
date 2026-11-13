"""Offline contract tests for the Hack2skill directory connector.

The connector is driven through an injected ``http_get`` against a real page of
the public-list API stored in ``tests/fixtures/directories``. Degraded, ended
and paged rows are produced by mutating copies in test code, never by editing
the fixture.
"""

from __future__ import annotations

import copy
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from app.ingestion.fetcher import FetchError
from app.sources.connectors.base import ConnectorQuery, DiscoveryCandidate
from app.sources.connectors.hack2skill import MAX_PAGES, Hack2SkillConnector

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


def _payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        (FIXTURES / "hack2skill_public_list.json").read_text(encoding="utf-8")
    )
    return copy.deepcopy(payload)


def _connector(
    responses: Any, calls: list[str] | None = None
) -> Hack2SkillConnector:
    """``responses`` is a payload, or a ``page -> payload`` callable."""

    async def http_get(url: str) -> Any:
        if calls is not None:
            calls.append(url)
        if callable(responses):
            page = int(parse_qs(urlparse(url).query)["page"][0])
            return responses(page)
        return responses

    return Hack2SkillConnector(http_get=http_get, now=_now)


def _by_url(items: list[DiscoveryCandidate]) -> dict[str, DiscoveryCandidate]:
    return {item.url: item for item in items}


async def _walk(connector: Hack2SkillConnector) -> list[DiscoveryCandidate]:
    items: list[DiscoveryCandidate] = []
    cursor: str | None = None
    for _ in range(40):
        page = await connector.discover(_query(), cursor)
        items += page.items
        cursor = page.next_cursor
        if not cursor:
            break
    return items


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


async def test_parses_online_and_hybrid_rows() -> None:
    calls: list[str] = []
    page = await _connector(_payload(), calls).discover(_query())

    assert len(calls) == 1
    parsed = urlparse(calls[0])
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == (
        "https://hack2skill.com/api/v1/innovator/public/event/public-list"
    )
    params = parse_qs(parsed.query, keep_blank_values=True)
    assert params["page"] == ["1"]
    assert params["records"] == ["9"]
    assert params["search"] == [""]
    assert params["start"] == ["2026-10-10T12:00:00.000Z"]
    assert params["end"] == ["2027-10-10T12:00:00.000Z"]

    assert page.next_cursor == "2"  # the payload says ``pages: 2``
    by_url = _by_url(page.items)
    assert set(by_url) == {
        "https://hack2skill.com/event/aibuildercup2026",
        "https://hack2skill.com/event/datathon-2026",
        "https://hack2skill.com/event/pwvirtual1",
    }
    for item in page.items:
        assert set(item.metadata) == REQUIRED_KEYS
        assert item.metadata["source"] == "hack2skill"
        assert item.metadata["prize_value"] is None
        assert item.metadata["themes"] == []
        assert item.metadata["directory_url"] == item.url

    virtual = by_url["https://hack2skill.com/event/pwvirtual1"]
    assert virtual.title == "Virtual: PromptWars"
    assert virtual.external_id == "69cca4b245645a10e1172e76"
    assert virtual.metadata["mode"] == "online"
    assert virtual.metadata["location"] == "Online"
    # No submissionEnd: the registration deadline stands in for the end date.
    assert virtual.metadata["ends_at"] == "2026-11-30T04:53:00Z"
    assert virtual.metadata["registration_ends_at"] == "2026-11-30T04:53:00Z"

    hybrid = by_url["https://hack2skill.com/event/datathon-2026"]
    assert hybrid.metadata["mode"] == "hybrid"
    assert hybrid.metadata["location"] == "Hybrid"
    assert hybrid.metadata["starts_at"] == "2026-07-31T18:30:00Z"
    assert hybrid.metadata["ends_at"] == "2026-10-15T18:29:00Z"
    assert hybrid.metadata["registration_ends_at"] == "2026-10-15T18:29:00Z"


async def test_submission_end_wins_over_registration_end() -> None:
    page = await _connector(_payload()).discover(_query())
    cup = _by_url(page.items)["https://hack2skill.com/event/aibuildercup2026"]
    assert cup.metadata["ends_at"] == "2026-10-18T18:29:00Z"  # submissionEnd
    assert cup.metadata["registration_ends_at"] == "2026-10-11T18:29:00Z"


async def test_event_urls_relative_and_absolute() -> None:
    payload = _payload()
    rows = payload["data"]
    rows[3]["eventUrl"] = "/event/aibuildercup2026/"  # slash-wrapped slug
    rows[4]["eventUrl"] = "https://partner.example/hack"  # already absolute
    rows[5]["eventUrl"] = "../escape"  # unsafe -> skipped
    page = await _connector(payload).discover(_query())
    urls = {item.url for item in page.items}
    assert "https://hack2skill.com/event/aibuildercup2026" in urls
    assert "https://partner.example/hack" in urls
    assert not any("escape" in url for url in urls)


async def test_accepts_the_docs_payload_shape() -> None:
    payload = _payload()
    nested = {"success": True, "data": {"docs": payload["data"], "pages": 1}}
    page = await _connector(nested).discover(_query())
    assert len(page.items) == 3
    assert page.next_cursor is None


async def test_hybrid_location_uses_city_and_country_when_present() -> None:
    payload = _payload()
    for row in payload["data"]:
        if row.get("eventUrl") == "datathon-2026":
            row["city"], row["country"] = "Pune", "India"
    page = await _connector(payload).discover(_query())
    row = _by_url(page.items)["https://hack2skill.com/event/datathon-2026"]
    assert row.metadata["location"] == "Hybrid, Pune, India"


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #


async def test_in_person_rows_are_dropped() -> None:
    payload = _payload()
    modes = {row["eventUrl"]: row["mode"] for row in payload["data"] if row.get("eventUrl")}
    in_person = {slug for slug, mode in modes.items() if mode == "IN_PERSON"}
    assert in_person  # the fixture really contains in-person rows
    page = await _connector(payload).discover(_query())
    kept = {item.url.rsplit("/", 1)[1] for item in page.items}
    assert kept and not (kept & in_person)
    assert {item.metadata["mode"] for item in page.items} <= {"online", "hybrid"}


async def test_ended_rows_are_dropped() -> None:
    payload = _payload()
    for row in payload["data"]:
        if row.get("eventUrl") == "pwvirtual1":
            row["submissionEnd"] = "2026-10-01T00:00:00.000Z"  # over
        if row.get("eventUrl") == "datathon-2026":
            row["submissionEnd"] = None
            row["registrationEnd"] = "2026-10-09T00:00:00.000Z"  # fallback is over
    page = await _connector(payload).discover(_query())
    assert [item.url for item in page.items] == [
        "https://hack2skill.com/event/aibuildercup2026"
    ]


async def test_unknown_missing_and_bad_rows_are_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = _payload()
    rows = [row for row in payload["data"] if row["mode"] != "IN_PERSON"]
    assert len(rows) == 4  # three kept rows + the row without ``eventUrl``
    rows[0]["mode"] = "METAVERSE"  # unknown -> skipped
    rows[1]["submissionEnd"] = "not-a-date"  # bad date -> skipped
    payload["data"] = rows
    with caplog.at_level(logging.INFO):
        page = await _connector(payload).discover(_query())
    assert len(page.items) == 1
    reasons = {
        r.reason for r in caplog.records if r.getMessage() == "hack2skill_row_skipped"
    }
    assert reasons == {"unknown_mode", "bad_dates", "missing_id_title_or_url"}


async def test_query_text_filters_by_title() -> None:
    page = await _connector(_payload()).discover(_query(query_text="promptwars"))
    assert [item.title for item in page.items] == ["Virtual: PromptWars"]
    none = await _connector(_payload()).discover(_query(query_text="no such hackathon"))
    assert none.items == []


# --------------------------------------------------------------------------- #
# Paging
# --------------------------------------------------------------------------- #


async def test_walks_pages_until_the_last() -> None:
    first = _payload()
    first["pages"] = 3
    second = _payload()
    second["pages"] = 3
    for row in second["data"]:
        row["_id"] = "p2" + row["_id"]
        if row.get("eventUrl"):
            row["eventUrl"] = "p2-" + row["eventUrl"]
    third = {"success": True, "data": [], "pages": 3}
    calls: list[str] = []
    connector = _connector(lambda page: {1: first, 2: second, 3: third}[page], calls)
    items = await _walk(connector)

    assert [parse_qs(urlparse(u).query)["page"][0] for u in calls] == ["1", "2", "3"]
    assert len(items) == 6
    assert len({item.external_id for item in items}) == 6


async def test_repeated_rows_across_pages_are_deduplicated() -> None:
    payload = _payload()
    payload["pages"] = 2
    items = await _walk(_connector(payload))
    assert len(items) == 3  # page 2 repeats page 1


async def test_paging_is_bounded() -> None:
    payload = _payload()
    payload["pages"] = 999
    calls: list[str] = []

    def fresh_rows(page: int) -> dict[str, Any]:
        data = copy.deepcopy(payload)
        for row in data["data"]:
            row["_id"] = f"{page}-{row['_id']}"
        return data

    await _walk(_connector(fresh_rows, calls))
    assert len(calls) == MAX_PAGES


async def test_fixture_mode_paginates_by_offset() -> None:
    connector = Hack2SkillConnector(fixtures=_payload()["data"], now=_now)
    small = ConnectorQuery(module="hackathon", result_cap=2)
    first = await connector.discover(small)
    assert len(first.items) == 2 and first.next_cursor == "2"
    second = await connector.discover(small, first.next_cursor)
    assert len(second.items) == 1 and second.next_cursor is None
    assert first.items[0].url != second.items[0].url


# --------------------------------------------------------------------------- #
# Failure modes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("trigger", ["waf_page", "http_405", "http_429", "html"])
async def test_bot_wall_flags_blocked_and_returns_empty(
    trigger: str, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str] = []

    async def http_get(url: str) -> str:
        calls.append(url)
        if trigger.startswith("http_"):
            raise FetchError(f"HTTP {trigger[5:]} for {url}")
        if trigger == "html":
            return "<html><head><title>Welcome</title></head><body>hi</body></html>"
        return (FIXTURES / "waf_challenge.html").read_text(encoding="utf-8")

    connector = Hack2SkillConnector(http_get=http_get, now=_now)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is True
    assert connector.degraded is None
    assert len(calls) == 1  # no retry inside the same run
    records = [r for r in caplog.records if r.getMessage() == "source_blocked"]
    assert len(records) == 1 and records[0].source == "hack2skill"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "payload",
    [
        ["not", "a", "dict"],
        {"success": True},
        {"success": True, "data": "oops"},
        {"success": True, "data": {"docs": None}},
    ],
)
async def test_broken_payload_degrades(
    payload: Any, caplog: pytest.LogCaptureFixture
) -> None:
    connector = _connector(payload)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is False
    assert connector.degraded == "hack2skill_directory_failed"
    assert any(r.getMessage() == "hack2skill_directory_failed" for r in caplog.records)


async def test_invalid_json_and_network_errors_degrade() -> None:
    async def bad_json(_url: str) -> str:
        return "{not json"

    connector = Hack2SkillConnector(http_get=bad_json, now=_now)
    assert (await connector.discover(_query())).items == []
    assert connector.degraded == "hack2skill_directory_failed"

    async def boom(url: str) -> Any:
        raise FetchError(f"HTTP 500 for {url}")

    failed = Hack2SkillConnector(http_get=boom, now=_now)
    assert (await failed.discover(_query())).items == []
    assert failed.blocked is False
    assert failed.degraded == "hack2skill_directory_failed"


async def test_non_dict_rows_are_ignored() -> None:
    payload = _payload()
    payload["data"] = [None, "row", 7, *payload["data"]]
    page = await _connector(payload).discover(_query())
    assert len(page.items) == 3


async def test_fetch_detail_points_at_the_event_page() -> None:
    connector = _connector(_payload())
    page = await connector.discover(_query())
    request = await connector.fetch_detail(page.items[0])
    assert request.url == page.items[0].url
    assert request.metadata == {"connector": "hack2skill"}
    assert connector.name == connector.connector_type == "hack2skill"
