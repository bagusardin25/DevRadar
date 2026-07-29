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
# A currency marker is REQUIRED. The old pattern made it optional, so prose like
# "Grand prize awarded to teams of 2-5" parsed as a $5 prize pool.
_PRIZE = re.compile(
    r"(?:prizes?|pool|awards?)[^\n]{0,40}?"
    r"(?:"
    r"(?P<sym>[$€£])\s*(?P<sym_amt>\d[\d,]*(?:\.\d+)?)\s*(?P<sym_mult>[km])?"
    r"|(?P<pre_code>USD|EUR|GBP)\s*(?P<pre_amt>\d[\d,]*(?:\.\d+)?)\s*(?P<pre_mult>[km])?"
    r"|(?P<post_amt>\d[\d,]*(?:\.\d+)?)\s*(?P<post_mult>[km])?\s*(?P<post_code>USD|EUR|GBP)\b"
    r")",
    re.I,
)
_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}
_MULTIPLIERS = {"k": 1_000, "m": 1_000_000}
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


def _keyword_boundary(keyword: str) -> re.Pattern[str]:
    """Match `keyword` as a whole token rather than as a substring.

    Plain `in` matching read "AI" out of *available*, *email* and *domain*, and
    "Go" out of *google*, so nearly every page scored tech hits it never
    mentioned. `+`/`#` count as part of a token so a future "C++"/"C#" keyword
    is not clipped mid-name.
    """
    prefix = r"(?<![\w+#])" if keyword[0].isalnum() else ""
    suffix = r"(?![\w+#])" if keyword[-1].isalnum() else ""
    return re.compile(prefix + re.escape(keyword) + suffix, re.I)


_TECH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (tech, _keyword_boundary(tech)) for tech in _TECH_KEYWORDS
)

#: How far from a label to look for its date. Long enough to bridge
#: "Registration opens 2026-07-01 and closes 2026-08-10", short enough that a
#: footer copyright is never adopted by a heading paragraphs above it.
_DATE_LABEL_WINDOW = 120

# Ordered most-specific first: `registration_deadline` is claimed before
# `submission_deadline` so the latter's bare `\bdeadline\b` fallback cannot
# steal the date belonging to "Registration deadline".
_HACKATHON_DATE_LABELS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "registration_open_at",
        re.compile(
            r"registration\s+(?:opens?|begins?|starts?)"
            r"|(?:applications?|sign[-\s]?ups?)\s+open"
            r"|kick[-\s]?off",
            re.I,
        ),
    ),
    (
        "registration_deadline",
        re.compile(
            r"registration[^.\n]{0,40}?\b(?:closes?|closed|deadline|ends?)\b"
            r"|(?:apply|register|sign\s+up)\s+by"
            r"|applications?\s+close"
            r"|last\s+day\s+to\s+register"
            r"|entry\s+deadline",
            re.I,
        ),
    ),
    (
        "submission_deadline",
        re.compile(
            r"submissions?[^.\n]{0,20}?\b(?:deadline|due|closes?|ends?)\b"
            r"|(?:projects?|entries)\s+due"
            r"|final\s+submission"
            r"|hacking\s+ends?"
            r"|due\s+by"
            r"|\bdeadline\b",
            re.I,
        ),
    ),
)

_AI_OFFER_DATE_LABELS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "starts_at",
        re.compile(
            r"\b(?:starts?|begins?|available\s+from|effective|valid\s+from)\b",
            re.I,
        ),
    ),
    (
        "expires_at",
        re.compile(
            r"\b(?:expires?|expiry|expiration|ends?|until|through"
            r"|valid\s+(?:until|through|till))\b",
            re.I,
        ),
    ),
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


def _find_dates_with_pos(text: str) -> list[tuple[int, datetime]]:
    """Every parseable date with the offset it was written at, in reading order."""
    found: list[tuple[int, datetime]] = []
    for pattern in (_ISO_DT, _US_DATE):
        for m in pattern.finditer(text):
            dt = _parse_date(m.group(1))
            if dt:
                found.append((m.start(1), dt))
    found.sort(key=lambda pair: pair[0])
    return found


def _label_dates(
    text: str,
    labels: tuple[tuple[str, re.Pattern[str]], ...],
) -> dict[str, datetime]:
    """Assign dates to fields by the wording written next to them.

    Dates used to be assigned by sort order — earliest opens, latest closes —
    which happily promoted a footer copyright to "registration opens" and a
    privacy-policy revision date to "registration deadline". A wrong deadline is
    worse than none: a bogus past registration date flips a live hackathon to
    `registration_closed`. So anything without a label near it stays unassigned
    and the verifier raises `missing_deadline_or_expiry` instead.
    """
    dates = _find_dates_with_pos(text)
    claimed: set[int] = set()
    out: dict[str, datetime] = {}
    for field_name, pattern in labels:
        for match in pattern.finditer(text):
            best: tuple[int, int, datetime] | None = None
            for index, (pos, dt) in enumerate(dates):
                if index in claimed:
                    continue
                if pos >= match.end():
                    distance = pos - match.end()
                elif pos < match.start():
                    # Dates written before their label ("Aug 10 — registration
                    # closes") are rarer, so they must be nearer to win.
                    distance = (match.start() - pos) * 2
                else:
                    continue  # date sits inside the label match itself
                if distance > _DATE_LABEL_WINDOW:
                    continue
                if best is None or distance < best[0]:
                    best = (distance, index, dt)
            if best is not None:
                claimed.add(best[1])
                out[field_name] = best[2]
                break
    return out


def _detect_mode(text: str) -> str | None:
    for pattern, mode in _MODE_MAP:
        if pattern.search(text):
            return mode
    return None


def _detect_technologies(text: str) -> list[str]:
    return [tech for tech, pattern in _TECH_PATTERNS if pattern.search(text)]


def _detect_prize(text: str) -> tuple[Decimal | None, str | None]:
    """Prize amount and its currency, or `(None, None)` when unmarked.

    Only an amount carrying a currency marker counts — an unlabelled number
    near the word "prize" is far more often a team size or a rank than a pool.
    """
    m = _PRIZE.search(text)
    if not m:
        return None, None
    if m.group("sym_amt"):
        raw, mult = m.group("sym_amt"), m.group("sym_mult")
        currency = _CURRENCY_SYMBOLS.get(m.group("sym"), "USD")
    elif m.group("pre_amt"):
        raw, mult = m.group("pre_amt"), m.group("pre_mult")
        currency = m.group("pre_code").upper()
    else:
        raw, mult = m.group("post_amt"), m.group("post_mult")
        currency = m.group("post_code").upper()
    try:
        value = Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None, None
    if mult:
        value *= _MULTIPLIERS.get(mult.lower(), 1)
    return value, currency


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
    prize, currency = _detect_prize(text)
    team_min, team_max = 1, 1
    tm = _TEAM.search(text)
    if tm:
        team_min, team_max = int(tm.group(1)), int(tm.group(2))
    else:
        ts = _TEAM_SINGLE.search(text)
        if ts:
            team_max = int(ts.group(1))

    labelled = _label_dates(text, _HACKATHON_DATE_LABELS)
    registration_open = labelled.get("registration_open_at")
    registration_deadline = labelled.get("registration_deadline")
    submission_deadline = labelled.get("submission_deadline")

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

    # Label-driven, same as hackathons: an offer with no stated expiry keeps a
    # null `expires_at` (correct for a permanent free tier) rather than
    # inheriting whatever date happened to appear last on the page.
    labelled = _label_dates(text, _AI_OFFER_DATE_LABELS)
    starts_at = labelled.get("starts_at")
    expires_at = labelled.get("expires_at")

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
