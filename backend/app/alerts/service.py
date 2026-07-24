"""Alert subscription and delivery service."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.email_provider import ConsoleEmailProvider, EmailMessage, EmailProvider
from app.alerts.matcher import match_listing
from app.alerts.models import AlertSubscription, NotificationDelivery
from app.alerts.schemas import AlertCreateRequest, AlertCreateResponse
from app.alerts.tokens import confirmation_expiry, generate_token, hash_token
from app.catalog.models import Listing
from app.config import Settings
from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.submissions.security import encrypt_email, hash_email


class AlertService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        email: EmailProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._email = email or ConsoleEmailProvider()

    async def create_subscription(
        self, command: AlertCreateRequest
    ) -> tuple[AlertCreateResponse, str]:
        """Create unconfirmed subscription; returns (response, raw_confirm_token)."""
        if command.website:
            raise ForbiddenError(detail="Submission rejected")

        email_norm = str(command.email).strip().lower()
        email_h = hash_email(email_norm, self._settings.email_hmac_key)
        cipher = encrypt_email(email_norm, self._settings)

        confirm_raw = generate_token()
        unsub_raw = generate_token()
        now = datetime.now(UTC)

        sub = AlertSubscription(
            email_ciphertext=cipher,
            email_hash=email_h,
            confirmed=False,
            filter_json=command.filters or {},
            cadence=command.cadence or "daily",
            confirm_token_hash=hash_token(confirm_raw, self._settings.session_secret),
            unsubscribe_token_hash=hash_token(unsub_raw, self._settings.session_secret),
            confirm_expires_at=confirmation_expiry(now),
        )
        self._session.add(sub)
        await self._session.flush()

        # Console "send" confirmation (redacted)
        await self._email.send(
            EmailMessage(
                to_hash=email_h,
                subject="Confirm your DevRadar alerts",
                body_text=f"Confirm token (dev): {confirm_raw}",
                idempotency_key=f"confirm:{sub.id}",
            )
        )
        return (
            AlertCreateResponse(),
            confirm_raw,
        )

    async def confirm_subscription(self, token: str) -> AlertSubscription:
        th = hash_token(token, self._settings.session_secret)
        result = await self._session.execute(
            select(AlertSubscription).where(AlertSubscription.confirm_token_hash == th)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            raise NotFoundError(detail="Invalid confirmation token")
        now = datetime.now(UTC)
        if sub.confirm_expires_at and sub.confirm_expires_at < now:
            raise ValidationError(detail="Confirmation token expired")
        if sub.unsubscribed_at is not None:
            raise ValidationError(detail="Subscription was unsubscribed")
        sub.confirmed = True
        sub.confirmed_at = now
        sub.confirm_token_hash = None  # single use
        await self._session.flush()
        return sub

    async def unsubscribe(self, token: str) -> None:
        th = hash_token(token, self._settings.session_secret)
        result = await self._session.execute(
            select(AlertSubscription).where(
                AlertSubscription.unsubscribe_token_hash == th
            )
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            raise NotFoundError(detail="Invalid unsubscribe token")
        sub.unsubscribed_at = datetime.now(UTC)
        sub.confirmed = False
        await self._session.flush()

    async def deliver_notification(
        self,
        subscription: AlertSubscription,
        listing: Listing,
        *,
        template: str = "new_match",
    ) -> NotificationDelivery | None:
        if not subscription.confirmed or subscription.unsubscribed_at is not None:
            return None
        if not match_listing(listing, subscription.filter_json or {}):
            return None

        idem = f"{subscription.id}:{listing.id}:{template}"
        existing = await self._session.execute(
            select(NotificationDelivery).where(
                NotificationDelivery.idempotency_key == idem
            )
        )
        if existing.scalar_one_or_none() is not None:
            return None  # duplicate suppression

        delivery = NotificationDelivery(
            subscription_id=subscription.id,
            listing_id=listing.id,
            template=template,
            idempotency_key=idem,
            status="queued",
            attempts=1,
        )
        self._session.add(delivery)
        await self._session.flush()

        msg_id = await self._email.send(
            EmailMessage(
                to_hash=subscription.email_hash,
                subject=f"DevRadar: {listing.title}",
                body_text=f"New match: {listing.title} ({listing.slug})",
                idempotency_key=idem,
            )
        )
        delivery.status = "sent"
        delivery.provider_message_id = msg_id
        await self._session.flush()
        return delivery
