"""Celery tasks for alert scanning and outbound webhooks."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.alerts.service import AlertService
from app.alerts.webhook import deliver_webhook
from app.catalog.models import Listing
from app.config import get_settings
from app.db import create_engine, create_session_maker
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _scan(
    *,
    lookback_hours: int,
    limit_listings: int,
) -> dict[str, Any]:
    settings = get_settings()
    engine = create_engine(settings)
    session_maker = create_session_maker(engine)
    try:
        async with session_maker() as session:
            svc = AlertService(session, settings)
            summary = await svc.scan_and_deliver(
                lookback_hours=lookback_hours,
                limit_listings=limit_listings,
                send_webhooks=True,
            )
            await session.commit()
            return summary
    finally:
        await engine.dispose()


async def _webhook_listing(listing_id: str) -> dict[str, Any]:
    settings = get_settings()
    if not (settings.webhook_url or "").strip():
        return {"skipped": True, "reason": "webhook_url_empty"}
    engine = create_engine(settings)
    session_maker = create_session_maker(engine)
    try:
        async with session_maker() as session:
            result = await session.execute(
                select(Listing)
                .where(Listing.id == UUID(listing_id))
                .options(
                    selectinload(Listing.hackathon),
                    selectinload(Listing.ai_offer),
                )
            )
            listing = result.scalar_one_or_none()
            if listing is None:
                return {"skipped": True, "reason": "listing_not_found"}
            return await deliver_webhook(settings, listing, event="listing.match")
    finally:
        await engine.dispose()


@celery_app.task(name="alerts.scan_matches")  # type: ignore[untyped-decorator]
def scan_matches(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Scheduled scan: match new listings to confirmed alert subscriptions."""
    payload = payload or {}
    lookback = int(payload.get("lookback_hours") or 48)
    limit = int(payload.get("limit_listings") or 100)
    result = _run(_scan(lookback_hours=lookback, limit_listings=limit))
    logger.info("alerts_scan_matches", extra=result)
    return {"ok": True, **result, "payload": payload}


@celery_app.task(name="alerts.deliver_webhook")  # type: ignore[untyped-decorator]
def deliver_webhook_task(listing_id: str) -> dict[str, Any]:
    """Fire operator webhook for a single listing id."""
    result = _run(_webhook_listing(listing_id))
    logger.info("alerts_deliver_webhook", extra=result)
    return result
