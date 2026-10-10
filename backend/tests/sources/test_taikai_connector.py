"""Offline contract tests for the TAIKAI directory connector.

The fixture is a trimmed real ``/en/hackathons`` page (10 challenges in the
``__NEXT_DATA__`` Apollo cache). TAIKAI exposes no mode field, so none of the
real rows say "online": rows are given a mode cue by mutating the embedded
JSON in test code.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.ingestion.fetcher import FetchError
from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.taikai import TaikaiConnector, extract_challenges, mode_from_text

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "directories"
NOW = datetime(2026, 10, 10, tzinfo=UTC)
NEXT_DATA = re.compile(r'(<script id="__NEXT_DATA__"[^>]*>)(.*?)(</script>)', re.DOTALL)
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


def _page(mutate: Any = None) -> str:
    """The fixture page; ``mutate(apollo_state)`` edits the embedded cache."""
    html = _read("taikai_hackathons.html")
    if mutate is None:
        return html
    match = NEXT_DATA.search(html)
    assert match is not None
    data = json.loads(match.group(2))
    mutate(data["props"]["apolloState"])
    body = json.dumps(data)
    return html[: match.start(2)] + body + html[match.end(2) :]


def _challenge(state: dict[str, Any], slug: str) -> dict[str, Any]:
    for key, value in state.items():
        if key.startswith("Challenge:") and value["slug"] == slug:
            assert isinstance(value, dict)
            return value
    raise KeyError(slug)


def _connector(html: str, calls: list[str] | None = None) -> TaikaiConnector:
    async def http_get(url: str) -> str:
        if calls is not None:
            calls.append(url)
        return html

    return TaikaiConnector(http_get=http_get, now=_now)


def _with_cues(state: dict[str, Any]) -> None:
    _challenge(state, "spacexai-digital-transformation-lab")["shortDescription"] = (
        "A fully online challenge for Portuguese SMEs"
    )
    _challenge(state, "space-for-peace-resilience")["shortDescription"] = (
        "Lisbon, 2-4 November - Online + IRL finals"
    )
    # hack4guimaraes2035 stays without any cue; veles-hack-2026 is already over.


def test_extracts_challenges_with_refs_resolved() -> None:
    rows = extract_challenges(_read("taikai_hackathons.html"))
    assert rows is not None and len(rows) == 10
    first = rows[0]
    assert first["slug"] == "spacexai-digital-transformation-lab"
    assert first["organization"]["slug"] == "spacexai"
    assert first["prizeCurrency"]["name"] == "USD"
    assert first["steps"][0]["startDate"].startswith("2026-")


async def test_real_snapshot_has_no_confirmed_online_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[str] = []
    connector = _connector(_read("taikai_hackathons.html"), calls)
    with caplog.at_level(logging.INFO):
        page = await connector.discover(_query())
    # Three challenges are open but say nothing about their mode; Veles Hack's
    # last milestone (8 Oct) has passed; the other six are closed.
    assert page.items == [] and page.next_cursor is None
    assert calls == ["https://taikai.network/en/hackathons"]
    skipped = [r for r in caplog.records if r.getMessage() == "taikai_row_skipped"]
    assert len(skipped) == 3
    assert {r.reason for r in skipped} == {"unknown_mode"}  # type: ignore[attr-defined]
    assert connector.degraded is None and connector.blocked is False


async def test_mode_cue_makes_rows_candidates() -> None:
    page = await _connector(_page(_with_cues)).discover(_query())
    assert [item.url for item in page.items] == [
        "https://taikai.network/en/spacexai/hackathons/spacexai-digital-transformation-lab",
        "https://taikai.network/en/cassinihackathons/hackathons/space-for-peace-resilience",
    ]
    online, hybrid = page.items
    assert online.title == "SpaceXAI Digital Transformation Lab"
    assert set(online.metadata) == METADATA_KEYS
    assert online.metadata["source"] == "taikai"
    assert online.metadata["mode"] == "online" and online.metadata["location"] == "Online"
    assert hybrid.metadata["mode"] == "hybrid" and hybrid.metadata["location"] == "Hybrid"
    assert online.metadata["organization"] == "SpaceXAI"
    assert online.metadata["themes"] == ["Artificial Intelligence"]
    assert online.metadata["directory_url"] == online.url
    assert online.metadata["registration_ends_at"] is None
    # earliest milestone .. end of the UTC day of the latest milestone
    assert online.metadata["starts_at"] == "2026-09-15T23:00:00Z"
    assert online.metadata["ends_at"] == "2026-10-27T23:59:59Z"


async def test_prize_is_numeric_only_for_usd() -> None:
    page = await _connector(_page(_with_cues)).discover(_query())
    usd, eur = page.items
    assert usd.metadata["prize_value"] == 3500.0
    assert usd.metadata["prize_text"] == "3,500 USD"
    assert eur.metadata["prize_value"] is None
    assert eur.metadata["prize_text"] == "9,000 EUR"

    def free(state: dict[str, Any]) -> None:
        _with_cues(state)
        _challenge(state, "spacexai-digital-transformation-lab")["prize"] = 0

    free_page = await _connector(_page(free)).discover(_query())
    assert free_page.items[0].metadata["prize_value"] is None
    assert free_page.items[0].metadata["prize_text"] is None


async def test_closed_unpublished_and_ended_rows_are_dropped() -> None:
    def mutate(state: dict[str, Any]) -> None:
        _with_cues(state)
        for slug in ("spacexai-digital-transformation-lab", "space-for-peace-resilience",
                     "hack4guimaraes2035", "veles-hack-2026"):
            _challenge(state, slug)["shortDescription"] = "Online hackathon"
        _challenge(state, "spacexai-digital-transformation-lab")["isClosed"] = True
        _challenge(state, "space-for-peace-resilience")["isPublic"] = False
        publish = state[_challenge(state, "hack4guimaraes2035")["publishInfo"]["__ref"]]
        publish["state"] = "DRAFT"
        # veles-hack-2026 is still isClosed=false but its milestones are over.

    page = await _connector(_page(mutate)).discover(_query())
    assert page.items == []

    def only_veles_reopened(state: dict[str, Any]) -> None:
        veles = _challenge(state, "veles-hack-2026")
        veles["shortDescription"] = "Online hackathon"
        state[veles["steps"][-1]["__ref"]]["startDate"] = "2026-10-12T09:00:00.000Z"

    reopened = await _connector(_page(only_veles_reopened)).discover(_query())
    assert [item.title for item in reopened.items] == ["Veles Hack 2026"]
    assert reopened.items[0].metadata["ends_at"] == "2026-10-12T23:59:59Z"


async def test_unsafe_slug_is_skipped(caplog: pytest.LogCaptureFixture) -> None:
    def mutate(state: dict[str, Any]) -> None:
        row = _challenge(state, "spacexai-digital-transformation-lab")
        row["shortDescription"] = "Online"
        row["slug"] = "../escape"

    with caplog.at_level(logging.INFO):
        page = await _connector(_page(mutate)).discover(_query())
    assert page.items == []
    assert any(
        r.getMessage() == "taikai_row_skipped"
        and r.reason == "missing_title_or_bad_slug"  # type: ignore[attr-defined]
        for r in caplog.records
    )


async def test_query_text_filters_by_title() -> None:
    connector = _connector(_page(_with_cues))
    page = await connector.discover(_query(query_text="cassini"))
    assert [item.title for item in page.items] == [
        "CASSINI Hackathons - Space for Peace and Resilience"
    ]
    assert (await connector.discover(_query(query_text="nothing like this"))).items == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A fully online hackathon", "online"),
        ("Join our virtual challenge", "online"),
        ("Remote-first build week", "online"),
        ("Amsterdam 4-5 September - Online + IRL Hacker Battle", "hybrid"),
        ("Valencia, 6 - 8 October - Online participation possible", "hybrid"),
        ("Virtual and in-person tracks", "hybrid"),
        ("A hybrid hackathon", "hybrid"),
        ("In-person only in Lisbon, online judging", None),
        ("Create innovative solutions using EU space technologies", None),
        ("", None),
    ],
)
def test_mode_from_text(text: str, expected: str | None) -> None:
    assert mode_from_text(text) == expected


@pytest.mark.parametrize(
    "breakage",
    ["no_next_data", "bad_json", "no_apollo", "no_challenges", "renamed_fields"],
)
async def test_shape_change_degrades_instead_of_raising(
    breakage: str, caplog: pytest.LogCaptureFixture
) -> None:
    html = _read("taikai_hackathons.html")
    if breakage == "no_next_data":
        html = html.replace("__NEXT_DATA__", "__NEXT_STATE__")
    elif breakage == "bad_json":
        html = NEXT_DATA.sub(lambda m: m.group(1) + "{not json" + m.group(3), html)
    elif breakage == "no_apollo":
        html = html.replace("apolloState", "cache")
    elif breakage == "no_challenges":
        html = html.replace('"Challenge:', '"Contest:').replace("challenges(", "contests(")
    else:
        html = html.replace('"slug"', '"handle"')
    connector = _connector(html)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.degraded == "taikai_payload_missing"
    assert any(r.getMessage() == "taikai_payload_missing" for r in caplog.records)


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

    connector = TaikaiConnector(http_get=http_get, now=_now)
    with caplog.at_level(logging.WARNING):
        page = await connector.discover(_query())
    assert page.items == [] and page.next_cursor is None
    assert connector.blocked is True and connector.degraded is None
    assert len(calls) == 1
    records = [r for r in caplog.records if r.getMessage() == "source_blocked"]
    assert len(records) == 1 and records[0].source == "taikai"  # type: ignore[attr-defined]


async def test_plain_http_error_is_a_failure_not_a_block() -> None:
    async def http_get(url: str) -> str:
        raise FetchError(f"HTTP 500 for {url}")

    connector = TaikaiConnector(http_get=http_get, now=_now)
    page = await connector.discover(_query())
    assert page.items == [] and connector.blocked is False
    assert connector.degraded == "taikai_directory_failed"


async def test_fixture_mode_paginates_by_offset() -> None:
    rows = extract_challenges(_page(_with_cues))
    assert rows is not None
    connector = TaikaiConnector(fixtures=rows, now=_now)
    small = ConnectorQuery(module="hackathon", result_cap=1)
    first = await connector.discover(small)
    assert len(first.items) == 1 and first.next_cursor == "1"
    second = await connector.discover(small, first.next_cursor)
    assert len(second.items) == 1 and second.next_cursor is None
    assert first.items[0].url != second.items[0].url


def test_connector_identity() -> None:
    connector = TaikaiConnector()
    assert connector.name == "taikai" and connector.connector_type == "taikai"
