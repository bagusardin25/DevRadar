#!/usr/bin/env python3
"""Seed catalogue rows from the X MCP manual collection.

Source of truth:
  ../../data/manual-collection/seed_listings.json

Usage (from backend/):
  uv run python scripts/seed_x_mcp_collection.py
  uv run python scripts/seed_x_mcp_collection.py --dry-run
  uv run python scripts/seed_x_mcp_collection.py --json-path ../data/manual-collection/seed_listings.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

# Ensure `app` is importable when run as a script.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.catalog.enums import (  # noqa: E402
    ConnectorType,
    EffortEstimate,
    HackathonMode,
    ListingKind,
    OfferType,
    SourceTier,
    VerificationStatus,
)
from app.catalog.repository import ListingRepository  # noqa: E402
from app.catalog.schemas import (  # noqa: E402
    AIOfferCreateSchema,
    HackathonCreateSchema,
    ListingCreateSchema,
)
from app.config import get_settings  # noqa: E402
from app.db import create_engine, create_session_maker  # noqa: E402
from app.ingestion.models import DiscoverySignal, ListingSource, VerificationEvent  # noqa: E402
from app.ingestion.scoring import (  # noqa: E402
    ScoreBreakdown,
    ScoringInput,
    keyword_hits_from_fields,
    score_verification,
)
from app.sources.models import Source  # noqa: E402

DEFAULT_JSON = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "manual-collection"
    / "seed_listings.json"
)

# Fields a listing of each kind is expected to carry. Used for the
# completeness component of the score.
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "hackathon": (
        "title",
        "description",
        "official_url",
        "registration_deadline",
        "submission_deadline",
        "prize_value",
        "technologies",
        "eligibility",
    ),
    "ai_offer": (
        "title",
        "description",
        "product_name",
        "provider",
        "offer_type",
        "offer_value",
        "claim_url",
        "target_users",
    ),
}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _score_for(item: dict[str, Any], kind: str, now: datetime) -> ScoreBreakdown:
    """Score a seed row with the same function the ingestion pipeline uses.

    Seeds previously carried a hand-written ``confidence_score`` next to a
    frozen breakdown constant, so the headline number and the bars meant to
    explain it came from two unrelated places: every listing showed identical
    components while the confidence varied, and neither added up to the other.
    Deriving both here keeps the scorecard auditable.
    """
    if kind == "hackathon":
        opens = _parse_dt(item.get("registration_open_at"))
        reg = _parse_dt(item.get("registration_deadline"))
        sub = _parse_dt(item.get("submission_deadline"))
        deadlines = [d for d in (reg, sub) if d is not None]
        milestones = [d for d in (opens, reg, sub) if d is not None]
        has_valid_dates = len(deadlines) > 0
        dates_ordered = milestones == sorted(milestones)
        deadline_in_future = bool(deadlines) and max(deadlines) > now
        link_ok = bool(item.get("official_url"))
    else:
        expires = _parse_dt(item.get("expires_at")) if item.get("expires_at") else None
        starts = _parse_dt(item.get("starts_at")) if item.get("starts_at") else None
        # An open-ended free tier has no expiry; that is a valid, ordered state
        # rather than missing data.
        has_valid_dates = True
        dates_ordered = not (starts and expires) or starts <= expires
        deadline_in_future = expires is None or expires > now
        link_ok = bool(item.get("claim_url") or item.get("official_terms_url"))

    required = _REQUIRED_FIELDS[kind]
    present = sum(1 for field in required if item.get(field))

    return score_verification(
        ScoringInput(
            has_valid_dates=has_valid_dates,
            deadline_in_future=deadline_in_future,
            dates_ordered=dates_ordered,
            keyword_hits=keyword_hits_from_fields(kind, item),
            # The seed always attaches the organiser's own page as primary.
            source_tier="tier_1",
            cross_source_count=len(item.get("x_posts") or []),
            last_checked_at=now,
            now=now,
            required_fields_present=present,
            required_fields_total=len(required),
            link_ok=link_ok,
        )
    )


def _apply_rescore(
    session: Any,
    listing: Any,
    item: dict[str, Any],
    kind: str,
    checked_url: str,
) -> None:
    """Rescore a listing and record the result as a verification event.

    The public API reads ``confidence_score`` off the listing row but takes
    ``score_breakdown`` from the newest verification event
    (``app/catalog/service.py::_build_audit``). Writing only the row would
    leave the scorecard rendering a stale breakdown against a fresh
    confidence, so both are updated together.
    """
    scored = _score_for(item, kind, datetime.now(UTC))
    status = VerificationStatus(str(listing.verification_status))

    listing.confidence_score = Decimal(str(scored.confidence))
    listing.score_breakdown = scored.as_dict()
    session.add(
        VerificationEvent(
            listing_id=listing.id,
            event_type="seed_rescore",
            previous_status=status,
            new_status=status,
            checked_urls=[checked_url] if checked_url else [],
            score_breakdown=scored.as_dict(),
            notes="Rescored from seed evidence with app.ingestion.scoring.",
        )
    )


def _effort(value: str | None) -> EffortEstimate:
    if value and value in {e.value for e in EffortEstimate}:
        return EffortEstimate(value)
    return EffortEstimate.WEEKS_1_2


def _status(value: str) -> VerificationStatus:
    return VerificationStatus(value)


def _mode(value: str) -> HackathonMode:
    return HackathonMode(value)


def _offer_type(value: str) -> OfferType:
    return OfferType(value)


async def _get_or_create_source(
    session: Any,
    *,
    name: str,
    connector: ConnectorType,
    tier: SourceTier,
    base_url: str | None,
    notes: str,
) -> Source:
    result = await session.execute(select(Source).where(Source.name == name))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    source = Source(
        name=name,
        connector_type=connector,
        trust_tier=tier,
        base_url=base_url,
        enabled=True,
        notes=notes,
    )
    session.add(source)
    await session.flush()
    return source


async def _ensure_sources(session: Any) -> tuple[Source, Source]:
    official = await _get_or_create_source(
        session,
        name="X MCP seed — official sites",
        connector=ConnectorType.OFFICIAL_SITE,
        tier=SourceTier.TIER_1,
        base_url=None,
        notes="Primary official URLs curated from X MCP discovery (2026-07-24).",
    )
    x_src = await _get_or_create_source(
        session,
        name="X MCP manual discovery",
        connector=ConnectorType.X_RECENT_SEARCH,
        tier=SourceTier.TIER_3,
        base_url="https://x.com",
        notes="Tier-3 discovery signals from hosted X MCP searches. Post text not stored.",
    )
    return official, x_src


def _prize_label_for(item: dict[str, Any]) -> str:
    label = (item.get("prize_label") or "").strip()
    if label:
        return label
    try:
        value = Decimal(str(item.get("prize_value") or 0))
    except Exception:
        value = Decimal("0")
    currency = item.get("prize_currency") or "USD"
    if value > 0:
        if currency == "USD":
            return f"${value:,.0f} USD"
        return f"{value:,.0f} {currency}"
    return "Prize TBA"


async def _update_hackathon_prize(
    session: Any,
    repo: ListingRepository,
    item: dict[str, Any],
    *,
    dry_run: bool,
) -> str:
    """Refresh prize fields (and a few core catalogue fields) on an existing row."""
    slug = item["slug"]
    existing = await repo.get_by_slug(slug)
    if existing is None or existing.hackathon is None:
        return f"miss  hackathon {slug} (not in DB)"
    if dry_run:
        return f"dry   update {slug} prize"
    h = existing.hackathon
    h.prize_value = Decimal(str(item.get("prize_value") or 0))
    h.prize_currency = item.get("prize_currency") or "USD"
    h.prize_label = _prize_label_for(item)
    if item.get("description"):
        existing.description = item["description"]
    if item.get("title"):
        existing.title = item["title"]
    if item.get("status"):
        existing.verification_status = _status(item["status"])
    if item.get("official_url"):
        h.official_url = item["official_url"]
    if item.get("organizer"):
        h.organizer = item["organizer"]
    if item.get("eligible_countries") is not None:
        h.eligible_countries = list(item.get("eligible_countries") or [])
    if item.get("eligibility") is not None:
        h.eligibility = list(item.get("eligibility") or [])
    if item.get("technologies") is not None:
        h.technologies = list(item.get("technologies") or [])
    if item.get("suitable_reasons") is not None:
        h.suitable_reasons = list(item.get("suitable_reasons") or [])
    if item.get("registration_deadline") is not None:
        h.registration_deadline = _parse_dt(item.get("registration_deadline"))
    if item.get("submission_deadline") is not None:
        h.submission_deadline = _parse_dt(item.get("submission_deadline"))
    # Deadlines and fields just changed, so the old score no longer describes
    # this row — rescore from the same evidence the scorecard displays.
    _apply_rescore(session, existing, item, "hackathon", item["official_url"])
    await session.flush()
    return f"upd   hackathon {slug}"


async def _seed_hackathon(
    session: Any,
    repo: ListingRepository,
    item: dict[str, Any],
    official_src: Source,
    x_src: Source,
    *,
    dry_run: bool,
    update_existing: bool,
) -> str:
    slug = item["slug"]
    existing = await repo.get_by_slug(slug)
    if existing is not None:
        if update_existing:
            return await _update_hackathon_prize(
                session, repo, item, dry_run=dry_run
            )
        return f"skip  hackathon {slug} (exists)"

    if dry_run:
        return f"dry   hackathon {slug}"

    now = datetime.now(UTC)
    status = _status(item["status"])
    scored = _score_for(item, "hackathon", now)
    score = Decimal(str(scored.confidence))
    breakdown = scored.as_dict()

    listing = await repo.create_hackathon(
        ListingCreateSchema(
            kind=ListingKind.HACKATHON,
            slug=slug,
            title=item["title"],
            description=item.get("description", ""),
            verification_status=status,
            confidence_score=score,
            score_breakdown=breakdown,
            published_at=now
            if status
            in {
                VerificationStatus.VERIFIED_ACTIVE,
                VerificationStatus.LIKELY_ACTIVE,
                VerificationStatus.REGISTRATION_CLOSED,
            }
            else None,
            last_checked_at=now,
            first_seen_at=now,
        ),
        HackathonCreateSchema(
            organizer=item["organizer"],
            registration_open_at=_parse_dt(item.get("registration_open_at")),
            registration_deadline=_parse_dt(item.get("registration_deadline")),
            submission_deadline=_parse_dt(item.get("submission_deadline")),
            mode=_mode(item.get("mode", "online")),
            location=item.get("location"),
            eligible_countries=list(item.get("eligible_countries") or ["Worldwide"]),
            eligibility=list(item.get("eligibility") or ["Developer"]),
            team_min=int(item.get("team_min") or 1),
            team_max=int(item.get("team_max") or 4),
            prize_value=Decimal(str(item.get("prize_value") or 0)),
            prize_currency=item.get("prize_currency") or "USD",
            prize_label=_prize_label_for(item),
            technologies=list(item.get("technologies") or ["AI"]),
            official_url=item["official_url"],
            suitable_reasons=list(item.get("suitable_reasons") or []),
            effort_estimate=_effort(item.get("effort_estimate")),
        ),
    )

    official_url = item["official_url"]
    session.add(
        ListingSource(
            listing_id=listing.id,
            source_id=official_src.id,
            source_url=official_url,
            is_primary=True,
            observed_fields={
                "title": item["title"],
                "seed": "x_mcp_collection",
            },
        )
    )

    for post in item.get("x_posts") or []:
        post_url = post["post_url"]
        post_id = post["post_id"]
        author = post.get("author")
        session.add(
            ListingSource(
                listing_id=listing.id,
                source_id=x_src.id,
                source_url=post_url,
                is_primary=False,
                observed_fields={
                    "postId": post_id,
                    "author": author,
                    "seed": "x_mcp_collection",
                },
            )
        )
        # Discovery signal (no post text).
        existing_sig = await session.execute(
            select(DiscoverySignal).where(
                DiscoverySignal.source_id == x_src.id,
                DiscoverySignal.external_id == post_id,
            )
        )
        if existing_sig.scalar_one_or_none() is None:
            session.add(
                DiscoverySignal(
                    source_id=x_src.id,
                    external_id=post_id,
                    url=post_url,
                    author=f"@{author}" if author and not str(author).startswith("@") else author,
                    signal_created_at=now,
                    discovered_urls=[official_url] if official_url else [],
                    extracted_information={
                        "candidateType": "hackathon",
                        "slug": slug,
                        "title": item["title"],
                    },
                    review_state=status.value,
                    last_checked_at=now,
                )
            )

    session.add(
        VerificationEvent(
            listing_id=listing.id,
            event_type="seed_publish",
            previous_status=VerificationStatus.NEEDS_REVIEW,
            new_status=status,
            checked_urls=[official_url],
            score_breakdown=breakdown,
            notes="Seeded from X MCP manual collection (2026-07-24).",
        )
    )
    await session.flush()
    return f"add   hackathon {slug}"


async def _update_ai_offer(
    session: Any,
    repo: ListingRepository,
    item: dict[str, Any],
    *,
    dry_run: bool,
) -> str:
    slug = item["slug"]
    existing = await repo.get_by_slug(slug)
    if existing is None or existing.ai_offer is None:
        return f"miss  ai_offer  {slug} (not in DB)"
    if dry_run:
        return f"dry   update ai_offer {slug}"
    o = existing.ai_offer
    if item.get("description"):
        existing.description = item["description"]
    if item.get("title"):
        existing.title = item["title"]
    if item.get("status"):
        existing.verification_status = _status(item["status"])
    # Rescore rather than copying a hand-written number, so confidence and
    # breakdown stay derived from the same evidence.
    _apply_rescore(
        session,
        existing,
        item,
        "ai_offer",
        item.get("claim_url") or item.get("official_terms_url") or "",
    )
    o.product_name = item.get("product_name") or o.product_name
    o.provider = item.get("provider") or o.provider
    if item.get("offer_type"):
        o.offer_type = _offer_type(item["offer_type"])
    if item.get("offer_value") is not None:
        o.offer_value = item["offer_value"] or ""
    if item.get("target_users") is not None:
        o.target_users = list(item["target_users"] or [])
    if item.get("requirements") is not None:
        o.requirements = list(item["requirements"] or [])
    if item.get("supported_regions") is not None:
        o.supported_regions = list(item["supported_regions"] or [])
    if item.get("official_terms_url"):
        o.official_terms_url = item["official_terms_url"]
    if item.get("claim_url"):
        o.claim_url = item["claim_url"]
    if item.get("tags") is not None:
        o.tags = list(item["tags"] or [])
    if item.get("suitable_reasons") is not None:
        o.suitable_reasons = list(item["suitable_reasons"] or [])
    if "expires_at" in item:
        o.expires_at = (
            _parse_dt(item.get("expires_at")) if item.get("expires_at") else None
        )
    await session.flush()
    return f"upd   ai_offer  {slug}"


async def _seed_ai_offer(
    session: Any,
    repo: ListingRepository,
    item: dict[str, Any],
    official_src: Source,
    x_src: Source,
    *,
    dry_run: bool,
    update_existing: bool = False,
) -> str:
    slug = item["slug"]
    existing = await repo.get_by_slug(slug)
    if existing is not None:
        if update_existing:
            return await _update_ai_offer(session, repo, item, dry_run=dry_run)
        return f"skip  ai_offer  {slug} (exists)"

    if dry_run:
        return f"dry   ai_offer  {slug}"

    now = datetime.now(UTC)
    status = _status(item["status"])
    scored = _score_for(item, "ai_offer", now)
    score = Decimal(str(scored.confidence))
    breakdown = scored.as_dict()
    expires = _parse_dt(item.get("expires_at")) if item.get("expires_at") else None

    listing = await repo.create_ai_offer(
        ListingCreateSchema(
            kind=ListingKind.AI_OFFER,
            slug=slug,
            title=item["title"],
            description=item.get("description", ""),
            verification_status=status,
            confidence_score=score,
            score_breakdown=breakdown,
            published_at=now
            if status
            in {
                VerificationStatus.VERIFIED_ACTIVE,
                VerificationStatus.LIKELY_ACTIVE,
            }
            else None,
            last_checked_at=now,
            first_seen_at=now,
        ),
        AIOfferCreateSchema(
            product_name=item["product_name"],
            provider=item["provider"],
            offer_type=_offer_type(item.get("offer_type", "free_tier")),
            offer_value=item.get("offer_value") or "",
            target_users=list(item.get("target_users") or ["Developer"]),
            requirements=list(item.get("requirements") or []),
            starts_at=now,
            expires_at=expires,
            supported_regions=list(item.get("supported_regions") or ["Worldwide"]),
            official_terms_url=item["official_terms_url"],
            claim_url=item["claim_url"],
            tags=list(item.get("tags") or ["free", "ai"]),
            suitable_reasons=list(item.get("suitable_reasons") or []),
        ),
    )

    terms = item["official_terms_url"]
    session.add(
        ListingSource(
            listing_id=listing.id,
            source_id=official_src.id,
            source_url=terms,
            is_primary=True,
            observed_fields={"productName": item["product_name"], "seed": "x_mcp_collection"},
        )
    )

    for post in item.get("x_posts") or []:
        post_url = post["post_url"]
        post_id = post["post_id"]
        author = post.get("author")
        session.add(
            ListingSource(
                listing_id=listing.id,
                source_id=x_src.id,
                source_url=post_url,
                is_primary=False,
                observed_fields={
                    "postId": post_id,
                    "author": author,
                    "seed": "x_mcp_collection",
                },
            )
        )
        existing_sig = await session.execute(
            select(DiscoverySignal).where(
                DiscoverySignal.source_id == x_src.id,
                DiscoverySignal.external_id == post_id,
            )
        )
        if existing_sig.scalar_one_or_none() is None:
            session.add(
                DiscoverySignal(
                    source_id=x_src.id,
                    external_id=post_id,
                    url=post_url,
                    author=f"@{author}" if author and not str(author).startswith("@") else author,
                    signal_created_at=now,
                    discovered_urls=[terms],
                    extracted_information={
                        "candidateType": "ai_offer",
                        "slug": slug,
                        "productName": item["product_name"],
                    },
                    review_state=status.value,
                    last_checked_at=now,
                )
            )

    session.add(
        VerificationEvent(
            listing_id=listing.id,
            event_type="seed_publish",
            previous_status=VerificationStatus.NEEDS_REVIEW,
            new_status=status,
            checked_urls=[terms, item.get("claim_url") or terms],
            score_breakdown=breakdown,
            notes="Seeded from X MCP manual collection (2026-07-24).",
        )
    )
    await session.flush()
    return f"add   ai_offer  {slug}"


async def run(json_path: Path, *, dry_run: bool, update_existing: bool) -> int:
    if not json_path.is_file():
        print(f"ERROR: seed file not found: {json_path}", file=sys.stderr)
        return 1

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    hackathons = list(payload.get("hackathons") or [])
    offers = list(payload.get("ai_offers") or [])
    print(f"Loaded {len(hackathons)} hackathons + {len(offers)} AI offers from {json_path}")

    if dry_run:
        print("Dry-run mode — no database writes.")
        for h in hackathons:
            action = "update" if update_existing else "seed"
            print(f"  would {action} hackathon: {h['slug']} prize={_prize_label_for(h)}")
        for o in offers:
            print(f"  would seed ai_offer:  {o['slug']}")
        return 0

    settings = get_settings()
    engine = create_engine(settings)
    session_maker = create_session_maker(engine)

    lines: list[str] = []
    try:
        async with session_maker() as session:
            official_src, x_src = await _ensure_sources(session)
            repo = ListingRepository(session)
            for item in hackathons:
                lines.append(
                    await _seed_hackathon(
                        session,
                        repo,
                        item,
                        official_src,
                        x_src,
                        dry_run=False,
                        update_existing=update_existing,
                    )
                )
            for item in offers:
                lines.append(
                    await _seed_ai_offer(
                        session,
                        repo,
                        item,
                        official_src,
                        x_src,
                        dry_run=False,
                        update_existing=update_existing,
                    )
                )
            await session.commit()
    finally:
        await engine.dispose()

    added = sum(1 for line in lines if line.startswith("add"))
    updated = sum(1 for line in lines if line.startswith("upd"))
    skipped = sum(1 for line in lines if line.startswith("skip"))
    for line in lines:
        print(line)
    print(f"Done. added={added} updated={updated} skipped={skipped} total={len(lines)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed catalogue from X MCP collection JSON")
    parser.add_argument(
        "--json-path",
        type=Path,
        default=DEFAULT_JSON,
        help=f"Path to seed_listings.json (default: {DEFAULT_JSON})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned inserts without writing to the database",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update prize/title/description on existing hackathon slugs (idempotent seed alone only inserts)",
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            run(args.json_path, dry_run=args.dry_run, update_existing=args.update)
        )
    )


if __name__ == "__main__":
    main()
