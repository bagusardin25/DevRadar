"""Dispatch live discovery jobs to the Celery worker after DB commit."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol
from uuid import UUID

logger = logging.getLogger(__name__)

TASK_NAME = "discovery.run_live_discovery"


class DiscoveryEnqueuePort(Protocol):
    async def enqueue_discovery_run(self, run_id: UUID) -> bool:
        """Return True when the job reached the broker."""
        ...


class CeleryDiscoveryEnqueue:
    """Send the run to the `fetch` queue; never raise into the request path."""

    async def enqueue_discovery_run(self, run_id: UUID) -> bool:
        def _send() -> None:
            from app.worker.celery_app import celery_app

            celery_app.send_task(TASK_NAME, args=[str(run_id)], queue="fetch")

        try:
            await asyncio.to_thread(_send)
        except Exception as exc:
            # Broker down: the row stays `queued` and the API reports it honestly.
            logger.warning(
                "discovery_enqueue_failed",
                extra={"run_id": str(run_id), "error": f"{type(exc).__name__}: {exc}"},
            )
            return False
        return True


class InMemoryDiscoveryEnqueue:
    """Test double that records dispatched run ids."""

    def __init__(self, *, succeed: bool = True) -> None:
        self.calls: list[str] = []
        self._succeed = succeed

    async def enqueue_discovery_run(self, run_id: UUID) -> bool:
        self.calls.append(str(run_id))
        return self._succeed
