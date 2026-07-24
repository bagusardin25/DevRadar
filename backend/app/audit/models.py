"""ORM models for immutable admin audit logging."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UUIDPrimaryKeyMixin


class AdminAuditLog(UUIDPrimaryKeyMixin, Base):
    """Append-only record of admin mutations (no updates/deletes in app code)."""

    __tablename__ = "admin_audit_log"

    actor_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    actor_login: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    request_trace_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
