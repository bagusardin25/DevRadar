"""Persistence helpers for catalogue listings."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.enums import ListingKind, VerificationStatus
from app.catalog.models import AIOffer, Hackathon, Listing
from app.catalog.schemas import AIOfferCreateSchema, HackathonCreateSchema, ListingCreateSchema


class ListingRepository:
    """Repository for Listing aggregate roots."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, listing_id: UUID) -> Listing | None:
        result = await self._session.execute(
            select(Listing)
            .where(Listing.id == listing_id)
            .options(
                selectinload(Listing.hackathon),
                selectinload(Listing.ai_offer),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Listing | None:
        result = await self._session.execute(
            select(Listing)
            .where(Listing.slug == slug)
            .options(
                selectinload(Listing.hackathon),
                selectinload(Listing.ai_offer),
            )
        )
        return result.scalar_one_or_none()

    async def create_listing(self, data: ListingCreateSchema) -> Listing:
        kwargs: dict[str, object] = {
            "kind": data.kind,
            "slug": data.slug,
            "title": data.title,
            "description": data.description,
            "verification_status": data.verification_status,
            "confidence_score": data.confidence_score,
            "score_breakdown": data.score_breakdown,
            "search_extra": data.search_extra,
            "published_at": data.published_at,
            "last_checked_at": data.last_checked_at,
        }
        if data.first_seen_at is not None:
            kwargs["first_seen_at"] = data.first_seen_at
        listing = Listing(**kwargs)
        self._session.add(listing)
        await self._session.flush()
        return listing

    async def create_hackathon(
        self,
        listing_data: ListingCreateSchema,
        hackathon_data: HackathonCreateSchema,
    ) -> Listing:
        if listing_data.kind != ListingKind.HACKATHON:
            listing_data = listing_data.model_copy(update={"kind": ListingKind.HACKATHON})
        # Build search_extra from organizer + technologies when not provided.
        if not listing_data.search_extra:
            parts = [
                hackathon_data.organizer,
                *hackathon_data.technologies,
                *hackathon_data.eligibility,
            ]
            listing_data = listing_data.model_copy(
                update={"search_extra": " ".join(parts).strip()}
            )

        listing = await self.create_listing(listing_data)
        hackathon = Hackathon(
            listing_id=listing.id,
            **hackathon_data.model_dump(),
        )
        self._session.add(hackathon)
        await self._session.flush()
        await self._session.refresh(listing, attribute_names=["hackathon"])
        return listing

    async def create_ai_offer(
        self,
        listing_data: ListingCreateSchema,
        offer_data: AIOfferCreateSchema,
    ) -> Listing:
        if listing_data.kind != ListingKind.AI_OFFER:
            listing_data = listing_data.model_copy(update={"kind": ListingKind.AI_OFFER})
        if not listing_data.search_extra:
            extra = " ".join([offer_data.provider, offer_data.product_name, *offer_data.tags])
            listing_data = listing_data.model_copy(update={"search_extra": extra.strip()})

        listing = await self.create_listing(listing_data)
        offer = AIOffer(
            listing_id=listing.id,
            **offer_data.model_dump(),
        )
        self._session.add(offer)
        await self._session.flush()
        await self._session.refresh(listing, attribute_names=["ai_offer"])
        return listing

    async def list_by_status(
        self,
        statuses: list[VerificationStatus],
        *,
        kind: ListingKind | None = None,
        limit: int = 50,
    ) -> list[Listing]:
        stmt = (
            select(Listing)
            .where(Listing.verification_status.in_(statuses))
            .options(
                selectinload(Listing.hackathon),
                selectinload(Listing.ai_offer),
            )
            .order_by(Listing.published_at.desc().nullslast(), Listing.id)
            .limit(limit)
        )
        if kind is not None:
            stmt = stmt.where(Listing.kind == kind)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
