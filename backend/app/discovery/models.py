"""Live discovery run model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LiveDiscoveryRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "live_discovery_runs"

    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'queued'")
    )
    connector_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    result_cap: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("10"))
    verified_listing_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    request_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(Text, nullable=False)
    cost_units: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
