"""Build listing child rows from loosely-typed candidate fields.

Extraction (pipeline) and admin approval (review queue) both end up with a bag of
optional fields that has to become a valid ``HackathonCreateSchema`` /
``AIOfferCreateSchema``. Keeping the fallbacks in one place stops the two paths
from drifting apart on what counts as a publishable row.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.catalog.schemas import AIOfferCreateSchema, HackathonCreateSchema


def build_hackathon_create(
    fields: dict[str, Any],
    *,
    official_url: str,
    suitable_reasons: list[str] | None = None,
) -> HackathonCreateSchema:
    return HackathonCreateSchema(
        organizer=str(fields.get("organizer") or "Unknown"),
        registration_open_at=fields.get("registration_open_at"),
        registration_deadline=fields.get("registration_deadline"),
        submission_deadline=fields.get("submission_deadline"),
        mode=fields.get("mode") or "online",
        location=fields.get("location"),
        eligible_countries=list(fields.get("eligible_countries") or []),
        eligibility=list(fields.get("eligibility") or []),
        team_min=int(fields.get("team_min") or 1),
        team_max=int(fields.get("team_max") or 1),
        prize_value=Decimal(str(fields.get("prize_value") or 0)),
        prize_label=str(fields.get("prize_label") or "").strip(),
        prize_currency=str(fields.get("prize_currency") or "USD"),
        technologies=list(fields.get("technologies") or []),
        official_url=official_url,
        suitable_reasons=list(suitable_reasons or []),
    )


def build_ai_offer_create(
    fields: dict[str, Any],
    *,
    official_url: str,
    title: str,
    suitable_reasons: list[str] | None = None,
) -> AIOfferCreateSchema:
    return AIOfferCreateSchema(
        product_name=str(fields.get("product_name") or title),
        provider=str(fields.get("provider") or "Unknown"),
        offer_type=fields.get("offer_type") or "free_tier",
        offer_value=str(fields.get("offer_value") or ""),
        target_users=list(fields.get("target_users") or []),
        requirements=list(fields.get("requirements") or []),
        starts_at=fields.get("starts_at"),
        expires_at=fields.get("expires_at"),
        supported_regions=list(fields.get("supported_regions") or []),
        official_terms_url=str(fields.get("official_terms_url") or official_url),
        claim_url=str(fields.get("claim_url") or official_url),
        tags=list(fields.get("tags") or []),
        suitable_reasons=list(suitable_reasons or []),
    )
