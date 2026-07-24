"""ORM models for the public catalogue (listings, hackathons, AI offers)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.catalog.enums import (
    EffortEstimate,
    HackathonMode,
    ListingKind,
    OfferType,
    VerificationStatus,
)
from app.db import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.ingestion.models import ListingSource, VerificationEvent


class Listing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Common parent row for every searchable opportunity."""

    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="confidence_score_range",
        ),
        Index("ix_listings_kind_status_published", "kind", "verification_status", "published_at"),
        Index("ix_listings_last_checked_at", "last_checked_at"),
        Index(
            "ix_listings_search_document",
            "search_document",
            postgresql_using="gin",
        ),
        Index(
            "ix_listings_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    kind: Mapped[ListingKind] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{VerificationStatus.NEEDS_REVIEW.value}'"),
        index=True,
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default=text("0"),
    )
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    # Denormalized organizer/provider + tags for full-text search generation.
    search_extra: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    search_document: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('english', coalesce(description, '')), 'B') || "
            "setweight(to_tsvector('english', coalesce(search_extra, '')), 'C')",
            persisted=True,
        ),
        nullable=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    hackathon: Mapped[Hackathon | None] = relationship(
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )
    ai_offer: Mapped[AIOffer | None] = relationship(
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )
    listing_sources: Mapped[list[ListingSource]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
    )
    verification_events: Mapped[list[VerificationEvent]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="VerificationEvent.created_at",
    )


class Hackathon(TimestampMixin, Base):
    """Hackathon-specific fields, 1:1 with listings."""

    __tablename__ = "hackathons"
    __table_args__ = (
        CheckConstraint("team_min >= 1", name="team_min_positive"),
        CheckConstraint("team_max >= team_min", name="team_max_gte_min"),
        CheckConstraint("prize_value >= 0", name="prize_non_negative"),
        Index("ix_hackathons_technologies", "technologies", postgresql_using="gin"),
        Index("ix_hackathons_eligible_countries", "eligible_countries", postgresql_using="gin"),
        Index("ix_hackathons_eligibility", "eligibility", postgresql_using="gin"),
        Index("ix_hackathons_submission_deadline", "submission_deadline"),
    )

    listing_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organizer: Mapped[str] = mapped_column(Text, nullable=False)
    organizer_logo: Mapped[str | None] = mapped_column(Text, nullable=True)
    registration_open_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    registration_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submission_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mode: Mapped[HackathonMode] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    eligible_countries: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    eligibility: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    team_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    team_max: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    prize_value: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        server_default=text("0"),
    )
    prize_currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'USD'"))
    technologies: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    official_url: Mapped[str] = mapped_column(Text, nullable=False)
    suitable_reasons: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    effort_estimate: Mapped[EffortEstimate | None] = mapped_column(Text, nullable=True)

    listing: Mapped[Listing] = relationship(back_populates="hackathon")


class AIOffer(TimestampMixin, Base):
    """AI offer / deal fields, 1:1 with listings."""

    __tablename__ = "ai_offers"
    __table_args__ = (
        Index("ix_ai_offers_tags", "tags", postgresql_using="gin"),
        Index("ix_ai_offers_supported_regions", "supported_regions", postgresql_using="gin"),
        Index("ix_ai_offers_expires_at", "expires_at"),
        Index("ix_ai_offers_offer_type", "offer_type"),
    )

    listing_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_logo: Mapped[str | None] = mapped_column(Text, nullable=True)
    offer_type: Mapped[OfferType] = mapped_column(Text, nullable=False)
    offer_value: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    target_users: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    requirements: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supported_regions: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    official_terms_url: Mapped[str] = mapped_column(Text, nullable=False)
    claim_url: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    suitable_reasons: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )

    listing: Mapped[Listing] = relationship(back_populates="ai_offer")
