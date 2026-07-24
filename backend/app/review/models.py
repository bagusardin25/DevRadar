"""ORM models for the admin review queue."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.catalog.enums import ReviewCandidateType, ReviewItemState
from app.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReviewItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Human review queue entry for candidates needing attention."""

    __tablename__ = "review_items"

    candidate_type: Mapped[ReviewCandidateType] = mapped_column(
        Text, nullable=False, index=True
    )
    candidate_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    candidate_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("50"), index=True
    )
    state: Mapped[ReviewItemState] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{ReviewItemState.OPEN.value}'"),
        index=True,
    )
    assigned_admin_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    extraction_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    listing_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Optimistic concurrency for simultaneous admin actions.
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    resolution: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
