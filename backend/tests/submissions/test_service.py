"""Unit/service tests for community submissions."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import ReviewCandidateType, ReviewItemState, SubmissionState
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.errors import ForbiddenError, RateLimitError, ValidationError
from app.review.models import ReviewItem
from app.submissions.enqueue import InMemorySubmissionEnqueue
from app.submissions.models import CommunitySubmission
from app.submissions.schemas import SubmissionCreateRequest
from app.submissions.security import hash_ip, job_idempotency_key
from app.submissions.service import AbuseContext, SubmissionService
from app.submissions.url_policy import canonicalize_url


@pytest.fixture
async def session() -> AsyncSession:
    settings = Settings()
    engine = create_engine(settings)
    maker = create_session_maker(engine)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def enqueue() -> InMemorySubmissionEnqueue:
    return InMemorySubmissionEnqueue()


@pytest.fixture
def service(
    session: AsyncSession, settings: Settings, enqueue: InMemorySubmissionEnqueue
) -> SubmissionService:
    return SubmissionService(
        session,
        settings,
        enqueue,
        rate_limit_store={},
    )


def _cmd(**kwargs: object) -> SubmissionCreateRequest:
    base = {
        "url": "https://example.com/hackathon/2026",
        "form_opened_at": time.time() - 5,
    }
    base.update(kwargs)
    return SubmissionCreateRequest.model_validate(base)


def _abuse(**kwargs: object) -> AbuseContext:
    base: dict[str, object] = {"ip_address": "203.0.113.10"}
    base.update(kwargs)
    return AbuseContext(**base)  # type: ignore[arg-type]


class TestUrlPolicy:
    def test_canonicalizes_https_and_strips_fragment(self) -> None:
        c = canonicalize_url("HTTPS://Example.COM/path/?b=2&a=1#frag")
        assert c.canonical == "https://example.com/path/?a=1&b=2"
        assert c.host == "example.com"

    def test_adds_https_when_missing_scheme(self) -> None:
        c = canonicalize_url("example.com/foo")
        assert c.scheme == "https"
        assert c.canonical.startswith("https://example.com/foo")

    def test_rejects_ftp(self) -> None:
        with pytest.raises(ValidationError):
            canonicalize_url("ftp://example.com/file")

    def test_rejects_localhost(self) -> None:
        with pytest.raises(ValidationError):
            canonicalize_url("http://localhost/admin")

    def test_rejects_private_ip(self) -> None:
        with pytest.raises(ValidationError):
            canonicalize_url("http://192.168.1.10/hack")

    def test_rejects_loopback(self) -> None:
        with pytest.raises(ValidationError):
            canonicalize_url("http://127.0.0.1/")

    def test_rejects_metadata_ip(self) -> None:
        with pytest.raises(ValidationError):
            canonicalize_url("http://169.254.169.254/latest/meta-data")

    def test_rejects_credentials(self) -> None:
        with pytest.raises(ValidationError):
            canonicalize_url("https://user:pass@example.com/x")


class TestSubmissionService:
    async def test_happy_path_queues_and_enqueues_after_commit(
        self,
        session: AsyncSession,
        service: SubmissionService,
        enqueue: InMemorySubmissionEnqueue,
    ) -> None:
        # Random URL — the test database is persistent and enforces a 24h
        # duplicate window per canonical URL.
        url = f"https://devpost.com/software/awesome-{uuid4().hex[:8]}"
        receipt = await service.submit_candidate(
            _cmd(url=url),
            _abuse(),
        )
        assert receipt.status == SubmissionState.QUEUED
        assert receipt.tracking_id
        assert receipt.duplicate is False
        # Hooks registered, not yet run (commit happens outside service).
        hooks = session.info.get("after_commit_hooks", [])
        assert len(hooks) == 1
        await session.commit()
        for hook in hooks:
            await hook()
        assert len(enqueue.calls) == 1
        assert enqueue.calls[0]["canonical_url"] == url

    async def test_honeypot_rejected(
        self, service: SubmissionService
    ) -> None:
        with pytest.raises(ForbiddenError):
            await service.submit_candidate(
                _cmd(website="http://spam.example"),
                _abuse(),
            )

    async def test_too_fast_rejected(self, service: SubmissionService) -> None:
        with pytest.raises(ForbiddenError):
            await service.submit_candidate(
                _cmd(form_opened_at=time.time()),
                _abuse(),
            )

    async def test_duplicate_url_within_window(
        self,
        session: AsyncSession,
        service: SubmissionService,
        enqueue: InMemorySubmissionEnqueue,
    ) -> None:
        first = await service.submit_candidate(
            _cmd(url="https://example.com/dup-event"),
            _abuse(ip_address="203.0.113.1"),
        )
        await session.commit()
        for hook in session.info.get("after_commit_hooks", []):
            await hook()
        session.info["after_commit_hooks"] = []

        second = await service.submit_candidate(
            _cmd(url="https://example.com/dup-event"),
            _abuse(ip_address="203.0.113.2"),
        )
        assert second.duplicate is True
        assert second.status == SubmissionState.DUPLICATE
        # No new enqueue hook for duplicates
        assert session.info.get("after_commit_hooks", []) == []
        assert first.tracking_id != second.tracking_id

    async def test_idempotency_key_returns_same_receipt(
        self,
        session: AsyncSession,
        service: SubmissionService,
    ) -> None:
        key = f"idem-{uuid4().hex}"
        first = await service.submit_candidate(
            _cmd(url="https://example.com/idem-a"),
            _abuse(idempotency_key=key),
        )
        await session.commit()
        session.info["after_commit_hooks"] = []

        second = await service.submit_candidate(
            _cmd(url="https://example.com/idem-a"),
            _abuse(idempotency_key=key),
        )
        assert first.tracking_id == second.tracking_id

    async def test_rate_limit(self, service: SubmissionService) -> None:
        ip = "198.51.100.50"
        for i in range(10):
            await service.submit_candidate(
                _cmd(url=f"https://example.com/rl-{i}-{uuid4().hex[:6]}"),
                _abuse(ip_address=ip),
            )
        with pytest.raises(RateLimitError):
            await service.submit_candidate(
                _cmd(url=f"https://example.com/rl-over-{uuid4().hex[:6]}"),
                _abuse(ip_address=ip),
            )

    async def test_job_idempotency_key_stable_for_url(self) -> None:
        a = job_idempotency_key("https://example.com/x")
        b = job_idempotency_key("https://example.com/x")
        c = job_idempotency_key("https://example.com/y")
        assert a == b
        assert a != c

    async def test_ip_hash_is_not_plaintext(self, settings: Settings) -> None:
        h = hash_ip("203.0.113.9", settings.session_secret)
        assert "203.0.113.9" not in h
        assert len(h) == 64

    async def test_public_status(
        self,
        session: AsyncSession,
        service: SubmissionService,
    ) -> None:
        receipt = await service.submit_candidate(
            _cmd(
                url=f"https://example.com/status-check-{uuid4().hex[:8]}",
                claimed_type="hackathon",
            ),
            _abuse(),
        )
        await session.commit()
        status = await service.get_public_submission_status(receipt.tracking_id)
        assert status.tracking_id == receipt.tracking_id
        assert status.status == SubmissionState.QUEUED
        assert status.claimed_type is not None
        assert "queued" in status.message.lower() or "verification" in status.message.lower()

    async def test_public_status_includes_sanitized_ai_review(
        self,
        session: AsyncSession,
        service: SubmissionService,
    ) -> None:
        receipt = await service.submit_candidate(
            _cmd(
                url=f"https://example.com/review-status-{uuid4().hex[:8]}",
                claimed_type="ai_offer",
                claimed_title="Free Model Credits",
            ),
            _abuse(),
        )
        await session.flush()
        item = (
            await session.execute(
                select(ReviewItem).where(
                    ReviewItem.candidate_snapshot["trackingId"].as_string()
                    == receipt.tracking_id
                )
            )
        ).scalar_one()
        snapshot = dict(item.candidate_snapshot)
        snapshot["aiReview"] = {
            "recommendation": "needs_more_info",
            "confidence": 64,
            "summary": "The terms page needs a final human check.",
            "concerns": [
                {"severity": "medium", "message": "Expiry is unclear."}
            ],
            "suggestedFields": {"offer_value": "$50"},
            "engine": "openai:test",
            "model": "secret-model-name",
            "generatedAt": "2026-07-27T00:00:00+00:00",
        }
        item.candidate_snapshot = snapshot
        submission = await session.get(CommunitySubmission, item.candidate_id)
        assert submission is not None
        submission.state = SubmissionState.AWAITING_ADMIN
        submission.reviewed_at = datetime(2026, 7, 27, tzinfo=UTC)
        await session.flush()

        status = await service.get_public_submission_status(receipt.tracking_id)

        assert status.status == SubmissionState.AWAITING_ADMIN
        assert status.review is not None
        assert status.review.recommendation == "needs_more_info"
        assert status.review.confidence == 64
        dumped = status.model_dump()
        assert "suggested_fields" not in dumped["review"]
        assert "model" not in dumped["review"]

    async def test_unknown_tracking_404(self, service: SubmissionService) -> None:
        from app.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await service.get_public_submission_status("does-not-exist")

    async def test_queues_review_item_for_admin(
        self,
        session: AsyncSession,
        service: SubmissionService,
    ) -> None:
        """A live submission must appear in the admin review queue immediately."""
        url = f"https://example.com/for-admin-{uuid4().hex[:8]}"
        receipt = await service.submit_candidate(
            _cmd(
                url=url,
                claimed_title="Community Hack 2026",
                claimed_type="hackathon",
                notes="Found on Discord",
            ),
            _abuse(),
        )
        await session.commit()

        items = list(
            (
                await session.execute(
                    select(ReviewItem).where(
                        ReviewItem.candidate_type
                        == ReviewCandidateType.COMMUNITY_SUBMISSION.value
                    )
                )
            )
            .scalars()
            .all()
        )
        matching = [
            item
            for item in items
            if item.candidate_snapshot.get("trackingId") == receipt.tracking_id
        ]
        assert len(matching) == 1
        item = matching[0]
        assert item.state == ReviewItemState.OPEN
        snapshot = item.candidate_snapshot
        assert snapshot["url"] == url
        assert snapshot["claimedTitle"] == "Community Hack 2026"
        assert snapshot["claimedType"] == "hackathon"
        # Submitter PII must never surface to reviewers.
        assert "email" not in snapshot
        assert "ipHash" not in snapshot

    async def test_duplicate_submission_does_not_double_queue(
        self,
        session: AsyncSession,
        service: SubmissionService,
    ) -> None:
        """Second submission of the same URL is a duplicate — no new queue item."""
        url = f"https://example.com/dedupe-{uuid4().hex[:8]}"
        first = await service.submit_candidate(_cmd(url=url), _abuse(ip_address="203.0.113.9"))
        await session.commit()
        session.info["after_commit_hooks"] = []

        second = await service.submit_candidate(_cmd(url=url), _abuse(ip_address="203.0.113.10"))
        await session.commit()

        assert second.duplicate is True
        items = list(
            (
                await session.execute(
                    select(ReviewItem).where(
                        ReviewItem.candidate_type
                        == ReviewCandidateType.COMMUNITY_SUBMISSION.value
                    )
                )
            )
            .scalars()
            .all()
        )
        tracking_ids = {i.candidate_snapshot.get("trackingId") for i in items}
        assert first.tracking_id in tracking_ids
        assert second.tracking_id not in tracking_ids
