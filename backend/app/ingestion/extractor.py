"""Rule-first structured extraction with optional LLM fill-in."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from app.catalog.enums import ListingKind
from app.ingestion.extraction_schemas import (
    EXTRACTION_SCHEMA_VERSION,
    validate_extraction_payload,
)
from app.ingestion.llm_provider import (
    DisabledLLMProvider,
    ExtractionRequest,
    LLMProvider,
)
from app.ingestion.parser import ParsedDocument
from app.llm_usage import LLMCallUsage

EXTRACTOR_VERSION = "1.0.0"

# ISO-ish and common date patterns (deterministic).
_ISO_DT = re.compile(
    r"\b(20\d{2}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?)\b"
)
_US_DATE = re.compile(
    r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2})\b",
    re.I,
)
_PRIZE = re.compile(
    r"(?:prize|pool|award)[^\n$€£]{0,40}(?:\$|USD\s*)?([\d,]+(?:\.\d+)?)\s*(k|K|USD|usd)?",
    re.I,
)
_CREDITS = re.compile(
    r"(?:\$|USD\s*)?([\d,]+(?:\.\d+)?)\s*(?:USD\s+)?(?:in\s+)?(?:free\s+)?credits",
    re.I,
)
_TEAM = re.compile(r"teams?\s+of\s+(\d+)\s*[-–to]+\s*(\d+)", re.I)
_TEAM_SINGLE = re.compile(r"(?:team\s+size|up to)\s+(\d+)", re.I)

_TECH_KEYWORDS = (
    "Python",
    "TypeScript",
    "JavaScript",
    "Rust",
    "Go",
    "AI",
    "LLM",
    "Next.js",
    "React",
    "CUDA",
    "PyTorch",
    "TensorFlow",
)

_MODE_MAP = (
    (re.compile(r"\b(fully\s+)?online\b|\bvirtual\b|\bremote\b", re.I), "online"),
    (re.compile(r"\bhybrid\b", re.I), "hybrid"),
    (re.compile(r"\bin[-\s]?person\b|\bon[-\s]?site\b|\bin person\b", re.I), "in_person"),
)

_OFFER_TYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"free\s+tier|always\s+free", re.I), "free_tier"),
    (re.compile(r"free\s+credits|developer\s+credits", re.I), "free_credits"),
    (re.compile(r"student\s+program|github\s+student", re.I), "student_program"),
    (re.compile(r"open\s*source\s+program", re.I), "open_source_program"),
    (re.compile(r"hackathon\s+credits", re.I), "hackathon_credits"),
    (re.compile(r"promo\s*code|coupon", re.I), "promo_code"),
    (re.compile(r"free\s+model|open\s+weights", re.I), "free_model"),
    (re.compile(r"self[-\s]?hosted", re.I), "self_hosted_weights"),
    (re.compile(r"\btrial\b", re.I), "trial"),
]


@dataclass(slots=True)
class ExtractionResult:
    schema_version: str
    extractor_version: str
    listing_kind: ListingKind
    fields: dict[str, Any]
    method: Literal["rules", "llm", "hybrid", "failed"]
    field_sources: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    llm_attempted: bool = False
    llm_usage: LLMCallUsage | None = None


def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        pass
    # Month name formats
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(raw.replace(",", ""), fmt.replace(",", "")).replace(
                tzinfo=UTC
            )
        except ValueError:
            continue
    return None


def _find_dates(text: str) -> list[datetime]:
    found: list[datetime] = []
    for m in _ISO_DT.finditer(text):
        dt = _parse_date(m.group(1))
        if dt:
            found.append(dt)
    for m in _US_DATE.finditer(text):
        dt = _parse_date(m.group(1))
        if dt:
            found.append(dt)
    return found


def _detect_mode(text: str) -> str | None:
    for pattern, mode in _MODE_MAP:
        if pattern.search(text):
            return mode
    return None


def _detect_technologies(text: str) -> list[str]:
    hits: list[str] = []
    lower = text.lower()
    for tech in _TECH_KEYWORDS:
        if tech.lower() in lower and tech not in hits:
            hits.append(tech)
    return hits


def _detect_prize(text: str) -> tuple[Decimal | None, str | None]:
    m = _PRIZE.search(text)
    if not m:
        return None, None
    num = m.group(1).replace(",", "")
    try:
        value = Decimal(num)
    except InvalidOperation:
        return None, None
    suffix = (m.group(2) or "").lower()
    if suffix == "k":
        value *= 1000
    return value, "USD"


def _pick_official_url(parsed: ParsedDocument) -> str | None:
    if parsed.url:
        return parsed.url
    for link in parsed.links:
        href = link.href.lower()
        if any(x in href for x in ("rules", "official", "apply", "register", "devpost")):
            return link.href
    return parsed.links[0].href if parsed.links else None


def _rule_extract_hackathon(parsed: ParsedDocument) -> dict[str, Any]:
    text = parsed.text or ""
    title = parsed.title or _first_line(text)
    dates = _find_dates(text)
    prize, currency = _detect_prize(text)
    team_min, team_max = 1, 1
    tm = _TEAM.search(text)
    if tm:
        team_min, team_max = int(tm.group(1)), int(tm.group(2))
    else:
        ts = _TEAM_SINGLE.search(text)
        if ts:
            team_max = int(ts.group(1))

    registration_deadline = None
    submission_deadline = None
    registration_open = None
    # Heuristic: with 2+ dates, earliest open, mid registration, latest submission
    if len(dates) >= 3:
        ordered = sorted(dates)
        registration_open, registration_deadline, submission_deadline = (
            ordered[0],
            ordered[1],
            ordered[-1],
        )
    elif len(dates) == 2:
        ordered = sorted(dates)
        registration_deadline, submission_deadline = ordered[0], ordered[1]
    elif len(dates) == 1:
        submission_deadline = dates[0]

    organizer = None
    org_m = re.search(r"(?:organized|hosted)\s+by\s+([A-Z][\w &.+-]{1,60})", text)
    if org_m:
        organizer = org_m.group(1).strip()

    return {
        "title": title,
        "description": text[:500] if text else None,
        "organizer": organizer,
        "registration_open_at": registration_open,
        "registration_deadline": registration_deadline,
        "submission_deadline": submission_deadline,
        "mode": _detect_mode(text),
        "technologies": _detect_technologies(text),
        "prize_value": prize,
        "prize_currency": currency,
        "team_min": team_min,
        "team_max": max(team_max, team_min),
        "official_url": _pick_official_url(parsed),
        "eligible_countries": ["Worldwide"]
        if re.search(r"\bworldwide\b|\bglobal\b|\banyone\b", text, re.I)
        else [],
        "eligibility": _eligibility_labels(text),
    }


def _eligibility_labels(text: str) -> list[str]:
    labels: list[str] = []
    for label, pat in (
        ("Student", r"\bstudents?\b"),
        ("Developer", r"\bdevelopers?\b"),
        ("Startup", r"\bstartups?\b"),
    ):
        if re.search(pat, text, re.I):
            labels.append(label)
    return labels


def _first_line(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if len(line) >= 8:
            return line[:200]
    return None


def _rule_extract_ai_offer(parsed: ParsedDocument) -> dict[str, Any]:
    text = parsed.text or ""
    title = parsed.title or _first_line(text)
    offer_type = None
    for pattern, ot in _OFFER_TYPE_PATTERNS:
        if pattern.search(text):
            offer_type = ot
            break

    offer_value = None
    cm = _CREDITS.search(text)
    if cm:
        offer_value = f"${cm.group(1).replace(',', '')} free credits"
    elif offer_type == "free_tier":
        offer_value = "Free tier"

    dates = _find_dates(text)
    starts_at = dates[0] if dates else None
    expires_at = None
    if len(dates) >= 2:
        expires_at = dates[-1]
    elif dates and offer_type != "free_tier":
        expires_at = dates[0]
    # Permanent free tier: no expiry
    if offer_type == "free_tier" and not re.search(r"expir|until|ends?", text, re.I):
        expires_at = None

    provider = None
    prod = None
    # "AcmeAI Free Credits" style title
    if title:
        parts = title.split()
        if parts:
            provider = parts[0]
            prod = title

    claim = None
    terms = None
    for link in parsed.links:
        low = link.href.lower()
        if "claim" in low or "signup" in low or "register" in low:
            claim = link.href
        if "terms" in low or "pricing" in low:
            terms = link.href
    claim = claim or parsed.url
    terms = terms or parsed.url

    return {
        "title": title,
        "description": text[:500] if text else None,
        "product_name": prod or title,
        "provider": provider,
        "offer_type": offer_type,
        "offer_value": offer_value,
        "starts_at": starts_at,
        "expires_at": expires_at,
        "supported_regions": ["Worldwide"]
        if re.search(r"\bworldwide\b|\bglobal\b", text, re.I)
        else [],
        "official_terms_url": terms,
        "claim_url": claim,
        "official_url": parsed.url,
        "target_users": _eligibility_labels(text) or ["Developer"],
        "tags": _detect_technologies(text),
    }


def _merge_fields(
    base: dict[str, Any],
    extra: dict[str, Any],
    *,
    sources: dict[str, str],
    extra_source: str,
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if value is None or value == [] or value == "":
            continue
        current = merged.get(key)
        empty = current is None or current == [] or current == ""
        if empty:
            merged[key] = value
            sources[key] = extra_source
    return merged


class Extractor:
    """Rule-first extractor; LLM only fills missing fields when enabled."""

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self._llm = llm or DisabledLLMProvider()

    async def extract(
        self,
        parsed: ParsedDocument,
        listing_kind: ListingKind | str,
    ) -> ExtractionResult:
        kind = (
            listing_kind
            if isinstance(listing_kind, ListingKind)
            else ListingKind(str(listing_kind))
        )
        field_sources: dict[str, str] = {}
        errors: list[str] = []

        if kind == ListingKind.HACKATHON:
            raw_rules = _rule_extract_hackathon(parsed)
        else:
            raw_rules = _rule_extract_ai_offer(parsed)

        for k, v in raw_rules.items():
            if v is not None and v != []:
                field_sources[k] = "rules"

        method: Literal["rules", "llm", "hybrid", "failed"] = "rules"
        llm_attempted = False
        llm_usage: LLMCallUsage | None = None
        merged = dict(raw_rules)

        # When LLM is enabled: fill empty fields only (rules already set win).
        # Disabled provider: only rules (and tests use Echo for gap scenarios).
        use_llm = not isinstance(self._llm, DisabledLLMProvider)
        if use_llm and (
            _missing_critical(kind, merged) or _has_fillable_gaps(kind, merged)
        ):
            llm_attempted = True
            try:
                req = ExtractionRequest(
                    listing_kind=kind.value,
                    text=(parsed.text or "")[:12_000],
                    url=parsed.url,
                    schema_version=EXTRACTION_SCHEMA_VERSION,
                )
                llm_response = await self._llm.extract_json(req)
                llm_usage = llm_response.usage
                # Validate strictly; reject malformed entirely for LLM portion
                validated = validate_extraction_payload(
                    kind.value, llm_response.payload
                )
                llm_fields = validated.model_dump(exclude_none=True)
                before = set(field_sources)
                merged = _merge_fields(
                    merged, llm_fields, sources=field_sources, extra_source="llm"
                )
                if before and any(k not in before for k in field_sources):
                    method = "hybrid"
                elif not before and field_sources:
                    method = "llm"
                else:
                    method = "hybrid" if before else "rules"
            except Exception as exc:  # schema or provider failure
                errors.append(f"llm_rejected: {type(exc).__name__}: {exc}")

        # Final schema validation of merged rules+llm (coerce via model)
        try:
            # Serialize datetimes for validation path that already has datetime objects
            payload = _prepare_for_validate(merged)
            validated_final = validate_extraction_payload(kind.value, payload)
            fields = validated_final.model_dump(mode="python")
        except Exception as exc:
            errors.append(f"schema_rejected: {exc}")
            return ExtractionResult(
                schema_version=EXTRACTION_SCHEMA_VERSION,
                extractor_version=EXTRACTOR_VERSION,
                listing_kind=kind,
                fields=merged,
                method="failed",
                field_sources=field_sources,
                errors=errors,
                llm_attempted=llm_attempted,
                llm_usage=llm_usage,
            )

        return ExtractionResult(
            schema_version=EXTRACTION_SCHEMA_VERSION,
            extractor_version=EXTRACTOR_VERSION,
            listing_kind=kind,
            fields=fields,
            method=method,
            field_sources=field_sources,
            errors=errors,
            llm_attempted=llm_attempted,
            llm_usage=llm_usage,
        )


def _missing_critical(kind: ListingKind, fields: dict[str, Any]) -> bool:
    if kind == ListingKind.HACKATHON:
        return not fields.get("title") or not fields.get("submission_deadline")
    return not fields.get("product_name") and not fields.get("title")


def _has_fillable_gaps(kind: ListingKind, fields: dict[str, Any]) -> bool:
    """True when useful fields are still empty (LLM may fill them)."""
    if kind == ListingKind.HACKATHON:
        keys = (
            "title",
            "organizer",
            "submission_deadline",
            "registration_deadline",
            "mode",
            "prize_value",
            "official_url",
            "technologies",
        )
    else:
        keys = (
            "title",
            "product_name",
            "provider",
            "offer_type",
            "expires_at",
            "claim_url",
            "official_terms_url",
            "offer_value",
        )
    for key in keys:
        value = fields.get(key)
        if value is None or value == "" or value == []:
            return True
    return False


def _prepare_for_validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, Decimal):
            out[k] = v
        else:
            out[k] = v
    return out
