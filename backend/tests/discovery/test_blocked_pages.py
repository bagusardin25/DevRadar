"""Live discovery over a seed page behind a Cloudflare bot check (no database)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.config import Settings
from app.discovery import runner
from app.discovery.http import BlockedPage, fetch_document, fetch_document_or_block
from app.discovery.seeds import SeedCandidate
from app.ingestion.fetcher import FetchPolicy
from tests.challenge_pages import (
    CHALLENGE_403,
    EVENT_200,
    EVENT_URL,
    allow_fixture_hosts,
    mock_fetch_url,
)

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fixture_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_fixture_hosts(monkeypatch)


async def test_fetch_document_or_block_reports_the_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.discovery.http.fetch_url", mock_fetch_url(CHALLENGE_403))
    result = await fetch_document_or_block(EVENT_URL, FetchPolicy())
    assert result == BlockedPage(url=EVENT_URL, status_code=403, reason="cf-mitigated:challenge")
    # Feed resolution keeps its old contract: unusable means None.
    assert await fetch_document(EVENT_URL, FetchPolicy()) is None


async def test_fetch_document_still_returns_a_normal_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.discovery.http.fetch_url", mock_fetch_url(EVENT_200))
    doc = await fetch_document(EVENT_URL, FetchPolicy())
    assert doc is not None and doc.status_code == 200


async def test_blocked_seed_is_counted_blocked_not_failed_or_parsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.discovery.http.fetch_url", mock_fetch_url(CHALLENGE_403))

    def no_extraction(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a bot-check page must never reach extraction")

    monkeypatch.setattr(runner, "parse_document", no_extraction)
    summary = runner.DiscoverySummary()
    seed = SeedCandidate(
        url=EVENT_URL,
        connector_type="official_site",
        trust_tier="tier_2",
        module="hackathon",
        source_id=uuid4(),
    )

    await runner._process_candidate(
        None,  # type: ignore[arg-type]  # never reached for a blocked page
        None,  # type: ignore[arg-type]
        seed,
        settings=Settings(_env_file=None, app_env="test", llm_provider="disabled"),  # type: ignore[call-arg]
        policy=FetchPolicy(),
        now=NOW,
        summary=summary,
    )

    assert summary.blocked == 1
    assert summary.failed == 0
    assert summary.fetched == 0
    assert summary.as_meta()["blocked"] == 1
