"""Public alert API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field

from app.catalog.schemas import CamelModel


class AlertCreateRequest(CamelModel):
    email: EmailStr
    filters: dict[str, Any] = Field(default_factory=dict)
    cadence: str = "daily"
    # Honeypot
    website: str | None = None


class AlertCreateResponse(CamelModel):
    status: str = "pending_confirmation"
    message: str = "Check your email to confirm the subscription"


class AlertStatusResponse(CamelModel):
    confirmed: bool
    unsubscribed: bool
    cadence: str
    created_at: datetime | None = None
