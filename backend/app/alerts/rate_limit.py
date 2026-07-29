"""Abuse limits for anonymous alert confirmation emails."""

from __future__ import annotations

import time

from app.errors import RateLimitError

CLIENT_LIMIT = 10
EMAIL_LIMIT = 3
WINDOW_SECONDS = 3600


class AlertSignupRateLimiter:
    """Bound confirmation sends per trusted client and HMACed email address."""

    def __init__(
        self,
        redis_url: str,
        *,
        rate_limit_store: dict[str, list[float]] | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._rate_limit_store = rate_limit_store

    async def enforce(self, client_hash: str, email_hash: str) -> None:
        limits = (
            (
                f"client:{client_hash}",
                CLIENT_LIMIT,
                "Too many alert requests from this client",
            ),
            (
                f"email:{email_hash}",
                EMAIL_LIMIT,
                "Too many alert requests for this email",
            ),
        )
        if self._rate_limit_store is not None:
            for key, limit, detail in limits:
                self._consume_local(key, limit, detail)
            return

        import redis.asyncio as aioredis

        redis = aioredis.from_url(self._redis_url, decode_responses=True)
        try:
            for bucket, limit, detail in limits:
                key = f"devradar:rl:alerts:{bucket}"
                count = await redis.incr(key)
                if count == 1:
                    await redis.expire(key, WINDOW_SECONDS)
                if count > limit:
                    raise RateLimitError(detail=detail, retry_after=WINDOW_SECONDS)
        finally:
            aclose = getattr(redis, "aclose", None)
            if aclose is not None:
                await aclose()
            else:
                await redis.close()

    def _consume_local(self, key: str, limit: int, detail: str) -> None:
        assert self._rate_limit_store is not None
        now = time.time()
        bucket = self._rate_limit_store.setdefault(key, [])
        bucket[:] = [timestamp for timestamp in bucket if now - timestamp < WINDOW_SECONDS]
        if len(bucket) >= limit:
            raise RateLimitError(detail=detail, retry_after=WINDOW_SECONDS)
        bucket.append(now)
