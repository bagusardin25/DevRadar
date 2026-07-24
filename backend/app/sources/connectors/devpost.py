"""Devpost directory connector (fixture-driven offline; live optional)."""

from __future__ import annotations

from typing import Any

from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
    FetchRequest,
)


class DevpostConnector:
    name = "devpost"
    connector_type = "devpost"

    def __init__(self, fixtures: list[dict[str, Any]] | None = None) -> None:
        self._fixtures = fixtures or []

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        start = int(cursor or 0)
        cap = query.result_cap
        filtered = [
            f
            for f in self._fixtures
            if not query.query_text
            or query.query_text.lower() in (f.get("title") or "").lower()
        ]
        page = filtered[start : start + cap]
        items = [
            DiscoveryCandidate(
                external_id=str(f.get("id") or f["url"]),
                url=f["url"],
                title=f.get("title"),
                metadata={"source": "devpost"},
            )
            for f in page
        ]
        next_cursor = str(start + cap) if start + cap < len(filtered) else None
        return DiscoveryPage(items=items, next_cursor=next_cursor)

    async def fetch_detail(self, candidate: DiscoveryCandidate) -> FetchRequest:
        return FetchRequest(url=candidate.url, metadata={"connector": self.name})
