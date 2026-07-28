"""Public alert API schemas."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import EmailStr, Field, field_validator

from app.catalog.schemas import CamelModel


class AlertCreateRequest(CamelModel):
    email: EmailStr
    filters: dict[str, Any] = Field(default_factory=dict, max_length=20)
    cadence: Literal["instant", "daily", "weekly"] = "daily"
    # Honeypot
    website: str | None = Field(default=None, max_length=200)

    @field_validator("filters")
    @classmethod
    def bound_filters(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Keep stored/matched filter state cheap even for hostile JSON."""
        try:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("filters must be JSON-compatible") from exc
        if len(encoded.encode("utf-8")) > 8192:
            raise ValueError("filters must be at most 8192 bytes")

        text_limits = {
            "q": 200,
            "query": 200,
            "searchQuery": 200,
            "search_query": 200,
            "technology": 100,
            "technologies": 100,
            "tech": 100,
            "region": 100,
            "mode": 32,
            "offerType": 64,
            "offer_type": 64,
            "status": 200,
            "verificationStatus": 200,
        }
        for key, limit in text_limits.items():
            raw = value.get(key)
            values = raw if isinstance(raw, list) else [raw]
            if len(values) > 10:
                raise ValueError(f"filters.{key} accepts at most 10 values")
            if any(item is not None and len(str(item)) > limit for item in values):
                raise ValueError(f"filters.{key} is too long")
        return value


class AlertCreateResponse(CamelModel):
    status: str = "pending_confirmation"
    message: str = "Check your email to confirm the subscription"


class AlertStatusResponse(CamelModel):
    confirmed: bool
    unsubscribed: bool
    cadence: str
    created_at: datetime | None = None
