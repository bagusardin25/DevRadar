"""Operator outbound webhooks for new matching listings (Discord/n8n/etc)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from app.alerts.matcher import match_listing, normalize_alert_filters
from app.catalog.models import Listing
from app.config import Settings

logger = logging.getLogger(__name__)


def _listing_payload(listing: Listing) -> dict[str, Any]:
    """Minimal public JSON for automation tools."""
    status = getattr(listing.verification_status, "value", listing.verification_status)
    kind = getattr(listing.kind, "value", listing.kind)
    payload: dict[str, Any] = {
        "id": str(listing.id),
        "slug": listing.slug,
        "title": listing.title,
        "kind": kind,
        "description": (listing.description or "")[:500],
        "verificationStatus": status,
        "confidenceScore": float(listing.confidence_score or 0),
    }
    hack = getattr(listing, "hackathon", None)
    if hack is not None:
        payload["hackathon"] = {
            "mode": getattr(hack.mode, "value", hack.mode),
            "prizeValue": float(hack.prize_value or 0),
            "prizeCurrency": hack.prize_currency,
            "prizeLabel": hack.prize_label or "",
            "technologies": list(hack.technologies or []),
            "registrationDeadline": (
                hack.registration_deadline.isoformat() if hack.registration_deadline else None
            ),
            "submissionDeadline": (
                hack.submission_deadline.isoformat() if hack.submission_deadline else None
            ),
            "officialUrl": hack.official_url,
            "organizer": hack.organizer,
        }
    offer = getattr(listing, "ai_offer", None)
    if offer is not None:
        payload["aiOffer"] = {
            "provider": getattr(offer, "provider", None),
            "offerType": str(getattr(offer.offer_type, "value", offer.offer_type)),
            "offerValue": getattr(offer, "offer_value", None),
            "claimUrl": getattr(offer, "claim_url", None),
            "expiresAt": (
                offer.expires_at.isoformat()
                if getattr(offer, "expires_at", None)
                else None
            ),
            "tags": list(getattr(offer, "tags", None) or []),
        }
    return payload


def build_webhook_body(listing: Listing, *, event: str = "listing.match") -> dict[str, Any]:
    return {
        "event": event,
        "sentAt": datetime.now(UTC).isoformat(),
        "listing": _listing_payload(listing),
    }


def sign_body(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def deliver_webhook(
    settings: Settings,
    listing: Listing,
    *,
    event: str = "listing.match",
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """POST listing JSON to WEBHOOK_URL if configured and filters match.

    Returns a small result dict for logging / task stats.
    """
    url = (settings.webhook_url or "").strip()
    if not url:
        return {"skipped": True, "reason": "webhook_url_empty"}

    # Optional operator filter (JSON string in env)
    raw_filter = (settings.webhook_filter_json or "").strip()
    filters: dict[str, Any] = {}
    if raw_filter:
        try:
            parsed = json.loads(raw_filter)
            if isinstance(parsed, dict):
                filters = normalize_alert_filters(parsed)
        except json.JSONDecodeError:
            logger.warning("webhook_filter_json_invalid")
            return {"skipped": True, "reason": "invalid_filter_json"}

    if filters and not match_listing(listing, filters):
        return {"skipped": True, "reason": "filter_mismatch"}

    body_obj = build_webhook_body(listing, event=event)
    body_bytes = json.dumps(body_obj, separators=(",", ":"), default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "DevRadar-Webhook/1.0",
        "X-DevRadar-Event": event,
    }
    secret = (settings.webhook_secret or "").strip()
    if secret:
        headers["X-DevRadar-Signature"] = f"sha256={sign_body(body_bytes, secret)}"

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=20.0)
    try:
        resp = await client.post(url, content=body_bytes, headers=headers)
        ok = 200 <= resp.status_code < 300
        logger.info(
            "webhook_deliver",
            extra={
                "ok": ok,
                "status": resp.status_code,
                "listing_id": str(listing.id),
                "event": event,
            },
        )
        return {
            "skipped": False,
            "ok": ok,
            "status": resp.status_code,
            "listing_id": str(listing.id),
        }
    except httpx.HTTPError as exc:
        logger.warning(
            "webhook_deliver_error",
            extra={"error": str(exc), "listing_id": str(listing.id)},
        )
        return {
            "skipped": False,
            "ok": False,
            "error": str(exc),
            "listing_id": str(listing.id),
        }
    finally:
        if owns_client:
            await client.aclose()


async def deliver_webhook_for_id(
    settings: Settings,
    listing_id: UUID,
    listing: Listing,
    **kwargs: Any,
) -> dict[str, Any]:
    """Thin wrapper kept for callers that only have an id + loaded listing."""
    _ = listing_id
    return await deliver_webhook(settings, listing, **kwargs)
