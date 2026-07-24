"""Deterministic normalization of extraction results into candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.catalog.enums import (
    EffortEstimate,
    HackathonMode,
    ListingKind,
    OfferType,
)
from app.ingestion.extractor import ExtractionResult
from app.submissions.url_policy import canonicalize_url

NORMALIZER_VERSION = "1.0.0"

_CURRENCY_MAP = {
    "usd": "USD",
    "$": "USD",
    "us$": "USD",
    "eur": "EUR",
    "€": "EUR",
    "gbp": "GBP",
    "£": "GBP",
    "idr": "IDR",
    "rp": "IDR",
}

_COUNTRY_MAP = {
    "usa": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "united states": "US",
    "united states of america": "US",
    "uk": "GB",
    "u.k.": "GB",
    "united kingdom": "GB",
    "great britain": "GB",
    "worldwide": "Worldwide",
    "global": "Worldwide",
    "anywhere": "Worldwide",
    "international": "Worldwide",
    "indonesia": "ID",
    "singapore": "SG",
    "india": "IN",
    "germany": "DE",
    "france": "FR",
    "japan": "JP",
    "europe": "Europe",
    "asia": "Asia",
}

_MODE_ALIASES = {
    "online": HackathonMode.ONLINE,
    "virtual": HackathonMode.ONLINE,
    "remote": HackathonMode.ONLINE,
    "hybrid": HackathonMode.HYBRID,
    "in_person": HackathonMode.IN_PERSON,
    "in-person": HackathonMode.IN_PERSON,
    "in person": HackathonMode.IN_PERSON,
    "onsite": HackathonMode.IN_PERSON,
    "on-site": HackathonMode.IN_PERSON,
}

_OFFER_ALIASES = {
    "free_credits": OfferType.FREE_CREDITS,
    "free credits": OfferType.FREE_CREDITS,
    "free_tier": OfferType.FREE_TIER,
    "free tier": OfferType.FREE_TIER,
    "trial": OfferType.TRIAL,
    "student_program": OfferType.STUDENT_PROGRAM,
    "student program": OfferType.STUDENT_PROGRAM,
    "open_source_program": OfferType.OPEN_SOURCE_PROGRAM,
    "hackathon_credits": OfferType.HACKATHON_CREDITS,
    "promo_code": OfferType.PROMO_CODE,
    "promo code": OfferType.PROMO_CODE,
    "free_model": OfferType.FREE_MODEL,
    "self_hosted_weights": OfferType.SELF_HOSTED_WEIGHTS,
    "self-hosted": OfferType.SELF_HOSTED_WEIGHTS,
}


@dataclass(slots=True)
class SourceContext:
    source_id: UUID | None = None
    source_url: str | None = None
    trust_tier: str | None = None
    connector_type: str | None = None


@dataclass(slots=True)
class CandidateListing:
    """Normalized candidate ready for dedup / verification."""

    kind: ListingKind
    title: str
    description: str
    official_url: str
    canonical_url: str
    fields: dict[str, Any] = field(default_factory=dict)
    field_sources: dict[str, str] = field(default_factory=dict)
    source_context: SourceContext | None = None
    extraction_method: str = "rules"
    normalizer_version: str = NORMALIZER_VERSION
    schema_version: str = ""
    warnings: list[str] = field(default_factory=list)


def _to_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, str):
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    return None


def normalize_currency(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    return _CURRENCY_MAP.get(key, raw.strip().upper()[:3])


def normalize_country(raw: str) -> str:
    key = raw.strip().lower()
    return _COUNTRY_MAP.get(key, raw.strip())


def normalize_countries(values: list[str] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for v in values:
        n = normalize_country(v)
        if n and n not in out:
            out.append(n)
    return out


def normalize_mode(raw: str | None) -> HackathonMode | None:
    if not raw:
        return None
    key = raw.strip().lower().replace(" ", "_")
    if key in _MODE_ALIASES:
        return _MODE_ALIASES[key]
    return _MODE_ALIASES.get(raw.strip().lower())


def normalize_offer_type(raw: str | None) -> OfferType | None:
    if not raw:
        return None
    key = raw.strip().lower().replace("-", "_")
    if key in _OFFER_ALIASES:
        return _OFFER_ALIASES[key]
    key2 = raw.strip().lower()
    return _OFFER_ALIASES.get(key2)


def normalize_url(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return canonicalize_url(raw).canonical
    except Exception:
        return None


def normalize_extraction(
    result: ExtractionResult,
    source_context: SourceContext | None = None,
) -> CandidateListing:
    """Convert ExtractionResult into a deterministic CandidateListing."""
    warnings: list[str] = list(result.errors)
    fields = dict(result.fields)
    kind = result.listing_kind

    title = (fields.get("title") or fields.get("product_name") or "").strip()
    if not title:
        title = "Untitled opportunity"
        warnings.append("missing_title_defaulted")

    description = (fields.get("description") or "").strip()
    official = (
        normalize_url(fields.get("official_url"))
        or normalize_url(fields.get("claim_url"))
        or normalize_url(fields.get("official_terms_url"))
        or normalize_url(source_context.source_url if source_context else None)
        or "https://invalid.example/"
    )
    if official.endswith("invalid.example/"):
        warnings.append("missing_official_url")

    # Date fields → UTC
    for key in (
        "registration_open_at",
        "registration_deadline",
        "submission_deadline",
        "starts_at",
        "expires_at",
    ):
        if key in fields:
            fields[key] = _to_utc(fields.get(key))

    # Conflicting dates: registration after submission
    reg = fields.get("registration_deadline")
    sub = fields.get("submission_deadline")
    if isinstance(reg, datetime) and isinstance(sub, datetime) and reg > sub:
        warnings.append("conflicting_dates_registration_after_submission")
        # Deterministic fix: swap
        fields["registration_deadline"], fields["submission_deadline"] = sub, reg

    if kind == ListingKind.HACKATHON:
        mode = normalize_mode(fields.get("mode") if isinstance(fields.get("mode"), str) else None)
        if fields.get("mode") and isinstance(fields["mode"], HackathonMode):
            mode = fields["mode"]
        elif isinstance(fields.get("mode"), str):
            mode = normalize_mode(fields["mode"])
        fields["mode"] = mode.value if mode else HackathonMode.ONLINE.value
        if mode is None:
            warnings.append("mode_defaulted_online")

        fields["eligible_countries"] = normalize_countries(fields.get("eligible_countries"))
        fields["prize_currency"] = normalize_currency(fields.get("prize_currency")) or "USD"
        if fields.get("prize_value") is not None:
            fields["prize_value"] = Decimal(str(fields["prize_value"]))
        team_min = int(fields.get("team_min") or 1)
        team_max = int(fields.get("team_max") or team_min)
        if team_max < team_min:
            team_max = team_min
            warnings.append("team_max_raised_to_min")
        fields["team_min"] = max(1, team_min)
        fields["team_max"] = max(1, team_max)
        fields["technologies"] = sorted(
            {str(t).strip() for t in (fields.get("technologies") or []) if str(t).strip()}
        )
        fields["eligibility"] = list(fields.get("eligibility") or [])
        if fields.get("effort_estimate"):
            try:
                EffortEstimate(str(fields["effort_estimate"]))
            except ValueError:
                fields["effort_estimate"] = None
                warnings.append("effort_estimate_dropped")
        fields["organizer"] = (fields.get("organizer") or "Unknown").strip()
        fields["official_url"] = official
    else:
        ot = fields.get("offer_type")
        if isinstance(ot, OfferType):
            fields["offer_type"] = ot.value
        else:
            normalized_ot = normalize_offer_type(str(ot) if ot else None)
            fields["offer_type"] = (
                normalized_ot.value if normalized_ot else OfferType.FREE_TIER.value
            )
            if normalized_ot is None:
                warnings.append("offer_type_defaulted_free_tier")
        fields["supported_regions"] = normalize_countries(fields.get("supported_regions"))
        fields["product_name"] = (fields.get("product_name") or title).strip()
        fields["provider"] = (fields.get("provider") or "Unknown").strip()
        fields["official_terms_url"] = (
            normalize_url(fields.get("official_terms_url")) or official
        )
        fields["claim_url"] = normalize_url(fields.get("claim_url")) or official
        fields["official_url"] = official
        # Permanent free tier keeps expires_at null
        if fields.get("offer_type") == OfferType.FREE_TIER.value and not fields.get(
            "expires_at"
        ):
            fields["expires_at"] = None

    return CandidateListing(
        kind=kind,
        title=title,
        description=description,
        official_url=official,
        canonical_url=official,
        fields=fields,
        field_sources=dict(result.field_sources),
        source_context=source_context,
        extraction_method=result.method,
        schema_version=result.schema_version,
        warnings=warnings,
    )
