"""Submission review pipeline: build (pure) + apply (DB enrichment)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_review.schemas import ReviewRecommendation
from app.catalog.enums import (
    ListingKind,
    ReviewCandidateType,
    ReviewItemState,
    SubmissionState,
    VerificationStatus,
)
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.review.models import ReviewItem
from app.submissions.models import CommunitySubmission
from app.submissions.review_pipeline import (
    apply_submission_review,
    build_submission_review,
)

NOW = datetime(2026, 7, 27, tzinfo=UTC)


def _disabled_settings() -> Settings:
    """Force the heuristic path so tests never touch the network."""
    return Settings(llm_provider="disabled", llm_api_key="")


def _fetch_result(
    *,
    submission_deadline: str,
    registration_deadline: str = "2026-08-01T00:00:00+00:00",
    ok: bool = True,
) -> dict:
    return {
        "ok": ok,
        "final_url": "https://example.com/hack-2026",
        "listing_kind": "hackathon",
        "extraction": {
            "method": "rules",
            "llm_attempted": False,
            "errors": [],
            "field_sources": {},
            "fields": {
                "title": "Community Hack 2026",
                "organizer": "Org",
                "mode": "online",
                "official_url": "https://example.com/hack-2026",
                "registration_deadline": registration_deadline,
                "submission_deadline": submission_deadline,
                "technologies": ["Python", "AI"],
                "prize_value": 10000,
                "prize_currency": "USD",
            },
        },
    }


@pytest.fixture
async def session() -> AsyncSession:
    settings = Settings()
    engine = create_engine(settings)
    maker = create_session_maker(engine)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_build_review_expired_rejects() -> None:
    outcome = await build_submission_review(
        _fetch_result(
            registration_deadline="2026-05-01T00:00:00+00:00",
            submission_deadline="2026-06-01T00:00:00+00:00",
        ),
        claimed_type="hackathon",
        settings=_disabled_settings(),
        now=NOW,
    )
    assert outcome.result.status is VerificationStatus.EXPIRED
    assert outcome.ai_review.recommendation is ReviewRecommendation.REJECT
    assert outcome.ai_review.engine == "heuristic"
    assert outcome.candidate.kind is ListingKind.HACKATHON


@pytest.mark.asyncio
async def test_build_review_uses_claimed_type_over_fetch_default() -> None:
    fetch = _fetch_result(submission_deadline="2026-09-01T00:00:00+00:00")
    fetch["listing_kind"] = "hackathon"  # worker default
    outcome = await build_submission_review(
        fetch, claimed_type="ai_offer", settings=_disabled_settings(), now=NOW
    )
    # claimed_type is authoritative even though the fetch defaulted to hackathon.
    assert outcome.candidate.kind is ListingKind.AI_OFFER


async def _make_open_submission(session: AsyncSession) -> CommunitySubmission:
    submission = CommunitySubmission(
        tracking_id=uuid4().hex,
        original_url="https://example.com/hack-2026",
        canonical_url="https://example.com/hack-2026",
        claimed_type="hackathon",
        claimed_title="Community Hack 2026",
        ip_hash="hash",
        state=SubmissionState.QUEUED,
        metadata_json={"host": "example.com"},
    )
    session.add(submission)
    await session.flush()
    session.add(
        ReviewItem(
            candidate_type=ReviewCandidateType.COMMUNITY_SUBMISSION,
            candidate_id=submission.id,
            candidate_snapshot={
                "url": submission.canonical_url,
                "claimedTitle": "Community Hack 2026",
            },
            reason="Community submission awaiting verification",
            priority=60,
            state=ReviewItemState.OPEN,
        )
    )
    await session.flush()
    return submission


@pytest.mark.asyncio
async def test_apply_enriches_open_review_item(session: AsyncSession) -> None:
    submission = await _make_open_submission(session)

    review = await apply_submission_review(
        session,
        submission.id,
        _fetch_result(submission_deadline="2026-09-01T00:00:00+00:00"),
        settings=_disabled_settings(),
        now=NOW,
    )
    assert review is not None

    item = (
        await session.execute(
            ReviewItem.__table__.select().where(
                ReviewItem.candidate_id == submission.id
            )
        )
    ).first()
    assert item is not None
    snapshot = item.candidate_snapshot
    assert "aiReview" in snapshot
    assert snapshot["aiReview"]["recommendation"] in {
        "approve",
        "reject",
        "needs_more_info",
    }
    assert "verification" in snapshot
    # Original snapshot keys are preserved.
    assert snapshot["url"] == "https://example.com/hack-2026"
    assert item.version == 2
    assert item.reason.startswith("AI initial review:")

    await session.refresh(submission)
    assert submission.state == SubmissionState.AWAITING_ADMIN
    assert submission.reviewed_at == NOW
    assert snapshot["kind"] == "hackathon"
    assert snapshot["fields"]["organizer"] == "Org"
    assert snapshot["aiUsage"]["calls"] == []
    assert snapshot["aiUsage"]["totalTokens"] == 0
    assert snapshot["aiUsage"]["estimatedCostUsd"] == "0.00000000"
    assert snapshot["aiUsage"]["pricingVersion"] == "2026-07-27"


@pytest.mark.asyncio
async def test_apply_skips_already_resolved_item(session: AsyncSession) -> None:
    submission = await _make_open_submission(session)
    item = (
        await session.execute(
            ReviewItem.__table__.select().where(
                ReviewItem.candidate_id == submission.id
            )
        )
    ).first()
    # An admin already decided — the AI pass must not clobber it.
    await session.execute(
        ReviewItem.__table__.update()
        .where(ReviewItem.candidate_id == submission.id)
        .values(state=ReviewItemState.APPROVED)
    )
    await session.flush()

    review = await apply_submission_review(
        session,
        submission.id,
        _fetch_result(submission_deadline="2026-09-01T00:00:00+00:00"),
        settings=_disabled_settings(),
        now=NOW,
    )
    assert review is None
    refreshed = (
        await session.execute(
            ReviewItem.__table__.select().where(
                ReviewItem.candidate_id == submission.id
            )
        )
    ).first()
    assert "aiReview" not in refreshed.candidate_snapshot
    assert refreshed.version == item.version
