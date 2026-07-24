"""API tests for public AI offer catalogue."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import OfferType, VerificationStatus
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.main import create_app
from tests.factories import seed_ai_offer


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
        yield client


class TestAIOfferList:
    async def test_default_excludes_needs_review(
        self, api_client, db_session: AsyncSession
    ) -> None:
        visible = await seed_ai_offer(
            db_session,
            slug=f"ao-v-{uuid4().hex[:8]}",
            title="Visible Credits Deal",
            status=VerificationStatus.VERIFIED_ACTIVE,
        )
        hidden = await seed_ai_offer(
            db_session,
            slug=f"ao-h-{uuid4().hex[:8]}",
            title="Hidden Credits Draft",
            status=VerificationStatus.NEEDS_REVIEW,
        )
        await db_session.commit()

        response = await api_client.get("/api/v1/ai-offers", params={"q": "Credits"})
        assert response.status_code == 200
        slugs = {item["slug"] for item in response.json()["items"]}
        assert visible.slug in slugs
        assert hidden.slug not in slugs

        await db_session.delete(visible)
        await db_session.delete(hidden)
        await db_session.commit()

    async def test_filter_offer_type_region_tags(
        self, api_client, db_session: AsyncSession
    ) -> None:
        match = await seed_ai_offer(
            db_session,
            slug=f"ao-m-{uuid4().hex[:8]}",
            title="Student Free Tier Match",
            offer_type=OfferType.FREE_TIER,
            region="Europe",
            tag="student",
        )
        other = await seed_ai_offer(
            db_session,
            slug=f"ao-o-{uuid4().hex[:8]}",
            title="Promo Code Other",
            offer_type=OfferType.PROMO_CODE,
            region="Asia",
            tag="promo",
        )
        await db_session.commit()

        response = await api_client.get(
            "/api/v1/ai-offers",
            params={
                "offerType": "free_tier",
                "region": "Europe",
                "tags": "student",
            },
        )
        assert response.status_code == 200
        slugs = {item["slug"] for item in response.json()["items"]}
        assert match.slug in slugs
        assert other.slug not in slugs

        await db_session.delete(match)
        await db_session.delete(other)
        await db_session.commit()

    async def test_only_free_no_card(
        self, api_client, db_session: AsyncSession
    ) -> None:
        free = await seed_ai_offer(
            db_session,
            slug=f"ao-f-{uuid4().hex[:8]}",
            title="Free Model Weights",
            offer_type=OfferType.FREE_MODEL,
            product_name="OpenWeights",
        )
        trial = await seed_ai_offer(
            db_session,
            slug=f"ao-t-{uuid4().hex[:8]}",
            title="Paid Trial",
            offer_type=OfferType.TRIAL,
            product_name="PaidAI",
        )
        await db_session.commit()

        response = await api_client.get(
            "/api/v1/ai-offers",
            params={"onlyFreeNoCard": "true", "q": "Free Model"},
        )
        assert response.status_code == 200
        slugs = {item["slug"] for item in response.json()["items"]}
        assert free.slug in slugs

        response_all = await api_client.get(
            "/api/v1/ai-offers",
            params={"q": "Paid Trial"},
        )
        trial_slugs = {item["slug"] for item in response_all.json()["items"]}
        # trial still visible without free filter
        assert trial.slug in trial_slugs

        free_filter = await api_client.get(
            "/api/v1/ai-offers",
            params={"onlyFreeNoCard": "true", "q": "Paid Trial"},
        )
        assert trial.slug not in {i["slug"] for i in free_filter.json()["items"]}

        await db_session.delete(free)
        await db_session.delete(trial)
        await db_session.commit()

    async def test_camel_case_response_fields(
        self, api_client, db_session: AsyncSession
    ) -> None:
        listing = await seed_ai_offer(
            db_session,
            slug=f"ao-c-{uuid4().hex[:8]}",
            title="Camel Case Offer",
        )
        await db_session.commit()

        response = await api_client.get(f"/api/v1/ai-offers/{listing.slug}")
        assert response.status_code == 200
        body = response.json()
        assert "productName" in body
        assert "offerType" in body
        assert "officialTermsUrl" in body
        assert "claimUrl" in body
        assert "supportedRegions" in body
        assert "discoverySources" in body
        assert "confidenceScore" in body

        await db_session.delete(listing)
        await db_session.commit()


class TestAIOfferDetail:
    async def test_detail_and_etag(
        self, api_client, db_session: AsyncSession
    ) -> None:
        listing = await seed_ai_offer(
            db_session,
            slug=f"ao-d-{uuid4().hex[:8]}",
            title="Detail Offer",
        )
        await db_session.commit()

        response = await api_client.get(f"/api/v1/ai-offers/{listing.slug}")
        assert response.status_code == 200
        assert "ETag" in response.headers
        assert response.json()["provider"] == "AcmeAI"

        cached = await api_client.get(
            f"/api/v1/ai-offers/{listing.slug}",
            headers={"If-None-Match": response.headers["ETag"]},
        )
        assert cached.status_code == 304

        await db_session.delete(listing)
        await db_session.commit()
