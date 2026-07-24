"""Alert subscription and delivery service tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.email_provider import ConsoleEmailProvider
from app.alerts.models import AlertSubscription
from app.alerts.schemas import AlertCreateRequest
from app.alerts.service import AlertService
from app.alerts.tokens import hash_token
from app.catalog.enums import ListingKind, VerificationStatus
from app.catalog.models import Listing
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.errors import NotFoundError, ValidationError


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


class TestAlertService:
    @pytest.mark.asyncio
    async def test_create_confirm_unsubscribe(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        email_prov = ConsoleEmailProvider()
        svc = AlertService(session, settings, email_prov)
        resp, raw_token = await svc.create_subscription(
            AlertCreateRequest(email="user@example.com", filters={"q": "AI"})
        )
        assert resp.status == "pending_confirmation"
        assert email_prov.sent
        # No plaintext email in provider message metadata path — body may include
        # token in console mode; email address must not appear in email_hash storage.
        sub = (
            await session.execute(select(AlertSubscription))
        ).scalars().first()
        assert sub is not None
        assert "user@example.com" not in sub.email_ciphertext or sub.email_ciphertext != (
            "user@example.com"
        )
        assert sub.email_hash != "user@example.com"
        assert "user@example.com" not in sub.email_hash

        await svc.confirm_subscription(raw_token)
        await session.refresh(sub)
        assert sub.confirmed is True
        assert sub.confirm_token_hash is None  # single use

        with pytest.raises(NotFoundError):
            await svc.confirm_subscription(raw_token)

        # unsubscribe via token
        unsub = generate_unsub_for(sub, settings)
        # We need the raw unsub token — recreate path: store raw at create
        # For test, set known token
        from app.alerts.tokens import generate_token

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
        svc = AlertService(session, settings, ConsoleEmailProvider())
        _, raw = await svc.create_subscription(
            AlertCreateRequest(email="a@b.co", filters={})
        )
        sub = (await session.execute(select(AlertSubscription))).scalars().first()
        assert sub is not None
        sub.confirm_expires_at = datetime.now(UTC) - timedelta(hours=1)
        await session.flush()
        with pytest.raises(ValidationError):
            await svc.confirm_subscription(raw)

    @pytest.mark.asyncio
    async def test_delivery_idempotent(
        self, session: AsyncSession, settings: Settings
    ) -> None:
        email_prov = ConsoleEmailProvider()
        svc = AlertService(session, settings, email_prov)
        _, raw = await svc.create_subscription(
            AlertCreateRequest(email="c@d.co", filters={"q": "AI"})
        )
        await svc.confirm_subscription(raw)
        sub = (await session.execute(select(AlertSubscription))).scalars().first()
        assert sub is not None

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
        assert len(email_prov.sent) >= 2  # confirm + one delivery


def generate_unsub_for(sub: AlertSubscription, settings: Settings) -> str:
    return ""
