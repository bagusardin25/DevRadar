"""Community submission application service."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import ListingKind, SubmissionState
from app.config import Settings
from app.errors import ForbiddenError, NotFoundError, RateLimitError, ValidationError
from app.submissions.enqueue import SubmissionEnqueuePort
from app.submissions.models import CommunitySubmission
from app.submissions.schemas import (
    SubmissionCreateRequest,
    SubmissionReceipt,
    SubmissionStatusPublic,
)
from app.submissions.security import (
    encrypt_email,
    hash_email,
    hash_ip,
    hash_user_agent,
    job_idempotency_key,
)
from app.submissions.url_policy import canonicalize_url

MIN_SUBMIT_SECONDS = 2.0
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW_SECONDS = 3600
DUPLICATE_URL_WINDOW = timedelta(hours=24)

STATUS_MESSAGES: dict[SubmissionState, str] = {
    SubmissionState.RECEIVED: "We received your submission.",
    SubmissionState.QUEUED: "Your submission is queued for verification.",
    SubmissionState.PROCESSING: "We are verifying the linked opportunity.",
    SubmissionState.DUPLICATE: "This URL was already submitted recently.",
    SubmissionState.ACCEPTED: "The opportunity was accepted into the catalogue.",
    SubmissionState.REJECTED: "This submission could not be verified.",
}


@dataclass(slots=True)
class AbuseContext:
    ip_address: str
    user_agent: str | None = None
    idempotency_key: str | None = None


class SubmissionService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        enqueue: SubmissionEnqueuePort,
        *,
        redis_url: str | None = None,
        rate_limit_store: dict[str, list[float]] | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._enqueue = enqueue
        self._redis_url = redis_url or settings.redis_url
        # In-process fallback used by unit tests when Redis is not required.
        self._rate_limit_store = rate_limit_store

    async def submit_candidate(
        self,
        command: SubmissionCreateRequest,
        abuse: AbuseContext,
    ) -> SubmissionReceipt:
        self._reject_honeypot(command)
        self._reject_too_fast(command)

        # Client idempotency — return prior receipt without re-enqueue side effects.
        if abuse.idempotency_key:
            existing = await self._get_by_idempotency_key(abuse.idempotency_key)
            if existing is not None:
                is_dup = existing.state == SubmissionState.DUPLICATE
                return self._receipt(existing, duplicate=is_dup)

        canonical = canonicalize_url(command.url)
        ip_hash = hash_ip(abuse.ip_address, self._settings.session_secret)
        await self._enforce_rate_limit(ip_hash)

        # Same canonical URL within window → mark duplicate of prior.
        prior = await self._find_recent_by_url(canonical.canonical)
        job_key = job_idempotency_key(canonical.canonical)

        email_cipher: str | None = None
        email_hash: str | None = None
        if command.email:
            email = command.email.strip()
            if "@" not in email or "." not in email.split("@")[-1]:
                raise ValidationError(
                    detail="Invalid email address",
                    errors=[{"field": "email", "message": "Invalid email format"}],
                )
            email_cipher = encrypt_email(email, self._settings)
            email_hash = hash_email(email, self._settings.email_hmac_key)

        tracking_id = secrets.token_urlsafe(18)
        state = SubmissionState.DUPLICATE if prior else SubmissionState.QUEUED
        submission = CommunitySubmission(
            tracking_id=tracking_id,
            original_url=canonical.original,
            canonical_url=canonical.canonical,
            claimed_type=command.claimed_type,
            claimed_title=command.claimed_title,
            notes=command.notes,
            submitter_email_ciphertext=email_cipher,
            submitter_email_hash=email_hash,
            ip_hash=ip_hash,
            user_agent_hash=(
                hash_user_agent(abuse.user_agent, self._settings.session_secret)
                if abuse.user_agent
                else None
            ),
            state=state,
            duplicate_of_id=prior.id if prior else None,
            idempotency_key=abuse.idempotency_key,
            job_idempotency_key=job_key,
            metadata_json={
                "host": canonical.host,
                "scheme": canonical.scheme,
            },
        )
        self._session.add(submission)
        await self._session.flush()

        if state != SubmissionState.DUPLICATE:
            self._register_after_commit(
                submission.id,
                job_key,
                canonical.canonical,
            )
        return self._receipt(submission, duplicate=state == SubmissionState.DUPLICATE)

    async def get_public_submission_status(self, tracking_id: str) -> SubmissionStatusPublic:
        result = await self._session.execute(
            select(CommunitySubmission).where(CommunitySubmission.tracking_id == tracking_id)
        )
        submission = result.scalar_one_or_none()
        if submission is None:
            raise NotFoundError(detail="Submission not found")
        state = SubmissionState(submission.state)
        claimed: ListingKind | None = None
        if submission.claimed_type:
            try:
                claimed = ListingKind(submission.claimed_type)
            except ValueError:
                claimed = None
        return SubmissionStatusPublic(
            tracking_id=submission.tracking_id,
            status=state,
            submitted_at=submission.created_at,
            claimed_type=claimed,
            message=STATUS_MESSAGES.get(state, "Status updated."),
        )

    def _register_after_commit(
        self,
        submission_id: UUID,
        job_key: str,
        canonical_url: str,
    ) -> None:
        hooks: list[Any] = self._session.info.setdefault("after_commit_hooks", [])

        async def _hook() -> None:
            import logging

            enqueued = await self._enqueue.enqueue_fetch_submission(
                submission_id, job_key, canonical_url
            )
            logger_msg = (
                "submission_enqueued" if enqueued else "submission_enqueue_deduped"
            )
            logging.getLogger(__name__).info(
                logger_msg,
                extra={"submission_id": str(submission_id)},
            )

        hooks.append(_hook)

    async def _get_by_idempotency_key(self, key: str) -> CommunitySubmission | None:
        result = await self._session.execute(
            select(CommunitySubmission).where(CommunitySubmission.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def _find_recent_by_url(self, canonical_url: str) -> CommunitySubmission | None:
        cutoff = datetime.now(UTC) - DUPLICATE_URL_WINDOW
        result = await self._session.execute(
            select(CommunitySubmission)
            .where(
                CommunitySubmission.canonical_url == canonical_url,
                CommunitySubmission.created_at >= cutoff,
            )
            .order_by(CommunitySubmission.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _enforce_rate_limit(self, ip_hash: str) -> None:
        if self._rate_limit_store is not None:
            now = time.time()
            bucket = self._rate_limit_store.setdefault(ip_hash, [])
            bucket[:] = [t for t in bucket if now - t < RATE_LIMIT_WINDOW_SECONDS]
            if len(bucket) >= RATE_LIMIT_MAX:
                raise RateLimitError(detail="Too many submissions from this client")
            bucket.append(now)
            return

        import redis.asyncio as aioredis

        r = aioredis.from_url(self._redis_url, decode_responses=True)
        try:
            key = f"devradar:rl:submissions:{ip_hash}"
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, RATE_LIMIT_WINDOW_SECONDS)
            if count > RATE_LIMIT_MAX:
                raise RateLimitError(detail="Too many submissions from this client")
        finally:
            aclose = getattr(r, "aclose", None)
            if aclose is not None:
                await aclose()
            else:
                await r.close()

    @staticmethod
    def _reject_honeypot(command: SubmissionCreateRequest) -> None:
        if command.website:
            raise ForbiddenError(detail="Submission rejected")

    @staticmethod
    def _reject_too_fast(command: SubmissionCreateRequest) -> None:
        if command.form_opened_at is None:
            return
        elapsed = time.time() - command.form_opened_at
        if elapsed < MIN_SUBMIT_SECONDS:
            raise ForbiddenError(detail="Submission rejected")

    @staticmethod
    def _receipt(submission: CommunitySubmission, *, duplicate: bool) -> SubmissionReceipt:
        state = SubmissionState(submission.state)
        return SubmissionReceipt(
            tracking_id=submission.tracking_id,
            status=state,
            message=STATUS_MESSAGES.get(state, "Submission received."),
            duplicate=duplicate,
        )
