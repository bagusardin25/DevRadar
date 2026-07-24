"""Unit tests for review service transitions and audit atomicity."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AdminAuditLog
from app.auth.sessions import AdminIdentity
from app.catalog.enums import (
    ReviewCandidateType,
    ReviewItemState,
    VerificationStatus,
)
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.errors import ConflictError
from app.review.models import ReviewItem
from app.review.schemas import (
    ApproveReviewRequest,
    MergeReviewRequest,
    RejectReviewRequest,
)
from app.review.service import ReviewService
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
        github_id="111",
        login="admin",
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
