"""Authenticated catalogue CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.admin_schemas import (
    AdminAIOfferRead,
    AdminAIOfferWrite,
    AdminHackathonRead,
    AdminHackathonWrite,
    AdminListingRead,
)
from app.catalog.enums import ActorType, ListingKind, VerificationStatus
from app.catalog.models import AIOffer, Hackathon, Listing
from app.catalog.repository import ListingRepository
from app.catalog.schemas import AIOfferReadSchema, HackathonReadSchema, ListingCreateSchema
from app.errors import ConflictError, NotFoundError
from app.ingestion.models import VerificationEvent


class AdminCatalogueService:
    """CRUD service for listing aggregates, including admin audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _listing_read(listing: Listing) -> AdminListingRead:
        return AdminListingRead.model_validate(listing)

    @classmethod
    def to_hackathon_read(cls, listing: Listing) -> AdminHackathonRead:
        if listing.hackathon is None:
            raise ValueError("Listing is missing hackathon child")
        return AdminHackathonRead(
            listing=cls._listing_read(listing),
            hackathon=HackathonReadSchema.model_validate(listing.hackathon),
        )

    @classmethod
    def to_ai_offer_read(cls, listing: Listing) -> AdminAIOfferRead:
        if listing.ai_offer is None:
            raise ValueError("Listing is missing AI offer child")
        return AdminAIOfferRead(
            listing=cls._listing_read(listing),
            ai_offer=AIOfferReadSchema.model_validate(listing.ai_offer),
        )

    async def list_hackathons(
        self,
        *,
        query: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Listing], int]:
        stmt = (
            select(Listing)
            .join(Hackathon, Hackathon.listing_id == Listing.id)
            .where(Listing.kind == ListingKind.HACKATHON)
            .options(selectinload(Listing.hackathon))
        )
        if query and query.strip():
            term = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    Listing.title.ilike(term),
                    Listing.slug.ilike(term),
                    Hackathon.organizer.ilike(term),
                )
            )
        total = await self._count(stmt)
        rows = list(
            (
                await self._session.execute(
                    stmt.order_by(Listing.updated_at.desc(), Listing.id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .scalars()
            .unique()
            .all()
        )
        return rows, total

    async def list_ai_offers(
        self,
        *,
        query: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Listing], int]:
        stmt = (
            select(Listing)
            .join(AIOffer, AIOffer.listing_id == Listing.id)
            .where(Listing.kind == ListingKind.AI_OFFER)
            .options(selectinload(Listing.ai_offer))
        )
        if query and query.strip():
            term = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    Listing.title.ilike(term),
                    Listing.slug.ilike(term),
                    AIOffer.product_name.ilike(term),
                    AIOffer.provider.ilike(term),
                )
            )
        total = await self._count(stmt)
        rows = list(
            (
                await self._session.execute(
                    stmt.order_by(Listing.updated_at.desc(), Listing.id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .scalars()
            .unique()
            .all()
        )
        return rows, total

    async def create_hackathon(
        self,
        body: AdminHackathonWrite,
        *,
        actor_id: str,
    ) -> Listing:
        await self._ensure_slug_available(body.listing.slug)
        now = datetime.now(UTC)
        listing_data = ListingCreateSchema(
            kind=ListingKind.HACKATHON,
            **body.listing.model_dump(),
            published_at=self._published_at(body.listing.verification_status, now=now),
            last_checked_at=now,
        )
        listing = await ListingRepository(self._session).create_hackathon(
            listing_data,
            body.hackathon,
        )
        self._add_audit_event(
            listing,
            event_type="admin_create",
            previous_status=None,
            official_url=body.hackathon.official_url,
            actor_id=actor_id,
        )
        await self._refresh_aggregate(listing, "hackathon")
        return listing

    async def create_ai_offer(
        self,
        body: AdminAIOfferWrite,
        *,
        actor_id: str,
    ) -> Listing:
        await self._ensure_slug_available(body.listing.slug)
        now = datetime.now(UTC)
        listing_data = ListingCreateSchema(
            kind=ListingKind.AI_OFFER,
            **body.listing.model_dump(),
            published_at=self._published_at(body.listing.verification_status, now=now),
            last_checked_at=now,
        )
        listing = await ListingRepository(self._session).create_ai_offer(
            listing_data,
            body.ai_offer,
        )
        self._add_audit_event(
            listing,
            event_type="admin_create",
            previous_status=None,
            official_url=body.ai_offer.official_terms_url,
            actor_id=actor_id,
        )
        await self._refresh_aggregate(listing, "ai_offer")
        return listing

    async def update_hackathon(
        self,
        listing_id: UUID,
        body: AdminHackathonWrite,
        *,
        actor_id: str,
    ) -> Listing:
        listing = await self._get_listing(listing_id, ListingKind.HACKATHON)
        await self._ensure_slug_available(body.listing.slug, exclude_id=listing.id)
        previous_status = VerificationStatus(str(listing.verification_status))
        self._apply_listing_fields(listing, body.listing.model_dump())
        if listing.hackathon is None:
            raise NotFoundError(detail="Hackathon data not found")
        self._apply_fields(listing.hackathon, body.hackathon.model_dump())
        listing.search_extra = " ".join(
            [
                body.hackathon.organizer,
                *body.hackathon.technologies,
                *body.hackathon.eligibility,
            ]
        ).strip()
        self._add_audit_event(
            listing,
            event_type="admin_update",
            previous_status=previous_status,
            official_url=body.hackathon.official_url,
            actor_id=actor_id,
        )
        await self._refresh_aggregate(listing, "hackathon")
        return listing

    async def update_ai_offer(
        self,
        listing_id: UUID,
        body: AdminAIOfferWrite,
        *,
        actor_id: str,
    ) -> Listing:
        listing = await self._get_listing(listing_id, ListingKind.AI_OFFER)
        await self._ensure_slug_available(body.listing.slug, exclude_id=listing.id)
        previous_status = VerificationStatus(str(listing.verification_status))
        self._apply_listing_fields(listing, body.listing.model_dump())
        if listing.ai_offer is None:
            raise NotFoundError(detail="AI offer data not found")
        self._apply_fields(listing.ai_offer, body.ai_offer.model_dump())
        listing.search_extra = " ".join(
            [body.ai_offer.provider, body.ai_offer.product_name, *body.ai_offer.tags]
        ).strip()
        self._add_audit_event(
            listing,
            event_type="admin_update",
            previous_status=previous_status,
            official_url=body.ai_offer.official_terms_url,
            actor_id=actor_id,
        )
        await self._refresh_aggregate(listing, "ai_offer")
        return listing

    async def delete_listing(self, listing_id: UUID, kind: ListingKind) -> None:
        listing = await self._get_listing(listing_id, kind)
        await self._session.delete(listing)
        await self._session.flush()

    async def _get_listing(self, listing_id: UUID, kind: ListingKind) -> Listing:
        result = await self._session.execute(
            select(Listing)
            .where(Listing.id == listing_id, Listing.kind == kind)
            .options(
                selectinload(Listing.hackathon),
                selectinload(Listing.ai_offer),
            )
        )
        listing = result.scalar_one_or_none()
        if listing is None:
            raise NotFoundError(detail=f"{kind.value} not found")
        return listing

    async def _ensure_slug_available(
        self,
        slug: str,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        stmt = select(Listing.id).where(Listing.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Listing.id != exclude_id)
        if (await self._session.execute(stmt)).scalar_one_or_none() is not None:
            raise ConflictError(detail=f"Slug '{slug}' is already in use")

    async def _count(self, stmt: Any) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        return int(result.scalar_one())

    @staticmethod
    def _published_at(status: VerificationStatus, *, now: datetime) -> datetime | None:
        return None if status == VerificationStatus.NEEDS_REVIEW else now

    def _apply_listing_fields(self, listing: Listing, data: dict[str, Any]) -> None:
        previous_published = listing.published_at
        self._apply_fields(listing, data)
        now = datetime.now(UTC)
        if (
            listing.verification_status != VerificationStatus.NEEDS_REVIEW
            and previous_published is None
        ):
            listing.published_at = now
        listing.last_checked_at = now

    @staticmethod
    def _apply_fields(target: Any, data: dict[str, Any]) -> None:
        for field, value in data.items():
            setattr(target, field, value)

    def _add_audit_event(
        self,
        listing: Listing,
        *,
        event_type: str,
        previous_status: VerificationStatus | None,
        official_url: str,
        actor_id: str,
    ) -> None:
        self._session.add(
            VerificationEvent(
                listing_id=listing.id,
                event_type=event_type,
                previous_status=previous_status,
                new_status=listing.verification_status,
                checked_urls=[official_url],
                score_breakdown=listing.score_breakdown or {},
                notes="Catalogue entry managed through admin CRUD",
                actor_type=ActorType.ADMIN,
                actor_id=actor_id,
            )
        )

    async def _refresh_aggregate(self, listing: Listing, child: str) -> None:
        await self._session.flush()
        await self._session.refresh(listing)
        await self._session.refresh(listing, attribute_names=[child])
        relation = getattr(listing, child)
        if relation is not None:
            await self._session.refresh(relation)
