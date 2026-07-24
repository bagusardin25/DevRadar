"""Scheduler lease + crawl run enqueue tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import ConnectorType, CrawlRunStatus, SourceTier
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.ingestion.models import CrawlRun
from app.sources.models import Source, SourceQuery
from app.worker.schedules import enqueue_due_source_queries

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_engine(Settings())
    maker = create_session_maker(engine)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


async def _seed_query(
    session: AsyncSession,
    *,
    enabled: bool = True,
    source_enabled: bool = True,
    budget: int = 100,
    next_run_at: datetime | None = None,
) -> SourceQuery:
    source = Source(
        name=f"src-{uuid4().hex[:8]}",
        connector_type=ConnectorType.DEVPOST,
        trust_tier=SourceTier.TIER_2,
        enabled=source_enabled,
    )
    session.add(source)
    await session.flush()
    q = SourceQuery(
        source_id=source.id,
        module="hackathon",
        name="default",
        enabled=enabled,
        cost_budget=budget,
        next_run_at=next_run_at,
        schedule={"interval_seconds": 3600},
        result_cap=20,
    )
    session.add(q)
    await session.flush()
    return q


class TestScheduler:
    @pytest.mark.asyncio
    async def test_enqueues_due_query(self, session: AsyncSession) -> None:
        await _seed_query(session, next_run_at=NOW - timedelta(minutes=1))
        summary = await enqueue_due_source_queries(session, now=NOW, lease_owner="s1")
        assert summary.enqueued == 1
        assert len(summary.crawl_run_ids) == 1
        runs = list((await session.execute(select(CrawlRun))).scalars().all())
        assert runs[0].status == CrawlRunStatus.QUEUED or str(runs[0].status) == "queued"

    @pytest.mark.asyncio
    async def test_skips_disabled(self, session: AsyncSession) -> None:
        await _seed_query(session, enabled=False, next_run_at=NOW - timedelta(hours=1))
        summary = await enqueue_due_source_queries(session, now=NOW)
        assert summary.enqueued == 0

    @pytest.mark.asyncio
    async def test_skips_zero_budget(self, session: AsyncSession) -> None:
        await _seed_query(session, budget=0, next_run_at=NOW - timedelta(hours=1))
        summary = await enqueue_due_source_queries(session, now=NOW)
        assert summary.skipped_budget >= 1
        assert summary.enqueued == 0

    @pytest.mark.asyncio
    async def test_idempotent_window(self, session: AsyncSession) -> None:
        await _seed_query(session, next_run_at=NOW - timedelta(minutes=5))
        s1 = await enqueue_due_source_queries(session, now=NOW, lease_owner="a")
        # Force due again
        q = (
            await session.execute(select(SourceQuery))
        ).scalars().first()
        assert q is not None
        q.next_run_at = NOW - timedelta(seconds=1)
        await session.flush()
        s2 = await enqueue_due_source_queries(session, now=NOW, lease_owner="b")
        # Same window → no second crawl with same key
        runs = list((await session.execute(select(CrawlRun))).scalars().all())
        assert s1.enqueued == 1
        assert len(runs) == 1
