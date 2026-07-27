"""Dispatch submission review jobs to Celery after the API commit succeeds."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol
from uuid import UUID

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

TASK_NAME = "ingestion.fetch_submission"
QUEUE_NAME = "fetch"
IDEM_PREFIX = "devradar:job:idempotency:"


class SubmissionEnqueuePort(Protocol):
    async def enqueue_fetch_submission(
        self,
        submission_id: UUID,
        job_idempotency_key: str,
        canonical_url: str,
    ) -> bool:
        """Return True if newly enqueued, False if idempotent duplicate."""
        ...


class CelerySubmissionEnqueue:
    """Send a real Celery message while retaining a short idempotency lease."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    async def enqueue_fetch_submission(
        self,
        submission_id: UUID,
        job_idempotency_key: str,
        canonical_url: str,
    ) -> bool:
        del canonical_url  # The worker reloads authoritative data from PostgreSQL.
        r = aioredis.from_url(self._redis_url, decode_responses=True)
        try:
            idem_key = f"{IDEM_PREFIX}{job_idempotency_key}"
            # 48h window — matches dual 24h buckets around a boundary.
            created = await r.set(idem_key, str(submission_id), nx=True, ex=48 * 3600)
            if not created:
                logger.info(
                    "submission_job_idempotent_skip",
                    extra={"job_key": job_idempotency_key},
                )
                return False
            def _send() -> None:
                from app.worker.celery_app import celery_app

                celery_app.send_task(
                    TASK_NAME,
                    args=[str(submission_id)],
                    task_id=job_idempotency_key,
                    queue=QUEUE_NAME,
                )

            try:
                await asyncio.to_thread(_send)
            except Exception as exc:
                # A failed broker send must not strand the idempotency lease.
                await r.delete(idem_key)
                logger.warning(
                    "submission_enqueue_failed",
                    extra={
                        "submission_id": str(submission_id),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
                return False
            return True
        finally:
            aclose = getattr(r, "aclose", None)
            if aclose is not None:
                await aclose()
            else:
                await r.close()


class InMemorySubmissionEnqueue:
    """Test double that records enqueue calls."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self._seen: set[str] = set()

    async def enqueue_fetch_submission(
        self,
        submission_id: UUID,
        job_idempotency_key: str,
        canonical_url: str,
    ) -> bool:
        if job_idempotency_key in self._seen:
            return False
        self._seen.add(job_idempotency_key)
        self.calls.append(
            {
                "submission_id": str(submission_id),
                "idempotency_key": job_idempotency_key,
                "canonical_url": canonical_url,
            }
        )
        return True
