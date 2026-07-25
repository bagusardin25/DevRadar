"""Live discovery job service with rate limits and caching."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.constants import ALLOWED_MODULES, DEFAULT_MODULE
from app.discovery.enqueue import DiscoveryEnqueuePort
from app.discovery.models import LiveDiscoveryRun
from app.errors import RateLimitError, ValidationError
from app.submissions.security import hash_ip

logger = logging.getLogger(__name__)

MIN_QUERY_LEN = 2
MAX_RESULTS = 20
CACHE_WINDOW_SECONDS = 300
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 3600


@dataclass(slots=True)
class DiscoveryReceipt:
    id: UUID
    status: str
    message: str


class LiveDiscoveryService:
    def __init__(
        self,
        session: AsyncSession,
        session_secret: str,
        *,
        redis_url: str | None = None,
        rate_limit_store: dict[str, list[float]] | None = None,
        enqueue: DiscoveryEnqueuePort | None = None,
    ) -> None:
        self._session = session
        self._secret = session_secret
        self._redis_url = redis_url
        # In-process fallback used by unit tests when Redis is not required.
        self._rate = rate_limit_store
        self._enqueue = enqueue

    def _register_after_commit(self, run_id: UUID) -> None:
        """Dispatch the worker job only once the run row is durable."""
        if self._enqueue is None:
            return
        enqueue = self._enqueue
        hooks: list[Any] = self._session.info.setdefault("after_commit_hooks", [])

        async def _hook() -> None:
            dispatched = await enqueue.enqueue_discovery_run(run_id)
            logger.info(
                "discovery_enqueued" if dispatched else "discovery_enqueue_unavailable",
                extra={"run_id": str(run_id)},
            )

        hooks.append(_hook)

    def _request_hash(
        self, query: str, connectors: list[str], cap: int, module: str
    ) -> str:
        material = (
            f"{query.strip().lower()}|{'|'.join(sorted(connectors))}|{cap}|{module}"
        )
        return hashlib.sha256(material.encode()).hexdigest()

    async def _enforce_rate_limit(self, ip_hash: str) -> None:
        """Cap live-discovery starts per client.

        Live discovery spends real budget (outbound fetches, optional paid
        APIs), so the counter lives in Redis: an in-process dict would reset on
        restart and give each worker its own quota.
        """
        if self._rate is not None:
            now = time.time()
            bucket = self._rate.setdefault(ip_hash, [])
            bucket[:] = [t for t in bucket if now - t < RATE_LIMIT_WINDOW]
            if len(bucket) >= RATE_LIMIT_MAX:
                raise RateLimitError(detail="Live discovery rate limit exceeded")
            bucket.append(now)
            return

        import redis.asyncio as aioredis

        r = aioredis.from_url(
            self._redis_url or "redis://localhost:6379/0", decode_responses=True
        )
        try:
            key = f"devradar:rl:discovery:{ip_hash}"
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, RATE_LIMIT_WINDOW)
            if count > RATE_LIMIT_MAX:
                raise RateLimitError(detail="Live discovery rate limit exceeded")
        finally:
            aclose = getattr(r, "aclose", None)
            if aclose is not None:
                await aclose()
            else:
                await r.close()

    async def start(
        self,
        *,
        query: str,
        ip_address: str,
        connectors: list[str] | None = None,
        result_cap: int = 10,
        module: str = DEFAULT_MODULE,
    ) -> DiscoveryReceipt:
        q = query.strip()
        if len(q) < MIN_QUERY_LEN:
            raise ValidationError(
                detail=f"Query must be at least {MIN_QUERY_LEN} characters",
                errors=[{"field": "query", "message": "too short"}],
            )
        cap = max(1, min(result_cap, MAX_RESULTS))
        connectors = connectors or ["official_site"]
        if len(connectors) > 3:
            raise ValidationError(detail="Too many connectors (max 3)")
        mod = module.strip().lower()
        if mod not in ALLOWED_MODULES:
            raise ValidationError(
                detail=f"Unknown module: {module}",
                errors=[{"field": "module", "message": "must be hackathon or ai_offer"}],
            )

        ip_h = hash_ip(ip_address, self._secret)
        await self._enforce_rate_limit(ip_h)

        req_hash = self._request_hash(q, connectors, cap, mod)
        # Cache identical requests
        cutoff = datetime.now(UTC)
        existing = await self._session.execute(
            select(LiveDiscoveryRun)
            .where(LiveDiscoveryRun.request_hash == req_hash)
            .order_by(LiveDiscoveryRun.created_at.desc())
            .limit(1)
        )
        prior = existing.scalar_one_or_none()
        if prior is not None and prior.created_at:
            age = (cutoff - prior.created_at).total_seconds()
            if age < CACHE_WINDOW_SECONDS and prior.status in {
                "queued",
                "running",
                "completed",
            }:
                return DiscoveryReceipt(
                    id=prior.id,
                    status=str(prior.status),
                    message="Returning cached discovery run",
                )

        run = LiveDiscoveryRun(
            query=q,
            status="queued",
            connector_types=connectors,
            result_cap=cap,
            request_hash=req_hash,
            ip_hash=ip_h,
            verified_listing_ids=[],
            meta_json={"opt_in": True, "module": mod},
        )
        self._session.add(run)
        await self._session.flush()
        self._register_after_commit(run.id)
        return DiscoveryReceipt(
            id=run.id,
            status="queued",
            message="Live discovery queued",
        )

    async def get(self, run_id: UUID) -> LiveDiscoveryRun:
        result = await self._session.execute(
            select(LiveDiscoveryRun).where(LiveDiscoveryRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            from app.errors import NotFoundError

            raise NotFoundError(detail="Discovery run not found")
        return run
