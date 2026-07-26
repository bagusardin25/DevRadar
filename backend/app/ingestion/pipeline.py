"""Orchestrate candidate → verify → listing / review_item (idempotent)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.builders import build_ai_offer_create, build_hackathon_create
from app.catalog.enums import (
    ListingKind,
    ReviewCandidateType,
    ReviewItemState,
    VerificationStatus,
)
from app.catalog.models import Listing
from app.catalog.repository import ListingRepository
from app.catalog.schemas import ListingCreateSchema
from app.ingestion.models import VerificationEvent
from app.ingestion.normalizer import CandidateListing
from app.ingestion.verifier import VerificationEvidence, VerificationResult, verify
from app.review.models import ReviewItem

PIPELINE_VERSION = "1.0.0"


@dataclass(slots=True)
class PipelineOutcome:
    listing_id: UUID | None
    review_item_id: UUID | None
    status: VerificationStatus
    created_listing: bool
    created_review: bool
    idempotent_replay: bool
    score_total: int
    reasons: list[str]


def slugify_title(title: str) -> str:
    import re

    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "listing"
    return f"{base}-{uuid4().hex[:8]}"


class IngestionPipeline:
    """Persist verification outcomes idempotently by job key."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ListingRepository(session)

    async def process_candidate(
        self,
        candidate: CandidateListing,
        evidence: VerificationEvidence,
        *,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> PipelineOutcome:
        now = now or datetime.now(UTC)

        # Idempotency: prior verification event with same key in notes/metadata
        existing = await self._find_by_idempotency(idempotency_key)
        if existing is not None:
            return existing

        result = verify(candidate, evidence, now=now)
        return await self._apply(candidate, result, evidence, idempotency_key, now)

    async def _find_by_idempotency(self, key: str) -> PipelineOutcome | None:
        # Filter in Python for portable JSONB key lookup.
        items = list((await self._session.execute(select(ReviewItem))).scalars().all())
        for item in items:
            snap = item.candidate_snapshot or {}
            if snap.get("pipeline_idempotency_key") == key:
                return PipelineOutcome(
                    listing_id=item.listing_id,
                    review_item_id=item.id,
                    status=VerificationStatus.NEEDS_REVIEW,
                    created_listing=False,
                    created_review=False,
                    idempotent_replay=True,
                    score_total=0,
                    reasons=["idempotent_replay"],
                )
        listings = list((await self._session.execute(select(Listing))).scalars().all())
        for listing in listings:
            breakdown = listing.score_breakdown or {}
            if breakdown.get("pipelineIdempotencyKey") == key:
                return PipelineOutcome(
                    listing_id=listing.id,
                    review_item_id=None,
                    status=VerificationStatus(str(listing.verification_status)),
                    created_listing=False,
                    created_review=False,
                    idempotent_replay=True,
                    score_total=int(breakdown.get("total") or 0),
                    reasons=["idempotent_replay"],
                )
        return None

    async def _apply(
        self,
        candidate: CandidateListing,
        result: VerificationResult,
        evidence: VerificationEvidence,
        idempotency_key: str,
        now: datetime,
    ) -> PipelineOutcome:
        score_dict: dict[str, Any] = dict(result.score.as_dict())
        score_dict["total"] = result.score.total
        score_dict["pipelineIdempotencyKey"] = idempotency_key

        listing_id: UUID | None = None
        review_id: UUID | None = None
        created_listing = False
        created_review = False

        if result.publishable and result.status in {
            VerificationStatus.VERIFIED_ACTIVE,
            VerificationStatus.LIKELY_ACTIVE,
            VerificationStatus.REGISTRATION_CLOSED,
        }:
            listing = await self._create_listing(candidate, result, score_dict, now)
            listing_id = listing.id
            created_listing = True
            self._session.add(
                VerificationEvent(
                    listing_id=listing.id,
                    event_type="pipeline_publish",
                    previous_status=None,
                    new_status=result.status,
                    notes="; ".join(result.reasons),
                    deterministic_checks=result.checks,
                    score_breakdown=score_dict,
                    checked_urls=[candidate.official_url],
                    actor_type="pipeline",
                )
            )
        else:
            # Always create review item for needs_review / cancelled / low confidence
            item = ReviewItem(
                candidate_type=ReviewCandidateType.LISTING,
                candidate_snapshot={
                    "title": candidate.title,
                    "kind": candidate.kind.value,
                    "fields": _jsonable(candidate.fields),
                    "canonical_url": candidate.canonical_url,
                    "pipeline_idempotency_key": idempotency_key,
                    "verification": {
                        "status": result.status.value,
                        "reasons": result.reasons,
                        "checks": result.checks,
                        "score": score_dict,
                    },
                },
                reason="; ".join(result.reasons) or "needs_review",
                priority=80 if evidence.only_tier3 else 50,
                state=ReviewItemState.OPEN,
            )
            self._session.add(item)
            await self._session.flush()
            review_id = item.id
            created_review = True

            # Optionally still create a needs_review listing shell for provenance
            if result.status == VerificationStatus.NEEDS_REVIEW and candidate.title:
                listing = await self._create_listing(
                    candidate,
                    result,
                    score_dict,
                    now,
                    force_status=VerificationStatus.NEEDS_REVIEW,
                )
                listing_id = listing.id
                created_listing = True
                item.listing_id = listing.id
                self._session.add(
                    VerificationEvent(
                        listing_id=listing.id,
                        event_type="pipeline_review",
                        previous_status=None,
                        new_status=result.status,
                        notes="; ".join(result.reasons),
                        deterministic_checks=result.checks,
                        score_breakdown=score_dict,
                        checked_urls=[candidate.official_url],
                        actor_type="pipeline",
                    )
                )

        await self._session.flush()
        return PipelineOutcome(
            listing_id=listing_id,
            review_item_id=review_id,
            status=result.status,
            created_listing=created_listing,
            created_review=created_review,
            idempotent_replay=False,
            score_total=result.score.total,
            reasons=list(result.reasons),
        )

    async def _create_listing(
        self,
        candidate: CandidateListing,
        result: VerificationResult,
        score_dict: dict[str, Any],
        now: datetime,
        force_status: VerificationStatus | None = None,
    ) -> Listing:
        status = force_status or result.status
        slug = slugify_title(candidate.title)
        listing_data = ListingCreateSchema(
            kind=candidate.kind,
            slug=slug,
            title=candidate.title,
            description=candidate.description,
            verification_status=status,
            confidence_score=Decimal(str(result.score.confidence)),
            score_breakdown=score_dict,
            published_at=now
            if status
            in {VerificationStatus.VERIFIED_ACTIVE, VerificationStatus.LIKELY_ACTIVE}
            else None,
            last_checked_at=now,
        )
        f = candidate.fields
        if candidate.kind == ListingKind.HACKATHON:
            return await self._repo.create_hackathon(
                listing_data,
                build_hackathon_create(
                    f,
                    official_url=candidate.official_url,
                    suitable_reasons=list(result.reasons),
                ),
            )
        return await self._repo.create_ai_offer(
            listing_data,
            build_ai_offer_create(
                f,
                official_url=candidate.official_url,
                title=candidate.title,
                suitable_reasons=list(result.reasons),
            ),
        )


def _jsonable(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, (Decimal, UUID)):
            out[k] = str(v)
        else:
            out[k] = v
    return out
