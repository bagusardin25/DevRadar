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
from app.ingestion.models import CrawlRun
from app.review.models import ReviewItem
from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.devpost import DevpostConnector
from app.sources.connectors.lablab import LablabConnector
from app.sources.models import Source
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


class TestDirectoryPagination:
    async def test_next_cursor_uses_the_page_size_devpost_served(self) -> None:
        # Devpost caps per_page at 40: 85 events = pages of 40, 40, 5.
        calls: list[str] = []

        async def fake_get(url: str) -> dict:
            calls.append(url)
            page = int(url.split("page=")[1].split("&")[0])
            count = {1: 40, 2: 40, 3: 5}[page]
            start = (page - 1) * 40
            return {
                "hackathons": [
                    {
                        "id": start + i,
                        "title": f"Event {start + i}",
                        "url": f"https://e{start + i}.devpost.com/",
                        "displayed_location": {"icon": "globe", "location": "Online"},
                    }
                    for i in range(count)
                ],
                "meta": {"total_count": 85, "per_page": 40},
            }

        connector = DevpostConnector(http_get=fake_get)
        query = ConnectorQuery(module="hackathon", result_cap=50)
        cursor: str | None = None
        urls: list[str] = []
        while True:
            page = await connector.discover(query, cursor)
            urls += [item.url for item in page.items]
            cursor = page.next_cursor
            if not cursor:
                break
        assert len(urls) == 85
        assert all("per_page=40" in call for call in calls)

    async def test_known_events_do_not_use_up_the_cap(self) -> None:
        from app.harvest.runner import collect_new_candidates

        rows = [
            {
                "id": str(i),
                "url": f"https://e{i}.devpost.com/",
                "title": f"Event {i}",
                "displayed_location": {"icon": "globe", "location": "Online"},
            }
            for i in range(100)
        ]
        from app.submissions.url_policy import canonicalize_url

        known = {canonicalize_url(f"https://e{i}.devpost.com/").canonical for i in range(60)}
        fresh, discovered, duplicates = await collect_new_candidates(
            DevpostConnector(fixtures=rows), known=known, limit=20
        )
        assert [hit.url for hit in fresh] == [
            f"https://e{i}.devpost.com/" for i in range(60, 80)
        ]
        assert duplicates == 60
        assert discovered == 80


LABLAB_ROW = {
    "id": "lab-1",
    "name": "Lablab Agents Sprint",
    "slug": "lablab-agents-sprint",
    "type": "HACKATHON",
    "eventType": "ONLINE",
    "startAt": "2026-09-01T19:00:00.000Z",
    "endAt": "2026-12-01T19:00:00.000Z",
    "deletedAt": None,
    "signupActive": True,
    "_count": {"participants": 10},
}


class TestMultiSourceHarvest:
    async def test_multi_source_queues_per_source(self, session: AsyncSession) -> None:
        async def fake_fetch(url: str, policy):
            return _doc(url, ONLINE_HTML)

        summary = await run_online_hackathon_harvest(
            session,
            _settings(),
            now=NOW,
            connectors={
                "devpost": _connector(),
                "lablab": LablabConnector(fixtures=[LABLAB_ROW], now=lambda: NOW),
            },
            fetch_page=fake_fetch,
        )
        assert summary.queued == 2
        meta = summary.as_meta()
        assert meta["sources"]["devpost"]["queued"] == 1
        assert meta["sources"]["lablab"]["queued"] == 1

        names = {
            source.name
            for source in (await session.execute(select(Source))).scalars().all()
        }
        assert {"Devpost (online harvest)", "lablab.ai (online harvest)"} <= names

        snapshots = {
            (await session.get(ReviewItem, UUID(item_id))).candidate_snapshot["source"]  # type: ignore[union-attr]
            for item_id in summary.review_item_ids
        }
        assert snapshots == {"harvest_devpost", "harvest_lablab"}

    async def test_blocked_source_fails_its_run_only(self, session: AsyncSession) -> None:
        async def fake_fetch(url: str, policy):
            return _doc(url, ONLINE_HTML)

        async def waf(_url: str) -> str:
            return "<html><head><title>Human Verification</title></head>awswaf</html>"

        summary = await run_online_hackathon_harvest(
            session,
            _settings(),
            now=NOW.replace(hour=16),
            connectors={
                "devpost": _connector(),
                "lablab": LablabConnector(http_get=waf, now=lambda: NOW),
            },
            fetch_page=fake_fetch,
        )
        assert summary.queued == 1
        assert summary.as_meta()["sources"]["lablab"]["error"] == "blocked"
        runs = list((await session.execute(select(CrawlRun))).scalars().all())
        by_status = {str(run.status) for run in runs}
        assert "failed" in by_status
