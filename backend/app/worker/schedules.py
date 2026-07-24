"""Scheduler: lease due source_queries and enqueue crawl runs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import CrawlRunStatus, CrawlTrigger
from app.ingestion.models import CrawlRun
from app.sources.models import Source, SourceQuery


@dataclass(slots=True)
class EnqueueSummary:
    leased: int
    enqueued: int
    skipped_disabled: int
    skipped_budget: int
    crawl_run_ids: list[str]


def _window_key(query_id: str, window_start: datetime) -> str:
    material = f"schedule|{query_id}|{window_start.isoformat()}"
    return hashlib.sha256(material.encode()).hexdigest()


async def enqueue_due_source_queries(
    session: AsyncSession,
    now: datetime | None = None,
    *,
    lease_owner: str | None = None,
    lease_seconds: int = 120,
    per_run_cap: int = 50,
) -> EnqueueSummary:
    """Select due queries with a DB lease so only one scheduler enqueues them."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    owner = lease_owner or f"scheduler-{uuid4().hex[:8]}"
    lease_until = now + timedelta(seconds=lease_seconds)

    result = await session.execute(
        select(SourceQuery, Source)
        .join(Source, Source.id == SourceQuery.source_id)
        .where(
            SourceQuery.enabled.is_(True),
            Source.enabled.is_(True),
            or_(
                SourceQuery.next_run_at.is_(None),
                SourceQuery.next_run_at <= now,
            ),
            or_(
                SourceQuery.lease_expires_at.is_(None),
                SourceQuery.lease_expires_at < now,
            ),
        )
        .order_by(SourceQuery.next_run_at.nullsfirst())
        .limit(per_run_cap)
    )
    rows = list(result.all())

    summary = EnqueueSummary(
        leased=0,
        enqueued=0,
        skipped_disabled=0,
        skipped_budget=0,
        crawl_run_ids=[],
    )

    for query, source in rows:
        if not source.enabled or not query.enabled:
            summary.skipped_disabled += 1
            continue
        if query.cost_budget <= 0:
            summary.skipped_budget += 1
            continue

        # Take lease
        query.lease_owner = owner
        query.lease_expires_at = lease_until
        summary.leased += 1

        interval = int((query.schedule or {}).get("interval_seconds", 86400))
        window_start = now.replace(minute=0, second=0, microsecond=0)
        idem = _window_key(str(query.id), window_start)

        # Skip if crawl already exists for this window
        existing = await session.execute(
            select(CrawlRun).where(CrawlRun.idempotency_key == idem)
        )
        if existing.scalar_one_or_none() is not None:
            query.next_run_at = now + timedelta(seconds=interval)
            query.lease_owner = None
            query.lease_expires_at = None
            continue

        run = CrawlRun(
            source_id=source.id,
            source_query_id=query.id,
            trigger=CrawlTrigger.SCHEDULE,
            status=CrawlRunStatus.QUEUED,
            idempotency_key=idem,
            started_at=None,
            cost_units=0,
        )
        session.add(run)
        await session.flush()

        query.last_run_at = now
        query.next_run_at = now + timedelta(seconds=interval)
        query.lease_owner = None
        query.lease_expires_at = None
        summary.enqueued += 1
        summary.crawl_run_ids.append(str(run.id))

    await session.flush()
    return summary
