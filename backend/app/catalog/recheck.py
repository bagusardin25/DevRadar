"""Recheck published listings by re-fetching official URLs and re-extracting fields.

Safe merge policy:
- Never invent missing prizes/deadlines if extraction fails.
- Only overwrite string fields when extraction returns non-empty values.
- Always bump last_checked_at and append a verification_event.
- Works with LLM_PROVIDER=disabled (rules-only) or openai (hybrid fill).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.enums import ListingKind, VerificationStatus
from app.catalog.models import Listing
from app.config import Settings, get_settings
from app.ingestion.fetcher import FetchError, FetchPolicy, fetch_url
from app.ingestion.llm_provider import create_extractor
from app.ingestion.models import VerificationEvent
from app.ingestion.parser import parse_document
from app.ingestion.ssrf import SSRFError

logger = logging.getLogger(__name__)

_ACTIVE = (
    VerificationStatus.VERIFIED_ACTIVE.value,
    VerificationStatus.LIKELY_ACTIVE.value,
    VerificationStatus.REGISTRATION_CLOSED.value,
)


@dataclass(slots=True)
class RecheckItemResult:
    slug: str
    kind: str
    ok: bool
    url: str = ""
    method: str = ""
    updated_fields: list[str] = field(default_factory=list)
    error: str | None = None
    status_code: int | None = None


@dataclass(slots=True)
class RecheckSummary:
    scanned: int = 0
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[RecheckItemResult] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(UTC)


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _primary_url(listing: Listing) -> str | None:
    if listing.kind == ListingKind.AI_OFFER.value and listing.ai_offer:
        o = listing.ai_offer
        for candidate in (o.official_terms_url, o.claim_url):
            if candidate and str(candidate).strip():
                return str(candidate).strip()
    if listing.kind == ListingKind.HACKATHON.value and listing.hackathon:
        u = listing.hackathon.official_url
        if u and str(u).strip():
            return str(u).strip()
    return None


def _looks_like_page_chrome(text: str) -> bool:
    """Heuristic: nav/docs chrome should not replace curated catalogue copy."""
    t = text.lower()
    bad = (
        "skip to main content",
        "skip to content",
        "collapse sidebar",
        "scroll breadcrumbs",
        "sign in",
        "log in",
        "cookie",
        "documentation index",
        "view all docs",
    )
    if any(b in t for b in bad):
        return True
    # Title-like "Pricing · Foo docs" without free-tier language
    return bool("pricing" in t and "free" not in t and "credit" not in t and len(t) < 80)


def _looks_like_offer_value(text: str) -> bool:
    t = text.lower()
    keys = (
        "free",
        "credit",
        "neuron",
        "tier",
        "rpm",
        "tpm",
        "quota",
        "$",
        "usd",
        "student",
        "always free",
        "no charge",
        "rate limit",
    )
    return any(k in t for k in keys) and not _looks_like_page_chrome(text)


def _merge_ai_offer(listing: Listing, extracted: dict[str, Any]) -> list[str]:
    """Conservative merge: protect curated product/provider/description.

    Prefer filling empty fields and improving offer_value when extraction
    clearly describes a free tier / credits (not page chrome).
    """
    o = listing.ai_offer
    if o is None:
        return []
    updated: list[str] = []

    # Only fill product_name / provider when empty or placeholder-short
    for attr, key in (("product_name", "product_name"), ("provider", "provider")):
        cur = (getattr(o, attr) or "").strip()
        val = extracted.get(key)
        if not isinstance(val, str) or not val.strip():
            continue
        val = val.strip()
        if _looks_like_page_chrome(val):
            continue
        if len(cur) < 3 and val != cur:
            setattr(o, attr, val[:200])
            updated.append(attr)

    # offer_value: only if looks like a real free-tier summary
    ov = extracted.get("offer_value")
    if isinstance(ov, str) and ov.strip() and _looks_like_offer_value(ov):
        ov = ov.strip()[:300]
        # Prefer longer / more specific free-tier wording
        prefer = len(ov) >= 12 and (
            not o.offer_value
            or len(ov) > len(o.offer_value)
            or "tba" in (o.offer_value or "").lower()
        )
        if ov != (o.offer_value or "").strip() and prefer:
            o.offer_value = ov
            updated.append("offer_value")

    # Do not auto-change offer_type / expires_at / tags / arrays from noisy pages —
    # only fill empty arrays.
    for arr_attr, key in (
        ("target_users", "target_users"),
        ("requirements", "requirements"),
        ("supported_regions", "supported_regions"),
        ("tags", "tags"),
        ("suitable_reasons", "suitable_reasons"),
    ):
        current = list(getattr(o, arr_attr) or [])
        if current:
            continue
        val = extracted.get(key)
        if isinstance(val, list) and val:
            cleaned = [str(x).strip() for x in val if str(x).strip()][:12]
            # Filter tech-keyword noise like lone "Go"/"Python" from keyword scans
            if cleaned:
                setattr(o, arr_attr, cleaned)
                updated.append(arr_attr)

    # Description: never replace curated copy with raw page text chrome
    # (recheck still proves URL is live via verification_event)

    return updated


def _merge_hackathon(listing: Listing, extracted: dict[str, Any]) -> list[str]:
    """Conservative merge for hackathons — fill gaps, don't trash curated titles."""
    h = listing.hackathon
    if h is None:
        return []
    updated: list[str] = []

    org = extracted.get("organizer")
    if (
        isinstance(org, str)
        and org.strip()
        and len((h.organizer or "").strip()) < 2
        and not _looks_like_page_chrome(org)
    ):
        h.organizer = org.strip()[:200]
        updated.append("organizer")

    prize = _as_decimal(extracted.get("prize_value"))
    if prize is not None and prize > 0 and (
        h.prize_value is None or Decimal(str(h.prize_value or 0)) <= 0
    ):
        h.prize_value = prize
        updated.append("prize_value")
        cur = extracted.get("prize_currency") or h.prize_currency or "USD"
        if not (h.prize_label or "").strip() or "tba" in (h.prize_label or "").lower():
            h.prize_label = (
                f"${prize:,.0f} {cur}" if str(cur).upper() == "USD" else f"{prize:,.0f} {cur}"
            )
            updated.append("prize_label")

    for attr, key in (
        ("registration_deadline", "registration_deadline"),
        ("submission_deadline", "submission_deadline"),
    ):
        if getattr(h, attr) is not None:
            continue
        val = extracted.get(key)
        if isinstance(val, datetime):
            setattr(h, attr, val)
            updated.append(attr)
        elif isinstance(val, str) and val.strip():
            try:
                setattr(h, attr, datetime.fromisoformat(val.replace("Z", "+00:00")))
                updated.append(attr)
            except ValueError:
                pass

    for arr_attr, key in (
        ("technologies", "technologies"),
        ("eligibility", "eligibility"),
        ("eligible_countries", "eligible_countries"),
    ):
        current = list(getattr(h, arr_attr) or [])
        if current:
            continue
        val = extracted.get(key)
        if isinstance(val, list) and val:
            cleaned = [str(x).strip() for x in val if str(x).strip()][:16]
            if cleaned:
                setattr(h, arr_attr, cleaned)
                updated.append(arr_attr)

    return updated


async def recheck_listing(
    session: AsyncSession,
    listing: Listing,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> RecheckItemResult:
    settings = settings or get_settings()
    now = now or _now()
    slug = listing.slug
    kind = str(listing.kind)
    url = _primary_url(listing)
    if not url:
        return RecheckItemResult(
            slug=slug, kind=kind, ok=False, error="no_official_url"
        )

    policy = FetchPolicy(
        timeout_seconds=float(settings.fetch_timeout_seconds),
        max_bytes=int(settings.fetch_max_bytes),
        max_redirects=int(settings.fetch_max_redirects),
        allowed_content_type_prefixes=(
            "text/html",
            "text/plain",
            "text/markdown",
            "application/xhtml",
            "application/xml",
            "text/xml",
            "application/json",
            "application/rss",
            "application/atom",
        ),
        user_agent=(
            "Mozilla/5.0 (compatible; DevRadarBot/0.2; +https://github.com/bagusardin25/DevRadar)"
        ),
    )

    try:
        doc = await fetch_url(url, policy)
    except (SSRFError, FetchError, Exception) as exc:
        listing.last_checked_at = now
        session.add(
            VerificationEvent(
                listing_id=listing.id,
                event_type="official_url_recheck_failed",
                previous_status=VerificationStatus(str(listing.verification_status)),
                new_status=VerificationStatus(str(listing.verification_status)),
                checked_urls=[url],
                score_breakdown={},
                notes=f"Recheck fetch failed: {type(exc).__name__}: {exc}"[:500],
            )
        )
        return RecheckItemResult(
            slug=slug, kind=kind, ok=False, url=url, error=str(exc)[:300]
        )

    if doc.not_modified:
        listing.last_checked_at = now
        return RecheckItemResult(
            slug=slug,
            kind=kind,
            ok=True,
            url=doc.final_url or url,
            method="not_modified",
            status_code=304,
        )

    if doc.status_code >= 400:
        listing.last_checked_at = now
        session.add(
            VerificationEvent(
                listing_id=listing.id,
                event_type="official_url_recheck_failed",
                previous_status=VerificationStatus(str(listing.verification_status)),
                new_status=VerificationStatus(str(listing.verification_status)),
                checked_urls=[doc.final_url or url],
                score_breakdown={"httpStatus": doc.status_code},
                notes=f"HTTP {doc.status_code} on recheck",
            )
        )
        return RecheckItemResult(
            slug=slug,
            kind=kind,
            ok=False,
            url=doc.final_url or url,
            error=f"http_{doc.status_code}",
            status_code=doc.status_code,
        )

    parsed = parse_document(
        doc.body, url=doc.final_url or url, content_type=doc.content_type
    )
    extractor = create_extractor(settings)
    kind_enum = (
        ListingKind.AI_OFFER
        if listing.kind == ListingKind.AI_OFFER.value
        else ListingKind.HACKATHON
    )
    extraction = await extractor.extract(parsed, kind_enum)
    fields = dict(extraction.fields or {})

    if kind_enum == ListingKind.AI_OFFER:
        updated = _merge_ai_offer(listing, fields)
    else:
        updated = _merge_hackathon(listing, fields)

    listing.last_checked_at = now
    prev = VerificationStatus(str(listing.verification_status))
    session.add(
        VerificationEvent(
            listing_id=listing.id,
            event_type="official_url_recheck",
            previous_status=prev,
            new_status=prev,
            checked_urls=[doc.final_url or url],
            score_breakdown={
                "extractMethod": extraction.method,
                "llmAttempted": extraction.llm_attempted,
                "httpStatus": doc.status_code,
                "updatedFieldCount": len(updated),
            },
            notes=(
                f"Recheck OK via {extraction.method}; "
                f"updated={','.join(updated) if updated else 'none'}"
            )[:500],
        )
    )

    return RecheckItemResult(
        slug=slug,
        kind=kind,
        ok=True,
        url=doc.final_url or url,
        method=extraction.method,
        updated_fields=updated,
        status_code=doc.status_code,
    )


async def recheck_catalogue(
    session: AsyncSession,
    *,
    kind: ListingKind | None = ListingKind.AI_OFFER,
    limit: int = 25,
    only_slugs: list[str] | None = None,
    settings: Settings | None = None,
) -> RecheckSummary:
    """Recheck up to `limit` active listings (default AI offers)."""
    settings = settings or get_settings()
    stmt = (
        select(Listing)
        .where(Listing.verification_status.in_(_ACTIVE))
        .options(
            selectinload(Listing.hackathon),
            selectinload(Listing.ai_offer),
        )
        .order_by(Listing.last_checked_at.asc().nullsfirst())
        .limit(limit)
    )
    if kind is not None:
        stmt = stmt.where(Listing.kind == kind.value)
    if only_slugs:
        stmt = stmt.where(Listing.slug.in_(only_slugs))

    listings = list((await session.execute(stmt)).scalars().all())
    summary = RecheckSummary(scanned=len(listings))

    for listing in listings:
        try:
            result = await recheck_listing(session, listing, settings=settings)
        except Exception as exc:
            logger.exception("recheck_failed", extra={"slug": listing.slug})
            result = RecheckItemResult(
                slug=listing.slug,
                kind=str(listing.kind),
                ok=False,
                error=f"unexpected: {exc}"[:300],
            )
        summary.results.append(result)
        if result.ok:
            summary.ok += 1
        elif result.error == "no_official_url":
            summary.skipped += 1
        else:
            summary.failed += 1

    await session.flush()
    return summary
