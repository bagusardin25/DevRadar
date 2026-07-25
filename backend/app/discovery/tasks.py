"""Celery task that executes queued live discovery runs."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

# Import the full model graph so SQLAlchemy relationships resolve in the worker.
import app.models  # noqa: F401
from app.config import get_settings
from app.db import create_engine, create_session_maker
from app.discovery.models import LiveDiscoveryRun
from app.discovery.runner import STATUS_QUEUED, execute_discovery_run
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _execute(run_id: str) -> dict[str, Any]:
    settings = get_settings()
    engine = create_engine(settings)
    session_maker = create_session_maker(engine)
    try:
        async with session_maker() as session:
            result = await session.execute(
                select(LiveDiscoveryRun).where(LiveDiscoveryRun.id == UUID(run_id))
            )
            run = result.scalar_one_or_none()
            if run is None:
                return {"ok": False, "reason": "run_not_found", "run_id": run_id}
            if str(run.status) != STATUS_QUEUED:
                # Already claimed by another worker, or replayed after completion.
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": f"status_{run.status}",
                    "run_id": run_id,
                }

            summary = await execute_discovery_run(session, run, settings=settings)
            await session.commit()
            return {
                "ok": True,
                "run_id": run_id,
                "status": str(run.status),
                "verified": len(summary.verified_listing_ids),
                **summary.as_meta(),
            }
    finally:
        await engine.dispose()


@celery_app.task(name="discovery.run_live_discovery")  # type: ignore[untyped-decorator]
def run_live_discovery(run_id: str) -> dict[str, Any]:
    """Fetch, verify and publish listings for one live discovery run."""
    result: dict[str, Any] = _run(_execute(run_id))
    logger.info("discovery_run_task", extra=result)
    return result
