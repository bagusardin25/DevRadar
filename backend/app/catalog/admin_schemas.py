"""Admin catalogue request/response schemas.

The public catalogue intentionally exposes a curated projection. Admin CRUD
uses aggregate-shaped schemas so operators can edit every content field
without making system metadata (IDs and timestamps) writable.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.catalog.enums import ListingKind, VerificationStatus
from app.catalog.schemas import (
    AIOfferCreateSchema,
    AIOfferReadSchema,
    CamelModel,
    HackathonCreateSchema,
    HackathonReadSchema,
)


class AdminListingWrite(CamelModel):
    """Editable fields shared by hackathons and AI offers."""

    slug: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    verification_status: VerificationStatus = VerificationStatus.NEEDS_REVIEW
    confidence_score: Decimal = Field(default=Decimal("0"), ge=0, le=1)


class AdminListingRead(AdminListingWrite):
    id: UUID
    kind: ListingKind
    first_seen_at: datetime
    published_at: datetime | None = None
    last_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminHackathonWrite(CamelModel):
    listing: AdminListingWrite
    hackathon: HackathonCreateSchema

    @model_validator(mode="after")
    def validate_team_range(self) -> AdminHackathonWrite:
        if self.hackathon.team_max < self.hackathon.team_min:
            raise ValueError("teamMax must be greater than or equal to teamMin")
        return self


class AdminAIOfferWrite(CamelModel):
    listing: AdminListingWrite
    ai_offer: AIOfferCreateSchema


class AdminHackathonRead(CamelModel):
    listing: AdminListingRead
    hackathon: HackathonReadSchema


class AdminAIOfferRead(CamelModel):
    listing: AdminListingRead
    ai_offer: AIOfferReadSchema


class AdminHackathonListResponse(CamelModel):
    items: list[AdminHackathonRead]
    total: int


class AdminAIOfferListResponse(CamelModel):
    items: list[AdminAIOfferRead]
    total: int

