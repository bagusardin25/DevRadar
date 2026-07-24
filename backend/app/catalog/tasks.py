"""Celery tasks for catalogue maintenance."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.catalog.enums import ListingKind
from app.catalog.lifecycle import apply_lifecycle_transitions
from app.catalog.recheck import recheck_catalogue
from app.config import get_settings
from app.db import create_engine, create_session_maker
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sweep() -> dict[str, int]:
    settings = get_settings()
    engine = create_engine(settings)
    session_maker = create_session_maker(engine)
    try:
        async with session_maker() as session:
            summary = await apply_lifecycle_transitions(session)
            await session.commit()
            return {
                "scanned": summary.scanned,
                "closed": summary.closed,
                "expired": summary.expired,
                "unchanged": summary.unchanged,
            }
    finally:
        await engine.dispose()


async def _recheck(
    *,
    kind: str | None,
    limit: int,
    slugs: list[str] | None,
) -> dict[str, Any]:
    settings = get_settings()
    engine = create_engine(settings)
    session_maker = create_session_maker(engine)
    kind_enum: ListingKind | None
    if kind is None or kind == "all":
        kind_enum = None
    else:
        kind_enum = ListingKind(kind)
    try:
        async with session_maker() as session:
            summary = await recheck_catalogue(
                session,
                kind=kind_enum,
                limit=limit,
                only_slugs=slugs,
                settings=settings,
            )
            await session.commit()
            return {
                "scanned": summary.scanned,
                "ok": summary.ok,
                "failed": summary.failed,
                "skipped": summary.skipped,
                "results": [
                    {
                        "slug": r.slug,
                        "kind": r.kind,
                        "ok": r.ok,
                        "url": r.url,
                        "method": r.method,
                        "updated_fields": r.updated_fields,
                        "error": r.error,
                        "status_code": r.status_code,
                    }
                    for r in summary.results
                ],
            }
    finally:
        await engine.dispose()


@celery_app.task(name="catalog.lifecycle_sweep")  # type: ignore[untyped-decorator]
def lifecycle_sweep() -> dict[str, int]:
    """Expire / close listings past deadlines (safe to run on a schedule)."""
    result = _run(_sweep())
    logger.info("lifecycle_sweep", extra=result)
    return result


@celery_app.task(name="catalog.recheck_official_urls")  # type: ignore[untyped-decorator]
def recheck_official_urls(
    kind: str = "ai_offer",
    limit: int = 20,
    slugs: list[str] | None = None,
) -> dict[str, Any]:
    """Re-fetch official URLs and merge extracted fields (rules + optional LLM)."""
    result = _run(_recheck(kind=kind, limit=limit, slugs=slugs))
    logger.info(
        "recheck_official_urls",
        extra={
            "scanned": result.get("scanned"),
            "ok": result.get("ok"),
            "failed": result.get("failed"),
        },
    )
    return result
