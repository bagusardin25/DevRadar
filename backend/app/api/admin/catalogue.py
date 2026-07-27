"""Admin CRUD routes for hackathons and AI offers."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import AdminUser, AdminUserRead, DbSession
from app.catalog.admin_schemas import (
    AdminAIOfferListResponse,
    AdminAIOfferRead,
    AdminAIOfferWrite,
    AdminHackathonListResponse,
    AdminHackathonRead,
    AdminHackathonWrite,
)
from app.catalog.admin_service import AdminCatalogueService
from app.catalog.enums import ListingKind

router = APIRouter(prefix="/admin/catalogue", tags=["Admin Catalogue"])


@router.get("/hackathons", response_model=AdminHackathonListResponse)
async def list_hackathons(
    session: DbSession,
    _admin: AdminUserRead,
    q: Annotated[str | None, Query(max_length=200)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> AdminHackathonListResponse:
    service = AdminCatalogueService(session)
    items, total = await service.list_hackathons(query=q, offset=offset, limit=limit)
    return AdminHackathonListResponse(
        items=[service.to_hackathon_read(item) for item in items],
        total=total,
    )


@router.post(
    "/hackathons",
    response_model=AdminHackathonRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_hackathon(
    body: AdminHackathonWrite,
    session: DbSession,
    admin: AdminUser,
) -> AdminHackathonRead:
    service = AdminCatalogueService(session)
    listing = await service.create_hackathon(body, actor_id=admin.admin_user_id)
    return service.to_hackathon_read(listing)


@router.put("/hackathons/{listing_id}", response_model=AdminHackathonRead)
async def update_hackathon(
    listing_id: UUID,
    body: AdminHackathonWrite,
    session: DbSession,
    admin: AdminUser,
) -> AdminHackathonRead:
    service = AdminCatalogueService(session)
    listing = await service.update_hackathon(
        listing_id,
        body,
        actor_id=admin.admin_user_id,
    )
    return service.to_hackathon_read(listing)


@router.delete("/hackathons/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hackathon(
    listing_id: UUID,
    session: DbSession,
    _admin: AdminUser,
) -> Response:
    await AdminCatalogueService(session).delete_listing(listing_id, ListingKind.HACKATHON)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/ai-offers", response_model=AdminAIOfferListResponse)
async def list_ai_offers(
    session: DbSession,
    _admin: AdminUserRead,
    q: Annotated[str | None, Query(max_length=200)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> AdminAIOfferListResponse:
    service = AdminCatalogueService(session)
    items, total = await service.list_ai_offers(query=q, offset=offset, limit=limit)
    return AdminAIOfferListResponse(
        items=[service.to_ai_offer_read(item) for item in items],
        total=total,
    )


@router.post(
    "/ai-offers",
    response_model=AdminAIOfferRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_ai_offer(
    body: AdminAIOfferWrite,
    session: DbSession,
    admin: AdminUser,
) -> AdminAIOfferRead:
    service = AdminCatalogueService(session)
    listing = await service.create_ai_offer(body, actor_id=admin.admin_user_id)
    return service.to_ai_offer_read(listing)


@router.put("/ai-offers/{listing_id}", response_model=AdminAIOfferRead)
async def update_ai_offer(
    listing_id: UUID,
    body: AdminAIOfferWrite,
    session: DbSession,
    admin: AdminUser,
) -> AdminAIOfferRead:
    service = AdminCatalogueService(session)
    listing = await service.update_ai_offer(
        listing_id,
        body,
        actor_id=admin.admin_user_id,
    )
    return service.to_ai_offer_read(listing)


@router.delete("/ai-offers/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_offer(
    listing_id: UUID,
    session: DbSession,
    _admin: AdminUser,
) -> Response:
    await AdminCatalogueService(session).delete_listing(listing_id, ListingKind.AI_OFFER)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
