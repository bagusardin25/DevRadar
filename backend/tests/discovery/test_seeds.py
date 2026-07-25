"""Seed resolution: which connectors can actually produce candidate URLs.

Assertions are scoped to the source each test creates, so the suite stays green
against a database that already has seeded discovery sources.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import ConnectorType
from app.config import Settings
from app.discovery import seeds as seeds_module
from app.discovery.http import build_fetch_policy
from app.discovery.seeds import SeedResolution, resolve_seed_candidates
from tests.discovery.conftest import FEED_XML, add_source, make_document


def urls_from(result: SeedResolution, source_id: UUID) -> list[str]:
    return [c.url for c in result.candidates if c.source_id == source_id]


class TestSeedResolution:
    async def test_official_site_seed_urls(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        source = await add_source(
            session,
            connector_type=ConnectorType.OFFICIAL_SITE,
            query_config={
                "seed_urls": [
                    "https://example.com/a",
                    "https://example.com/b",
                ]
            },
        )
        result = await resolve_seed_candidates(
            session,
            query_text="hackathon",
            connector_types=["official_site"],
            cap=50,
            policy=build_fetch_policy(settings),
        )
        assert urls_from(result, source.id) == [
            "https://example.com/a",
            "https://example.com/b",
        ]
        assert result.unsupported == []

    async def test_rss_inline_feed_needs_no_network(
        self, session: AsyncSession, settings: Settings, monkeypatch
    ) -> None:
        source = await add_source(
            session,
            connector_type=ConnectorType.RSS,
            query_config={"feed_xml": FEED_XML},
        )

        async def unreachable(url: str, policy):
            raise AssertionError(f"inline feed must not hit the network: {url}")

        monkeypatch.setattr(seeds_module, "fetch_document", unreachable)
        result = await resolve_seed_candidates(
            session,
            query_text="",
            connector_types=["rss"],
            cap=50,
            policy=build_fetch_policy(settings),
        )
        assert len(urls_from(result, source.id)) == 2

    async def test_rss_feed_url_is_fetched_live(
        self, session: AsyncSession, settings: Settings, monkeypatch
    ) -> None:
        source = await add_source(
            session,
            connector_type=ConnectorType.RSS,
            query_config={"feed_url": "https://example.com/feed.xml"},
        )
        requested: list[str] = []

        async def fake_fetch(url: str, policy):
            requested.append(url)
            return make_document(url, FEED_XML.encode())

        monkeypatch.setattr(seeds_module, "fetch_document", fake_fetch)
        result = await resolve_seed_candidates(
            session,
            query_text="",
            connector_types=["rss"],
            cap=50,
            policy=build_fetch_policy(settings),
        )
        assert "https://example.com/feed.xml" in requested
        assert result.fetches >= 1
        assert urls_from(result, source.id) == [
            "https://example.com/hackathons/ai-builders",
            "https://example.com/hackathons/robotics-sprint",
        ]

    async def test_failed_feed_is_reported_not_swallowed(
        self, session: AsyncSession, settings: Settings, monkeypatch
    ) -> None:
        source = await add_source(
            session,
            connector_type=ConnectorType.RSS,
            query_config={"feed_url": "https://example.com/dead.xml"},
        )

        async def fake_fetch(url: str, policy):
            return None

        monkeypatch.setattr(seeds_module, "fetch_document", fake_fetch)
        result = await resolve_seed_candidates(
            session,
            query_text="",
            connector_types=["rss"],
            cap=50,
            policy=build_fetch_policy(settings),
        )
        assert urls_from(result, source.id) == []
        assert "https://example.com/dead.xml" in result.feeds_failed

    async def test_query_text_filters_feed_items(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        source = await add_source(
            session,
            connector_type=ConnectorType.RSS,
            query_config={"feed_xml": FEED_XML},
        )
        result = await resolve_seed_candidates(
            session,
            query_text="robotics",
            connector_types=["rss"],
            cap=50,
            policy=build_fetch_policy(settings),
        )
        assert urls_from(result, source.id) == [
            "https://example.com/hackathons/robotics-sprint"
        ]

    async def test_module_scopes_the_sources(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        """A hackathon search must not crawl AI-offer sources."""
        hackathon = await add_source(
            session,
            connector_type=ConnectorType.OFFICIAL_SITE,
            query_config={"seed_urls": ["https://example.com/hack"]},
            module="hackathon",
        )
        offer = await add_source(
            session,
            connector_type=ConnectorType.OFFICIAL_SITE,
            query_config={"seed_urls": ["https://example.com/offer"]},
            module="ai_offer",
        )
        result = await resolve_seed_candidates(
            session,
            query_text="",
            connector_types=["official_site"],
            cap=50,
            policy=build_fetch_policy(settings),
            module="hackathon",
        )
        assert urls_from(result, hackathon.id) == ["https://example.com/hack"]
        assert urls_from(result, offer.id) == []

    async def test_stub_connectors_reported_as_unsupported(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        """devpost/mlh/hackerearth have no crawler — say so instead of returning []."""
        result = await resolve_seed_candidates(
            session,
            query_text="ai hackathon",
            connector_types=["devpost", "mlh", "hackerearth"],
            cap=10,
            policy=build_fetch_policy(settings),
        )
        assert result.candidates == []
        assert sorted(result.unsupported) == ["devpost", "hackerearth", "mlh"]

    async def test_cap_is_respected(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        await add_source(
            session,
            connector_type=ConnectorType.OFFICIAL_SITE,
            query_config={"seed_urls": [f"https://example.com/{i}" for i in range(10)]},
        )
        result = await resolve_seed_candidates(
            session,
            query_text="",
            connector_types=["official_site"],
            cap=3,
            policy=build_fetch_policy(settings),
        )
        assert len(result.candidates) == 3

    async def test_disabled_source_is_skipped(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        source = await add_source(
            session,
            connector_type=ConnectorType.OFFICIAL_SITE,
            query_config={"seed_urls": ["https://example.com/off"]},
            enabled=False,
        )
        result = await resolve_seed_candidates(
            session,
            query_text="",
            connector_types=["official_site"],
            cap=50,
            policy=build_fetch_policy(settings),
        )
        assert urls_from(result, source.id) == []
