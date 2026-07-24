"""Admin pipeline observability routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.dependencies import AdminUser, AdminUserRead, DbSession
from app.catalog.enums import CrawlRunStatus
from app.catalog.schemas import CamelModel
from app.errors import NotFoundError
from app.ingestion.models import CrawlRun

router = APIRouter(prefix="/admin/crawl-runs", tags=["Admin Pipeline"])


class CrawlRunPublic(CamelModel):
    id: UUID
    source_id: UUID
    status: str
    trigger: str
    discovered_count: int
    fetched_count: int
    failed_count: int
    error_summary: str | None = None
    idempotency_key: str | None = None


@router.get("")
async def list_crawl_runs(
    session: DbSession,
    _admin: AdminUserRead,
) -> dict[str, Any]:
    rows = list(
        (
            await session.execute(
                select(CrawlRun).order_by(CrawlRun.created_at.desc()).limit(100)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            CrawlRunPublic(
                id=r.id,
                source_id=r.source_id,
                status=str(r.status),
                trigger=str(r.trigger),
                discovered_count=r.discovered_count,
                fetched_count=r.fetched_count,
                failed_count=r.failed_count,
                error_summary=r.error_summary,
                idempotency_key=r.idempotency_key,
            )
            for r in rows
        ]
    }


@router.post("/{run_id}/retry")
async def retry_crawl_run(
    run_id: UUID,
    session: DbSession,
    _admin: AdminUser,
) -> CrawlRunPublic:
    result = await session.execute(select(CrawlRun).where(CrawlRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError(detail="Crawl run not found")
    # Idempotent retry: re-queue failed runs only once per key suffix
    if str(run.status) != CrawlRunStatus.FAILED.value and str(run.status) != "failed":
        # still allow re-queue from partial
        pass
    retry_key = f"{run.idempotency_key or run.id}:retry"
    existing = await session.execute(
        select(CrawlRun).where(CrawlRun.idempotency_key == retry_key)
    )
    prior = existing.scalar_one_or_none()
    if prior is not None:
        run = prior
    else:
        run.status = CrawlRunStatus.QUEUED
        run.error_summary = None
        run.idempotency_key = retry_key
        await session.flush()
    return CrawlRunPublic(
        id=run.id,
        source_id=run.source_id,
        status=str(run.status),
        trigger=str(run.trigger),
        discovered_count=run.discovered_count,
        fetched_count=run.fetched_count,
        failed_count=run.failed_count,
        error_summary=run.error_summary,
        idempotency_key=run.idempotency_key,
    )
