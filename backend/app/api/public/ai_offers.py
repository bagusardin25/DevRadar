"""Public AI offer catalogue endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Response

from app.api.dependencies import Catalogue
from app.api.limits import (
    MAX_CURSOR_LENGTH,
    MAX_FILTER_VALUE_LENGTH,
    MAX_SEARCH_QUERY_LENGTH,
    MAX_SLUG_LENGTH,
    MAX_STATUS_PARAM_LENGTH,
    MAX_TAGS_PARAM_LENGTH,
)
from app.catalog.enums import OfferType
from app.catalog.public_schemas import AIOfferCollectionResponse, AIOfferPublic
from app.catalog.search import AIOfferFilters, parse_tag_filters
from app.catalog.service import listing_etag, parse_status_param

router = APIRouter(prefix="/ai-offers", tags=["AI Offers"])


@router.get("", response_model=AIOfferCollectionResponse)
async def list_ai_offers(
    service: Catalogue,
    q: Annotated[
        str | None,
        Query(max_length=MAX_SEARCH_QUERY_LENGTH, description="Full-text / fuzzy search"),
    ] = None,
    offer_type: Annotated[OfferType | None, Query(alias="offerType")] = None,
    target_user: Annotated[
        str | None, Query(alias="targetUser", max_length=MAX_FILTER_VALUE_LENGTH)
    ] = None,
    region: Annotated[str | None, Query(max_length=MAX_FILTER_VALUE_LENGTH)] = None,
    status: Annotated[
        str | None,
        Query(
            max_length=MAX_STATUS_PARAM_LENGTH,
            description="Comma-separated statuses; default verified_active,likely_active",
        ),
    ] = None,
    expires_before: Annotated[datetime | None, Query(alias="expiresBefore")] = None,
    expires_after: Annotated[datetime | None, Query(alias="expiresAfter")] = None,
    tags: Annotated[
        str | None,
        Query(max_length=MAX_TAGS_PARAM_LENGTH, description="Comma-separated tags"),
    ] = None,
    only_free_no_card: Annotated[bool, Query(alias="onlyFreeNoCard")] = False,
    cursor: Annotated[str | None, Query(max_length=MAX_CURSOR_LENGTH)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> AIOfferCollectionResponse:
    tag_list = parse_tag_filters(tags)
    filters = AIOfferFilters(
        query=q,
        offer_type=offer_type,
        target_user=target_user,
        region=region,
        status=parse_status_param(status),
        expires_before=expires_before,
        expires_after=expires_after,
        tags=tag_list,
        only_free_no_card=only_free_no_card,
    )
    items, next_cursor, total = await service.search_ai_offers(
        filters, cursor=cursor, limit=limit
    )
    return AIOfferCollectionResponse(
        items=items,
        next_cursor=next_cursor,
        total_estimate=total,
    )


@router.get("/{slug}", response_model=AIOfferPublic)
async def get_ai_offer(
    slug: Annotated[str, Path(min_length=1, max_length=MAX_SLUG_LENGTH)],
    service: Catalogue,
    response: Response,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
) -> AIOfferPublic | Response:
    item = await service.get_ai_offer_by_slug(slug)
    etag = listing_etag(item)
    response.headers["ETag"] = etag
    if if_none_match and if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return item
