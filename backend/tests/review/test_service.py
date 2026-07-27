"""Unit tests for review service transitions and audit atomicity."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AdminAuditLog
from app.auth.sessions import AdminIdentity
from app.catalog.enums import (
    ListingKind,
    ReviewCandidateType,
    ReviewItemState,
    SubmissionState,
    VerificationStatus,
)
from app.catalog.models import Listing
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.errors import ConflictError, ValidationError
from app.review.models import ReviewItem
from app.review.schemas import (
    ApproveReviewRequest,
    MergeReviewRequest,
    RejectReviewRequest,
)
from app.review.service import ReviewService
from app.submissions.models import CommunitySubmission
from tests.factories import seed_hackathon


@pytest.fixture
async def session() -> AsyncSession:
    settings = Settings()
    engine = create_engine(settings)
    maker = create_session_maker(engine)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


def _admin() -> AdminIdentity:
    return AdminIdentity(
        subject="111",
        email="admin@example.com",
        admin_user_id=str(uuid4()),
        csrf_token="csrf-token",
        session_id="sess",
    )


async def _open_item(
    session: AsyncSession,
    *,
    listing_id=None,
    version: int = 1,
) -> ReviewItem:
    item = ReviewItem(
        candidate_type=ReviewCandidateType.LISTING,
        candidate_snapshot={"title": "Candidate"},
        reason="needs human review",
        priority=10,
        state=ReviewItemState.OPEN,
        listing_id=listing_id,
        version=version,
    )
    session.add(item)
    await session.flush()
    return item


class TestReviewService:
    async def test_approve_publishes_listing_and_writes_audit(
        self, session: AsyncSession
    ) -> None:
        listing = await seed_hackathon(
            session,
            slug=f"rev-ap-{uuid4().hex[:8]}",
            title="Needs Approve",
            status=VerificationStatus.NEEDS_REVIEW,
        )
        item = await _open_item(session, listing_id=listing.id)
        svc = ReviewService(session)
        result = await svc.approve_review_item(
            item.id,
            ApproveReviewRequest(expected_version=1, notes="LGTM"),
            _admin(),
            trace_id="trace-1",
        )
        assert result.state == ReviewItemState.APPROVED or str(result.state) == "approved"
        assert result.version == 2
        await session.refresh(listing)
        assert str(listing.verification_status) == VerificationStatus.VERIFIED_ACTIVE.value
        assert listing.published_at is not None

        audits = list(
            (
                await session.execute(
                    select(AdminAuditLog).where(AdminAuditLog.action == "review.approve")
                )
            )
            .scalars()
            .all()
        )
        assert any(a.target_id == item.id for a in audits)

    async def test_reject_with_reason(self, session: AsyncSession) -> None:
        item = await _open_item(session)
        svc = ReviewService(session)
        result = await svc.reject_review_item(
            item.id,
            RejectReviewRequest(expected_version=1, reason="Spam link"),
            _admin(),
        )
        assert str(result.state) == ReviewItemState.REJECTED.value
        assert result.resolution is not None
        assert result.resolution["reason"] == "Spam link"

    async def test_merge_into_listing(self, session: AsyncSession) -> None:
        listing = await seed_hackathon(
            session,
            slug=f"rev-mg-{uuid4().hex[:8]}",
            title="Merge Target",
            status=VerificationStatus.VERIFIED_ACTIVE,
        )
        item = await _open_item(session)
        svc = ReviewService(session)
        result = await svc.merge_review_item(
            item.id,
            MergeReviewRequest(
                expected_version=1,
                target_listing_id=listing.id,
                notes="Same event",
            ),
            _admin(),
        )
        assert str(result.state) == ReviewItemState.MERGED.value
        assert result.listing_id == listing.id

    async def test_version_conflict(self, session: AsyncSession) -> None:
        item = await _open_item(session, version=3)
        svc = ReviewService(session)
        with pytest.raises(ConflictError):
            await svc.reject_review_item(
                item.id,
                RejectReviewRequest(expected_version=1, reason="stale"),
                _admin(),
            )

    async def test_approve_community_submission_publishes_listing(
        self, session: AsyncSession
    ) -> None:
        """Approving a submission publishes a real catalogue row."""
        submission = CommunitySubmission(
            tracking_id=f"track-{uuid4().hex[:12]}",
            original_url="https://example.com/comm-approve",
            canonical_url=f"https://example.com/comm-approve-{uuid4().hex[:6]}",
            claimed_type="hackathon",
            claimed_title="Community Hack",
            ip_hash="deadbeef",
            state=SubmissionState.QUEUED,
            metadata_json={"host": "example.com"},
        )
        session.add(submission)
        await session.flush()

        item = ReviewItem(
            candidate_type=ReviewCandidateType.COMMUNITY_SUBMISSION,
            candidate_id=submission.id,
            candidate_snapshot={
                "source": "community_submission",
                "trackingId": submission.tracking_id,
                "url": submission.canonical_url,
                "claimedTitle": submission.claimed_title,
                "claimedType": submission.claimed_type,
            },
            reason="Community submission awaiting verification",
            priority=60,
            state=ReviewItemState.OPEN,
            version=1,
        )
        session.add(item)
        await session.flush()

        svc = ReviewService(session)
        result = await svc.approve_review_item(
            item.id,
            ApproveReviewRequest(
                expected_version=1,
                notes="Verified manually",
                corrections={
                    "fields": {
                        "organizer": "Test Org",
                        "mode": "online",
                    }
                },
            ),
            _admin(),
        )
        assert str(result.state) == ReviewItemState.APPROVED.value
        assert result.listing_id is not None

        listing = await session.get(Listing, result.listing_id)
        assert listing is not None
        assert str(listing.kind) == ListingKind.HACKATHON.value
        assert str(listing.verification_status) == VerificationStatus.VERIFIED_ACTIVE.value
        assert listing.title == "Community Hack"

        await session.refresh(submission)
        assert str(submission.state) == SubmissionState.ACCEPTED.value

    async def test_approve_uses_ai_review_extracted_ai_offer_fields(
        self, session: AsyncSession
    ) -> None:
        submission = CommunitySubmission(
            tracking_id=f"track-{uuid4().hex[:12]}",
            original_url="https://example.com/free-credits",
            canonical_url=f"https://example.com/free-credits-{uuid4().hex[:6]}",
            claimed_type="ai_offer",
            claimed_title="Acme Free Credits",
            ip_hash="deadbeef",
            state=SubmissionState.AWAITING_ADMIN,
            metadata_json={"host": "example.com"},
        )
        session.add(submission)
        await session.flush()
        item = ReviewItem(
            candidate_type=ReviewCandidateType.COMMUNITY_SUBMISSION,
            candidate_id=submission.id,
            candidate_snapshot={
                "source": "community_submission",
                "trackingId": submission.tracking_id,
                "url": submission.canonical_url,
                "title": "Acme Free Credits",
                "kind": "ai_offer",
                "officialUrl": submission.canonical_url,
                "fields": {
                    "product_name": "Acme Studio",
                    "provider": "Acme AI",
                    "offer_type": "free_credits",
                    "offer_value": "$50 credits",
                    "requirements": ["Developer account"],
                    "official_terms_url": submission.canonical_url,
                    "claim_url": submission.canonical_url,
                },
            },
            reason="AI initial review: approve (88/100)",
            priority=45,
            state=ReviewItemState.OPEN,
            version=2,
        )
        session.add(item)
        await session.flush()

        result = await ReviewService(session).approve_review_item(
            item.id,
            ApproveReviewRequest(expected_version=2, notes="AI fields verified"),
            _admin(),
        )

        listing = await session.get(Listing, result.listing_id)
        assert listing is not None
        await session.refresh(listing, attribute_names=["ai_offer"])
        assert str(listing.kind) == ListingKind.AI_OFFER.value
        assert listing.title == "Acme Free Credits"
        assert listing.ai_offer is not None
        assert listing.ai_offer.provider == "Acme AI"
        assert listing.ai_offer.offer_value == "$50 credits"

    async def test_reject_community_submission_updates_submission_state(
        self, session: AsyncSession
    ) -> None:
        submission = CommunitySubmission(
            tracking_id=f"track-{uuid4().hex[:12]}",
            original_url="https://example.com/comm-reject",
            canonical_url=f"https://example.com/comm-reject-{uuid4().hex[:6]}",
            ip_hash="deadbeef",
            state=SubmissionState.QUEUED,
            metadata_json={},
        )
        session.add(submission)
        await session.flush()

        item = ReviewItem(
            candidate_type=ReviewCandidateType.COMMUNITY_SUBMISSION,
            candidate_id=submission.id,
            candidate_snapshot={"trackingId": submission.tracking_id},
            reason="Community submission awaiting verification",
            priority=60,
            state=ReviewItemState.OPEN,
            version=1,
        )
        session.add(item)
        await session.flush()

        svc = ReviewService(session)
        await svc.reject_review_item(
            item.id,
            RejectReviewRequest(expected_version=1, reason="Spam link"),
            _admin(),
        )
        await session.refresh(submission)
        assert str(submission.state) == SubmissionState.REJECTED.value

    async def test_approve_submission_requires_publishable_fields(
        self, session: AsyncSession
    ) -> None:
        """Missing kind or URL surfaces as a validation error, not a crash."""
        item = ReviewItem(
            candidate_type=ReviewCandidateType.COMMUNITY_SUBMISSION,
            candidate_id=None,
            candidate_snapshot={"trackingId": "no-url-no-kind"},
            reason="Community submission awaiting verification",
            priority=60,
            state=ReviewItemState.OPEN,
            version=1,
        )
        session.add(item)
        await session.flush()

        svc = ReviewService(session)
        with pytest.raises(ValidationError):
            await svc.approve_review_item(
                item.id,
                ApproveReviewRequest(expected_version=1),
                _admin(),
            )

    async def test_cannot_approve_twice(self, session: AsyncSession) -> None:
        item = await _open_item(session)
        svc = ReviewService(session)
        await svc.approve_review_item(
            item.id,
            ApproveReviewRequest(expected_version=1),
            _admin(),
        )
        with pytest.raises(ConflictError):
            await svc.approve_review_item(
                item.id,
                ApproveReviewRequest(expected_version=2),
                _admin(),
            )
