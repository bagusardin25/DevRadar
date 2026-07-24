"""Combined search, stats, and filter metadata endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import Catalogue
from app.catalog.enums import ListingKind
from app.catalog.public_schemas import (
    CatalogueStatsResponse,
    CombinedSearchResponse,
    FilterMetaResponse,
)
from app.catalog.service import parse_status_param

router = APIRouter(tags=["Search"])


@router.get("/search", response_model=CombinedSearchResponse)
async def combined_search(
    service: Catalogue,
    q: Annotated[str | None, Query(description="Full-text / fuzzy search")] = None,
    kind: Annotated[ListingKind | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> CombinedSearchResponse:
    items, next_cursor, total = await service.combined_search(
        query=q,
        kind=kind,
        status=parse_status_param(status),
        cursor=cursor,
        limit=limit,
    )
    return CombinedSearchResponse(
        items=items,
        next_cursor=next_cursor,
        total_estimate=total,
    )


@router.get("/stats", response_model=CatalogueStatsResponse)
async def catalogue_stats(service: Catalogue) -> CatalogueStatsResponse:
    return await service.stats()


@router.get("/meta/filters", response_model=FilterMetaResponse)
async def filter_meta(service: Catalogue) -> FilterMetaResponse:
    return await service.filter_meta()
