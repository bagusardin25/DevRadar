"""Listing lifecycle: registration_closed / expired based on deadlines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.enums import ListingKind, VerificationStatus
from app.catalog.models import Listing
from app.ingestion.models import VerificationEvent

# Statuses we may auto-transition from (never touch cancelled / needs_review).
_ACTIVE_LIKE = frozenset(
    {
        VerificationStatus.VERIFIED_ACTIVE,
        VerificationStatus.LIKELY_ACTIVE,
        VerificationStatus.REGISTRATION_CLOSED,
    }
)


@dataclass(slots=True)
class LifecycleSummary:
    scanned: int = 0
    closed: int = 0
    expired: int = 0
    unchanged: int = 0


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def desired_hackathon_status(
    current: VerificationStatus,
    *,
    registration_deadline: datetime | None,
    submission_deadline: datetime | None,
    now: datetime,
) -> VerificationStatus | None:
    """Return a new status if a transition is needed, else None."""
    if current not in _ACTIVE_LIKE and current != VerificationStatus.EXPIRED:
        return None

    reg = _aware(registration_deadline)
    sub = _aware(submission_deadline)
    # Effective end of event: submission, else registration.
    end = sub or reg
    if end is not None and end < now:
        if current != VerificationStatus.EXPIRED:
            return VerificationStatus.EXPIRED
        return None

    if reg is not None and reg < now:
        # Registration ended but event still open (or no submission date yet).
        if current in {
            VerificationStatus.VERIFIED_ACTIVE,
            VerificationStatus.LIKELY_ACTIVE,
        }:
            return VerificationStatus.REGISTRATION_CLOSED
        return None

    return None


def desired_ai_offer_status(
    current: VerificationStatus,
    *,
    expires_at: datetime | None,
    now: datetime,
) -> VerificationStatus | None:
    if current not in _ACTIVE_LIKE and current != VerificationStatus.EXPIRED:
        return None
    exp = _aware(expires_at)
    if exp is not None and exp < now and current != VerificationStatus.EXPIRED:
        return VerificationStatus.EXPIRED
    return None


async def apply_lifecycle_transitions(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 500,
) -> LifecycleSummary:
    """Scan published-ish listings and advance statuses past deadlines."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    result = await session.execute(
        select(Listing)
        .where(
            Listing.verification_status.in_(
                [
                    VerificationStatus.VERIFIED_ACTIVE.value,
                    VerificationStatus.LIKELY_ACTIVE.value,
                    VerificationStatus.REGISTRATION_CLOSED.value,
                ]
            )
        )
        .options(
            selectinload(Listing.hackathon),
            selectinload(Listing.ai_offer),
        )
        .limit(limit)
    )
    listings = list(result.scalars().all())
    summary = LifecycleSummary(scanned=len(listings))

    for listing in listings:
        current = VerificationStatus(str(listing.verification_status))
        new_status: VerificationStatus | None = None
        notes = ""

        if listing.kind == ListingKind.HACKATHON.value and listing.hackathon:
            h = listing.hackathon
            new_status = desired_hackathon_status(
                current,
                registration_deadline=h.registration_deadline,
                submission_deadline=h.submission_deadline,
                now=now,
            )
            if new_status == VerificationStatus.EXPIRED:
                notes = "Auto-expired: submission/registration deadline passed."
                summary.expired += 1
            elif new_status == VerificationStatus.REGISTRATION_CLOSED:
                notes = "Auto-closed: registration deadline passed."
                summary.closed += 1
            else:
                summary.unchanged += 1
                continue
        elif listing.kind == ListingKind.AI_OFFER.value and listing.ai_offer:
            o = listing.ai_offer
            new_status = desired_ai_offer_status(
                current, expires_at=o.expires_at, now=now
            )
            if new_status == VerificationStatus.EXPIRED:
                notes = "Auto-expired: offer expires_at passed."
                summary.expired += 1
            else:
                summary.unchanged += 1
                continue
        else:
            summary.unchanged += 1
            continue

        if new_status is None:
            summary.unchanged += 1
            continue

        prev = current
        listing.verification_status = new_status
        listing.last_checked_at = now
        session.add(
            VerificationEvent(
                listing_id=listing.id,
                event_type="lifecycle_transition",
                previous_status=prev,
                new_status=new_status,
                checked_urls=[],
                score_breakdown={},
                notes=notes,
            )
        )

    await session.flush()
    return summary
