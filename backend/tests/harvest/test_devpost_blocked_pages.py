"""Devpost event pages behind a Cloudflare bot check (in-memory, no database).

The listing API (devpost.com/api/hackathons) keeps working while the event
pages answer "Just a moment...". The harvest must still queue the event from
the listing facts, flag it for a human, and never read the challenge as
content or treat the event as gone.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

import app.models  # noqa: F401
from app.catalog.enums import SourceTier
from app.config import Settings
from app.harvest import runner
from app.harvest.health import RunView, assess
from app.ingestion.fetcher import BotChallengeError, FetchedDocument
from app.ingestion.models import CrawlRun
from app.review.models import ReviewItem
from app.sources.connectors.devpost import DevpostConnector
from app.sources.models import Source
from tests.challenge_pages import (
    CHALLENGE_403,
    CHALLENGE_503,
    CHALLENGE_HTML,
    EVENT_200,
    EVENT_URL,
    HTML,
    allow_fixture_hosts,
    mock_fetch_url,
)

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)

# One row of devpost.com/api/hackathons, trimmed to what the harvest reads.
LISTING_ROW: dict[str, Any] = {
    "id": 25001,
    "title": "Kiroween Online Hack 2026",
    "url": EVENT_URL,
    "displayed_location": {"icon": "globe", "location": "Online"},
    "open_state": "open",
    "organization_name": "Example Labs",
    "submission_period_dates": "Oct 01 - Dec 05, 2026",
    "time_left_to_submission": "about 1 month left",
    "prize_amount": "$<span data-currency-value>10,000</span>",
    "themes": [{"id": 1, "name": "Machine Learning/AI"}],
}


class _ScalarResult:
    def scalar_one_or_none(self) -> None:
        return None


class _MemorySession:
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

    def of(self, kind: type) -> list[Any]:
        return [obj for obj in self.added if isinstance(obj, kind)]


def _settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        app_env="test",
        harvest_enabled=True,
        llm_provider="disabled",
        session_secret="test-session-secret-at-least-32-chars!!",
    )


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
    allow_fixture_hosts(monkeypatch)


async def _harvest(
    memory: _MemorySession,
    monkeypatch: pytest.MonkeyPatch,
    *,
    reply: Any = None,
    fetch_page: Any = None,
) -> runner.HarvestSummary:
    if reply is not None:
        # The production default fetcher, over a fixture reply.
        monkeypatch.setattr("app.discovery.http.fetch_url", mock_fetch_url(reply))
    return await runner.run_online_hackathon_harvest(
        memory,  # type: ignore[arg-type]
        _settings(),
        now=NOW,
        connectors={"devpost": DevpostConnector(fixtures=[dict(LISTING_ROW)])},
        fetch_page=fetch_page,
    )


def _assert_queued_from_listing_facts(item: ReviewItem, *, status_code: int) -> None:
    snap = item.candidate_snapshot
    fields, sources = snap["fields"], snap["fieldSources"]

    # Listing-API facts kept, each marked as coming from the directory.
    assert snap["title"] == "Kiroween Online Hack 2026"
    assert fields["organizer"] == "Example Labs"
    assert fields["prize_value"] == "10000"
    assert fields["submission_deadline"].startswith("2026-12-05T23:59:59")
    assert fields["mode"] == "online"
    assert fields["technologies"] == ["Machine Learning/AI"]
    for name in ("title", "organizer", "prize_value", "submission_deadline", "mode"):
        assert sources[name] == "directory"
    assert snap["officialUrl"].rstrip("/") == EVENT_URL.rstrip("/")
    assert snap["directory"]["dates"] == "Oct 01 - Dec 05, 2026"

    # Flagged for a human, not judged and not treated as gone.
    blocked = snap["pageBlocked"]
    assert blocked["statusCode"] == status_code
    assert blocked["needsHumanCheck"] is True
    assert snap["verification"]["status"] == "needs_review"
    assert "page_blocked_by_bot_check" in snap["verification"]["reasons"]
    assert snap["aiReview"]["recommendation"] == "needs_more_info"
    assert "bot check" in item.reason
    assert str(item.state) == "open"

    # Nothing from the challenge page was read as content.
    assert snap["description"] == ""
    assert "Just a moment" not in snap["title"]
    assert "Just a moment" not in json.dumps(fields)


async def test_cloudflare_403_queues_the_event_from_listing_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = _MemorySession()
    summary = await _harvest(memory, monkeypatch, reply=CHALLENGE_403)

    assert summary.queued == 1
    assert summary.pages_blocked == 1
    assert summary.skipped_fetch == 0
    assert summary.failed == 0
    sources = summary.as_meta()["sources"]
    assert sources["devpost"]["pages_blocked"] == 1
    assert sources["devpost"]["error"] is None  # the listing itself worked

    (item,) = memory.of(ReviewItem)
    _assert_queued_from_listing_facts(item, status_code=403)
    assert item.candidate_snapshot["pageBlocked"]["reason"] == "cf-mitigated:challenge"
    assert "Just a moment" not in json.dumps(item.candidate_snapshot)

    (run,) = memory.of(CrawlRun)
    assert str(run.status) == "partial"
    assert run.error_summary == "pages_blocked:1"


async def test_cloudflare_503_without_header_is_also_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = _MemorySession()
    summary = await _harvest(memory, monkeypatch, reply=CHALLENGE_503)

    assert summary.pages_blocked == 1
    (item,) = memory.of(ReviewItem)
    _assert_queued_from_listing_facts(item, status_code=503)


async def test_injected_fetcher_returning_a_200_challenge_is_not_parsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fetch(url: str, _policy: Any) -> FetchedDocument:
        return FetchedDocument(
            url=url, final_url=url, status_code=200, content_type=HTML, body=CHALLENGE_HTML
        )

    memory = _MemorySession()
    summary = await _harvest(memory, monkeypatch, fetch_page=fetch)

    assert summary.pages_blocked == 1
    (item,) = memory.of(ReviewItem)
    _assert_queued_from_listing_facts(item, status_code=200)


async def test_injected_fetcher_raising_a_challenge_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fetch(url: str, _policy: Any) -> FetchedDocument:
        raise BotChallengeError(url, 403, "cf-mitigated:challenge")

    memory = _MemorySession()
    summary = await _harvest(memory, monkeypatch, fetch_page=fetch)

    assert summary.pages_blocked == 1
    (item,) = memory.of(ReviewItem)
    _assert_queued_from_listing_facts(item, status_code=403)


async def test_normal_event_page_still_parses_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = _MemorySession()
    summary = await _harvest(memory, monkeypatch, reply=EVENT_200)

    assert summary.queued == 1
    assert summary.pages_blocked == 0
    (item,) = memory.of(ReviewItem)
    snap = item.candidate_snapshot
    assert "pageBlocked" not in snap
    assert snap["title"] == "Kiroween Online Hack 2026"
    assert snap["fieldSources"]["title"] != "directory"  # read from the page
    assert snap["fields"]["submission_deadline"].startswith("2026-12-05")
    assert "page_blocked_by_bot_check" not in snap["verification"]["reasons"]
    assert item.reason.startswith("Harvest (online Devpost): AI ")
    (run,) = memory.of(CrawlRun)
    assert str(run.status) == "succeeded"


def test_health_flags_blocked_pages() -> None:
    runs = [
        RunView(status="partial", started_at=NOW, discovered=12, error="pages_blocked:3"),
        RunView(status="succeeded", started_at=NOW, discovered=12),
    ]
    health = assess("devpost", runs, now=NOW)
    assert "pages_blocked" in health.flags
    assert "blocked" not in health.flags  # the listing API itself was fine
