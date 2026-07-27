"""Deterministic reviewer: turn a verification result into a readable review.

This is the always-on baseline (no API key required). It never invents facts —
every concern is grounded in a check that `verify()` already ran or a warning
the normalizer already raised.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.ai_review.schemas import (
    AIReview,
    ReviewConcern,
    ReviewConcernSeverity,
    ReviewRecommendation,
)
from app.catalog.enums import ListingKind, VerificationStatus
from app.ingestion.normalizer import CandidateListing
from app.ingestion.verifier import VerificationResult

_H = ReviewConcernSeverity.HIGH
_M = ReviewConcernSeverity.MEDIUM
_L = ReviewConcernSeverity.LOW

# Machine reason / warning code -> (severity, human sentence).
_REASON_INFO: dict[str, tuple[ReviewConcernSeverity, str]] = {
    # verifier reasons
    "official_cancellation": (_H, "The source indicates this opportunity was cancelled."),
    "submission_deadline_passed": (_H, "The submission deadline has already passed."),
    "offer_expired": (_H, "The offer's expiry date is in the past."),
    "link_check_failed": (_H, "The submitted link could not be reached or returned an error."),
    "dates_out_of_order": (
        _M,
        "Registration date falls after the close date — the dates look inconsistent.",
    ),
    "missing_deadline_or_expiry": (
        _M,
        "No deadline/expiry was found, so it can't be confirmed the opportunity is still open.",
    ),
    "tier3_only_requires_review": (
        _M,
        "Only social/unofficial sources back this — an official URL is needed to verify it.",
    ),
    "incomplete_or_failed_checks": (
        _M,
        "Key fields are missing or one or more automated checks failed.",
    ),
    "registration_closed": (
        _L,
        "Registration appears closed, though submissions may still be open.",
    ),
    "default_needs_review": (_L, "Automated checks were inconclusive; a human should confirm."),
    # normalizer warnings
    "missing_official_url": (_H, "No official URL could be resolved from the page."),
    "missing_title_defaulted": (_M, "No clear title was found; a placeholder was used."),
    "conflicting_dates_registration_after_submission": (
        _M,
        "Registration and submission dates were out of order (auto-corrected — please verify).",
    ),
    "offer_type_defaulted_free_tier": (_L, "Offer type was unclear and defaulted to 'free tier'."),
    "mode_defaulted_online": (_L, "Participation mode was unclear and defaulted to 'online'."),
}

# Positive reasons carry no concern — they explain a confident pass instead.
_POSITIVE_REASONS = frozenset(
    {"auto_verified", "likely_active_partial_evidence"}
)

# Fields worth surfacing for the admin to confirm/correct, per kind.
_SUGGEST_KEYS = {
    ListingKind.HACKATHON: (
        "title",
        "organizer",
        "mode",
        "official_url",
        "registration_deadline",
        "submission_deadline",
        "prize_value",
        "prize_currency",
        "technologies",
    ),
    ListingKind.AI_OFFER: (
        "title",
        "product_name",
        "provider",
        "offer_type",
        "offer_value",
        "official_url",
        "claim_url",
        "expires_at",
    ),
}

_TERMINAL_REJECT = frozenset(
    {VerificationStatus.EXPIRED, VerificationStatus.CANCELLED}
)
_PUBLISHABLE = frozenset(
    {
        VerificationStatus.VERIFIED_ACTIVE,
        VerificationStatus.LIKELY_ACTIVE,
        VerificationStatus.REGISTRATION_CLOSED,
    }
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _suggested_fields(candidate: CandidateListing) -> dict[str, Any]:
    keys = _SUGGEST_KEYS.get(candidate.kind, ())
    out: dict[str, Any] = {}
    for key in keys:
        val = candidate.fields.get(key)
        if val in (None, "", []):
            continue
        out[key] = _jsonable(val)
    if candidate.title and "title" not in out:
        out["title"] = candidate.title
    return out


def _concerns(codes: list[str]) -> list[ReviewConcern]:
    seen: set[str] = set()
    concerns: list[ReviewConcern] = []
    for code in codes:
        if code in _POSITIVE_REASONS or code in seen:
            continue
        seen.add(code)
        severity, message = _REASON_INFO.get(
            code, (_L, f"Automated check flagged: {code.replace('_', ' ')}.")
        )
        concerns.append(ReviewConcern(severity=severity, message=message))
    return concerns


def _recommend(result: VerificationResult) -> ReviewRecommendation:
    if result.status in _TERMINAL_REJECT:
        return ReviewRecommendation.REJECT
    if result.publishable and result.status in _PUBLISHABLE:
        return ReviewRecommendation.APPROVE
    return ReviewRecommendation.NEEDS_MORE_INFO


def _confidence(result: VerificationResult, recommendation: ReviewRecommendation) -> int:
    # Terminal rejects are date-driven and near-certain; otherwise trust the score.
    if recommendation is ReviewRecommendation.REJECT:
        return 90
    return int(max(0, min(100, result.score.total)))


def _summary(
    candidate: CandidateListing,
    result: VerificationResult,
    recommendation: ReviewRecommendation,
    n_concerns: int,
) -> str:
    kind_label = "Hackathon" if candidate.kind == ListingKind.HACKATHON else "AI offer"
    host = ""
    ctx = candidate.source_context
    if ctx and ctx.source_url:
        host = f" from {ctx.source_url.split('/')[2]}" if "//" in ctx.source_url else ""
    verdict = {
        ReviewRecommendation.APPROVE: "looks publishable",
        ReviewRecommendation.REJECT: "should not be published",
        ReviewRecommendation.NEEDS_MORE_INFO: "needs a human check before publishing",
    }[recommendation]
    concern_txt = "no concerns" if n_concerns == 0 else (
        f"{n_concerns} concern{'s' if n_concerns != 1 else ''} flagged"
    )
    return (
        f'{kind_label} "{candidate.title}"{host}: auto-verification returned '
        f"{result.status.value} at {result.score.total}/100 confidence; {concern_txt}. "
        f"Recommendation: it {verdict}."
    )


def heuristic_review(candidate: CandidateListing, result: VerificationResult) -> AIReview:
    """Build a grounded review from the deterministic verification result."""
    recommendation = _recommend(result)
    codes = [*result.reasons, *candidate.warnings]
    concerns = _concerns(codes)
    return AIReview(
        recommendation=recommendation,
        confidence=_confidence(result, recommendation),
        summary=_summary(candidate, result, recommendation, len(concerns)),
        concerns=concerns,
        suggested_fields=_suggested_fields(candidate),
        engine="heuristic",
        model=None,
    )


def unreachable_review(
    *, title: str, kind: ListingKind, url: str, detail: str | None = None
) -> AIReview:
    """Review for a submission whose URL could not be fetched/verified."""
    reason = detail or "the link could not be fetched"
    kind_label = "hackathon" if kind == ListingKind.HACKATHON else "AI offer"
    return AIReview(
        recommendation=ReviewRecommendation.NEEDS_MORE_INFO,
        confidence=20,
        summary=(
            f"Could not auto-verify this {kind_label} submission because {reason}. "
            "A human should open the link and confirm it manually."
        ),
        concerns=[
            ReviewConcern(
                severity=_H,
                message=(
                    f"The submitted URL could not be fetched or parsed ({reason}); "
                    "no automated verification was possible."
                ),
            )
        ],
        suggested_fields={"title": title, "official_url": url} if title else {"official_url": url},
        engine="heuristic",
        model=None,
    )
