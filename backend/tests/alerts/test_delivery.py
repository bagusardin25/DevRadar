"""Alert subscription and delivery service tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.email_provider import ConsoleEmailProvider
from app.alerts.models import AlertSubscription
from app.alerts.schemas import AlertCreateRequest
from app.alerts.service import AlertService
from app.alerts.tokens import generate_token, hash_token
from app.catalog.enums import ListingKind, VerificationStatus
from app.catalog.models import Listing
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.errors import NotFoundError, ValidationError
from app.submissions.security import hash_email


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_engine(Settings())
    maker = create_session_maker(engine)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-at-least-32-chars!!",
        email_hmac_key="test-hmac-key-at-least-32-characters!!",
        email_encryption_key="test-email-encryption-key-material",
    )


async def _get_sub_by_email(
    session: AsyncSession, settings: Settings, email: str
) -> AlertSubscription:
    h = hash_email(email.strip().lower(), settings.email_hmac_key)
    result = await session.execute(
        select(AlertSubscription)
        .where(AlertSubscription.email_hash == h)
        .order_by(AlertSubscription.created_at.desc())
    )
    sub = result.scalars().first()
    assert sub is not None
    return sub


class TestAlertService:
    @pytest.mark.asyncio
    async def test_create_confirm_unsubscribe(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        email = f"user-{uuid4().hex[:8]}@example.com"
        email_prov = ConsoleEmailProvider()
        svc = AlertService(session, settings, email_prov)
        resp, raw_token = await svc.create_subscription(
            AlertCreateRequest(email=email, filters={"q": "AI"})
        )
        assert resp.status == "pending_confirmation"
        assert email_prov.sent
        sub = await _get_sub_by_email(session, settings, email)
        assert email not in sub.email_hash
        assert sub.email_ciphertext != email

        await svc.confirm_subscription(raw_token)
        await session.refresh(sub)
        assert sub.confirmed is True
        assert sub.confirm_token_hash is None

        with pytest.raises(NotFoundError):
            await svc.confirm_subscription(raw_token)

        raw_unsub = generate_token()
        sub.unsubscribe_token_hash = hash_token(raw_unsub, settings.session_secret)
        await session.flush()
        await svc.unsubscribe(raw_unsub)
        await session.refresh(sub)
        assert sub.unsubscribed_at is not None

    @pytest.mark.asyncio
    async def test_expired_confirmation(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        email = f"exp-{uuid4().hex[:8]}@example.com"
        svc = AlertService(session, settings, ConsoleEmailProvider())
        _, raw = await svc.create_subscription(
            AlertCreateRequest(email=email, filters={})
        )
        sub = await _get_sub_by_email(session, settings, email)
        sub.confirm_expires_at = datetime.now(UTC) - timedelta(hours=1)
        await session.flush()
        with pytest.raises(ValidationError):
            await svc.confirm_subscription(raw)

    @pytest.mark.asyncio
    async def test_pending_duplicate_reuses_subscription_row(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        email = f"retry-{uuid4().hex[:8]}@example.com"
        email_prov = ConsoleEmailProvider()
        svc = AlertService(session, settings, email_prov)
        request = AlertCreateRequest(
            email=email,
            filters={"q": "AI", "kind": "hackathon"},
            cadence="daily",
        )

        _, first_token = await svc.create_subscription(request)
        _, second_token = await svc.create_subscription(request)

        email_h = hash_email(email, settings.email_hmac_key)
        row_count = await session.scalar(
            select(func.count())
            .select_from(AlertSubscription)
            .where(AlertSubscription.email_hash == email_h)
        )
        assert row_count == 1
        assert first_token != second_token
        assert len(email_prov.sent) == 2

    @pytest.mark.asyncio
    async def test_new_signup_cleans_expired_unconfirmed_rows(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        email_prov = ConsoleEmailProvider()
        svc = AlertService(session, settings, email_prov)
        expired_email = f"expired-{uuid4().hex[:8]}@example.com"
        await svc.create_subscription(
            AlertCreateRequest(email=expired_email, filters={"q": "AI"})
        )
        expired = await _get_sub_by_email(session, settings, expired_email)
        expired_id = expired.id
        expired.confirm_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.flush()

        await svc.create_subscription(
            AlertCreateRequest(
                email=f"fresh-{uuid4().hex[:8]}@example.com",
                filters={"q": "AI"},
            )
        )

        assert await session.get(AlertSubscription, expired_id) is None

    @pytest.mark.asyncio
    async def test_delivery_idempotent(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        email = f"del-{uuid4().hex[:8]}@example.com"
        email_prov = ConsoleEmailProvider()
        svc = AlertService(session, settings, email_prov)
        _, raw = await svc.create_subscription(
            AlertCreateRequest(email=email, filters={"q": "AI"})
        )
        await svc.confirm_subscription(raw)
        sub = await _get_sub_by_email(session, settings, email)
        await session.refresh(sub)
        assert sub.confirmed is True

        listing = Listing(
            kind=ListingKind.HACKATHON,
            slug=f"al-{uuid4().hex[:8]}",
            title="Global AI Hackathon",
            description="AI",
            verification_status=VerificationStatus.VERIFIED_ACTIVE,
            search_extra="AI",
        )
        session.add(listing)
        await session.flush()

        d1 = await svc.deliver_notification(sub, listing)
        d2 = await svc.deliver_notification(sub, listing)
        assert d1 is not None
        assert d2 is None
        assert len(email_prov.sent) >= 2
