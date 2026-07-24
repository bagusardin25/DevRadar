"""Public catalogue response schemas aligned with frontend `src/types/index.ts`."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from app.catalog.enums import (
    EffortEstimate,
    HackathonMode,
    ListingKind,
    OfferType,
    VerificationStatus,
)
from app.catalog.schemas import CamelModel

DiscoverySourceType = Literal[
    "x", "devpost", "mlh", "official_site", "reddit", "github"
]
PipelineStep = Literal["fetched", "parsed", "extracted", "verified"]


class ScoreBreakdownPublic(CamelModel):
    status_and_deadline: int = Field(ge=0, le=35, default=0)
    keyword_match: int = Field(ge=0, le=25, default=0)
    source_credibility: int = Field(ge=0, le=20, default=0)
    freshness: int = Field(ge=0, le=15, default=0)
    completeness: int = Field(ge=0, le=5, default=0)


class DiscoverySourcePublic(CamelModel):
    type: DiscoverySourceType
    url: str
    author: str | None = None
    post_id: str | None = None
    fetched_at: datetime
    tier: str


class VerificationAuditPublic(CamelModel):
    last_checked_at: datetime | None = None
    confidence_score: Decimal = Field(ge=0, le=1, default=Decimal("0"))
    score_breakdown: ScoreBreakdownPublic = Field(default_factory=ScoreBreakdownPublic)
    verifier_notes: str = ""
    checked_urls: list[str] = Field(default_factory=list)
    pipeline_step: PipelineStep = "verified"


class HackathonPublic(CamelModel):
    id: str
    slug: str
    title: str
    organizer: str
    organizer_logo: str | None = None
    description: str
    registration_open_at: datetime | None = None
    registration_deadline: datetime | None = None
    submission_deadline: datetime | None = None
    mode: HackathonMode
    location: str | None = None
    eligible_countries: list[str] = Field(default_factory=list)
    eligibility: list[str] = Field(default_factory=list)
    team_min: int = 1
    team_max: int = 1
    prize_value: Decimal = Decimal("0")
    prize_currency: str = "USD"
    technologies: list[str] = Field(default_factory=list)
    official_url: str
    discovery_sources: list[DiscoverySourcePublic] = Field(default_factory=list)
    verification_status: VerificationStatus
    confidence_score: Decimal
    last_checked_at: datetime | None = None
    suitable_reasons: list[str] = Field(default_factory=list)
    effort_estimate: EffortEstimate | None = None
    audit: VerificationAuditPublic


class AIOfferPublic(CamelModel):
    id: str
    slug: str
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
    verification_status: VerificationStatus
    confidence_score: Decimal
    last_checked_at: datetime | None = None
    description: str
    tags: list[str] = Field(default_factory=list)
    discovery_sources: list[DiscoverySourcePublic] = Field(default_factory=list)
    suitable_reasons: list[str] = Field(default_factory=list)
    audit: VerificationAuditPublic


class CombinedSearchItem(CamelModel):
    """Combined search hit with a kind discriminant."""

    kind: ListingKind
    item: HackathonPublic | AIOfferPublic


class CollectionResponse(CamelModel):
    items: list[Any]
    next_cursor: str | None = None
    total_estimate: int = 0


class HackathonCollectionResponse(CamelModel):
    items: list[HackathonPublic]
    next_cursor: str | None = None
    total_estimate: int = 0


class AIOfferCollectionResponse(CamelModel):
    items: list[AIOfferPublic]
    next_cursor: str | None = None
    total_estimate: int = 0


class CombinedSearchResponse(CamelModel):
    items: list[CombinedSearchItem]
    next_cursor: str | None = None
    total_estimate: int = 0


class CatalogueStatsResponse(CamelModel):
    hackathons_active: int = 0
    ai_offers_active: int = 0
    sources_enabled: int = 0
    last_indexed_at: datetime | None = None


class FilterMetaResponse(CamelModel):
    technologies: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    eligibility_labels: list[str] = Field(default_factory=list)
    offer_types: list[str] = Field(default_factory=list)
    modes: list[str] = Field(default_factory=list)
    verification_statuses: list[str] = Field(default_factory=list)
