"""Pydantic schemas for community submissions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.catalog.enums import ListingKind, SubmissionState
from app.catalog.schemas import CamelModel

ClaimedType = Literal["hackathon", "ai_offer"]


class SubmissionCreateRequest(CamelModel):
    """Public POST /submissions body."""

    url: str = Field(min_length=1, max_length=2048)
    claimed_type: ClaimedType | None = None
    claimed_title: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)
    email: str | None = Field(default=None, max_length=320)
    # Honeypot — must remain empty; bots often fill hidden fields.
    website: str | None = Field(default=None, max_length=200)
    # Client-side form open timestamp (unix seconds). Used for min-submit-time.
    form_opened_at: float | None = None

    @field_validator("url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()


class SubmissionReceipt(CamelModel):
    """202 response after accepting a submission."""

    tracking_id: str
    status: SubmissionState
    message: str = "Submission received and queued for verification"
    duplicate: bool = False


class SubmissionReviewConcernPublic(CamelModel):
    severity: Literal["high", "medium", "low"]
    message: str


class SubmissionReviewPublic(CamelModel):
    """Sanitized AI pre-review visible only through the opaque tracking token."""

    recommendation: Literal["approve", "reject", "needs_more_info"]
    confidence: int = Field(ge=0, le=100)
    summary: str
    concerns: list[SubmissionReviewConcernPublic] = Field(default_factory=list)
    generated_at: datetime | None = None


class SubmissionStatusPublic(CamelModel):
    """Coarse public status — no reviewer notes or internal IDs."""

    tracking_id: str
    status: SubmissionState
    submitted_at: datetime
    claimed_type: ListingKind | None = None
    message: str
    reviewed_at: datetime | None = None
    review: SubmissionReviewPublic | None = None
