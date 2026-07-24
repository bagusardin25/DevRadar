"""Admin review queue endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.dependencies import AdminUser, AdminUserRead, ReviewSvc
from app.catalog.enums import ReviewItemState
from app.review.schemas import (
    ApproveReviewRequest,
    MergeReviewRequest,
    RejectReviewRequest,
    ReviewActionResult,
    ReviewItemListResponse,
    ReviewItemPublic,
)
from app.review.service import ReviewService

router = APIRouter(prefix="/admin/review-items", tags=["Admin Review"])


@router.get("", response_model=ReviewItemListResponse)
async def list_review_items(
    service: ReviewSvc,
    _admin: AdminUserRead,
    state: Annotated[ReviewItemState | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReviewItemListResponse:
    items, total = await service.list_items(state=state, limit=limit)
    return ReviewItemListResponse(
        items=[ReviewService.to_public(i) for i in items],
        total=total,
    )


@router.get("/{item_id}", response_model=ReviewItemPublic)
async def get_review_item(
    item_id: UUID,
    service: ReviewSvc,
    _admin: AdminUserRead,
) -> ReviewItemPublic:
    item = await service.get_item(item_id)
    return ReviewService.to_public(item)


@router.post("/{item_id}/approve", response_model=ReviewActionResult)
async def approve_review_item(
    item_id: UUID,
    body: ApproveReviewRequest,
    request: Request,
    service: ReviewSvc,
    admin: AdminUser,
) -> ReviewActionResult:
    trace_id = getattr(request.state, "trace_id", None)
    item = await service.approve_review_item(
        item_id, body, admin, trace_id=trace_id
    )
    return ReviewActionResult(
        item=ReviewService.to_public(item),
        message="Review item approved",
    )


@router.post("/{item_id}/reject", response_model=ReviewActionResult)
async def reject_review_item(
    item_id: UUID,
    body: RejectReviewRequest,
    request: Request,
    service: ReviewSvc,
    admin: AdminUser,
) -> ReviewActionResult:
    trace_id = getattr(request.state, "trace_id", None)
    item = await service.reject_review_item(
        item_id, body, admin, trace_id=trace_id
    )
    return ReviewActionResult(
        item=ReviewService.to_public(item),
        message="Review item rejected",
    )


@router.post("/{item_id}/merge", response_model=ReviewActionResult)
async def merge_review_item(
    item_id: UUID,
    body: MergeReviewRequest,
    request: Request,
    service: ReviewSvc,
    admin: AdminUser,
) -> ReviewActionResult:
    trace_id = getattr(request.state, "trace_id", None)
    item = await service.merge_review_item(
        item_id, body, admin, trace_id=trace_id
    )
    return ReviewActionResult(
        item=ReviewService.to_public(item),
        message="Review item merged",
    )
