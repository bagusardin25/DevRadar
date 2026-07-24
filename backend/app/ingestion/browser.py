"""Browser-fallback worker contract (Playwright runs in isolated container).

This module intentionally has no Playwright import so the API process and
unit tests stay free of browser dependencies. The browser worker container
should import a separate entrypoint that calls `run_browser_fetch`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.ingestion.fetcher import FetchedDocument, FetchPolicy, browser_fallback_eligible


@dataclass(slots=True)
class BrowserFetchRequest:
    url: str
    policy: FetchPolicy
    reason: str = "spa_shell"


class BrowserFetcher(Protocol):
    async def fetch(self, request: BrowserFetchRequest) -> FetchedDocument: ...


class BrowserFallbackDisabled:
    """Default implementation: browser fetch is not available in-process."""

    async def fetch(self, request: BrowserFetchRequest) -> FetchedDocument:
        raise RuntimeError(
            "Browser fetch is disabled in this process. "
            "Run the isolated browser worker instead."
        )


def should_use_browser(
    fetched: FetchedDocument | None,
    policy: FetchPolicy | None = None,
) -> bool:
    """Gate used by the pipeline before enqueueing a browser job."""
    return browser_fallback_eligible(fetched, policy=policy)


# Environment keys that MUST NOT be injected into the browser worker container.
BROWSER_WORKER_FORBIDDEN_ENV = frozenset(
    {
        "DATABASE_URL",
        "REDIS_URL",
        "SESSION_SECRET",
        "EMAIL_ENCRYPTION_KEY",
        "EMAIL_HMAC_KEY",
        "GITHUB_CLIENT_SECRET",
        "LLM_API_KEY",
        "X_BEARER_TOKEN",
        "OBJECT_STORAGE_SECRET_KEY",
    }
)
