"""Scheduled online hackathon harvest — queue only, never publishes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # noqa: F401
from app.catalog.enums import ReviewCandidateType, ReviewItemState, VerificationStatus
from app.catalog.models import Listing
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.harvest.runner import run_online_hackathon_harvest
from app.ingestion.fetcher import FetchedDocument
from app.review.models import ReviewItem
from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.devpost import DevpostConnector
from tests.factories import seed_hackathon

NOW = datetime(2026, 8, 14, 8, 15, tzinfo=UTC)

ONLINE_HTML = b"""<html><head><title>Online Agents Hack 2026</title></head>
<body>
  <h1>Online Agents Hack 2026</h1>
  <p>Organizer: Example Labs</p>
  <p>This event is fully online and open worldwide.</p>
  <p>Submission deadline 2026-09-30T23:59:00Z.</p>
  <p>Prize pool $12,000 USD.</p>
</body></html>"""

IN_PERSON_HTML = b"""<html><head><title>SF Hardware Summit 2026</title></head>
<body>
  <h1>SF Hardware Summit 2026</h1>
  <p>In-person only at the San Francisco Convention Center.</p>
  <p>Submission deadline 2026-09-30T23:59:00Z.</p>
</body></html>"""


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_engine(Settings(_env_file=None))  # type: ignore[arg-type]
    maker = create_session_maker(engine)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


def _settings(**overrides: object) -> Settings:
    data: dict[str, object] = {
        "app_env": "test",
        "harvest_enabled": True,
        "harvest_devpost_cap": 10,
        "llm_provider": "disabled",
        "session_secret": "test-session-secret-at-least-32-chars!!",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)  # type: ignore[arg-type]


def _doc(url: str, body: bytes) -> FetchedDocument:
    return FetchedDocument(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        body=body,
    )


def _connector() -> DevpostConnector:
    return DevpostConnector(
        fixtures=[
            {
                "id": "101",
                "url": "https://online-agents.devpost.com/",
                "title": "Online Agents Hack 2026",
                "displayed_location": {"icon": "globe", "location": "Online"},
                "organization_name": "Example Labs",
                "prize_amount": '$<span data-currency-value>12000</span>',
                "themes": [{"name": "AI"}],
            },
            {
                "id": "202",
                "url": "https://sf-hardware.devpost.com/",
                "title": "SF Hardware Summit 2026",
                "displayed_location": {"icon": "map-marker", "location": "San Francisco, CA"},
            },
        ]
    )


class TestHarvestRunner:
    async def test_disabled_harvest_is_a_noop(self, session: AsyncSession) -> None:
        summary = await run_online_hackathon_harvest(
            session,
            _settings(harvest_enabled=False),
            now=NOW,
            connector=_connector(),
        )
        assert summary.queued == 0
        assert summary.discovered == 0

    async def test_queues_online_event_without_publishing(
        self, session: AsyncSession
    ) -> None:
        async def fake_fetch(url: str, policy):
            return _doc(url, ONLINE_HTML)

        summary = await run_online_hackathon_harvest(
            session,
            _settings(),
            cap=10,
            now=NOW,
            connector=_connector(),
            fetch_page=fake_fetch,
        )
        assert summary.discovered == 1  # in-person row filtered at discover
        assert summary.queued == 1
        assert summary.review_item_ids

        item = await session.get(ReviewItem, UUID(summary.review_item_ids[0]))
        assert item is not None
        assert item.candidate_type == ReviewCandidateType.LISTING
        assert str(item.state) == ReviewItemState.OPEN.value
        snap = item.candidate_snapshot
        assert snap["harvest"] is True
        assert snap["kind"] == "hackathon"
        assert snap["officialUrl"]
        assert "aiReview" in snap
        assert item.listing_id is None

        listings = list((await session.execute(select(Listing))).scalars().all())
        assert listings == []

    async def test_skips_url_already_in_catalogue(self, session: AsyncSession) -> None:
        listing = await seed_hackathon(
            session,
            slug=f"dup-{uuid4().hex[:8]}",
            title="Already listed",
            status=VerificationStatus.VERIFIED_ACTIVE,
        )
        listing.hackathon.official_url = "https://online-agents.devpost.com/"
        await session.flush()

        async def fake_fetch(url: str, policy):
            return _doc(url, ONLINE_HTML)

        summary = await run_online_hackathon_harvest(
            session,
            _settings(),
            now=NOW,
            connector=_connector(),
            fetch_page=fake_fetch,
        )
        assert summary.queued == 0
        assert summary.skipped_duplicate == 1

    async def test_skips_when_official_page_is_in_person(
        self, session: AsyncSession
    ) -> None:
        connector = DevpostConnector(
            fixtures=[
                {
                    "id": "303",
                    "url": "https://sf-hardware.devpost.com/",
                    "title": "SF Hardware Summit 2026",
                    "displayed_location": {"icon": "globe", "location": "Online"},
                }
            ]
        )

        async def fake_fetch(url: str, policy):
            return _doc(url, IN_PERSON_HTML)

        summary = await run_online_hackathon_harvest(
            session,
            _settings(),
            now=NOW.replace(hour=16),
            connector=connector,
            fetch_page=fake_fetch,
        )
        assert summary.queued == 0
        assert summary.skipped_offline == 1

    async def test_same_window_does_not_run_twice(self, session: AsyncSession) -> None:
        async def fake_fetch(url: str, policy):
            return _doc(url, ONLINE_HTML)

        first = await run_online_hackathon_harvest(
            session,
            _settings(),
            now=NOW,
            connector=_connector(),
            fetch_page=fake_fetch,
        )
        second = await run_online_hackathon_harvest(
            session,
            _settings(),
            now=NOW.replace(minute=40),
            connector=_connector(),
            fetch_page=fake_fetch,
        )
        assert first.queued == 1
        assert second.queued == 0
        assert second.crawl_run_id == first.crawl_run_id


class TestDevpostOnlineFilter:
    async def test_fixtures_drop_in_person_rows(self) -> None:
        page = await _connector().discover(ConnectorQuery(module="hackathon", result_cap=10))
        urls = {item.url for item in page.items}
        assert "https://online-agents.devpost.com/" in urls
        assert "https://sf-hardware.devpost.com/" not in urls

    async def test_live_directory_parses_api_payload(self) -> None:
        async def fake_get(_url: str) -> dict:
            return {
                "hackathons": [
                    {
                        "id": 1,
                        "title": "Online Only",
                        "url": "https://online.devpost.com/",
                        "displayed_location": {"icon": "globe", "location": "Online"},
                        "prize_amount": "$<span data-currency-value>5,000</span>",
                        "organization_name": "Org",
                        "themes": [{"name": "AI"}],
                    },
                    {
                        "id": 2,
                        "title": "NYC Onsite",
                        "url": "https://nyc.devpost.com/",
                        "displayed_location": {
                            "icon": "map-marker",
                            "location": "New York, NY",
                        },
                    },
                ],
                "meta": {"total_count": 2, "per_page": 20},
            }

        connector = DevpostConnector(http_get=fake_get)
        page = await connector.discover(ConnectorQuery(module="hackathon", result_cap=20))
        assert [item.title for item in page.items] == ["Online Only"]
        assert page.items[0].metadata["prize_value"] == 5000
        assert page.items[0].metadata["mode"] == "online"
