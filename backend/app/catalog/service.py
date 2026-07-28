"""Catalogue application service: serialization, detail fetch, stats, meta."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.limits import MAX_STATUS_PARAM_LENGTH
from app.catalog.completeness import ai_offer_completeness, hackathon_completeness
from app.catalog.enums import (
    ConnectorType,
    HackathonMode,
    ListingKind,
    OfferType,
    SourceTier,
    VerificationStatus,
)
from app.catalog.lifecycle import apply_lifecycle_transitions
from app.catalog.models import AIOffer, Hackathon, Listing
from app.catalog.public_schemas import (
    AIOfferPublic,
    CatalogueStatsResponse,
    CombinedSearchItem,
    CompletenessPublic,
    DiscoverySourcePublic,
    DiscoverySourceType,
    FilterMetaResponse,
    HackathonPublic,
    ScoreBreakdownPublic,
    VerificationAuditPublic,
)
from app.catalog.search import (
    DEFAULT_PUBLIC_STATUSES,
    PUBLIC_VISIBLE_STATUSES,
    AIOfferFilters,
    HackathonFilters,
    PageResult,
    combined_search,
    search_ai_offers,
    search_hackathons,
)
from app.errors import NotFoundError, ValidationError
from app.ingestion.models import ListingSource, VerificationEvent
from app.sources.models import Source

TIER_LABELS: dict[str, str] = {
    SourceTier.TIER_1.value: "Tier 1 (Official)",
    SourceTier.TIER_2.value: "Tier 2 (Aggregator)",
    SourceTier.TIER_3.value: "Tier 3 (Discovery Signal)",
}

CONNECTOR_TO_DISCOVERY: dict[str, str] = {
    ConnectorType.DEVPOST.value: "devpost",
    ConnectorType.MLH.value: "mlh",
    ConnectorType.HACKEREARTH.value: "official_site",
    ConnectorType.RSS.value: "official_site",
    ConnectorType.OFFICIAL_SITE.value: "official_site",
    ConnectorType.X_RECENT_SEARCH.value: "x",
    ConnectorType.REDDIT.value: "reddit",
    ConnectorType.GITHUB.value: "github",
    ConnectorType.MANUAL.value: "official_site",
    ConnectorType.COMMUNITY.value: "official_site",
}


def _as_decimal(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _score_breakdown(raw: dict[str, Any] | None) -> ScoreBreakdownPublic:
    raw = raw or {}

    def pick(*keys: str, default: int = 0) -> int:
        for key in keys:
            if key in raw and raw[key] is not None:
                return int(raw[key])
        return default

    return ScoreBreakdownPublic(
        status_and_deadline=pick("statusAndDeadline", "status_and_deadline"),
        keyword_match=pick("keywordMatch", "keyword_match"),
        source_credibility=pick("sourceCredibility", "source_credibility"),
        freshness=pick("freshness"),
        completeness=pick("completeness"),
    )


def _map_discovery_type(connector: str | None) -> DiscoverySourceType:
    if not connector:
        return "official_site"
    mapped = CONNECTOR_TO_DISCOVERY.get(connector, "official_site")
    return mapped  # type: ignore[return-value]


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


async def _sources_by_id(
    session: AsyncSession, source_ids: list[UUID]
) -> dict[UUID, Source]:
    if not source_ids:
        return {}
    result = await session.execute(select(Source).where(Source.id.in_(source_ids)))
    return {row.id: row for row in result.scalars().all()}


_X_STATUS_WITH_HANDLE = re.compile(
    r"^https?://(?:www\.)?(?:x|twitter|fxtwitter|vxtwitter)\.com/"
    r"(?!i/web/status/)([^/?#]+)/status(?:es)?/(\d+)",
    re.IGNORECASE,
)


def _anonymize_social_url(url: str) -> str:
    """Rewrite `x.com/<handle>/status/<id>` to the handle-free canonical form.

    Dropping the `author` field from the response is pointless if the very next
    field spells the handle out in a URL path. The `i/web/status/<id>` form
    resolves to the same post, so provenance survives. Non-matching URLs — and
    URLs already in canonical form — pass through untouched.
    """
    match = _X_STATUS_WITH_HANDLE.match(url)
    if match is None:
        return url
    return f"https://x.com/i/web/status/{match.group(2)}"


def _build_discovery_sources(
    listing_sources: list[ListingSource],
    sources: dict[UUID, Source],
) -> list[DiscoverySourcePublic]:
    items: list[DiscoverySourcePublic] = []
    for ls in listing_sources:
        source = sources.get(ls.source_id) if ls.source_id else None
        connector = (
            _enum_value(source.connector_type)
            if source
            else ConnectorType.OFFICIAL_SITE.value
        )
        tier_raw = (
            _enum_value(source.trust_tier) if source else SourceTier.TIER_2.value
        )
        items.append(
            DiscoverySourcePublic(
                type=_map_discovery_type(connector),
                url=_anonymize_social_url(ls.source_url),
                fetched_at=ls.last_observed_at,
                tier=TIER_LABELS.get(tier_raw, "Tier 2 (Aggregator)"),
            )
        )
    return items


def _build_audit(listing: Listing) -> VerificationAuditPublic:
    events = list(listing.verification_events or [])
    latest: VerificationEvent | None = events[-1] if events else None
    # `latest.notes` stays server-side — see VerificationAuditPublic.
    checked = list(latest.checked_urls) if latest else []
    breakdown_raw = (
        latest.score_breakdown if latest and latest.score_breakdown else listing.score_breakdown
    )
    return VerificationAuditPublic(
        last_checked_at=listing.last_checked_at,
        confidence_score=_as_decimal(listing.confidence_score),
        score_breakdown=_score_breakdown(breakdown_raw),
        checked_urls=checked,
        pipeline_step="verified",
    )


def _completeness_public(raw: dict[str, Any]) -> CompletenessPublic:
    return CompletenessPublic(
        score=int(raw.get("score") or 0),
        missing=list(raw.get("missing") or []),
        flags=list(raw.get("flags") or []),
        has_deadline=bool(raw.get("hasDeadline")),
        has_prize=bool(raw.get("hasPrize")),
        has_strong_url=bool(raw.get("hasStrongUrl")),
        has_eligibility=bool(raw.get("hasEligibility")),
        has_description=bool(raw.get("hasDescription")),
    )


def to_hackathon_public(
    listing: Listing,
    sources: dict[UUID, Source],
) -> HackathonPublic:
    h = listing.hackathon
    if h is None:
        raise ValueError("Listing is missing hackathon child")
    mode = h.mode if isinstance(h.mode, HackathonMode) else HackathonMode(str(h.mode))
    completeness = _completeness_public(hackathon_completeness(listing, h))
    return HackathonPublic(
        id=str(listing.id),
        slug=listing.slug,
        title=listing.title,
        organizer=h.organizer,
        organizer_logo=h.organizer_logo,
        description=listing.description,
        registration_open_at=h.registration_open_at,
        registration_deadline=h.registration_deadline,
        submission_deadline=h.submission_deadline,
        mode=mode,
        location=h.location,
        eligible_countries=list(h.eligible_countries or []),
        eligibility=list(h.eligibility or []),
        team_min=h.team_min,
        team_max=h.team_max,
        prize_value=_as_decimal(h.prize_value),
        prize_currency=h.prize_currency,
        prize_label=(h.prize_label or "").strip(),
        technologies=list(h.technologies or []),
        official_url=h.official_url,
        discovery_sources=_build_discovery_sources(
            list(listing.listing_sources or []), sources
        ),
        verification_status=VerificationStatus(_enum_value(listing.verification_status)),
        confidence_score=_as_decimal(listing.confidence_score),
        last_checked_at=listing.last_checked_at,
        suitable_reasons=list(h.suitable_reasons or []),
        effort_estimate=h.effort_estimate,
        audit=_build_audit(listing),
        completeness=completeness,
    )


def to_ai_offer_public(
    listing: Listing,
    sources: dict[UUID, Source],
) -> AIOfferPublic:
    o = listing.ai_offer
    if o is None:
        raise ValueError("Listing is missing ai_offer child")
    offer_type = (
        o.offer_type if isinstance(o.offer_type, OfferType) else OfferType(str(o.offer_type))
    )
    completeness = _completeness_public(ai_offer_completeness(listing, o))
    return AIOfferPublic(
        id=str(listing.id),
        slug=listing.slug,
        product_name=o.product_name,
        provider=o.provider,
        provider_logo=o.provider_logo,
        offer_type=offer_type,
        offer_value=o.offer_value,
        target_users=list(o.target_users or []),
        requirements=list(o.requirements or []),
        starts_at=o.starts_at,
        expires_at=o.expires_at,
        supported_regions=list(o.supported_regions or []),
        official_terms_url=o.official_terms_url,
        claim_url=o.claim_url,
        verification_status=VerificationStatus(_enum_value(listing.verification_status)),
        confidence_score=_as_decimal(listing.confidence_score),
        last_checked_at=listing.last_checked_at,
        description=listing.description,
        tags=list(o.tags or []),
        discovery_sources=_build_discovery_sources(
            list(listing.listing_sources or []), sources
        ),
        suitable_reasons=list(o.suitable_reasons or []),
        audit=_build_audit(listing),
        completeness=completeness,
    )


async def hydrate_sources_for_listings(
    session: AsyncSession, listings: list[Listing]
) -> dict[UUID, Source]:
    ids: list[UUID] = []
    for listing in listings:
        for ls in listing.listing_sources or []:
            if ls.source_id is not None:
                ids.append(ls.source_id)
    return await _sources_by_id(session, ids)


async def serialize_hackathon_page(
    session: AsyncSession, page: PageResult
) -> tuple[list[HackathonPublic], str | None, int]:
    sources = await hydrate_sources_for_listings(session, page.listings)
    items = [to_hackathon_public(listing, sources) for listing in page.listings]
    return items, page.next_cursor, page.total_estimate


async def serialize_ai_offer_page(
    session: AsyncSession, page: PageResult
) -> tuple[list[AIOfferPublic], str | None, int]:
    sources = await hydrate_sources_for_listings(session, page.listings)
    items = [to_ai_offer_public(listing, sources) for listing in page.listings]
    return items, page.next_cursor, page.total_estimate


async def serialize_combined_page(
    session: AsyncSession, page: PageResult
) -> tuple[list[CombinedSearchItem], str | None, int]:
    sources = await hydrate_sources_for_listings(session, page.listings)
    items: list[CombinedSearchItem] = []
    for listing in page.listings:
        kind = ListingKind(listing.kind)
        if kind == ListingKind.HACKATHON:
            items.append(
                CombinedSearchItem(kind=kind, item=to_hackathon_public(listing, sources))
            )
        else:
            items.append(
                CombinedSearchItem(kind=kind, item=to_ai_offer_public(listing, sources))
            )
    return items, page.next_cursor, page.total_estimate


class CatalogueService:
    """High-level catalogue operations used by public API routes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _refresh_lifecycle(self) -> None:
        """Advance past-deadline listings before serving catalogue reads.

        Flushes only — request-scoped session commits at end of request.
        """
        await apply_lifecycle_transitions(self._session)

    async def search_hackathons(
        self,
        filters: HackathonFilters,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[HackathonPublic], str | None, int]:
        await self._refresh_lifecycle()
        page = await search_hackathons(
            self._session, filters, cursor=cursor, limit=limit
        )
        return await serialize_hackathon_page(self._session, page)

    async def search_ai_offers(
        self,
        filters: AIOfferFilters,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[AIOfferPublic], str | None, int]:
        await self._refresh_lifecycle()
        page = await search_ai_offers(self._session, filters, cursor=cursor, limit=limit)
        return await serialize_ai_offer_page(self._session, page)

    async def combined_search(
        self,
        *,
        query: str | None = None,
        kind: ListingKind | None = None,
        status: list[VerificationStatus] | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[CombinedSearchItem], str | None, int]:
        page = await combined_search(
            self._session,
            query=query,
            kind=kind,
            status=status,
            cursor=cursor,
            limit=limit,
        )
        return await serialize_combined_page(self._session, page)

    async def get_hackathon_by_slug(self, slug: str) -> HackathonPublic:
        await self._refresh_lifecycle()
        listing = await self._get_public_listing(slug, ListingKind.HACKATHON)
        sources = await hydrate_sources_for_listings(self._session, [listing])
        return to_hackathon_public(listing, sources)

    async def get_ai_offer_by_slug(self, slug: str) -> AIOfferPublic:
        await self._refresh_lifecycle()
        listing = await self._get_public_listing(slug, ListingKind.AI_OFFER)
        sources = await hydrate_sources_for_listings(self._session, [listing])
        return to_ai_offer_public(listing, sources)

    async def _get_public_listing(self, slug: str, kind: ListingKind) -> Listing:
        result = await self._session.execute(
            select(Listing)
            .where(Listing.slug == slug, Listing.kind == kind.value)
            .options(
                selectinload(Listing.hackathon),
                selectinload(Listing.ai_offer),
                selectinload(Listing.listing_sources),
                selectinload(Listing.verification_events),
            )
        )
        listing = result.scalar_one_or_none()
        if listing is None:
            raise NotFoundError(detail=f"{kind.value} not found")
        status = VerificationStatus(listing.verification_status)
        if status not in PUBLIC_VISIBLE_STATUSES:
            raise NotFoundError(detail=f"{kind.value} not found")
        return listing

    async def stats(self) -> CatalogueStatsResponse:
        statuses = list(DEFAULT_PUBLIC_STATUSES)
        h_count = await self._session.scalar(
            select(func.count())
            .select_from(Listing)
            .where(
                Listing.kind == ListingKind.HACKATHON.value,
                Listing.verification_status.in_(statuses),
            )
        )
        a_count = await self._session.scalar(
            select(func.count())
            .select_from(Listing)
            .where(
                Listing.kind == ListingKind.AI_OFFER.value,
                Listing.verification_status.in_(statuses),
            )
        )
        s_count = await self._session.scalar(
            select(func.count()).select_from(Source).where(Source.enabled.is_(True))
        )
        last = await self._session.scalar(
            select(func.max(Listing.last_checked_at)).where(
                Listing.verification_status.in_(statuses)
            )
        )
        return CatalogueStatsResponse(
            hackathons_active=int(h_count or 0),
            ai_offers_active=int(a_count or 0),
            sources_enabled=int(s_count or 0),
            last_indexed_at=last,
        )

    async def filter_meta(self) -> FilterMetaResponse:
        # Filter values are public catalogue data too. Scope every child-table
        # query through its listing so draft / needs-review rows cannot leak
        # tags, regions, or other metadata through this unauthenticated route.
        public_statuses = list(PUBLIC_VISIBLE_STATUSES)
        tech_rows = await self._session.execute(
            select(func.distinct(func.unnest(Hackathon.technologies)))
            .select_from(Hackathon)
            .join(Listing, Listing.id == Hackathon.listing_id)
            .where(
                Listing.kind == ListingKind.HACKATHON.value,
                Listing.verification_status.in_(public_statuses),
            )
        )
        offer_tag_rows = await self._session.execute(
            select(func.distinct(func.unnest(AIOffer.tags)))
            .select_from(AIOffer)
            .join(Listing, Listing.id == AIOffer.listing_id)
            .where(
                Listing.kind == ListingKind.AI_OFFER.value,
                Listing.verification_status.in_(public_statuses),
            )
        )
        regions_h = await self._session.execute(
            select(func.distinct(func.unnest(Hackathon.eligible_countries)))
            .select_from(Hackathon)
            .join(Listing, Listing.id == Hackathon.listing_id)
            .where(
                Listing.kind == ListingKind.HACKATHON.value,
                Listing.verification_status.in_(public_statuses),
            )
        )
        regions_a = await self._session.execute(
            select(func.distinct(func.unnest(AIOffer.supported_regions)))
            .select_from(AIOffer)
            .join(Listing, Listing.id == AIOffer.listing_id)
            .where(
                Listing.kind == ListingKind.AI_OFFER.value,
                Listing.verification_status.in_(public_statuses),
            )
        )
        eligibility = await self._session.execute(
            select(func.distinct(func.unnest(Hackathon.eligibility)))
            .select_from(Hackathon)
            .join(Listing, Listing.id == Hackathon.listing_id)
            .where(
                Listing.kind == ListingKind.HACKATHON.value,
                Listing.verification_status.in_(public_statuses),
            )
        )
        offer_types = await self._session.execute(
            select(func.distinct(AIOffer.offer_type))
            .select_from(AIOffer)
            .join(Listing, Listing.id == AIOffer.listing_id)
            .where(
                Listing.kind == ListingKind.AI_OFFER.value,
                Listing.verification_status.in_(public_statuses),
            )
        )

        def clean(values: list[Any]) -> list[str]:
            return sorted({str(v) for v in values if v})

        regions = clean([*regions_h.scalars().all(), *regions_a.scalars().all()])
        return FilterMetaResponse(
            technologies=clean(
                [*tech_rows.scalars().all(), *offer_tag_rows.scalars().all()]
            ),
            regions=regions,
            eligibility_labels=clean(list(eligibility.scalars().all())),
            offer_types=clean(list(offer_types.scalars().all())),
            modes=["online", "hybrid", "in_person"],
            verification_statuses=[s.value for s in DEFAULT_PUBLIC_STATUSES],
        )


def listing_etag(listing_like: HackathonPublic | AIOfferPublic) -> str:
    """Weak ETag from id + last_checked + confidence for conditional GET."""
    material = (
        f"{listing_like.id}:"
        f"{listing_like.last_checked_at.isoformat() if listing_like.last_checked_at else ''}:"
        f"{listing_like.confidence_score}:"
        f"{listing_like.verification_status}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f'W/"{digest}"'


def parse_status_param(raw: str | None) -> list[VerificationStatus]:
    if not raw:
        return []
    if len(raw) > MAX_STATUS_PARAM_LENGTH:
        raise ValidationError(
            detail="Verification status filter is too long",
            errors=[{"field": "status", "message": "Status filter is too long"}],
        )
    values: list[VerificationStatus] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            status = VerificationStatus(part)
            if status not in values:
                values.append(status)
        except ValueError:
            raise ValidationError(
                detail=f"Unknown verification status: {part}",
                errors=[{"field": "status", "message": f"Invalid status '{part}'"}],
            ) from None
    return values
