"""ORM models for crawl runs, raw documents, extraction, and verification."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.catalog.enums import (
    ActorType,
    CrawlRunStatus,
    CrawlTrigger,
    DocumentAvailability,
    ExtractionStatus,
    VerificationStatus,
)
from app.catalog.models import Listing
from app.db import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.sources.models import Source, SourceQuery


class CrawlRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One poll / crawl execution for observability and retries."""

    __tablename__ = "crawl_runs"
    __table_args__ = (
        Index("ix_crawl_runs_status_started", "status", "started_at"),
        Index("ix_crawl_runs_trace_id", "trace_id"),
    )

    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_query_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_queries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trigger: Mapped[CrawlTrigger] = mapped_column(Text, nullable=False)
    status: Mapped[CrawlRunStatus] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{CrawlRunStatus.QUEUED.value}'"),
        index=True,
    )
    discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    cost_units: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sanitized error only — never raw document bodies or secrets.
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Idempotency for scheduled windows / retries.
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)

    source: Mapped[Source] = relationship(back_populates="crawl_runs")
    source_query: Mapped[SourceQuery | None] = relationship(back_populates="crawl_runs")
    raw_documents: Mapped[list[RawDocument]] = relationship(back_populates="crawl_run")


class RawDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Fetched source document stored by content hash in object storage."""

    __tablename__ = "raw_documents"
    __table_args__ = (
        Index("ix_raw_documents_content_hash", "content_hash"),
        Index("ix_raw_documents_canonical_url", "canonical_url"),
        UniqueConstraint("content_hash", "canonical_url", name="uq_raw_documents_hash_url"),
    )

    source_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    crawl_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("crawl_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)  # SHA-256 hex
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_modified: Mapped[str | None] = mapped_column(Text, nullable=True)
    byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_class: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'standard'")
    )
    availability: Mapped[DocumentAvailability] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{DocumentAvailability.AVAILABLE.value}'"),
    )
    http_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    source: Mapped[Source | None] = relationship(back_populates="raw_documents")
    crawl_run: Mapped[CrawlRun | None] = relationship(back_populates="raw_documents")
    extraction_runs: Mapped[list[ExtractionRun]] = relationship(back_populates="raw_document")
    listing_sources: Mapped[list[ListingSource]] = relationship(back_populates="raw_document")


class DiscoverySignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tier-3 discovery signal (e.g. X post metadata). Post text is not retained."""

    __tablename__ = "discovery_signals"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_discovery_signals_source_external"),
        Index("ix_discovery_signals_review_state", "review_state"),
    )

    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(Text, nullable=False)  # post ID etc.
    url: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    discovered_urls: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    extracted_information: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    review_state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{VerificationStatus.NEEDS_REVIEW.value}'"),
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped[Source] = relationship(back_populates="discovery_signals")


class ListingSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Provenance link between a listing and an observed source URL."""

    __tablename__ = "listing_sources"
    __table_args__ = (
        UniqueConstraint(
            "listing_id",
            "source_id",
            "source_url",
            name="uq_listing_sources_listing_source_url",
        ),
    )

    listing_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    raw_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("raw_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    observed_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    listing: Mapped[Listing] = relationship(back_populates="listing_sources")
    raw_document: Mapped[RawDocument | None] = relationship(back_populates="listing_sources")


class ExtractionRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One structured extraction attempt against a raw document."""

    __tablename__ = "extraction_runs"
    __table_args__ = (Index("ix_extraction_runs_status", "status"),)

    raw_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("raw_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extractor_version: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    token_usage: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    cost_units: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[ExtractionStatus] = mapped_column(Text, nullable=False)
    error_category: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_document: Mapped[RawDocument] = relationship(back_populates="extraction_runs")


class VerificationEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only verification audit trail for a listing."""

    __tablename__ = "verification_events"
    __table_args__ = (Index("ix_verification_events_listing_created", "listing_id", "created_at"),)

    listing_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    previous_status: Mapped[VerificationStatus | None] = mapped_column(Text, nullable=True)
    new_status: Mapped[VerificationStatus] = mapped_column(Text, nullable=False)
    checked_urls: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    deterministic_checks: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[ActorType] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{ActorType.SYSTEM.value}'"),
    )
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    listing: Mapped[Listing] = relationship(back_populates="verification_events")
