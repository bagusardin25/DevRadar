"""Cross-source dedupe and per-source collection (DB-free)."""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.harvest.runner import (
    SourceBatch,
    _per_source_limit,
    collect_new_candidates,
    collect_source,
    merge_batches,
)
from app.sources.connectors.base import ConnectorQuery, DiscoveryCandidate, DiscoveryPage
from app.sources.connectors.directory_common import title_key
from app.submissions.url_policy import canonicalize_url


def _hit(
    url: str,
    title: str,
    starts: str | None = None,
    ends: str | None = None,
    *,
    mode: str = "online",
) -> DiscoveryCandidate:
    return DiscoveryCandidate(
        external_id=url,
        url=url,
        title=title,
        metadata={"mode": mode, "starts_at": starts, "ends_at": ends},
    )


def test_title_key() -> None:
    assert title_key("The HackNC 2026!") == "hacknc"
    assert title_key("  Café Hack — 2027 ") == "cafe hack"
    assert title_key("") == "" and title_key(None) == ""
    # Only whole tokens are dropped.
    assert title_key("Theory Hack 20260") == "theory hack 20260"


def test_merge_dedupes_same_url_across_sources() -> None:
    batches = {
        "devpost": SourceBatch(fresh=[_hit("https://x.example.com/", "X Hack")]),
        "mlh": SourceBatch(fresh=[_hit("https://x.example.com", "Something Else")]),
    }
    selected, cross = merge_batches(batches, total_cap=40)
    assert [(key, hit.title) for key, hit in selected] == [("devpost", "X Hack")]
    assert cross == {"mlh": 1}


def test_merge_dedupes_title_and_overlapping_dates() -> None:
    batches = {
        "devpost": SourceBatch(
            fresh=[
                _hit(
                    "https://hacknc.devpost.com/",
                    "HackNC 2026",
                    "2026-10-01T00:00:00Z",
                    "2026-10-12T23:59:59Z",
                )
            ]
        ),
        "mlh": SourceBatch(
            fresh=[
                _hit(
                    "https://hacknc.com/",
                    "HackNC",
                    "2026-10-09T01:11:11Z",
                    "2026-10-11T20:00:00Z",
                    mode="hybrid",
                )
            ]
        ),
    }
    selected, cross = merge_batches(batches, total_cap=40)
    assert [key for key, _hit_ in selected] == ["devpost"]
    assert cross == {"mlh": 1}


def test_merge_keeps_same_title_disjoint_dates() -> None:
    batches = {
        "devpost": SourceBatch(
            fresh=[
                _hit(
                    "https://a.example.com/",
                    "HackNC",
                    "2026-03-01T00:00:00Z",
                    "2026-03-03T00:00:00Z",
                )
            ]
        ),
        "mlh": SourceBatch(
            fresh=[
                _hit(
                    "https://b.example.com/",
                    "HackNC",
                    "2026-10-09T00:00:00Z",
                    "2026-10-11T00:00:00Z",
                )
            ]
        ),
    }
    selected, cross = merge_batches(batches, total_cap=40)
    assert len(selected) == 2 and cross == {}


def test_merge_requires_dates_and_a_long_enough_title() -> None:
    dates = ("2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z")
    batches = {
        "devpost": SourceBatch(
            fresh=[
                _hit("https://a1.example.com/", "AI Hack", *dates),
                _hit("https://a2.example.com/", "Long Enough Name", None, None),
                _hit("https://a3.example.com/", "AI", *dates),
            ]
        ),
        "lablab": SourceBatch(
            fresh=[
                _hit("https://b1.example.com/", "AI Hack", *dates),
                _hit("https://b2.example.com/", "Long Enough Name", *dates),
                _hit("https://b3.example.com/", "AI", *dates),
            ]
        ),
    }
    selected, cross = merge_batches(batches, total_cap=40)
    kept = {hit.url for _key, hit in selected}
    # "ai hack" (7 characters, same dates) is a duplicate; the pair where one
    # row has no date and the 2-character title are never merged.
    assert "https://b1.example.com/" not in kept
    assert {"https://b2.example.com/", "https://b3.example.com/"} <= kept
    assert cross == {"lablab": 1}


def test_merge_never_merges_inside_one_source() -> None:
    dates = ("2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z")
    batches = {
        "devpost": SourceBatch(
            fresh=[
                _hit("https://a.example.com/", "Spring Build Jam", *dates),
                _hit("https://b.example.com/", "Spring Build Jam", *dates),
            ]
        )
    }
    selected, cross = merge_batches(batches, total_cap=40)
    assert len(selected) == 2 and cross == {}


def test_merge_drops_fresh_row_matching_known_row_of_other_source() -> None:
    dates = ("2026-10-01T00:00:00Z", "2026-10-03T00:00:00Z")
    batches = {
        "devpost": SourceBatch(
            fresh=[],
            seen_known=[_hit("https://listed.devpost.com/", "Listed Already Hack", *dates)],
            discovered=1,
            duplicates=1,
        ),
        "lablab": SourceBatch(
            fresh=[_hit("https://lablab.ai/event/listed", "Listed Already Hack 2026", *dates)]
        ),
    }
    selected, cross = merge_batches(batches, total_cap=40)
    assert selected == []
    assert cross == {"lablab": 1}


def test_merge_round_robin_respects_total_cap() -> None:
    batches = {
        key: SourceBatch(
            fresh=[_hit(f"https://{key}{i}.example.com/", f"{key} event {i}") for i in range(10)]
        )
        for key in ("devpost", "devfolio", "lablab")
    }
    selected, cross = merge_batches(batches, total_cap=7)
    counts = {key: sum(1 for k, _h in selected if k == key) for key in batches}
    assert counts == {"devpost": 3, "devfolio": 2, "lablab": 2}
    assert [key for key, _h in selected] == [
        "devpost",
        "devfolio",
        "lablab",
        "devpost",
        "devfolio",
        "lablab",
        "devpost",
    ]
    assert cross == {}
    # A small source is not starved by a big one.
    batches["devfolio"] = SourceBatch(fresh=[_hit("https://only.example.com/", "Only One")])
    selected, _ = merge_batches(batches, total_cap=40)
    assert sum(1 for k, _h in selected if k == "devfolio") == 1
    assert len(selected) == 21


class _PagedConnector:
    def __init__(self, pages: list[list[DiscoveryCandidate]]) -> None:
        self._pages = pages
        self.calls: list[str | None] = []
        self.blocked = False

    async def discover(self, query: ConnectorQuery, cursor: str | None = None) -> DiscoveryPage:
        self.calls.append(cursor)
        index = int(cursor or 0)
        nxt = str(index + 1) if index + 1 < len(self._pages) else None
        return DiscoveryPage(items=self._pages[index], next_cursor=nxt)


async def test_collect_source_records_known_rows_and_respects_limit() -> None:
    rows = [_hit(f"https://e{i}.example.com/", f"Event {i}") for i in range(30)]
    known = {canonicalize_url(f"https://e{i}.example.com/").canonical for i in range(5)}
    client = _PagedConnector([rows[:10], rows[10:20], rows[20:]])
    batch = await collect_source(client, known=known, limit=8)
    assert [h.url for h in batch.fresh] == [f"https://e{i}.example.com/" for i in range(5, 13)]
    assert [h.url for h in batch.seen_known] == [f"https://e{i}.example.com/" for i in range(5)]
    assert (batch.discovered, batch.duplicates) == (13, 5)
    assert client.calls == [None, "1"]  # stopped as soon as the limit was met

    fresh, discovered, duplicates = await collect_new_candidates(
        _PagedConnector([rows[:10]]), known=known, limit=50
    )
    assert (len(fresh), discovered, duplicates) == (5, 10, 5)


async def test_collect_source_dedupes_repeated_urls_inside_a_source() -> None:
    page = [
        _hit("https://same.example.com/", "Same"),
        _hit("https://same.example.com", "Same again"),
    ]
    batch = await collect_source(_PagedConnector([page]), known=set(), limit=10)
    assert len(batch.fresh) == 1 and batch.discovered == 2


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, app_env="test", **overrides)  # type: ignore[arg-type]


def test_per_source_limits() -> None:
    settings = _settings(harvest_devpost_cap=20, harvest_source_cap=10)
    assert _per_source_limit("devpost", settings, None) == 20
    assert _per_source_limit("devfolio", settings, None) == 10
    assert _per_source_limit("mlh", settings, 5) == 5
    assert _per_source_limit("devpost", settings, 500) == 50
