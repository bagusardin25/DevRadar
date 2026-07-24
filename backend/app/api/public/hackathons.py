"""Public hackathon catalogue endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response

from app.api.dependencies import Catalogue
from app.catalog.enums import HackathonMode
from app.catalog.public_schemas import HackathonCollectionResponse, HackathonPublic
from app.catalog.search import HackathonFilters
from app.catalog.service import listing_etag, parse_status_param

router = APIRouter(prefix="/hackathons", tags=["Hackathons"])


@router.get("", response_model=HackathonCollectionResponse)
async def list_hackathons(
    service: Catalogue,
    q: Annotated[str | None, Query(description="Full-text / fuzzy search")] = None,
    mode: Annotated[HackathonMode | None, Query()] = None,
    region: Annotated[str | None, Query()] = None,
    eligibility: Annotated[str | None, Query()] = None,
    technology: Annotated[str | None, Query()] = None,
    status: Annotated[
        str | None,
        Query(description="Comma-separated statuses; default verified_active,likely_active"),
    ] = None,
    deadline_before: Annotated[datetime | None, Query(alias="deadlineBefore")] = None,
    deadline_after: Annotated[datetime | None, Query(alias="deadlineAfter")] = None,
    team_size: Annotated[int | None, Query(alias="teamSize", ge=1)] = None,
    prize_min: Annotated[Decimal | None, Query(alias="prizeMin", ge=0)] = None,
    only_closing_soon: Annotated[bool, Query(alias="onlyClosingSoon")] = False,
    only_big_prizes: Annotated[bool, Query(alias="onlyBigPrizes")] = False,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> HackathonCollectionResponse:
    filters = HackathonFilters(
        query=q,
        mode=mode,
        region=region,
        eligibility=eligibility,
        technology=technology,
        status=parse_status_param(status),
        deadline_before=deadline_before,
        deadline_after=deadline_after,
        team_size=team_size,
        prize_min=prize_min,
        only_closing_soon=only_closing_soon,
        only_big_prizes=only_big_prizes,
    )
    items, next_cursor, total = await service.search_hackathons(
        filters, cursor=cursor, limit=limit
    )
    return HackathonCollectionResponse(
        items=items,
        next_cursor=next_cursor,
        total_estimate=total,
    )


@router.get("/{slug}", response_model=HackathonPublic)
async def get_hackathon(
    slug: str,
    service: Catalogue,
    response: Response,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
) -> HackathonPublic | Response:
    item = await service.get_hackathon_by_slug(slug)
    etag = listing_etag(item)
    response.headers["ETag"] = etag
    if if_none_match and if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return item
