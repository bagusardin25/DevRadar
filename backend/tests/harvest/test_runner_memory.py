"""Runner orchestration against an in-memory session (no database needed).

The DB-backed twin of these checks lives in ``test_runner.py``; this file lets
the multi-source flow (per-source runs, caps, blocks) be verified without
Postgres.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

import app.models  # noqa: F401
from app.catalog.enums import SourceTier
from app.config import Settings
from app.harvest import runner
from app.ingestion.fetcher import FetchedDocument
from app.ingestion.models import CrawlRun
from app.review.models import ReviewItem
from app.sources.connectors.base import ConnectorQuery, DiscoveryPage
from app.sources.connectors.devfolio import DevfolioConnector
from app.sources.connectors.devpost import DevpostConnector
from app.sources.connectors.lablab import LablabConnector
from app.sources.connectors.mlh import MLHConnector
from app.sources.models import Source

NOW = datetime(2026, 8, 14, 8, 15, tzinfo=UTC)

ONLINE_HTML = b"""<html><head><title>Online Agents Hack 2026</title></head>
<body><h1>Online Agents Hack 2026</h1><p>Organizer: Example Labs</p>
<p>This event is fully online and open worldwide.</p>
<p>Submission deadline 2026-09-30T23:59:00Z.</p></body></html>"""


class _ScalarResult:
    def scalar_one_or_none(self) -> None:
        return None


class _MemorySession:
    """Just enough of AsyncSession for the harvest runner."""

    def __init__(self) -> None:
        self.added: list[Any] = []

    async def execute(self, _statement: Any) -> _ScalarResult:
        return _ScalarResult()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()


def _lablab_row(n: int) -> dict[str, Any]:
    return {
        "id": f"row-{n}",
        "name": f"Lab Event {n}",
        "slug": f"lab-event-{n}",
        "type": "HACKATHON",
        "eventType": "ONLINE",
        "startAt": f"2026-09-0{n}T00:00:00.000Z",
        "endAt": f"2026-10-0{n}T00:00:00.000Z",
    }


def _devfolio_row(n: int) -> dict[str, Any]:
    return {
        "uuid": f"d{n}",
        "name": f"Folio Event {n}",
        "slug": f"folio-{n}",
        "is_online": True,
        "starts_at": "2026-09-01T00:00:00.000Z",
        "ends_at": "2026-12-01T00:00:00.000Z",
        "hackathon_setting": {"subdomain": f"folio-{n}"},
    }


def _devpost_row(n: int) -> dict[str, Any]:
    return {
        "id": str(n),
        "url": f"https://dp-{n}.devpost.com/",
        "title": f"Post Event {n}",
        "displayed_location": {"icon": "globe", "location": "Online"},
    }


def _settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_env": "test",
        "harvest_enabled": True,
        "llm_provider": "disabled",
        "session_secret": "test-session-secret-at-least-32-chars!!",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)  # type: ignore[arg-type]


@pytest.fixture
def memory() -> _MemorySession:
    return _MemorySession()


@pytest.fixture(autouse=True)
def _no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    async def ensure_source(session: Any, key: str = "devpost") -> Source:
        info = runner.HARVEST_SOURCES[key]
        source = Source(
            name=info.name,
            connector_type=info.connector_type,
            trust_tier=SourceTier.TIER_2,
            base_url=info.base_url,
        )
        source.id = uuid4()
        return source

    async def known_urls(_session: Any) -> set[str]:
        return set()

    async def known_listings(_session: Any) -> dict[str, runner.KnownListing]:
        return {}

    monkeypatch.setattr(runner, "_ensure_harvest_source", ensure_source)
    monkeypatch.setattr(runner, "_known_urls", known_urls)
    monkeypatch.setattr(runner, "_known_listings", known_listings)


async def _fake_fetch(url: str, policy: Any) -> FetchedDocument:
    return FetchedDocument(
        url=url, final_url=url, status_code=200, content_type="text/html", body=ONLINE_HTML
    )


def _now() -> datetime:
    return NOW


async def test_runner_collects_every_source_and_applies_the_total_cap(
    memory: _MemorySession,
) -> None:
    lablab = LablabConnector(fixtures=[_lablab_row(n) for n in range(1, 6)], now=_now)
    devfolio = DevfolioConnector(fixtures=[_devfolio_row(n) for n in range(1, 6)], now=_now)
    summary = await runner.run_online_hackathon_harvest(
        memory,  # type: ignore[arg-type]
        _settings(harvest_source_cap=4, harvest_total_cap=5),
        now=NOW,
        connectors={"devfolio": devfolio, "lablab": lablab},
        fetch_page=_fake_fetch,
    )
    meta = summary.as_meta()
    assert summary.queued == 5  # total ceiling, shared round-robin
    assert meta["sources"]["devfolio"]["queued"] == 3
    assert meta["sources"]["lablab"]["queued"] == 2
    assert meta["sources"]["devfolio"]["discovered"] == 4  # per-source cap stops the walk
    assert summary.discovered == 8
    runs = [obj for obj in memory.added if isinstance(obj, CrawlRun)]
    assert len(runs) == 2
    assert {str(run.status) for run in runs} == {"succeeded"}
    assert summary.crawl_run_id == str(runs[0].id)
    items = [obj for obj in memory.added if isinstance(obj, ReviewItem)]
    assert {item.candidate_snapshot["source"] for item in items} == {
        "harvest_devfolio",
        "harvest_lablab",
    }
    assert all(item.reason.startswith("Harvest (online ") for item in items)
    directory = items[0].candidate_snapshot["directory"]
    assert directory["source"] == "devfolio"
    assert directory["startsAt"] == "2026-09-01T00:00:00Z"


async def test_runner_blocked_source_fails_its_run_and_others_continue(
    memory: _MemorySession,
) -> None:
    async def waf(_url: str) -> str:
        return "<html><head><title>Human Verification</title></head></html>"

    summary = await runner.run_online_hackathon_harvest(
        memory,  # type: ignore[arg-type]
        _settings(),
        now=NOW,
        connectors={
            "lablab": LablabConnector(http_get=waf, now=_now),
            "devfolio": DevfolioConnector(fixtures=[_devfolio_row(1)], now=_now),
        },
        fetch_page=_fake_fetch,
    )
    sources = summary.as_meta()["sources"]
    assert sources["lablab"]["error"] == "blocked"
    assert sources["devfolio"]["queued"] == 1
    assert sources["devfolio"]["error"] is None
    statuses = [str(run.status) for run in memory.added if isinstance(run, CrawlRun)]
    assert sorted(statuses) == ["failed", "succeeded"]


async def test_runner_degraded_sources_are_reported_as_partial_runs(
    memory: _MemorySession,
) -> None:
    async def no_payload(_url: str) -> str:
        return "<html><body>redesigned, no RSC payload</body></html>"

    async def server_error(_url: str) -> Any:
        raise RuntimeError("HTTP 500")

    summary = await runner.run_online_hackathon_harvest(
        memory,  # type: ignore[arg-type]
        _settings(),
        now=NOW,
        connectors={
            "lablab": LablabConnector(http_get=no_payload, now=_now),
            "devfolio": DevfolioConnector(http_get=server_error, now=_now),
            "mlh": MLHConnector(fixtures=[], now=_now),
            "devpost": DevpostConnector(fixtures=[_devpost_row(1)], now=_now),
        },
        fetch_page=_fake_fetch,
    )
    sources = summary.as_meta()["sources"]
    assert sources["lablab"]["error"] == "lablab_payload_missing"
    assert sources["devfolio"]["error"] == "devfolio_directory_failed"
    assert sources["mlh"]["error"] is None
    assert sources["devpost"]["error"] is None
    assert sources["devpost"]["queued"] == 1  # the healthy source still ran
    runs = {
        run.error_summary or "": str(run.status)
        for run in memory.added
        if isinstance(run, CrawlRun)
    }
    assert runs["lablab_payload_missing"] == "partial"
    assert runs["devfolio_directory_failed"] == "partial"
    assert runs[""] == "succeeded"


async def test_runner_isolates_a_crashing_source(memory: _MemorySession) -> None:
    class Exploding:
        blocked = False

        async def discover(
            self, query: ConnectorQuery, cursor: str | None = None
        ) -> DiscoveryPage:
            raise RuntimeError("boom")

    summary = await runner.run_online_hackathon_harvest(
        memory,  # type: ignore[arg-type]
        _settings(),
        now=NOW,
        connectors={
            "devfolio": Exploding(),
            "lablab": LablabConnector(fixtures=[_lablab_row(1)], now=_now),
        },
        fetch_page=_fake_fetch,
    )
    sources = summary.as_meta()["sources"]
    assert sources["devfolio"]["error"] == "RuntimeError"
    assert sources["lablab"]["queued"] == 1


async def test_runner_legacy_connector_argument_is_devpost_only(
    memory: _MemorySession,
) -> None:
    devpost = DevpostConnector(
        fixtures=[
            {
                "id": "1",
                "url": "https://one.devpost.com/",
                "title": "One",
                "displayed_location": {"icon": "globe", "location": "Online"},
            }
        ]
    )
    summary = await runner.run_online_hackathon_harvest(
        memory,  # type: ignore[arg-type]
        _settings(),
        now=NOW,
        connector=devpost,
        fetch_page=_fake_fetch,
    )
    assert list(summary.as_meta()["sources"]) == ["devpost"]
    assert summary.queued == 1


async def test_runner_with_no_sources_is_a_noop(memory: _MemorySession) -> None:
    summary = await runner.run_online_hackathon_harvest(
        memory,  # type: ignore[arg-type]
        _settings(harvest_sources=""),
        now=NOW,
        fetch_page=_fake_fetch,
    )
    assert summary.queued == 0 and summary.per_source == {}
    assert memory.added == []


async def test_runner_rejects_unknown_source_keys(memory: _MemorySession) -> None:
    with pytest.raises(ValueError, match="hackerrank"):
        await runner.run_online_hackathon_harvest(
            memory,  # type: ignore[arg-type]
            _settings(),
            now=NOW,
            connectors={"hackerrank": LablabConnector(fixtures=[], now=_now)},
        )


def test_window_key_keeps_devpost_hash_and_separates_sources() -> None:
    expected = hashlib.sha256(b"harvest|devpost|online|20260814T08").hexdigest()
    assert runner._window_key(NOW) == expected
    assert runner._window_key(NOW, "devpost") == expected
    keys = {runner._window_key(NOW, key) for key in runner.HARVEST_SOURCES}
    assert len(keys) == len(runner.HARVEST_SOURCES)
    assert runner._window_key(NOW, "mlh") != runner._window_key(NOW.replace(hour=16), "mlh")
