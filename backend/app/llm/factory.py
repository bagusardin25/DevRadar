"""Build the router from settings.

Kept separate from ``registry`` so ``app.config`` can import the parser without
pulling in httpx and the whole routing stack at module import time.
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.llm.registry import parse_provider_specs
from app.llm.router import LLMRouter

logger = logging.getLogger(__name__)


def build_router(settings: Settings) -> LLMRouter | None:
    """Return a configured router, or None when routing is off or unusable."""
    if not settings.llm_routing_enabled:
        return None

    specs = parse_provider_specs(settings.llm_providers_json)
    if not specs:
        # Already warned during settings validation; nothing routable here.
        return None

    logger.info(
        "llm_router_configured",
        extra={
            "providers": [spec.name for spec in specs],
            "strategy": settings.llm_routing_strategy,
        },
    )
    return LLMRouter(
        specs,
        redis_url=settings.redis_url,
        strategy=settings.llm_routing_strategy,
        deadline_seconds=settings.llm_deadline_seconds,
        max_attempts=settings.llm_max_attempts,
    )
