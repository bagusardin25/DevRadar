"""Pydantic schemas for catalogue entities (camelCase API surface)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.catalog.enums import (
    EffortEstimate,
    HackathonMode,
    ListingKind,
    OfferType,
    VerificationStatus,
)


class CamelModel(BaseModel):
    """Base model that serializes fields as camelCase for the frontend."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ScoreBreakdownSchema(CamelModel):
    """Five deterministic score components (points out of 100 components)."""

    status_and_deadline: int = Field(ge=0, le=35)
    keyword_match: int = Field(ge=0, le=25)
    source_credibility: int = Field(ge=0, le=20)
    freshness: int = Field(ge=0, le=15)
    completeness: int = Field(ge=0, le=5)


class ListingBaseSchema(CamelModel):
    kind: ListingKind
    slug: str
    title: str
    description: str = ""
    verification_status: VerificationStatus = VerificationStatus.NEEDS_REVIEW
    confidence_score: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    search_extra: str = ""


class ListingCreateSchema(ListingBaseSchema):
    first_seen_at: datetime | None = None
    published_at: datetime | None = None
    last_checked_at: datetime | None = None


class ListingReadSchema(ListingBaseSchema):
    id: UUID
    first_seen_at: datetime
    published_at: datetime | None
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class HackathonCreateSchema(CamelModel):
    organizer: str
    organizer_logo: str | None = None
    registration_open_at: datetime | None = None
    registration_deadline: datetime | None = None
    submission_deadline: datetime | None = None
    mode: HackathonMode
    location: str | None = None
    eligible_countries: list[str] = Field(default_factory=list)
    eligibility: list[str] = Field(default_factory=list)
    team_min: int = Field(default=1, ge=1)
    team_max: int = Field(default=1, ge=1)
    prize_value: Decimal = Field(default=Decimal("0"), ge=0)
    prize_currency: str = "USD"
    technologies: list[str] = Field(default_factory=list)
    official_url: str
    suitable_reasons: list[str] = Field(default_factory=list)
    effort_estimate: EffortEstimate | None = None


class HackathonReadSchema(HackathonCreateSchema):
    listing_id: UUID
    created_at: datetime
    updated_at: datetime


class AIOfferCreateSchema(CamelModel):
    product_name: str
    provider: str
    provider_logo: str | None = None
    offer_type: OfferType
    offer_value: str = ""
    target_users: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    supported_regions: list[str] = Field(default_factory=list)
    official_terms_url: str
    claim_url: str
    tags: list[str] = Field(default_factory=list)
    suitable_reasons: list[str] = Field(default_factory=list)


class AIOfferReadSchema(AIOfferCreateSchema):
    listing_id: UUID
    created_at: datetime
    updated_at: datetime
