"""Match catalogue listings against alert subscription filters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.catalog.models import Listing


def match_listing(
    listing: Listing,
    filter_json: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    """Return True if listing matches saved search filters."""
    now = now or datetime.now(UTC)
    status = str(
        getattr(listing.verification_status, "value", listing.verification_status)
    )
    if status not in {
        "verified_active",
        "likely_active",
        "registration_closed",
    }:
        return False

    kind = filter_json.get("kind")
    listing_kind = str(getattr(listing.kind, "value", listing.kind))
    if kind and listing_kind != kind:
        return False

    q = (filter_json.get("q") or filter_json.get("query") or "").strip().lower()
    if q:
        blob = f"{listing.title} {listing.description} {listing.search_extra}".lower()
        if q not in blob:
            return False

    if filter_json.get("onlyClosingSoon") or filter_json.get("only_closing_soon"):
        hack = getattr(listing, "hackathon", None)
        if hack is None or hack.submission_deadline is None:
            return False
        if hack.submission_deadline < now:
            return False
        if hack.submission_deadline > now + timedelta(days=14):
            return False

    status_filter = filter_json.get("status")
    if status_filter:
        allowed = {s.strip() for s in str(status_filter).split(",") if s.strip()}
        if status not in allowed:
            return False

    return True
