"""Celery task for the 3× daily online hackathon harvest."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import app.models  # noqa: F401
from app.config import get_settings
from app.db import create_engine, create_session_maker
from app.harvest.runner import run_online_hackathon_harvest
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _execute(*, cap: int | None) -> dict[str, Any]:
    settings = get_settings()
    engine = create_engine(settings)
    session_maker = create_session_maker(engine)
    try:
        async with session_maker() as session:
            summary = await run_online_hackathon_harvest(
                session, settings, cap=cap
            )
            await session.commit()
            return {"ok": True, **summary.as_meta()}
    finally:
        await engine.dispose()


@celery_app.task(name="harvest.run_online_hackathons")  # type: ignore[untyped-decorator]
def run_online_hackathons(cap: int | None = None) -> dict[str, Any]:
    """Discover online hackathons (HARVEST_SOURCES) and queue them for admin review."""
    result: dict[str, Any] = _run(_execute(cap=cap))
    logger.info("harvest_task", extra=result)
    return result
