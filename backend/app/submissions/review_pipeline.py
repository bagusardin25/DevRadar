"""Turn a fetched community submission into an AI initial review.

This closes the gap between "submission landed in the admin queue" and "an admin
has something to judge": after the worker fetches + extracts the URL, run the
deterministic verifier and the AI reviewer, then enrich the submission's OPEN
review item with a `verification` + `aiReview` block. The admin still decides.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, cast
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import the full model graph so SQLAlchemy relationships resolve in the worker.
import app.models  # noqa: F401
from app.ai_review.advisor import build_review_advisor
from app.ai_review.heuristic import unreachable_review
from app.ai_review.schemas import AIReview
from app.catalog.enums import (
    ListingKind,
    ReviewCandidateType,
    ReviewItemState,
    SubmissionState,
)
from app.config import Settings, get_settings
from app.db import create_engine, create_session_maker
from app.ingestion.extraction_schemas import EXTRACTION_SCHEMA_VERSION
from app.ingestion.extractor import EXTRACTOR_VERSION, ExtractionResult
from app.ingestion.normalizer import (
    CandidateListing,
    SourceContext,
    normalize_extraction,
)
from app.ingestion.verifier import VerificationEvidence, VerificationResult, verify
from app.llm_usage import LLMCallUsage, summarize_llm_usage
from app.review.models import ReviewItem
from app.submissions.models import CommunitySubmission

logger = logging.getLogger(__name__)

# Hosts that count as social / unofficial signal (tier-3): a link here can never
# auto-verify and always warrants a human check for an official source.
_SOCIAL_HOSTS = frozenset(
    {
        "x.com",
        "twitter.com",
        "mobile.twitter.com",
        "t.co",
        "reddit.com",
        "www.reddit.com",
        "old.reddit.com",
        "facebook.com",
        "www.facebook.com",
        "m.facebook.com",
        "linkedin.com",
        "www.linkedin.com",
        "medium.com",
        "t.me",
    }
)

# Re-rank the queue by the AI recommendation (higher = more urgent to clear).
_PRIORITY: dict[str, int] = {
    "approve": 45,
    "needs_more_info": 65,
    "reject": 80,
}


def _host(url: str | None) -> str:
    if not url:
        return ""
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _resolve_kind(claimed_type: str | None, fallback: str) -> ListingKind:
    for value in (claimed_type, fallback):
        if not value:
            continue
        try:
            return ListingKind(value)
        except ValueError:
            continue
    return ListingKind.HACKATHON


def _extraction_from_result(
    extraction: dict[str, Any], kind: ListingKind
) -> ExtractionResult:
    """Rebuild an ExtractionResult from the worker's serialized extraction dict."""
    method = cast(
        'Literal["rules", "llm", "hybrid", "failed"]',
        str(extraction.get("method") or "rules"),
    )
    return ExtractionResult(
        schema_version=EXTRACTION_SCHEMA_VERSION,
        extractor_version=EXTRACTOR_VERSION,
        listing_kind=kind,
        fields=dict(extraction.get("fields") or {}),
        method=method,
        field_sources=dict(extraction.get("field_sources") or {}),
        errors=list(extraction.get("errors") or []),
        llm_attempted=bool(extraction.get("llm_attempted", False)),
        llm_usage=LLMCallUsage.from_snapshot(extraction.get("usage")),
    )


def _submission_evidence(
    host: str, *, link_ok: bool, now: datetime
) -> VerificationEvidence:
    social = host in _SOCIAL_HOSTS
    return VerificationEvidence(
        source_tier="tier_3" if social else "tier_2",
        link_ok=link_ok,
        cross_source_count=1,
        last_checked_at=now,
        only_tier3=social,
    )


@dataclass(slots=True)
class SubmissionReviewOutcome:
    candidate: CandidateListing
    result: VerificationResult
    ai_review: AIReview
    usage_summary: dict[str, Any]


async def build_submission_review(
    fetch_result: dict[str, Any],
    *,
    claimed_type: str | None,
    settings: Settings,
    now: datetime | None = None,
) -> SubmissionReviewOutcome:
    """fetch_result → candidate → verify() → AI review. No DB access."""
    now = now or datetime.now(UTC)
    extraction = fetch_result.get("extraction") or {}
    kind = _resolve_kind(claimed_type, str(fetch_result.get("listing_kind") or ""))
    source_url = str(fetch_result.get("final_url") or fetch_result.get("url") or "")

    extraction_result = _extraction_from_result(extraction, kind)
    candidate = normalize_extraction(
        extraction_result,
        SourceContext(
            source_url=source_url or None,
            trust_tier="tier_3" if _host(source_url) in _SOCIAL_HOSTS else "tier_2",
            connector_type="community",
        ),
    )
    evidence = _submission_evidence(
        _host(source_url or candidate.canonical_url),
        link_ok=bool(fetch_result.get("ok", True)),
        now=now,
    )
    result = verify(candidate, evidence, now=now)
    advisor = build_review_advisor(settings)
    ai_review = await advisor.review(
        candidate,
        result,
        page_excerpt=str(fetch_result.get("page_excerpt") or ""),
    )
    return SubmissionReviewOutcome(
        candidate=candidate,
        result=result,
        ai_review=ai_review,
        usage_summary=summarize_llm_usage(
            [extraction_result.llm_usage, ai_review.llm_usage]
        ),
    )


def _verification_block(outcome: SubmissionReviewOutcome) -> dict[str, Any]:
    return {
        "status": outcome.result.status.value,
        "score": outcome.result.score.total,
        "scoreBreakdown": outcome.result.score.as_dict(),
        "reasons": list(outcome.result.reasons),
        "publishable": outcome.result.publishable,
        "checkedUrl": outcome.candidate.canonical_url,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "value"):
        return value.value
    return value


async def apply_submission_review(
    session: AsyncSession,
    submission_id: UUID | str,
    fetch_result: dict[str, Any],
    *,
    settings: Settings,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Enrich the submission's OPEN review item in place. Returns the aiReview dict."""
    now = now or datetime.now(UTC)
    sid = submission_id if isinstance(submission_id, UUID) else UUID(str(submission_id))

    submission = (
        await session.execute(
            select(CommunitySubmission).where(CommunitySubmission.id == sid)
        )
    ).scalar_one_or_none()
    if submission is None:
        logger.info("submission_review_skip_missing", extra={"submission_id": str(sid)})
        return None

    item = (
        await session.execute(
            select(ReviewItem)
            .where(
                ReviewItem.candidate_type == ReviewCandidateType.COMMUNITY_SUBMISSION,
                ReviewItem.candidate_id == sid,
            )
            .order_by(ReviewItem.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    # Never clobber a decision: only enrich an item still awaiting a human.
    if item is None or item.state not in {
        ReviewItemState.OPEN,
        ReviewItemState.IN_PROGRESS,
    }:
        return None

    extraction = fetch_result.get("extraction") if fetch_result else None
    ok = bool(
        fetch_result
        and fetch_result.get("ok")
        and not fetch_result.get("not_modified")
    )

    verification_block: dict[str, Any] | None = None
    if ok and extraction:
        outcome = await build_submission_review(
            fetch_result,
            claimed_type=submission.claimed_type,
            settings=settings,
            now=now,
        )
        ai_review = outcome.ai_review
        verification_block = _verification_block(outcome)
        usage_summary = outcome.usage_summary
    else:
        detail = None
        if fetch_result and fetch_result.get("error"):
            detail = str(fetch_result.get("error"))[:200]
        ai_review = unreachable_review(
            title=submission.claimed_title or "",
            kind=_resolve_kind(submission.claimed_type, ""),
            url=submission.canonical_url,
            detail=detail,
        )
        usage_summary = summarize_llm_usage([])

    snapshot = dict(item.candidate_snapshot or {})
    snapshot["aiReview"] = ai_review.to_snapshot()
    snapshot["aiUsage"] = usage_summary
    if verification_block is not None:
        snapshot["verification"] = verification_block
        snapshot["fields"] = _jsonable(outcome.candidate.fields)
        snapshot["fieldSources"] = dict(outcome.candidate.field_sources)
        snapshot["title"] = outcome.candidate.title
        snapshot["description"] = outcome.candidate.description
        snapshot["kind"] = outcome.candidate.kind.value
        snapshot["officialUrl"] = outcome.candidate.official_url
        snapshot["extraction"] = {
            "method": outcome.candidate.extraction_method,
            "schemaVersion": outcome.candidate.schema_version,
            "warnings": list(outcome.candidate.warnings),
        }
    snapshot["aiReviewedAt"] = now.astimezone(UTC).isoformat()

    # Reassign (not mutate) so SQLAlchemy flags the JSONB column dirty.
    item.candidate_snapshot = snapshot
    item.reason = (
        f"AI initial review: {ai_review.recommendation.value.replace('_', ' ')} "
        f"({ai_review.confidence}/100)"
    )
    item.priority = _PRIORITY.get(ai_review.recommendation.value, item.priority)
    item.version = (item.version or 1) + 1

    # Public lifecycle: the automated pass is complete; a human still decides.
    submission.state = SubmissionState.AWAITING_ADMIN
    submission.reviewed_at = now
    submission.last_error = (
        str(fetch_result.get("error"))[:1000]
        if fetch_result and fetch_result.get("error")
        else None
    )
    metadata = dict(submission.metadata_json or {})
    metadata["aiReviewEngine"] = ai_review.engine
    metadata["aiRecommendation"] = ai_review.recommendation.value
    metadata["aiEstimatedCostUsd"] = usage_summary.get("estimatedCostUsd")
    metadata["aiTotalTokens"] = usage_summary.get("totalTokens", 0)
    submission.metadata_json = metadata

    await session.flush()
    logger.info(
        "submission_ai_reviewed",
        extra={
            "submission_id": str(sid),
            "recommendation": ai_review.recommendation.value,
            "engine": ai_review.engine,
        },
    )
    return ai_review.to_snapshot()


async def finalize_submission_review(
    submission_id: UUID | str,
    fetch_result: dict[str, Any],
    *,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    """Worker entrypoint: own a session, enrich the review item, commit."""
    settings = settings or get_settings()
    engine = create_engine(settings)
    session_maker = create_session_maker(engine)
    try:
        async with session_maker() as session:
            review = await apply_submission_review(
                session, submission_id, fetch_result, settings=settings
            )
            await session.commit()
            return review
    finally:
        await engine.dispose()
