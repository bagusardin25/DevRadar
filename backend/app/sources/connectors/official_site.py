"""Official site connector — discovers seed URLs from query config."""

from __future__ import annotations

from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
    FetchRequest,
)


class OfficialSiteConnector:
    name = "official_site"
    connector_type = "official_site"

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        urls = list(query.config.get("seed_urls") or [])
        start = int(cursor or 0)
        cap = query.result_cap
        page = urls[start : start + cap]
        items = [
            DiscoveryCandidate(
                external_id=url,
                url=url,
                title=None,
                metadata={"source": "official_site"},
            )
            for url in page
        ]
        nxt = str(start + cap) if start + cap < len(urls) else None
        return DiscoveryPage(items=items, next_cursor=nxt)

    async def fetch_detail(self, candidate: DiscoveryCandidate) -> FetchRequest:
        return FetchRequest(url=candidate.url, metadata={"connector": self.name})
