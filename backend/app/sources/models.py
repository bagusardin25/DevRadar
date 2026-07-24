"""ORM models for the source registry and scheduled queries."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.catalog.enums import ConnectorType, SourceTier
from app.db import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.ingestion.models import CrawlRun, DiscoverySignal, RawDocument


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Curated ingestion source. Secrets are never stored here."""

    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    connector_type: Mapped[ConnectorType] = mapped_column(Text, nullable=False, index=True)
    trust_tier: Mapped[SourceTier] = mapped_column(Text, nullable=False, index=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    polling_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    fetch_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    # Environment key name only — never the secret value.
    credential_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    queries: Mapped[list[SourceQuery]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
    crawl_runs: Mapped[list[CrawlRun]] = relationship(back_populates="source")
    raw_documents: Mapped[list[RawDocument]] = relationship(back_populates="source")
    discovery_signals: Mapped[list[DiscoverySignal]] = relationship(back_populates="source")


class SourceQuery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Scheduled query / poll configuration against a source."""

    __tablename__ = "source_queries"

    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module: Mapped[str] = mapped_column(Text, nullable=False)  # hackathon | ai_offer
    name: Mapped[str] = mapped_column(Text, nullable=False)
    query_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    curated_accounts: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    # Cron-like or interval seconds stored as JSON for flexibility.
    schedule: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{\"interval_seconds\": 86400}'::jsonb"),
    )
    result_cap: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("50"))
    cost_budget: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_run_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    # Lease so only one scheduler instance enqueues a poll.
    lease_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    source: Mapped[Source] = relationship(back_populates="queries")
    crawl_runs: Mapped[list[CrawlRun]] = relationship(back_populates="source_query")
