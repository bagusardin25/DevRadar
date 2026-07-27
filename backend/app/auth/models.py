"""ORM model for allowlisted admin users."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdminUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Administrator identified by Google account (allowlist-gated)."""

    __tablename__ = "admin_users"

    # OAuth `sub` — stable, immutable Google account identifier.
    subject: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    allowlist_matched: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
