"""API tests for combined search, stats, and filter meta."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import VerificationStatus
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.main import create_app
from tests.factories import seed_ai_offer, seed_hackathon


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


class TestCombinedSearch:
    async def test_combined_result_discrimination(
        self, api_client, db_session: AsyncSession
    ) -> None:
        token = f"combo-{uuid4().hex[:8]}"
        hack = await seed_hackathon(
            db_session,
            slug=f"cs-h-{uuid4().hex[:8]}",
            title=f"{token} Hackathon Alpha",
        )
        offer = await seed_ai_offer(
            db_session,
            slug=f"cs-a-{uuid4().hex[:8]}",
            title=f"{token} Offer Beta",
            product_name=f"{token} Product",
        )
        await db_session.commit()

        response = await api_client.get("/api/v1/search", params={"q": token})
        assert response.status_code == 200
        body = response.json()
        our = [item for item in body["items"] if item["item"]["slug"] in {hack.slug, offer.slug}]
        kinds = {item["kind"] for item in our}
        assert "hackathon" in kinds
        assert "ai_offer" in kinds
        assert len(our) == 2
        for item in our:
            assert "item" in item

        await db_session.delete(hack)
        await db_session.delete(offer)
        await db_session.commit()

    async def test_combined_kind_filter(
        self, api_client, db_session: AsyncSession
    ) -> None:
        token = f"kind-{uuid4().hex[:8]}"
        hack = await seed_hackathon(
            db_session,
            slug=f"ck-h-{uuid4().hex[:8]}",
            title=f"{token} OnlyHack",
        )
        offer = await seed_ai_offer(
            db_session,
            slug=f"ck-a-{uuid4().hex[:8]}",
            title=f"{token} OnlyOffer",
        )
        await db_session.commit()

        response = await api_client.get(
            "/api/v1/search",
            params={"q": token, "kind": "hackathon"},
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert all(i["kind"] == "hackathon" for i in items)
        assert any(i["item"]["slug"] == hack.slug for i in items)
        assert not any(i["item"]["slug"] == offer.slug for i in items)

        await db_session.delete(hack)
        await db_session.delete(offer)
        await db_session.commit()

    async def test_ordering_by_score(
        self, api_client, db_session: AsyncSession
    ) -> None:
        from decimal import Decimal

        token = f"rank-{uuid4().hex[:8]}"
        low = await seed_hackathon(
            db_session,
            slug=f"rk-l-{uuid4().hex[:8]}",
            title=f"{token} Low Score",
            score=Decimal("0.500"),
        )
        high = await seed_hackathon(
            db_session,
            slug=f"rk-h-{uuid4().hex[:8]}",
            title=f"{token} High Score",
            score=Decimal("0.990"),
        )
        await db_session.commit()

        response = await api_client.get("/api/v1/search", params={"q": token})
        assert response.status_code == 200
        items = response.json()["items"]
        our = [i for i in items if i["item"]["slug"] in {low.slug, high.slug}]
        assert len(our) == 2
        assert our[0]["item"]["slug"] == high.slug
        assert our[1]["item"]["slug"] == low.slug

        await db_session.delete(low)
        await db_session.delete(high)
        await db_session.commit()


class TestStatsAndMeta:
    async def test_stats_counts_active(
        self, api_client, db_session: AsyncSession
    ) -> None:
        hack = await seed_hackathon(
            db_session,
            slug=f"st-h-{uuid4().hex[:8]}",
            title="Stats Hack",
            status=VerificationStatus.VERIFIED_ACTIVE,
        )
        offer = await seed_ai_offer(
            db_session,
            slug=f"st-a-{uuid4().hex[:8]}",
            title="Stats Offer",
            status=VerificationStatus.LIKELY_ACTIVE,
        )
        await db_session.commit()

        response = await api_client.get("/api/v1/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["hackathonsActive"] >= 1
        assert body["aiOffersActive"] >= 1
        assert "sourcesEnabled" in body

        await db_session.delete(hack)
        await db_session.delete(offer)
        await db_session.commit()

    async def test_filter_meta_shape(self, api_client) -> None:
        response = await api_client.get("/api/v1/meta/filters")
        assert response.status_code == 200
        body = response.json()
        assert "technologies" in body
        assert "regions" in body
        assert "eligibilityLabels" in body
        assert "offerTypes" in body
        assert "modes" in body
        assert body["modes"] == ["online", "hybrid", "in_person"]
