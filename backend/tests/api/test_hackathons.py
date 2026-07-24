"""API tests for public hackathon catalogue."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import HackathonMode, VerificationStatus
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.main import create_app
from tests.factories import seed_hackathon


@pytest.fixture
async def db_session() -> AsyncSession:
    settings = Settings()
    engine = create_engine(settings)
    maker = create_session_maker(engine)
    async with maker() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def api_client(settings: Settings):
    application = create_app(settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        yield client, application


async def _commit_seed(session: AsyncSession) -> None:
    await session.commit()


class TestHackathonList:
    async def test_empty_catalogue(self, api_client) -> None:
        client, _ = api_client
        # Use a filter that matches nothing
        response = await client.get(
            "/api/v1/hackathons",
            params={"q": f"zzz-no-match-{uuid4().hex}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["nextCursor"] is None
        assert body["totalEstimate"] == 0

    async def test_default_status_hides_needs_review(
        self, api_client, db_session: AsyncSession
    ) -> None:
        client, _ = api_client
        visible = await seed_hackathon(
            db_session,
            slug=f"visible-{uuid4().hex[:8]}",
            title="Visible Quantum Challenge",
            status=VerificationStatus.VERIFIED_ACTIVE,
        )
        hidden = await seed_hackathon(
            db_session,
            slug=f"hidden-{uuid4().hex[:8]}",
            title="Hidden Quantum Draft",
            status=VerificationStatus.NEEDS_REVIEW,
        )
        await _commit_seed(db_session)

        response = await client.get("/api/v1/hackathons", params={"q": "Quantum"})
        assert response.status_code == 200
        body = response.json()
        slugs = {item["slug"] for item in body["items"]}
        assert visible.slug in slugs
        assert hidden.slug not in slugs

        # cleanup
        await db_session.delete(visible)
        await db_session.delete(hidden)
        await db_session.commit()

    async def test_filter_mode_technology_region_eligibility(
        self, api_client, db_session: AsyncSession
    ) -> None:
        client, _ = api_client
        match = await seed_hackathon(
            db_session,
            slug=f"filter-m-{uuid4().hex[:8]}",
            title="Filter Match Event",
            mode=HackathonMode.ONLINE,
            technology="Rust",
            region="Indonesia",
            eligibility="Startup",
        )
        other = await seed_hackathon(
            db_session,
            slug=f"filter-o-{uuid4().hex[:8]}",
            title="Filter Other Event",
            mode=HackathonMode.IN_PERSON,
            technology="Go",
            region="Singapore",
            eligibility="Student",
        )
        await _commit_seed(db_session)

        response = await client.get(
            "/api/v1/hackathons",
            params={
                "mode": "online",
                "technology": "Rust",
                "region": "Indonesia",
                "eligibility": "Startup",
            },
        )
        assert response.status_code == 200
        slugs = {item["slug"] for item in response.json()["items"]}
        assert match.slug in slugs
        assert other.slug not in slugs

        await db_session.delete(match)
        await db_session.delete(other)
        await db_session.commit()

    async def test_only_big_prizes_and_closing_soon(
        self, api_client, db_session: AsyncSession
    ) -> None:
        client, _ = api_client
        big = await seed_hackathon(
            db_session,
            slug=f"big-{uuid4().hex[:8]}",
            title="Big Prize Soon",
            prize=Decimal("25000"),
            days_until_deadline=7,
            score=Decimal("0.95"),
        )
        small = await seed_hackathon(
            db_session,
            slug=f"small-{uuid4().hex[:8]}",
            title="Small Prize Far",
            prize=Decimal("500"),
            days_until_deadline=60,
            score=Decimal("0.70"),
        )
        await _commit_seed(db_session)

        response = await client.get(
            "/api/v1/hackathons",
            params={"onlyBigPrizes": "true", "onlyClosingSoon": "true"},
        )
        assert response.status_code == 200
        slugs = {item["slug"] for item in response.json()["items"]}
        assert big.slug in slugs
        assert small.slug not in slugs

        await db_session.delete(big)
        await db_session.delete(small)
        await db_session.commit()

    async def test_cursor_pagination_stable(
        self, api_client, db_session: AsyncSession
    ) -> None:
        client, _ = api_client
        prefix = f"page-{uuid4().hex[:6]}"
        listings = []
        for i in range(5):
            listings.append(
                await seed_hackathon(
                    db_session,
                    slug=f"{prefix}-{i}",
                    title=f"{prefix} Hackathon {i}",
                    score=Decimal(f"0.{90 - i}00"),
                )
            )
        await _commit_seed(db_session)

        page1 = await client.get(
            "/api/v1/hackathons",
            params={"q": prefix, "limit": 2},
        )
        assert page1.status_code == 200
        body1 = page1.json()
        assert len(body1["items"]) == 2
        assert body1["nextCursor"] is not None
        assert body1["totalEstimate"] >= 5

        page2 = await client.get(
            "/api/v1/hackathons",
            params={"q": prefix, "limit": 2, "cursor": body1["nextCursor"]},
        )
        assert page2.status_code == 200
        body2 = page2.json()
        ids1 = {item["id"] for item in body1["items"]}
        ids2 = {item["id"] for item in body2["items"]}
        assert ids1.isdisjoint(ids2)

        # Scores non-increasing across pages
        scores = [item["confidenceScore"] for item in body1["items"] + body2["items"]]
        assert scores == sorted(scores, reverse=True)

        for listing in listings:
            await db_session.delete(listing)
        await db_session.commit()

    async def test_invalid_cursor_returns_problem(
        self, api_client
    ) -> None:
        client, _ = api_client
        response = await client.get(
            "/api/v1/hackathons",
            params={"cursor": "not-a-valid-cursor"},
        )
        assert response.status_code == 422
        assert "application/problem+json" in response.headers["content-type"]
        assert response.json()["title"] == "Validation Error"


class TestHackathonDetail:
    async def test_detail_includes_provenance_and_audit(
        self, api_client, db_session: AsyncSession
    ) -> None:
        client, _ = api_client
        listing = await seed_hackathon(
            db_session,
            slug=f"detail-{uuid4().hex[:8]}",
            title="Detail Provenance Hack",
        )
        await _commit_seed(db_session)

        response = await client.get(f"/api/v1/hackathons/{listing.slug}")
        assert response.status_code == 200
        body = response.json()
        assert body["slug"] == listing.slug
        assert body["organizer"] == "Test Org"
        assert body["verificationStatus"] == "verified_active"
        assert "discoverySources" in body
        assert len(body["discoverySources"]) >= 1
        assert body["audit"]["verifierNotes"]
        assert body["audit"]["scoreBreakdown"]["statusAndDeadline"] >= 0
        assert "ETag" in response.headers

        await db_session.delete(listing)
        await db_session.commit()

    async def test_etag_not_modified(
        self, api_client, db_session: AsyncSession
    ) -> None:
        client, _ = api_client
        listing = await seed_hackathon(
            db_session,
            slug=f"etag-{uuid4().hex[:8]}",
            title="ETag Hack",
        )
        await _commit_seed(db_session)

        first = await client.get(f"/api/v1/hackathons/{listing.slug}")
        etag = first.headers["ETag"]
        second = await client.get(
            f"/api/v1/hackathons/{listing.slug}",
            headers={"If-None-Match": etag},
        )
        assert second.status_code == 304

        await db_session.delete(listing)
        await db_session.commit()

    async def test_needs_review_not_public(
        self, api_client, db_session: AsyncSession
    ) -> None:
        client, _ = api_client
        listing = await seed_hackathon(
            db_session,
            slug=f"nr-{uuid4().hex[:8]}",
            title="Needs Review Private",
            status=VerificationStatus.NEEDS_REVIEW,
        )
        await _commit_seed(db_session)

        response = await client.get(f"/api/v1/hackathons/{listing.slug}")
        assert response.status_code == 404

        await db_session.delete(listing)
        await db_session.commit()

    async def test_unknown_slug_404(self, api_client) -> None:
        client, _ = api_client
        response = await client.get("/api/v1/hackathons/does-not-exist-xyz")
        assert response.status_code == 404
