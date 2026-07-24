"""Live discovery job service with rate limits and caching."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.models import LiveDiscoveryRun
from app.errors import RateLimitError, ValidationError
from app.submissions.security import hash_ip

MIN_QUERY_LEN = 3
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
        rate_limit_store: dict[str, list[float]] | None = None,
    ) -> None:
        self._session = session
        self._secret = session_secret
        self._rate = rate_limit_store if rate_limit_store is not None else {}

    def _request_hash(self, query: str, connectors: list[str], cap: int) -> str:
        material = f"{query.strip().lower()}|{'|'.join(sorted(connectors))}|{cap}"
        return hashlib.sha256(material.encode()).hexdigest()

    async def start(
        self,
        *,
        query: str,
        ip_address: str,
        connectors: list[str] | None = None,
        result_cap: int = 10,
    ) -> DiscoveryReceipt:
        q = query.strip()
        if len(q) < MIN_QUERY_LEN:
            raise ValidationError(
                detail=f"Query must be at least {MIN_QUERY_LEN} characters",
                errors=[{"field": "query", "message": "too short"}],
            )
        cap = max(1, min(result_cap, MAX_RESULTS))
        connectors = connectors or ["devpost"]
        if len(connectors) > 3:
            raise ValidationError(detail="Too many connectors (max 3)")

        ip_h = hash_ip(ip_address, self._secret)
        now = time.time()
        bucket = self._rate.setdefault(ip_h, [])
        bucket[:] = [t for t in bucket if now - t < RATE_LIMIT_WINDOW]
        if len(bucket) >= RATE_LIMIT_MAX:
            raise RateLimitError(detail="Live discovery rate limit exceeded")
        bucket.append(now)

        req_hash = self._request_hash(q, connectors, cap)
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
            meta_json={"opt_in": True},
        )
        self._session.add(run)
        await self._session.flush()
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
