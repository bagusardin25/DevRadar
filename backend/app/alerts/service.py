"""Alert subscription and delivery service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.alerts.email_provider import (
    EmailMessage,
    EmailProvider,
    build_email_provider,
)
from app.alerts.matcher import match_listing, normalize_alert_filters
from app.alerts.models import AlertSubscription, NotificationDelivery
from app.alerts.schemas import AlertCreateRequest, AlertCreateResponse
from app.alerts.tokens import confirmation_expiry, generate_token, hash_token
from app.alerts.webhook import deliver_webhook
from app.catalog.enums import VerificationStatus
from app.catalog.models import Listing
from app.config import Settings
from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.submissions.security import decrypt_email, encrypt_email, hash_email

_VALID_CADENCES = frozenset({"instant", "daily", "weekly"})


class AlertService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        email: EmailProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._email = email or build_email_provider(settings)

    def _confirm_url(self, raw_token: str) -> str:
        """Link users open to confirm (proxied via frontend /api or direct API)."""
        base = self._settings.frontend_url.rstrip("/")
        api = self._settings.api_base_path.rstrip("/")
        return f"{base}{api}/alerts/confirm?token={raw_token}"

    def _unsubscribe_url(self, raw_token: str) -> str:
        base = self._settings.frontend_url.rstrip("/")
        api = self._settings.api_base_path.rstrip("/")
        return f"{base}{api}/alerts/unsubscribe?token={raw_token}"

    async def create_subscription(
        self, command: AlertCreateRequest
    ) -> tuple[AlertCreateResponse, str]:
        """Create unconfirmed subscription; returns (response, raw_confirm_token)."""
        if command.website:
            raise ForbiddenError(detail="Submission rejected")

        email_norm = str(command.email).strip().lower()
        email_h = hash_email(email_norm, self._settings.email_hmac_key)
        cipher = encrypt_email(email_norm, self._settings)

        cadence = (command.cadence or "daily").strip().lower()
        if cadence not in _VALID_CADENCES:
            cadence = "daily"

        filters = normalize_alert_filters(command.filters or {})

        confirm_raw = generate_token()
        now = datetime.now(UTC)
        confirm_hash = hash_token(confirm_raw, self._settings.session_secret)

        # Opportunistically bound storage from abandoned, never-confirmed signups.
        await self._session.execute(
            delete(AlertSubscription).where(
                AlertSubscription.confirmed.is_(False),
                AlertSubscription.confirmed_at.is_(None),
                AlertSubscription.confirm_expires_at.is_not(None),
                AlertSubscription.confirm_expires_at < now,
            )
        )

        existing_result = await self._session.execute(
            select(AlertSubscription)
            .where(
                AlertSubscription.email_hash == email_h,
                AlertSubscription.cadence == cadence,
                AlertSubscription.filter_json == filters,
                AlertSubscription.unsubscribed_at.is_(None),
            )
            .order_by(AlertSubscription.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        sub = existing_result.scalar_one_or_none()
        if sub is not None and sub.confirmed:
            # Keep the public response non-enumerating without sending another email.
            return AlertCreateResponse(), ""

        if sub is None:
            unsub_raw = generate_token()
            sub = AlertSubscription(
                email_ciphertext=cipher,
                email_hash=email_h,
                confirmed=False,
                filter_json=filters,
                cadence=cadence,
                confirm_token_hash=confirm_hash,
                unsubscribe_token_hash=hash_token(
                    unsub_raw, self._settings.session_secret
                ),
                confirm_expires_at=confirmation_expiry(now),
            )
            self._session.add(sub)
        else:
            # A bounded resend rotates the confirmation token but reuses the row.
            sub.email_ciphertext = cipher
            sub.confirm_token_hash = confirm_hash
            sub.confirm_expires_at = confirmation_expiry(now)
        await self._session.flush()

        confirm_url = self._confirm_url(confirm_raw)
        body = (
            "Confirm your DevRadar alert subscription.\n\n"
            f"Open this link within 24 hours:\n{confirm_url}\n\n"
            "If you did not request this, ignore this email.\n"
        )
        await self._email.send(
            EmailMessage(
                to_hash=email_h,
                to_address=email_norm,
                subject="Confirm your DevRadar alerts",
                body_text=body,
                idempotency_key=f"confirm:{sub.id}:{confirm_hash[:12]}",
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

    def _recipient(self, subscription: AlertSubscription) -> str | None:
        return decrypt_email(subscription.email_ciphertext, self._settings)

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

        frontend = self._settings.frontend_url.rstrip("/")
        body = self._match_email_body(listing, frontend=frontend, template=template)
        subject = self._match_email_subject(listing, template=template)

        msg_id = await self._email.send(
            EmailMessage(
                to_hash=subscription.email_hash,
                to_address=self._recipient(subscription),
                subject=subject,
                body_text=body,
                idempotency_key=idem,
            )
        )
        delivery.status = "sent"
        delivery.provider_message_id = msg_id
        await self._session.flush()
        return delivery

    def _match_email_subject(self, listing: Listing, *, template: str) -> str:
        if template == "closing_soon":
            return f"DevRadar: closing soon — {listing.title}"
        return f"DevRadar: new match — {listing.title}"

    @staticmethod
    def _rel_if_loaded(obj: object, name: str) -> Any:
        """Read a relationship only when already loaded (no async lazy-load)."""
        try:
            insp = sa_inspect(obj)
        except Exception:
            return getattr(obj, name, None)
        # Plain SimpleNamespace / non-ORM
        if not getattr(insp, "mapper", None):
            return getattr(obj, name, None)
        if name in insp.unloaded:
            return None
        return getattr(obj, name, None)

    def _match_email_body(
        self, listing: Listing, *, frontend: str, template: str
    ) -> str:
        kind = getattr(listing.kind, "value", listing.kind)
        lines = [
            f"DevRadar match ({template.replace('_', ' ')})",
            "",
            f"Title: {listing.title}",
            f"Kind: {kind}",
            f"Slug: {listing.slug}",
        ]
        hack = self._rel_if_loaded(listing, "hackathon")
        if hack is not None:
            if getattr(hack, "registration_deadline", None):
                lines.append(
                    f"Registration deadline: {hack.registration_deadline.isoformat()}"
                )
            if getattr(hack, "submission_deadline", None):
                lines.append(
                    f"Submission deadline: {hack.submission_deadline.isoformat()}"
                )
            prize_value = getattr(hack, "prize_value", None)
            if prize_value and float(prize_value) > 0:
                currency = getattr(hack, "prize_currency", "USD")
                lines.append(f"Prize: {currency} {prize_value}")
            elif getattr(hack, "prize_label", None):
                lines.append(f"Prize: {hack.prize_label}")
            if getattr(hack, "official_url", None):
                lines.append(f"Official: {hack.official_url}")
        offer = self._rel_if_loaded(listing, "ai_offer")
        if offer is not None:
            if getattr(offer, "offer_value", None):
                lines.append(f"Offer: {offer.offer_value}")
            claim = getattr(offer, "claim_url", None)
            if claim:
                lines.append(f"Claim: {claim}")
            exp = getattr(offer, "expires_at", None)
            if exp:
                lines.append(f"Expires: {exp.isoformat()}")

        lines.extend(
            [
                "",
                f"Browse catalogue: {frontend}",
                "",
                "You received this because you confirmed an email alert on DevRadar.",
            ]
        )
        return "\n".join(lines)

    async def scan_and_deliver(
        self,
        *,
        lookback_hours: int = 48,
        limit_listings: int = 100,
        send_webhooks: bool = True,
    ) -> dict[str, Any]:
        """Scan recent active listings against confirmed subscriptions.

        Also fires operator webhook once per listing when WEBHOOK_URL is set.
        """
        now = datetime.now(UTC)
        since = now - timedelta(hours=max(1, lookback_hours))

        subs_result = await self._session.execute(
            select(AlertSubscription).where(
                AlertSubscription.confirmed.is_(True),
                AlertSubscription.unsubscribed_at.is_(None),
            )
        )
        subscriptions = list(subs_result.scalars().all())

        listings_result = await self._session.execute(
            select(Listing)
            .where(
                Listing.verification_status.in_(
                    [
                        VerificationStatus.VERIFIED_ACTIVE,
                        VerificationStatus.LIKELY_ACTIVE,
                    ]
                ),
                Listing.published_at.is_not(None),
                Listing.published_at >= since,
            )
            .options(
                selectinload(Listing.hackathon),
                selectinload(Listing.ai_offer),
            )
            .order_by(Listing.published_at.desc())
            .limit(limit_listings)
        )
        listings = list(listings_result.scalars().all())

        delivered = 0
        matched_pairs = 0
        webhook_ok = 0
        webhook_fail = 0
        webhook_skip = 0

        for listing in listings:
            if send_webhooks and (self._settings.webhook_url or "").strip():
                wh = await deliver_webhook(
                    self._settings, listing, event="listing.published"
                )
                if wh.get("skipped"):
                    webhook_skip += 1
                elif wh.get("ok"):
                    webhook_ok += 1
                else:
                    webhook_fail += 1

            for sub in subscriptions:
                if match_listing(listing, sub.filter_json or {}, now=now):
                    matched_pairs += 1
                    # Closing-soon template when filter asks for it and deadline is near
                    template = "new_match"
                    filt = sub.filter_json or {}
                    if filt.get("onlyClosingSoon") or filt.get("only_closing_soon"):
                        template = "closing_soon"
                    result = await self.deliver_notification(
                        sub, listing, template=template
                    )
                    if result is not None:
                        delivered += 1

        return {
            "subscriptions": len(subscriptions),
            "listings_scanned": len(listings),
            "matched_pairs": matched_pairs,
            "delivered": delivered,
            "webhook_ok": webhook_ok,
            "webhook_fail": webhook_fail,
            "webhook_skip": webhook_skip,
        }
