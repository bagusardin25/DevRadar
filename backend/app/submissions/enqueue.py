"""Enqueue submission fetch jobs after DB commit (worker-ready contract)."""

from __future__ import annotations

import json
import logging
from typing import Protocol
from uuid import UUID

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

QUEUE_NAME = "devradar:queue:fetch"
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


class RedisSubmissionEnqueue:
    """Push fetch jobs to Redis; workers (Task 6+) consume them."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    async def enqueue_fetch_submission(
        self,
        submission_id: UUID,
        job_idempotency_key: str,
        canonical_url: str,
    ) -> bool:
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
            payload = {
                "task": "ingestion.fetch_submission",
                "submission_id": str(submission_id),
                "idempotency_key": job_idempotency_key,
                "canonical_url": canonical_url,
            }
            await r.lpush(QUEUE_NAME, json.dumps(payload))
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
