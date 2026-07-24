"""Versioned Pydantic schemas for structured extraction output."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EXTRACTION_SCHEMA_VERSION = "1.0.0"


class ExtractionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = None
    description: str | None = None
    official_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    raw_notes: str | None = None


class HackathonExtraction(ExtractionBase):
    """Fields the extractor may fill for a hackathon candidate."""

    organizer: str | None = None
    registration_open_at: datetime | None = None
    registration_deadline: datetime | None = None
    submission_deadline: datetime | None = None
    mode: Literal["online", "hybrid", "in_person"] | None = None
    location: str | None = None
    eligible_countries: list[str] = Field(default_factory=list)
    eligibility: list[str] = Field(default_factory=list)
    team_min: int | None = Field(default=None, ge=1)
    team_max: int | None = Field(default=None, ge=1)
    prize_value: Decimal | None = Field(default=None, ge=0)
    prize_currency: str | None = None
    technologies: list[str] = Field(default_factory=list)
    effort_estimate: str | None = None


class AIOfferExtraction(ExtractionBase):
    """Fields the extractor may fill for an AI offer candidate."""

    product_name: str | None = None
    provider: str | None = None
    offer_type: str | None = None
    offer_value: str | None = None
    target_users: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    supported_regions: list[str] = Field(default_factory=list)
    official_terms_url: str | None = None
    claim_url: str | None = None


def validate_extraction_payload(
    listing_kind: str, data: dict[str, Any]
) -> HackathonExtraction | AIOfferExtraction:
    """Validate LLM/rules output against the versioned schema."""
    if listing_kind == "hackathon":
        return HackathonExtraction.model_validate(data)
    if listing_kind == "ai_offer":
        return AIOfferExtraction.model_validate(data)
    raise ValueError(f"Unknown listing kind: {listing_kind}")
