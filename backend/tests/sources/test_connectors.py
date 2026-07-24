"""Contract tests for connectors using fixtures only."""

from __future__ import annotations

import pytest

from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.devpost import DevpostConnector
from app.sources.connectors.hackerearth import HackerEarthConnector
from app.sources.connectors.mlh import MLHConnector
from app.sources.connectors.official_site import OfficialSiteConnector
from app.sources.connectors.rss import RSSConnector

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Feed</title>
<item><title>AI Hackathon</title><link>https://example.com/a</link><guid>a1</guid></item>
<item><title>Other Event</title><link>https://example.com/b</link><guid>b1</guid></item>
</channel></rss>
"""


@pytest.mark.asyncio
async def test_devpost_discover_and_detail() -> None:
    c = DevpostConnector(
        fixtures=[
            {"id": "1", "url": "https://devpost.com/1", "title": "Hack One"},
            {"id": "2", "url": "https://devpost.com/2", "title": "Hack Two"},
        ]
    )
    page = await c.discover(ConnectorQuery(module="hackathon", result_cap=1))
    assert len(page.items) == 1
    assert page.next_cursor == "1"
    detail = await c.fetch_detail(page.items[0])
    assert detail.url.startswith("https://")


@pytest.mark.asyncio
async def test_mlh_and_hackerearth() -> None:
    mlh = MLHConnector(fixtures=[{"url": "https://mlh.io/e1", "title": "E1", "mode": "online"}])
    he = HackerEarthConnector(fixtures=[{"url": "https://he.com/c1", "title": "C1"}])
    assert (await mlh.discover(ConnectorQuery(module="hackathon"))).items
    assert (await he.discover(ConnectorQuery(module="hackathon"))).items


@pytest.mark.asyncio
async def test_rss_and_official() -> None:
    rss = RSSConnector(feed_xml=SAMPLE_RSS)
    page = await rss.discover(ConnectorQuery(module="hackathon", query_text="AI"))
    assert len(page.items) == 1
    assert page.items[0].title == "AI Hackathon"

    off = OfficialSiteConnector()
    page2 = await off.discover(
        ConnectorQuery(
            module="ai_offer",
            config={"seed_urls": ["https://openai.com/pricing", "https://x.ai"]},
            result_cap=10,
        )
    )
    assert len(page2.items) == 2
