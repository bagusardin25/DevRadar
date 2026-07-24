"""HackerEarth challenges connector (fixture-driven)."""

from __future__ import annotations

from typing import Any

from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
    FetchRequest,
)


class HackerEarthConnector:
    name = "hackerearth"
    connector_type = "hackerearth"

    def __init__(self, fixtures: list[dict[str, Any]] | None = None) -> None:
        self._fixtures = fixtures or []

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        start = int(cursor or 0)
        cap = min(query.result_cap, query.config.get("hard_cap", 50))
        page = self._fixtures[start : start + cap]
        items = [
            DiscoveryCandidate(
                external_id=str(f.get("id") or f["url"]),
                url=f["url"],
                title=f.get("title"),
                metadata={"source": "hackerearth"},
            )
            for f in page
        ]
        nxt = str(start + cap) if start + cap < len(self._fixtures) else None
        return DiscoveryPage(items=items, next_cursor=nxt)

    async def fetch_detail(self, candidate: DiscoveryCandidate) -> FetchRequest:
        return FetchRequest(url=candidate.url, metadata={"connector": self.name})
