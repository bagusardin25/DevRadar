"""X recent-search connector tests (fake API only)."""

from __future__ import annotations

import pytest

from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.x_recent_search import (
    FakeXApiClient,
    XRecentSearchConnector,
    build_x_query,
)


class TestXQuery:
    def test_adds_retweet_filter_and_accounts(self) -> None:
        q = build_x_query("hackathon AI", curated_accounts=["@OpenAI", "AnthropicAI"])
        assert "-is:retweet" in q
        assert "from:OpenAI" in q
        assert "from:AnthropicAI" in q


class TestXConnector:
    @pytest.mark.asyncio
    async def test_discover_no_post_text_retained(self) -> None:
        client = FakeXApiClient(
            pages=[
                {
                    "data": [
                        {
                            "id": "111",
                            "author_id": "user1",
                            "created_at": "2026-07-20T10:00:00Z",
                            "text": "SHOULD NOT BE STORED",
                            "discovered_urls": ["https://official.example/hack"],
                        }
                    ],
                    "meta": {},
                }
            ]
        )
        conn = XRecentSearchConnector(client, budget=1.0)
        page = await conn.discover(
            ConnectorQuery(module="hackathon", query_text="hackathon", result_cap=10)
        )
        assert len(page.items) == 1
        item = page.items[0]
        assert "text" not in item.metadata
        persist = conn.to_persistable(item)
        assert "text" not in persist
        assert persist["discovered_urls"] == ["https://official.example/hack"]
        assert client.calls[0]["query"]
        assert "-is:retweet" in client.calls[0]["query"]
        # seven-day bound
        assert client.calls[0]["start_time"] is not None

    @pytest.mark.asyncio
    async def test_budget_cap(self) -> None:
        client = FakeXApiClient(
            pages=[{"data": [{"id": str(i), "discovered_urls": []} for i in range(5)], "meta": {}}]
        )
        conn = XRecentSearchConnector(client, cost_per_post=0.5, budget=0.6)
        q = ConnectorQuery(module="hackathon", query_text="x", result_cap=5)
        page1 = await conn.discover(q)
        assert page1.items  # first call spends
        page2 = await conn.discover(q)
        assert page2.items == []  # budget exhausted

    @pytest.mark.asyncio
    async def test_fetch_detail_prefers_discovered_url(self) -> None:
        client = FakeXApiClient()
        conn = XRecentSearchConnector(client)
        from app.sources.connectors.base import DiscoveryCandidate

        cand = DiscoveryCandidate(
            external_id="9",
            url="https://x.com/i/web/status/9",
            metadata={"discovered_urls": ["https://tier1.example/page"]},
        )
        fr = await conn.fetch_detail(cand)
        assert fr.url == "https://tier1.example/page"
