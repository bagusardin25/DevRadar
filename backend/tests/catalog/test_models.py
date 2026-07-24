"""Catalogue model constraint and behavior tests."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import (
    HackathonMode,
    ListingKind,
    OfferType,
    VerificationStatus,
)
from app.catalog.models import Hackathon, Listing
from app.catalog.repository import ListingRepository
from app.catalog.schemas import (
    AIOfferCreateSchema,
    HackathonCreateSchema,
    ListingCreateSchema,
)
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.ingestion.models import VerificationEvent
from app.sources.models import Source


@pytest.fixture
async def session() -> AsyncSession:
    settings = Settings()
    engine = create_engine(settings)
    maker = create_session_maker(engine)
    async with maker() as session:
        try:
            yield session
            await session.rollback()
        finally:
            await session.close()
    await engine.dispose()


class TestListingConstraints:
    async def test_confidence_score_range_rejects_above_one(
        self, session: AsyncSession
    ) -> None:
        listing = Listing(
            kind=ListingKind.HACKATHON,
            slug=f"bad-score-{uuid4().hex[:8]}",
            title="Bad Score",
            confidence_score=Decimal("1.001"),
        )
        session.add(listing)
        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_confidence_score_range_rejects_negative(
        self, session: AsyncSession
    ) -> None:
        listing = Listing(
            kind=ListingKind.HACKATHON,
            slug=f"neg-score-{uuid4().hex[:8]}",
            title="Neg Score",
            confidence_score=Decimal("-0.1"),
        )
        session.add(listing)
        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_slug_must_be_unique(self, session: AsyncSession) -> None:
        slug = f"unique-slug-{uuid4().hex[:8]}"
        session.add(
            Listing(kind=ListingKind.HACKATHON, slug=slug, title="One")
        )
        await session.flush()
        session.add(
            Listing(kind=ListingKind.AI_OFFER, slug=slug, title="Two")
        )
        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_timestamps_are_timezone_aware(
        self, session: AsyncSession
    ) -> None:
        listing = Listing(
            kind=ListingKind.HACKATHON,
            slug=f"tz-{uuid4().hex[:8]}",
            title="TZ",
        )
        session.add(listing)
        await session.flush()
        await session.refresh(listing)
        assert listing.created_at.tzinfo is not None
        assert listing.updated_at.tzinfo is not None
        assert listing.first_seen_at.tzinfo is not None

    async def test_search_document_is_generated(
        self, session: AsyncSession
    ) -> None:
        listing = Listing(
            kind=ListingKind.HACKATHON,
            slug=f"search-{uuid4().hex[:8]}",
            title="Quantum Hackathon",
            description="Build quantum algorithms",
            search_extra="IBM Qiskit",
        )
        session.add(listing)
        await session.flush()
        result = await session.execute(
            text("SELECT search_document::text FROM listings WHERE id = :id"),
            {"id": listing.id},
        )
        vector = result.scalar_one()
        assert vector is not None
        assert "quantum" in vector.lower()


class TestHackathonConstraints:
    async def test_team_min_must_be_at_least_one(
        self, session: AsyncSession
    ) -> None:
        listing = Listing(
            kind=ListingKind.HACKATHON,
            slug=f"team-min-{uuid4().hex[:8]}",
            title="Team Min",
        )
        session.add(listing)
        await session.flush()
        session.add(
            Hackathon(
                listing_id=listing.id,
                organizer="Org",
                mode=HackathonMode.ONLINE,
                team_min=0,
                team_max=1,
                official_url="https://example.com",
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_team_max_must_be_gte_min(self, session: AsyncSession) -> None:
        listing = Listing(
            kind=ListingKind.HACKATHON,
            slug=f"team-max-{uuid4().hex[:8]}",
            title="Team Max",
        )
        session.add(listing)
        await session.flush()
        session.add(
            Hackathon(
                listing_id=listing.id,
                organizer="Org",
                mode=HackathonMode.ONLINE,
                team_min=3,
                team_max=2,
                official_url="https://example.com",
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_prize_must_be_non_negative(self, session: AsyncSession) -> None:
        listing = Listing(
            kind=ListingKind.HACKATHON,
            slug=f"prize-{uuid4().hex[:8]}",
            title="Prize",
        )
        session.add(listing)
        await session.flush()
        session.add(
            Hackathon(
                listing_id=listing.id,
                organizer="Org",
                mode=HackathonMode.ONLINE,
                prize_value=Decimal("-1"),
                official_url="https://example.com",
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_cascade_delete_removes_hackathon(
        self, session: AsyncSession
    ) -> None:
        listing = Listing(
            kind=ListingKind.HACKATHON,
            slug=f"cascade-h-{uuid4().hex[:8]}",
            title="Cascade",
        )
        session.add(listing)
        await session.flush()
        session.add(
            Hackathon(
                listing_id=listing.id,
                organizer="Org",
                mode=HackathonMode.HYBRID,
                official_url="https://example.com/h",
            )
        )
        await session.flush()
        listing_id = listing.id
        await session.delete(listing)
        await session.flush()
        result = await session.execute(
            select(Hackathon).where(Hackathon.listing_id == listing_id)
        )
        assert result.scalar_one_or_none() is None


class TestEnumValues:
    def test_verification_status_matches_frontend(self) -> None:
        expected = {
            "verified_active",
            "likely_active",
            "needs_review",
            "registration_closed",
            "expired",
            "cancelled",
        }
        assert {s.value for s in VerificationStatus} == expected

    def test_hackathon_mode_matches_frontend(self) -> None:
        assert {m.value for m in HackathonMode} == {
            "online",
            "hybrid",
            "in_person",
        }

    def test_offer_type_matches_frontend(self) -> None:
        expected = {
            "free_credits",
            "free_tier",
            "trial",
            "student_program",
            "open_source_program",
            "hackathon_credits",
            "promo_code",
            "free_model",
            "self_hosted_weights",
        }
        assert {o.value for o in OfferType} == expected


class TestRepository:
    async def test_create_hackathon_aggregate(self, session: AsyncSession) -> None:
        repo = ListingRepository(session)
        listing = await repo.create_hackathon(
            ListingCreateSchema(
                kind=ListingKind.HACKATHON,
                slug=f"repo-h-{uuid4().hex[:8]}",
                title="Repo Hackathon",
                description="A test hackathon",
                verification_status=VerificationStatus.VERIFIED_ACTIVE,
                confidence_score=Decimal("0.850"),
                score_breakdown={
                    "statusAndDeadline": 30,
                    "keywordMatch": 20,
                    "sourceCredibility": 15,
                    "freshness": 12,
                    "completeness": 5,
                },
            ),
            HackathonCreateSchema(
                organizer="DevRadar Labs",
                mode=HackathonMode.ONLINE,
                eligible_countries=["Worldwide"],
                eligibility=["Students"],
                team_min=1,
                team_max=4,
                prize_value=Decimal("10000"),
                prize_currency="USD",
                technologies=["Python", "AI"],
                official_url="https://example.com/hack",
            ),
        )
        assert listing.hackathon is not None
        assert listing.hackathon.organizer == "DevRadar Labs"
        assert listing.kind == ListingKind.HACKATHON
        assert "DevRadar" in listing.search_extra

    async def test_create_ai_offer_aggregate(self, session: AsyncSession) -> None:
        repo = ListingRepository(session)
        listing = await repo.create_ai_offer(
            ListingCreateSchema(
                kind=ListingKind.AI_OFFER,
                slug=f"repo-a-{uuid4().hex[:8]}",
                title="Free Credits",
                description="Cloud credits for builders",
            ),
            AIOfferCreateSchema(
                product_name="Cloud AI",
                provider="AcmeAI",
                offer_type=OfferType.FREE_CREDITS,
                offer_value="$100 free credits",
                official_terms_url="https://example.com/terms",
                claim_url="https://example.com/claim",
                tags=["credits", "llm"],
            ),
        )
        assert listing.ai_offer is not None
        assert listing.ai_offer.provider == "AcmeAI"
        assert listing.kind == ListingKind.AI_OFFER

    async def test_get_by_slug(self, session: AsyncSession) -> None:
        repo = ListingRepository(session)
        slug = f"lookup-{uuid4().hex[:8]}"
        await repo.create_hackathon(
            ListingCreateSchema(
                kind=ListingKind.HACKATHON,
                slug=slug,
                title="Lookup",
            ),
            HackathonCreateSchema(
                organizer="Org",
                mode=HackathonMode.IN_PERSON,
                location="Jakarta",
                official_url="https://example.com",
            ),
        )
        found = await repo.get_by_slug(slug)
        assert found is not None
        assert found.hackathon is not None
        assert found.hackathon.location == "Jakarta"


class TestProvenance:
    async def test_verification_event_is_append_only_row(
        self, session: AsyncSession
    ) -> None:
        listing = Listing(
            kind=ListingKind.HACKATHON,
            slug=f"ve-{uuid4().hex[:8]}",
            title="Verified Event",
        )
        session.add(listing)
        await session.flush()
        event = VerificationEvent(
            listing_id=listing.id,
            event_type="initial_check",
            previous_status=None,
            new_status=VerificationStatus.NEEDS_REVIEW,
            checked_urls=["https://example.com"],
            notes="seed",
        )
        session.add(event)
        await session.flush()
        result = await session.execute(
            select(VerificationEvent).where(VerificationEvent.listing_id == listing.id)
        )
        rows = list(result.scalars().all())
        assert len(rows) == 1
        assert rows[0].created_at.tzinfo is not None

    async def test_source_has_no_secret_column(self) -> None:
        column_names = {c.name for c in Source.__table__.columns}
        assert "credential_ref" in column_names
        assert "api_key" not in column_names
        assert "secret" not in column_names
        assert "password" not in column_names
