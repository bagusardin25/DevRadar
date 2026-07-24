"""ORM model for community opportunity submissions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.catalog.enums import SubmissionState
from app.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CommunitySubmission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """URL submitted by an anonymous visitor for verification."""

    __tablename__ = "community_submissions"
    __table_args__ = (
        Index("ix_community_submissions_canonical_url", "canonical_url"),
        Index("ix_community_submissions_state", "state"),
        Index("ix_community_submissions_created_at", "created_at"),
    )

    # Opaque public tracking token (not sequential).
    tracking_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    claimed_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional submitter contact — never store plaintext email.
    submitter_email_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitter_email_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Abuse identifiers (HMAC / SHA-256 hashes only).
    ip_hash: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    state: Mapped[SubmissionState] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{SubmissionState.RECEIVED.value}'"),
    )
    # Self-reference when this submission duplicates an earlier one.
    duplicate_of_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("community_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Client Idempotency-Key (unique when present).
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    # Job key: hash(canonical_url + time_bucket).
    job_idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Sanitized metadata for operators (no secrets / raw bodies).
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
