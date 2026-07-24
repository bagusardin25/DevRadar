"""X (Twitter) recent-search connector — Tier 3 discovery only.

Does not retain canonical post text. Stores only: post id/url, author,
created_at, discovered URLs, extracted info JSON, verification status, last check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
    FetchRequest,
)

MAX_RESULTS_PER_PAGE = 20
MAX_PAGES = 3
LOOKBACK_DAYS = 7


@dataclass(slots=True)
class XPostHit:
    post_id: str
    post_url: str
    author: str
    created_at: datetime
    discovered_urls: list[str] = field(default_factory=list)
    # Explicitly no post text field.


class XApiClient(Protocol):
    async def recent_search(
        self,
        query: str,
        *,
        max_results: int,
        next_token: str | None,
        start_time: datetime | None,
    ) -> dict[str, Any]: ...


class FakeXApiClient:
    """Offline test double."""

    def __init__(self, pages: list[dict[str, Any]] | None = None) -> None:
        self.pages = pages or []
        self.calls: list[dict[str, Any]] = []

    async def recent_search(
        self,
        query: str,
        *,
        max_results: int,
        next_token: str | None,
        start_time: datetime | None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "query": query,
                "max_results": max_results,
                "next_token": next_token,
                "start_time": start_time.isoformat() if start_time else None,
            }
        )
        idx = int(next_token or 0)
        if idx >= len(self.pages):
            return {"data": [], "meta": {}}
        page = self.pages[idx]
        meta = dict(page.get("meta") or {})
        if idx + 1 < len(self.pages):
            meta["next_token"] = str(idx + 1)
        return {"data": page.get("data") or [], "meta": meta, "includes": page.get("includes")}


def build_x_query(
    base: str,
    *,
    curated_accounts: list[str] | None = None,
    exclude_retweets: bool = True,
) -> str:
    parts = [base.strip()]
    if exclude_retweets and "-is:retweet" not in base:
        parts.append("-is:retweet")
    if curated_accounts:
        acc = " OR ".join(f"from:{a.lstrip('@')}" for a in curated_accounts)
        parts.append(f"({acc})")
    return " ".join(p for p in parts if p)


class XRecentSearchConnector:
    name = "x_recent_search"
    connector_type = "x_recent_search"

    def __init__(
        self,
        client: XApiClient,
        *,
        cost_per_post: float = 0.005,
        budget: float = 1.0,
    ) -> None:
        self._client = client
        self.cost_per_post = cost_per_post
        self.budget = budget
        self.cost_spent = 0.0

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        if self.cost_spent >= self.budget:
            return DiscoveryPage(items=[], next_cursor=None)

        accounts = list(query.config.get("curated_accounts") or [])
        base_q = query.query_text or query.config.get("query") or ""
        q = build_x_query(base_q, curated_accounts=accounts)
        start_time = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)
        max_results = min(query.result_cap, MAX_RESULTS_PER_PAGE)

        raw = await self._client.recent_search(
            q,
            max_results=max_results,
            next_token=cursor,
            start_time=start_time,
        )
        data = raw.get("data") or []
        self.cost_spent += len(data) * self.cost_per_post

        items: list[DiscoveryCandidate] = []
        for post in data:
            post_id = str(post.get("id") or "")
            author = str(post.get("author_id") or post.get("username") or "")
            created = post.get("created_at")
            if isinstance(created, str):
                try:
                    created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except ValueError:
                    created_at = datetime.now(UTC)
            else:
                created_at = datetime.now(UTC)
            urls = list(post.get("discovered_urls") or [])
            # Drop post text intentionally even if the API returned it.
            items.append(
                DiscoveryCandidate(
                    external_id=post_id,
                    url=f"https://x.com/i/web/status/{post_id}",
                    title=None,
                    metadata={
                        "author": author,
                        "created_at": created_at.isoformat(),
                        "discovered_urls": urls,
                        # no "text" key
                    },
                )
            )

        next_token = (raw.get("meta") or {}).get("next_token")
        page_idx = int(cursor or 0)
        if page_idx + 1 >= MAX_PAGES:
            next_token = None
        return DiscoveryPage(items=items, next_cursor=str(next_token) if next_token else None)

    async def fetch_detail(self, candidate: DiscoveryCandidate) -> FetchRequest:
        # Prefer first discovered external URL as Tier 1/2 fetch target
        urls = list(candidate.metadata.get("discovered_urls") or [])
        target = urls[0] if urls else candidate.url
        return FetchRequest(
            url=target,
            metadata={
                "connector": self.name,
                "post_id": candidate.external_id,
                "author": candidate.metadata.get("author"),
            },
        )

    def to_persistable(self, candidate: DiscoveryCandidate) -> dict[str, Any]:
        """Shape stored on discovery_signals — no post text."""
        return {
            "external_id": candidate.external_id,
            "url": candidate.url,
            "author": candidate.metadata.get("author"),
            "signal_created_at": candidate.metadata.get("created_at"),
            "discovered_urls": list(candidate.metadata.get("discovered_urls") or []),
            "extracted_information": {},
            "review_state": "needs_review",
        }
