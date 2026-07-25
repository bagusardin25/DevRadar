"""Match catalogue listings against alert subscription filters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.catalog.models import Listing

# Active statuses that may generate alerts (never expired/cancelled).
_ALERTABLE_STATUSES = frozenset(
    {
        "verified_active",
        "likely_active",
        "registration_closed",
    }
)


def _as_str(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _tech_blob(listing: Listing) -> str:
    parts: list[str] = []
    hack = getattr(listing, "hackathon", None)
    offer = getattr(listing, "ai_offer", None)
    if hack is not None:
        parts.extend(hack.technologies or [])
    if offer is not None:
        parts.extend(getattr(offer, "tags", None) or [])
    parts.append(listing.search_extra or "")
    parts.append(listing.title or "")
    parts.append(listing.description or "")
    return " ".join(parts).lower()


def _region_blob(listing: Listing) -> str:
    parts: list[str] = []
    hack = getattr(listing, "hackathon", None)
    offer = getattr(listing, "ai_offer", None)
    if hack is not None:
        parts.extend(hack.eligible_countries or [])
        parts.extend(hack.eligibility or [])
        if hack.location:
            parts.append(hack.location)
    if offer is not None:
        parts.extend(getattr(offer, "supported_regions", None) or [])
        parts.extend(getattr(offer, "target_users", None) or [])
    return " ".join(parts).lower()


def _deadline_for_closing(listing: Listing) -> datetime | None:
    """Prefer registration deadline, then submission / offer expiry."""
    hack = getattr(listing, "hackathon", None)
    if hack is not None:
        return hack.registration_deadline or hack.submission_deadline
    offer = getattr(listing, "ai_offer", None)
    if offer is not None:
        return getattr(offer, "expires_at", None)
    return None


def _prize_value(listing: Listing) -> Decimal:
    hack = getattr(listing, "hackathon", None)
    if hack is None:
        return Decimal("0")
    return _decimal(hack.prize_value)


def match_listing(
    listing: Listing,
    filter_json: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    """Return True if listing matches saved search filters.

    Supported filter keys (camelCase or snake_case):
      kind / targetType
      q / query / searchQuery
      mode
      technology / technologies / tech
      minPrize / prizeMin / min_prize / onlyBigPrizes
      onlyClosingSoon / only_closing_soon / closingSoonDays
      status
      offerType / offer_type
      region
    """
    now = now or datetime.now(UTC)
    filters = filter_json or {}

    status = _as_str(listing.verification_status)
    if status not in _ALERTABLE_STATUSES:
        return False

    # Explicit status allow-list (comma-separated or list)
    status_filter = filters.get("status") or filters.get("verificationStatus")
    if status_filter:
        allowed = {_as_str(s).strip() for s in _as_list(status_filter)}
        if status not in allowed:
            return False

    # Kind / target type
    kind = (
        filters.get("kind")
        or filters.get("targetType")
        or filters.get("target_type")
        or ""
    )
    kind = _as_str(kind).strip().lower()
    listing_kind = _as_str(listing.kind)
    if kind and kind not in {"all", "*"}:
        # Frontend sometimes uses "ai_deal"
        if kind == "ai_deal":
            kind = "ai_offer"
        if listing_kind != kind:
            return False

    # Free-text query
    q = (
        filters.get("q")
        or filters.get("query")
        or filters.get("searchQuery")
        or filters.get("search_query")
        or ""
    )
    q = str(q).strip().lower()
    if q:
        blob = f"{listing.title} {listing.description} {listing.search_extra}".lower()
        if q not in blob:
            return False

    # Mode (hackathons)
    mode = filters.get("mode")
    if mode and str(mode).strip().lower() not in {"", "all"}:
        hack = getattr(listing, "hackathon", None)
        if hack is None:
            return False
        if _as_str(hack.mode).lower() != str(mode).strip().lower():
            return False

    # Technology / tags
    tech_raw = (
        filters.get("technology")
        or filters.get("technologies")
        or filters.get("tech")
        or ""
    )
    tech_terms = [t.lower() for t in _as_list(tech_raw)]
    if tech_terms:
        blob = _tech_blob(listing)
        if not any(term in blob for term in tech_terms):
            return False

    # Region
    region = str(filters.get("region") or "").strip().lower()
    if region:
        if region not in _region_blob(listing):
            return False

    # Offer type (AI deals)
    offer_type = filters.get("offerType") or filters.get("offer_type")
    if offer_type and str(offer_type).strip():
        offer = getattr(listing, "ai_offer", None)
        if offer is None:
            return False
        if _as_str(offer.offer_type).lower() != str(offer_type).strip().lower():
            return False

    # Prize minimum / big prizes
    only_big = bool(filters.get("onlyBigPrizes") or filters.get("only_big_prizes"))
    min_prize_raw = (
        filters.get("minPrize")
        or filters.get("prizeMin")
        or filters.get("min_prize")
        or filters.get("prize_min")
    )
    if only_big and min_prize_raw is None:
        min_prize_raw = 10_000
    if min_prize_raw is not None and str(min_prize_raw).strip() != "":
        if listing_kind != "hackathon":
            return False
        if _prize_value(listing) < _decimal(min_prize_raw):
            return False

    # Closing soon window
    closing_soon = bool(
        filters.get("onlyClosingSoon")
        or filters.get("only_closing_soon")
        or filters.get("closingSoon")
    )
    days_raw = filters.get("closingSoonDays") or filters.get("closing_soon_days")
    try:
        window_days = int(days_raw) if days_raw is not None else 14
    except (TypeError, ValueError):
        window_days = 14
    if closing_soon:
        deadline = _deadline_for_closing(listing)
        if deadline is None:
            return False
        # Normalize naive → UTC for comparison
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        if deadline < now:
            return False
        if deadline > now + timedelta(days=window_days):
            return False

    return True


def normalize_alert_filters(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Canonicalize client filter payloads for storage."""
    if not raw:
        return {}
    out: dict[str, Any] = {}

    kind = raw.get("kind") or raw.get("targetType") or raw.get("target_type")
    if kind and str(kind).strip().lower() not in {"", "all", "*"}:
        k = str(kind).strip().lower()
        if k == "ai_deal":
            k = "ai_offer"
        out["kind"] = k

    q = raw.get("q") or raw.get("query") or raw.get("searchQuery") or raw.get("search_query")
    if q and str(q).strip():
        out["q"] = str(q).strip()

    mode = raw.get("mode")
    if mode and str(mode).strip().lower() not in {"", "all"}:
        out["mode"] = str(mode).strip().lower()

    tech = raw.get("technology") or raw.get("technologies") or raw.get("tech")
    terms = _as_list(tech)
    if terms:
        out["technology"] = terms[0] if len(terms) == 1 else terms

    region = raw.get("region")
    if region and str(region).strip():
        out["region"] = str(region).strip()

    offer_type = raw.get("offerType") or raw.get("offer_type")
    if offer_type and str(offer_type).strip():
        out["offerType"] = str(offer_type).strip()

    status = raw.get("status") or raw.get("verificationStatus")
    if status and str(status).strip():
        out["status"] = str(status).strip() if isinstance(status, str) else ",".join(_as_list(status))

    min_prize = (
        raw.get("minPrize")
        or raw.get("prizeMin")
        or raw.get("min_prize")
        or raw.get("prize_min")
    )
    if min_prize is not None and str(min_prize).strip() != "":
        try:
            out["minPrize"] = float(min_prize)
        except (TypeError, ValueError):
            pass
    elif raw.get("onlyBigPrizes") or raw.get("only_big_prizes"):
        out["onlyBigPrizes"] = True

    if raw.get("onlyClosingSoon") or raw.get("only_closing_soon") or raw.get("closingSoon"):
        out["onlyClosingSoon"] = True
        days = raw.get("closingSoonDays") or raw.get("closing_soon_days")
        if days is not None:
            try:
                out["closingSoonDays"] = int(days)
            except (TypeError, ValueError):
                out["closingSoonDays"] = 14

    return out
