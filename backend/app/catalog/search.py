"""Indexed catalogue search with full-text, trigram, filters, and cursor pagination."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import ColumnElement

from app.catalog.enums import (
    HackathonMode,
    ListingKind,
    OfferType,
    VerificationStatus,
)
from app.catalog.models import AIOffer, Hackathon, Listing
from app.errors import ValidationError

# Public list default: only publishable-active badges.
DEFAULT_PUBLIC_STATUSES: tuple[VerificationStatus, ...] = (
    VerificationStatus.VERIFIED_ACTIVE,
    VerificationStatus.LIKELY_ACTIVE,
)

# Allowed on public catalogue when explicitly filtered (never needs_review).
PUBLIC_VISIBLE_STATUSES: frozenset[VerificationStatus] = frozenset(
    {
        VerificationStatus.VERIFIED_ACTIVE,
        VerificationStatus.LIKELY_ACTIVE,
        VerificationStatus.REGISTRATION_CLOSED,
        VerificationStatus.EXPIRED,
        VerificationStatus.CANCELLED,
    }
)

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20
FAR_FUTURE = datetime(9999, 12, 31, tzinfo=UTC)
CLOSING_SOON_DAYS = 14
BIG_PRIZE_FLOOR = Decimal("10000")


@dataclass(slots=True)
class HackathonFilters:
    query: str | None = None
    mode: HackathonMode | None = None
    region: str | None = None
    eligibility: str | None = None
    technology: str | None = None
    status: list[VerificationStatus] = field(default_factory=list)
    deadline_before: datetime | None = None
    deadline_after: datetime | None = None
    team_size: int | None = None
    prize_min: Decimal | None = None
    only_closing_soon: bool = False
    only_big_prizes: bool = False


@dataclass(slots=True)
class AIOfferFilters:
    query: str | None = None
    offer_type: OfferType | None = None
    target_user: str | None = None
    region: str | None = None
    status: list[VerificationStatus] = field(default_factory=list)
    expires_before: datetime | None = None
    expires_after: datetime | None = None
    tags: list[str] = field(default_factory=list)
    only_free_no_card: bool = False


@dataclass(slots=True)
class CursorPayload:
    score: Decimal
    sort_ts: datetime
    listing_id: UUID


@dataclass(slots=True)
class PageResult:
    listings: list[Listing]
    next_cursor: str | None
    total_estimate: int


def encode_cursor(score: Decimal, sort_ts: datetime, listing_id: UUID) -> str:
    payload = {
        "s": str(score),
        "t": sort_ts.astimezone(UTC).isoformat(),
        "i": str(listing_id),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> CursorPayload:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        return CursorPayload(
            score=Decimal(str(data["s"])),
            sort_ts=datetime.fromisoformat(data["t"]),
            listing_id=UUID(str(data["i"])),
        )
    except Exception as exc:
        raise ValidationError(
            detail="Invalid cursor",
            errors=[{"field": "cursor", "message": "Cursor is malformed or expired"}],
        ) from exc


def resolve_statuses(
    requested: list[VerificationStatus] | None,
) -> list[VerificationStatus]:
    """Apply public defaults and strip non-public statuses."""
    if not requested:
        return list(DEFAULT_PUBLIC_STATUSES)
    filtered = [s for s in requested if s in PUBLIC_VISIBLE_STATUSES]
    return filtered or list(DEFAULT_PUBLIC_STATUSES)


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_PAGE_SIZE
    if limit < 1:
        raise ValidationError(
            detail="limit must be at least 1",
            errors=[{"field": "limit", "message": "Must be >= 1"}],
        )
    return min(limit, MAX_PAGE_SIZE)


def _text_search_clause(query: str | None) -> ColumnElement[bool] | None:
    if not query or not query.strip():
        return None
    q = query.strip()
    ts_query = func.websearch_to_tsquery("english", q)
    fts = Listing.search_document.op("@@")(ts_query)
    # Trigram similarity fallback for short / fuzzy titles.
    trigram = func.similarity(Listing.title, q) >= 0.15
    ilike = Listing.title.ilike(f"%{q}%")
    return or_(fts, trigram, ilike)


def _cursor_clause(
    sort_ts_expr: ColumnElement[Any],
    cursor: CursorPayload | None,
) -> ColumnElement[bool] | None:
    if cursor is None:
        return None
    # ORDER BY score DESC, sort_ts ASC, id ASC
    return or_(
        Listing.confidence_score < cursor.score,
        and_(
            Listing.confidence_score == cursor.score,
            sort_ts_expr > cursor.sort_ts,
        ),
        and_(
            Listing.confidence_score == cursor.score,
            sort_ts_expr == cursor.sort_ts,
            Listing.id > cursor.listing_id,
        ),
    )


def _load_options() -> list[Any]:
    return [
        selectinload(Listing.hackathon),
        selectinload(Listing.ai_offer),
        selectinload(Listing.listing_sources),
        selectinload(Listing.verification_events),
    ]


async def search_hackathons(
    session: AsyncSession,
    filters: HackathonFilters,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> PageResult:
    page_size = clamp_limit(limit)
    statuses = resolve_statuses(filters.status)
    cursor_payload = decode_cursor(cursor) if cursor else None

    sort_ts = func.coalesce(Hackathon.submission_deadline, FAR_FUTURE)

    stmt: Select[Any] = (
        select(Listing)
        .join(Hackathon, Hackathon.listing_id == Listing.id)
        .where(
            Listing.kind == ListingKind.HACKATHON,
            Listing.verification_status.in_(statuses),
        )
        .options(*_load_options())
    )

    text_clause = _text_search_clause(filters.query)
    if text_clause is not None:
        stmt = stmt.where(text_clause)

    if filters.mode is not None:
        stmt = stmt.where(Hackathon.mode == filters.mode.value)

    if filters.region:
        region = filters.region.strip()
        stmt = stmt.where(
            or_(
                Hackathon.eligible_countries.contains([region]),
                Hackathon.eligible_countries.contains(["Worldwide"]),
                Hackathon.location.ilike(f"%{region}%"),
            )
        )

    if filters.eligibility:
        stmt = stmt.where(Hackathon.eligibility.contains([filters.eligibility.strip()]))

    if filters.technology:
        stmt = stmt.where(Hackathon.technologies.contains([filters.technology.strip()]))

    if filters.deadline_before is not None:
        stmt = stmt.where(Hackathon.submission_deadline <= filters.deadline_before)
    if filters.deadline_after is not None:
        stmt = stmt.where(Hackathon.submission_deadline >= filters.deadline_after)

    if filters.only_closing_soon:
        now = datetime.now(UTC)
        soon = now + timedelta(days=CLOSING_SOON_DAYS)
        stmt = stmt.where(
            Hackathon.submission_deadline.is_not(None),
            Hackathon.submission_deadline >= now,
            Hackathon.submission_deadline <= soon,
        )

    if filters.team_size is not None:
        stmt = stmt.where(
            Hackathon.team_min <= filters.team_size,
            Hackathon.team_max >= filters.team_size,
        )

    prize_floor = filters.prize_min
    if filters.only_big_prizes:
        prize_floor = max(prize_floor or Decimal("0"), BIG_PRIZE_FLOOR)
    if prize_floor is not None:
        stmt = stmt.where(Hackathon.prize_value >= prize_floor)

    cursor_clause = _cursor_clause(sort_ts, cursor_payload)
    if cursor_clause is not None:
        stmt = stmt.where(cursor_clause)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = stmt.order_by(
        Listing.confidence_score.desc(),
        sort_ts.asc(),
        Listing.id.asc(),
    ).limit(page_size + 1)

    rows = list((await session.execute(stmt)).scalars().unique().all())
    next_cursor: str | None = None
    if len(rows) > page_size:
        last = rows[page_size - 1]
        deadline = last.hackathon.submission_deadline if last.hackathon else None
        next_cursor = encode_cursor(
            last.confidence_score,
            deadline or FAR_FUTURE,
            last.id,
        )
        rows = rows[:page_size]

    return PageResult(listings=rows, next_cursor=next_cursor, total_estimate=total)


async def search_ai_offers(
    session: AsyncSession,
    filters: AIOfferFilters,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> PageResult:
    page_size = clamp_limit(limit)
    statuses = resolve_statuses(filters.status)
    cursor_payload = decode_cursor(cursor) if cursor else None

    sort_ts = func.coalesce(AIOffer.expires_at, FAR_FUTURE)

    stmt: Select[Any] = (
        select(Listing)
        .join(AIOffer, AIOffer.listing_id == Listing.id)
        .where(
            Listing.kind == ListingKind.AI_OFFER,
            Listing.verification_status.in_(statuses),
        )
        .options(*_load_options())
    )

    text_clause = _text_search_clause(filters.query)
    if text_clause is not None:
        stmt = stmt.where(text_clause)

    if filters.offer_type is not None:
        stmt = stmt.where(AIOffer.offer_type == filters.offer_type.value)

    if filters.target_user:
        stmt = stmt.where(AIOffer.target_users.contains([filters.target_user.strip()]))

    if filters.region:
        region = filters.region.strip()
        stmt = stmt.where(
            or_(
                AIOffer.supported_regions.contains([region]),
                AIOffer.supported_regions.contains(["Worldwide"]),
                AIOffer.supported_regions.contains(["Global"]),
            )
        )

    if filters.expires_before is not None:
        stmt = stmt.where(
            AIOffer.expires_at.is_not(None),
            AIOffer.expires_at <= filters.expires_before,
        )
    if filters.expires_after is not None:
        stmt = stmt.where(
            or_(
                AIOffer.expires_at.is_(None),
                AIOffer.expires_at >= filters.expires_after,
            )
        )

    for tag in filters.tags:
        stmt = stmt.where(AIOffer.tags.contains([tag.strip()]))

    if filters.only_free_no_card:
        free_types = [
            OfferType.FREE_TIER.value,
            OfferType.FREE_CREDITS.value,
            OfferType.FREE_MODEL.value,
            OfferType.SELF_HOSTED_WEIGHTS.value,
        ]
        stmt = stmt.where(AIOffer.offer_type.in_(free_types))

    cursor_clause = _cursor_clause(sort_ts, cursor_payload)
    if cursor_clause is not None:
        stmt = stmt.where(cursor_clause)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = stmt.order_by(
        Listing.confidence_score.desc(),
        sort_ts.asc(),
        Listing.id.asc(),
    ).limit(page_size + 1)

    rows = list((await session.execute(stmt)).scalars().unique().all())
    next_cursor: str | None = None
    if len(rows) > page_size:
        last = rows[page_size - 1]
        expires = last.ai_offer.expires_at if last.ai_offer else None
        next_cursor = encode_cursor(
            last.confidence_score,
            expires or FAR_FUTURE,
            last.id,
        )
        rows = rows[:page_size]

    return PageResult(listings=rows, next_cursor=next_cursor, total_estimate=total)


async def combined_search(
    session: AsyncSession,
    *,
    query: str | None,
    kind: ListingKind | None = None,
    status: list[VerificationStatus] | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> PageResult:
    """Search across listing kinds with a shared ranking."""
    page_size = clamp_limit(limit)
    statuses = resolve_statuses(status)
    cursor_payload = decode_cursor(cursor) if cursor else None

    # Prefer submission/expiry deadline when present; else published_at / far future.
    sort_ts = func.coalesce(
        Hackathon.submission_deadline,
        AIOffer.expires_at,
        Listing.published_at,
        FAR_FUTURE,
    )

    stmt: Select[Any] = (
        select(Listing)
        .outerjoin(Hackathon, Hackathon.listing_id == Listing.id)
        .outerjoin(AIOffer, AIOffer.listing_id == Listing.id)
        .where(Listing.verification_status.in_(statuses))
        .options(*_load_options())
    )

    if kind is not None:
        stmt = stmt.where(Listing.kind == kind.value)

    text_clause = _text_search_clause(query)
    if text_clause is not None:
        stmt = stmt.where(text_clause)

    if cursor_payload is not None:
        stmt = stmt.where(
            or_(
                Listing.confidence_score < cursor_payload.score,
                and_(
                    Listing.confidence_score == cursor_payload.score,
                    sort_ts > cursor_payload.sort_ts,
                ),
                and_(
                    Listing.confidence_score == cursor_payload.score,
                    sort_ts == cursor_payload.sort_ts,
                    Listing.id > cursor_payload.listing_id,
                ),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await session.execute(count_stmt)).scalar_one())

    stmt = stmt.order_by(
        Listing.confidence_score.desc(),
        sort_ts.asc(),
        Listing.id.asc(),
    ).limit(page_size + 1)

    rows = list((await session.execute(stmt)).scalars().unique().all())
    next_cursor: str | None = None
    if len(rows) > page_size:
        last = rows[page_size - 1]
        sort_value = FAR_FUTURE
        if last.hackathon and last.hackathon.submission_deadline:
            sort_value = last.hackathon.submission_deadline
        elif last.ai_offer and last.ai_offer.expires_at:
            sort_value = last.ai_offer.expires_at
        elif last.published_at:
            sort_value = last.published_at
        next_cursor = encode_cursor(last.confidence_score, sort_value, last.id)
        rows = rows[:page_size]

    return PageResult(listings=rows, next_cursor=next_cursor, total_estimate=total)
