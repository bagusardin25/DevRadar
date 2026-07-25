"""End-to-end live discovery run with the network stubbed out."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import ConnectorType
from app.config import Settings
from app.discovery import runner as runner_module
from app.discovery.models import LiveDiscoveryRun
from app.discovery.runner import (
    STATUS_COMPLETED,
    DiscoverySummary,
    _error_summary,
    execute_discovery_run,
)
from tests.discovery.conftest import add_source, make_document


async def make_run(
    session: AsyncSession,
    *,
    connectors: list[str],
    query: str = "hackathon",
    cap: int = 5,
) -> LiveDiscoveryRun:
    run = LiveDiscoveryRun(
        query=query,
        status="queued",
        connector_types=connectors,
        result_cap=cap,
        request_hash=uuid4().hex,
        ip_hash="test-ip-hash",
        verified_listing_ids=[],
        meta_json={"opt_in": True},
    )
    session.add(run)
    await session.flush()
    return run


class TestExecuteDiscoveryRun:
    async def test_fetches_seed_url_and_completes(
        self, session: AsyncSession, settings: Settings, monkeypatch
    ) -> None:
        await add_source(
            session,
            connector_type=ConnectorType.OFFICIAL_SITE,
            query_config={"seed_urls": ["https://example.com/ai-builders"]},
        )
        fetched: list[str] = []

        async def fake_fetch(url: str, policy):
            fetched.append(url)
            return make_document(url)

        monkeypatch.setattr(runner_module, "fetch_document", fake_fetch)
        run = await make_run(session, connectors=["official_site"], cap=1)
        summary = await execute_discovery_run(session, run, settings=settings)

        assert "https://example.com/ai-builders" in fetched
        assert run.status == STATUS_COMPLETED
        assert run.started_at is not None
        assert run.finished_at is not None
        assert summary.candidates == 1
        assert summary.fetched == 1
        assert summary.cost_units == 1
        # Every fetched candidate lands somewhere: published or queued for review.
        assert summary.published + summary.needs_review == 1
        assert run.meta_json["fetched"] == 1

    async def test_dead_link_is_counted_not_fatal(
        self, session: AsyncSession, settings: Settings, monkeypatch
    ) -> None:
        await add_source(
            session,
            connector_type=ConnectorType.OFFICIAL_SITE,
            query_config={"seed_urls": ["https://example.com/dead"]},
        )

        async def fake_fetch(url: str, policy):
            return None

        monkeypatch.setattr(runner_module, "fetch_document", fake_fetch)
        run = await make_run(session, connectors=["official_site"], cap=1)
        summary = await execute_discovery_run(session, run, settings=settings)

        assert run.status == STATUS_COMPLETED
        assert summary.fetched == 0
        assert summary.failed == 1
        assert summary.cost_units == 1

    async def test_unsupported_connector_explains_empty_result(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        run = await make_run(session, connectors=["devpost", "mlh"])
        summary = await execute_discovery_run(session, run, settings=settings)

        assert run.status == STATUS_COMPLETED
        assert summary.candidates == 0
        assert run.verified_listing_ids == []
        assert run.error_summary is not None
        assert "devpost" in run.error_summary

    async def test_rerunning_same_url_does_not_duplicate(
        self, session: AsyncSession, settings: Settings, monkeypatch
    ) -> None:
        await add_source(
            session,
            connector_type=ConnectorType.OFFICIAL_SITE,
            query_config={"seed_urls": ["https://example.com/repeat-me"]},
        )

        async def fake_fetch(url: str, policy):
            return make_document(url)

        monkeypatch.setattr(runner_module, "fetch_document", fake_fetch)

        first_run = await make_run(session, connectors=["official_site"], cap=1)
        first = await execute_discovery_run(session, first_run, settings=settings)
        second_run = await make_run(session, connectors=["official_site"], cap=1)
        second = await execute_discovery_run(session, second_run, settings=settings)

        assert first.candidates == 1
        assert second.candidates == 1
        # Same URL → same idempotency key → the second pass reuses the first result.
        assert second.verified_listing_ids == first.verified_listing_ids


class TestErrorSummary:
    def test_silent_when_candidates_found(self) -> None:
        assert _error_summary(DiscoverySummary(candidates=3)) is None

    def test_names_the_missing_crawler(self) -> None:
        summary = DiscoverySummary(unsupported_connectors=["devpost"])
        assert "devpost" in (_error_summary(summary) or "")

    def test_reports_failed_feeds(self) -> None:
        summary = DiscoverySummary(feeds_failed=["https://example.com/a"])
        assert "feed" in (_error_summary(summary) or "").lower()

    def test_reports_missing_configuration(self) -> None:
        assert "No discovery sources configured" in (
            _error_summary(DiscoverySummary()) or ""
        )
