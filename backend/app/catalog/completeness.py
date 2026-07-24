"""Field completeness + trust flags for public catalogue cards."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from app.catalog.models import AIOffer, Hackathon, Listing

# Days left used for "closing soon" flag (matches search filter default).
CLOSING_SOON_DAYS = 14

# Hosts that are social / generic hubs — not strong official rules pages.
_WEAK_HOST_SUFFIXES = (
    "x.com",
    "twitter.com",
    "t.co",
    "typeform.com",
    "forms.gle",
    "bit.ly",
    "tinyurl.com",
)

# Bare aggregator roots (no event path) count as weak.
_WEAK_BARE_HOSTS = {
    "devfolio.co",
    "www.devfolio.co",
    "dorahacks.io",
    "www.dorahacks.io",
    "luma.com",
    "www.luma.com",
}


def is_weak_official_url(url: str | None) -> bool:
    if not url or not str(url).strip():
        return True
    try:
        parsed = urlparse(str(url).strip())
    except Exception:
        return True
    host = (parsed.hostname or "").lower()
    if not host:
        return True
    if any(host == s or host.endswith("." + s) for s in _WEAK_HOST_SUFFIXES):
        return True
    path = (parsed.path or "").strip("/")
    if host in _WEAK_BARE_HOSTS and not path:
        return True
    # Bare luma path with only event id is OK; bare domain is weak (above).
    return False


def _as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _has_meaningful_prize(hackathon: Hackathon) -> bool:
    if _as_decimal(hackathon.prize_value) > 0:
        return True
    label = (hackathon.prize_label or "").strip().lower()
    if not label:
        return False
    # Explicit free / TBA still counts as "documented" prize field for completeness,
    # but prize_known is separate.
    return True


def _prize_known(hackathon: Hackathon) -> bool:
    if _as_decimal(hackathon.prize_value) > 0:
        return True
    label = (hackathon.prize_label or "").strip().lower()
    if not label:
        return False
    if "tba" in label or "to be announced" in label or "upcoming" in label:
        return False
    return True


def hackathon_completeness(
    listing: Listing,
    hackathon: Hackathon,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a camelCase-friendly completeness payload for API serialization."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    checks: list[tuple[str, bool]] = []
    has_title = bool((listing.title or "").strip())
    has_description = len((listing.description or "").strip()) >= 40
    has_organizer = bool((hackathon.organizer or "").strip())
    deadline = hackathon.registration_deadline or hackathon.submission_deadline
    has_deadline = deadline is not None
    has_prize_field = _has_meaningful_prize(hackathon)
    prize_known = _prize_known(hackathon)
    has_eligibility = bool(hackathon.eligibility) or bool(hackathon.eligible_countries)
    has_tech = bool(hackathon.technologies)
    url = hackathon.official_url or ""
    has_url = bool(url.strip())
    weak_url = is_weak_official_url(url)
    strong_url = has_url and not weak_url

    checks = [
        ("title", has_title),
        ("description", has_description),
        ("organizer", has_organizer),
        ("deadline", has_deadline),
        ("prize", has_prize_field),
        ("eligibility", has_eligibility),
        ("technologies", has_tech),
        ("officialUrl", strong_url),
    ]
    passed = sum(1 for _, ok in checks if ok)
    score = int(round(100 * passed / len(checks))) if checks else 0
    missing = [name for name, ok in checks if not ok]

    flags: list[str] = []
    if weak_url:
        flags.append("weak_url")
    if not prize_known:
        flags.append("prize_tba")
    if deadline is not None:
        dl = deadline if deadline.tzinfo else deadline.replace(tzinfo=UTC)
        days = (dl - now).total_seconds() / 86400
        if 0 <= days <= CLOSING_SOON_DAYS:
            flags.append("closing_soon")
        if days < 0:
            flags.append("deadline_passed")

    return {
        "score": score,
        "missing": missing,
        "flags": flags,
        "hasDeadline": has_deadline,
        "hasPrize": prize_known,
        "hasStrongUrl": strong_url,
        "hasEligibility": has_eligibility,
        "hasDescription": has_description,
    }


def ai_offer_completeness(
    listing: Listing,
    offer: AIOffer,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    has_title = bool((listing.title or "").strip())
    has_description = len((listing.description or "").strip()) >= 40
    has_product = bool((offer.product_name or "").strip())
    has_provider = bool((offer.provider or "").strip())
    has_value = bool((offer.offer_value or "").strip())
    has_claim = bool((offer.claim_url or "").strip()) and not is_weak_official_url(
        offer.claim_url
    )
    has_terms = bool((offer.official_terms_url or "").strip()) and not is_weak_official_url(
        offer.official_terms_url
    )
    has_audience = bool(offer.target_users) or bool(offer.tags)
    has_regions = bool(offer.supported_regions)

    checks = [
        ("title", has_title),
        ("description", has_description),
        ("product", has_product),
        ("provider", has_provider),
        ("offerValue", has_value),
        ("claimUrl", has_claim),
        ("termsUrl", has_terms),
        ("audience", has_audience),
        ("regions", has_regions),
    ]
    passed = sum(1 for _, ok in checks if ok)
    score = int(round(100 * passed / len(checks))) if checks else 0
    missing = [name for name, ok in checks if not ok]
    flags: list[str] = []
    if is_weak_official_url(offer.claim_url) or is_weak_official_url(
        offer.official_terms_url
    ):
        flags.append("weak_url")
    if offer.expires_at is not None:
        exp = (
            offer.expires_at
            if offer.expires_at.tzinfo
            else offer.expires_at.replace(tzinfo=UTC)
        )
        days = (exp - now).total_seconds() / 86400
        if 0 <= days <= CLOSING_SOON_DAYS:
            flags.append("closing_soon")
        if days < 0:
            flags.append("expired")
    else:
        flags.append("no_expiry")  # permanent / unknown expiry

    return {
        "score": score,
        "missing": missing,
        "flags": flags,
        "hasDeadline": offer.expires_at is not None,
        "hasPrize": has_value,
        "hasStrongUrl": has_claim and has_terms,
        "hasEligibility": has_audience,
        "hasDescription": has_description,
    }
