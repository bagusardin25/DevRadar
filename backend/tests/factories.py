"""Test data helpers for seeding catalogue rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import (
    ConnectorType,
    EffortEstimate,
    HackathonMode,
    ListingKind,
    OfferType,
    SourceTier,
    VerificationStatus,
)
from app.catalog.models import Listing
from app.catalog.repository import ListingRepository
from app.catalog.schemas import (
    AIOfferCreateSchema,
    HackathonCreateSchema,
    ListingCreateSchema,
)
from app.ingestion.models import ListingSource, VerificationEvent
from app.sources.models import Source


async def seed_source(
    session: AsyncSession,
    *,
    name: str | None = None,
    connector: ConnectorType = ConnectorType.DEVPOST,
    tier: SourceTier = SourceTier.TIER_2,
) -> Source:
    source = Source(
        name=name or f"source-{uuid4().hex[:8]}",
        connector_type=connector,
        trust_tier=tier,
        base_url="https://example.com",
        enabled=True,
    )
    session.add(source)
    await session.flush()
    return source


async def seed_hackathon(
    session: AsyncSession,
    *,
    slug: str | None = None,
    title: str = "Test Hackathon",
    status: VerificationStatus = VerificationStatus.VERIFIED_ACTIVE,
    mode: HackathonMode = HackathonMode.ONLINE,
    technology: str = "Python",
    region: str = "Worldwide",
    eligibility: str = "Student",
    prize: Decimal = Decimal("50000"),
    score: Decimal = Decimal("0.900"),
    days_until_deadline: int = 20,
    source: Source | None = None,
) -> Listing:
    repo = ListingRepository(session)
    now = datetime.now(UTC)
    deadline = now + timedelta(days=days_until_deadline)
    listing = await repo.create_hackathon(
        ListingCreateSchema(
            kind=ListingKind.HACKATHON,
            slug=slug or f"hack-{uuid4().hex[:10]}",
            title=title,
            description=f"Description for {title}",
            verification_status=status,
            confidence_score=score,
            score_breakdown={
                "statusAndDeadline": 30,
                "keywordMatch": 20,
                "sourceCredibility": 18,
                "freshness": 12,
                "completeness": 5,
            },
            published_at=now if status != VerificationStatus.NEEDS_REVIEW else None,
            last_checked_at=now,
        ),
        HackathonCreateSchema(
            organizer="Test Org",
            registration_open_at=now - timedelta(days=10),
            registration_deadline=deadline - timedelta(days=5),
            submission_deadline=deadline,
            mode=mode,
            location="Remote" if mode == HackathonMode.ONLINE else "Jakarta",
            eligible_countries=[region],
            eligibility=[eligibility],
            team_min=1,
            team_max=4,
            prize_value=prize,
            prize_currency="USD",
            technologies=[technology, "AI"],
            official_url="https://example.com/hackathon",
            suitable_reasons=["Online", "Open worldwide"],
            effort_estimate=EffortEstimate.WEEKS_1_2,
        ),
    )
    if source is None:
        source = await seed_source(session)
    session.add(
        ListingSource(
            listing_id=listing.id,
            source_id=source.id,
            source_url=f"https://example.com/{listing.slug}",
            is_primary=True,
            observed_fields={"title": title},
        )
    )
    session.add(
        VerificationEvent(
            listing_id=listing.id,
            event_type="publish",
            previous_status=VerificationStatus.NEEDS_REVIEW,
            new_status=status,
            checked_urls=["https://example.com/hackathon"],
            score_breakdown=listing.score_breakdown,
            notes="Seeded verification event",
        )
    )
    await session.flush()
    await session.refresh(
        listing,
        attribute_names=["hackathon", "listing_sources", "verification_events"],
    )
    return listing


async def seed_ai_offer(
    session: AsyncSession,
    *,
    slug: str | None = None,
    title: str = "Free AI Credits",
    product_name: str = "Cloud AI",
    provider: str = "AcmeAI",
    status: VerificationStatus = VerificationStatus.VERIFIED_ACTIVE,
    offer_type: OfferType = OfferType.FREE_CREDITS,
    region: str = "Worldwide",
    tag: str = "credits",
    score: Decimal = Decimal("0.850"),
    days_until_expiry: int | None = 30,
    source: Source | None = None,
) -> Listing:
    repo = ListingRepository(session)
    now = datetime.now(UTC)
    expires = None if days_until_expiry is None else now + timedelta(days=days_until_expiry)
    listing = await repo.create_ai_offer(
        ListingCreateSchema(
            kind=ListingKind.AI_OFFER,
            slug=slug or f"offer-{uuid4().hex[:10]}",
            title=title,
            description=f"Description for {product_name}",
            verification_status=status,
            confidence_score=score,
            score_breakdown={
                "statusAndDeadline": 28,
                "keywordMatch": 18,
                "sourceCredibility": 16,
                "freshness": 12,
                "completeness": 4,
            },
            published_at=now if status != VerificationStatus.NEEDS_REVIEW else None,
            last_checked_at=now,
        ),
        AIOfferCreateSchema(
            product_name=product_name,
            provider=provider,
            offer_type=offer_type,
            offer_value="$100 free credits",
            target_users=["Developer", "Student"],
            requirements=["Email signup"],
            starts_at=now - timedelta(days=5),
            expires_at=expires,
            supported_regions=[region],
            official_terms_url="https://example.com/terms",
            claim_url="https://example.com/claim",
            tags=[tag, "ai"],
            suitable_reasons=["No credit card for free tier"],
        ),
    )
    if source is None:
        source = await seed_source(
            session,
            connector=ConnectorType.OFFICIAL_SITE,
            tier=SourceTier.TIER_1,
        )
    session.add(
        ListingSource(
            listing_id=listing.id,
            source_id=source.id,
            source_url=f"https://example.com/{listing.slug}",
            is_primary=True,
        )
    )
    session.add(
        VerificationEvent(
            listing_id=listing.id,
            event_type="publish",
            previous_status=VerificationStatus.NEEDS_REVIEW,
            new_status=status,
            checked_urls=["https://example.com/terms"],
            score_breakdown=listing.score_breakdown,
            notes="Seeded offer verification",
        )
    )
    await session.flush()
    await session.refresh(
        listing,
        attribute_names=["ai_offer", "listing_sources", "verification_events"],
    )
    return listing


async def delete_listing_graph(session: AsyncSession, listing: Listing) -> None:
    """Remove a seeded listing and dependents (cascade covers most)."""
    await session.delete(listing)
    await session.flush()
