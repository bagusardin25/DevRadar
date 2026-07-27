"""Schemas for admin review queue."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.catalog.enums import ReviewCandidateType, ReviewItemState
from app.catalog.schemas import CamelModel


class ReviewItemPublic(CamelModel):
    id: UUID
    candidate_type: ReviewCandidateType
    candidate_id: UUID | None = None
    candidate_snapshot: dict[str, Any] = Field(default_factory=dict)
    reason: str
    priority: int
    state: ReviewItemState
    assigned_admin_id: str | None = None
    listing_id: UUID | None = None
    version: int
    resolution: dict[str, Any] | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReviewItemListResponse(CamelModel):
    items: list[ReviewItemPublic]
    total: int


class ApproveReviewRequest(CamelModel):
    expected_version: int = Field(ge=1)
    notes: str | None = None
    # Optional field overrides applied to listing snapshot before publish.
    corrections: dict[str, Any] = Field(default_factory=dict)


class RejectReviewRequest(CamelModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)


class MergeReviewRequest(CamelModel):
    expected_version: int = Field(ge=1)
    target_listing_id: UUID
    notes: str | None = None


class ReviewActionResult(CamelModel):
    item: ReviewItemPublic
    message: str


class AdminMeResponse(CamelModel):
    subject: str
    email: str
    csrf_token: str
