"""Shared fixtures for live discovery tests (no network, no broker)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import ConnectorType, SourceTier
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.ingestion.fetcher import FetchedDocument
from app.sources.models import Source, SourceQuery

HACKATHON_HTML = b"""<html><head><title>AI Builders Hackathon 2026</title></head>
<body>
  <h1>AI Builders Hackathon 2026</h1>
  <p>Organizer: DevRadar Labs</p>
  <p>Registration deadline: 2026-09-01</p>
  <p>Submission deadline: 2026-09-15</p>
  <p>Prize pool: $10,000 USD</p>
  <p>An online hackathon open to developers worldwide.</p>
</body></html>"""

FEED_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Example hackathons</title>
  <item>
    <title>AI Builders Hackathon 2026</title>
    <link>https://example.com/hackathons/ai-builders</link>
    <guid>ai-builders</guid>
  </item>
  <item>
    <title>Robotics Sprint 2026</title>
    <link>https://example.com/hackathons/robotics-sprint</link>
    <guid>robotics-sprint</guid>
  </item>
</channel></rss>"""


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        session_secret="test-session-secret-at-least-32-chars!!",
    )


@pytest.fixture
async def session(settings: Settings) -> AsyncIterator[AsyncSession]:
    engine = create_engine(settings)
    maker = create_session_maker(engine)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


def make_document(url: str, body: bytes = HACKATHON_HTML) -> FetchedDocument:
    return FetchedDocument(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
    )


async def add_source(
    session: AsyncSession,
    *,
    connector_type: ConnectorType,
    query_config: dict,
    module: str = "hackathon",
    base_url: str | None = None,
    trust_tier: SourceTier = SourceTier.TIER_2,
    enabled: bool = True,
) -> Source:
    source = Source(
        name=f"src-{uuid4().hex[:8]}",
        connector_type=connector_type,
        trust_tier=trust_tier,
        base_url=base_url,
        enabled=enabled,
    )
    session.add(source)
    await session.flush()
    session.add(
        SourceQuery(
            source_id=source.id,
            module=module,
            name="default",
            query_config=query_config,
            schedule={"interval_seconds": 3600},
            result_cap=20,
            enabled=True,
        )
    )
    await session.flush()
    return source
