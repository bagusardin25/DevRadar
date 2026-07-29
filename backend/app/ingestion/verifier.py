"""Deterministic verification state machine for candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from app.catalog.enums import ListingKind, VerificationStatus
from app.ingestion.normalizer import CandidateListing
from app.ingestion.scoring import (
    ScoreBreakdown,
    ScoringInput,
    keyword_hits_from_fields,
    score_verification,
)

VERIFIER_VERSION = "2.0.0"

#: Minimum score to publish at all (as LIKELY_ACTIVE).
MIN_PUBLISH_SCORE = 70
#: Minimum score to claim VERIFIED_ACTIVE without a human confirming it.
#: Calibrated against scoring v2, where freshness and corroboration no longer
#: hand out constant points — reaching this now takes real evidence.
MIN_VERIFIED_SCORE = 85

Decision = Literal[
    "verified_active",
    "likely_active",
    "needs_review",
    "registration_closed",
    "expired",
    "cancelled",
]


@dataclass(slots=True)
class VerificationEvidence:
    """External checks available at verification time."""

    source_tier: str = "tier_2"  # tier_1 | tier_2 | tier_3
    link_ok: bool = True
    #: Independent sources backing this candidate, including the originating
    #: one. 1 (the default) means nothing has corroborated it yet.
    cross_source_count: int = 1
    #: When the source document was fetched. None = unknown, and unknown
    #: freshness scores zero — it is never treated as freshly checked.
    last_checked_at: datetime | None = None
    official_cancellation: bool = False
    only_tier3: bool = False


@dataclass(slots=True)
class VerificationResult:
    status: VerificationStatus
    score: ScoreBreakdown
    checks: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    publishable: bool = False
    needs_human_review: bool = False
    verifier_version: str = VERIFIER_VERSION


def _deadline_fields(candidate: CandidateListing) -> tuple[datetime | None, datetime | None]:
    f = candidate.fields
    if candidate.kind == ListingKind.HACKATHON:
        return f.get("registration_deadline"), f.get("submission_deadline")
    return f.get("starts_at"), f.get("expires_at")


def _required_field_count(candidate: CandidateListing) -> tuple[int, int]:
    f = candidate.fields
    if candidate.kind == ListingKind.HACKATHON:
        keys = ["title", "organizer", "mode", "official_url", "submission_deadline"]
    else:
        keys = ["product_name", "provider", "offer_type", "claim_url", "official_terms_url"]
    present = sum(1 for k in keys if f.get(k) not in (None, "", []))
    # title is on candidate
    if candidate.title:
        present = max(present, present)  # already in fields often
    if candidate.title and "title" not in f:
        present += 1
        keys = [*keys, "title"]
    return present, len(keys)


def verify(
    candidate: CandidateListing,
    evidence: VerificationEvidence,
    now: datetime | None = None,
) -> VerificationResult:
    """Pure verification: status + score from candidate + evidence + clock."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    reasons: list[str] = []
    checks: dict[str, Any] = {}

    if evidence.official_cancellation:
        score = score_verification(
            ScoringInput(
                has_valid_dates=False,
                deadline_in_future=False,
                dates_ordered=True,
                keyword_hits=0,
                source_tier=evidence.source_tier,
                cross_source_count=evidence.cross_source_count,
                last_checked_at=evidence.last_checked_at,
                now=now,
                required_fields_present=0,
                required_fields_total=5,
                link_ok=False,
            )
        )
        return VerificationResult(
            status=VerificationStatus.CANCELLED,
            score=score,
            checks={"cancelled": True},
            reasons=["official_cancellation"],
            publishable=False,
            needs_human_review=False,
        )

    # Tier 3 only can never be verified_active
    only_t3 = evidence.only_tier3 or evidence.source_tier == "tier_3"
    checks["only_tier3"] = only_t3

    reg_or_start, sub_or_exp = _deadline_fields(candidate)
    checks["registration_or_start"] = reg_or_start.isoformat() if reg_or_start else None
    checks["submission_or_expiry"] = sub_or_exp.isoformat() if sub_or_exp else None

    dates_ordered = True
    if reg_or_start and sub_or_exp and reg_or_start > sub_or_exp:
        dates_ordered = False
        reasons.append("dates_out_of_order")

    has_valid_dates = sub_or_exp is not None or (
        candidate.kind == ListingKind.AI_OFFER
        and candidate.fields.get("offer_type") == "free_tier"
    )
    if not has_valid_dates:
        reasons.append("missing_deadline_or_expiry")

    deadline_in_future = True
    status = VerificationStatus.NEEDS_REVIEW

    # Permanent free tier: expires_at null is OK
    permanent_offer = (
        candidate.kind == ListingKind.AI_OFFER
        and candidate.fields.get("offer_type") == "free_tier"
        and sub_or_exp is None
    )
    checks["permanent_offer"] = permanent_offer

    if candidate.kind == ListingKind.HACKATHON and sub_or_exp is not None:
        if sub_or_exp < now:
            deadline_in_future = False
            status = VerificationStatus.EXPIRED
            reasons.append("submission_deadline_passed")
        if reg_or_start is not None and reg_or_start < now and sub_or_exp >= now:
            # Check registration_deadline field specifically
            reg_dl = candidate.fields.get("registration_deadline")
            if reg_dl is not None and reg_dl < now and sub_or_exp >= now:
                status = VerificationStatus.REGISTRATION_CLOSED
                reasons.append("registration_closed")
                deadline_in_future = True  # submission still open

    if candidate.kind == ListingKind.AI_OFFER and sub_or_exp is not None and sub_or_exp < now:
        deadline_in_future = False
        status = VerificationStatus.EXPIRED
        reasons.append("offer_expired")

    if not evidence.link_ok:
        reasons.append("link_check_failed")

    present, total = _required_field_count(candidate)
    checks["required_fields"] = {"present": present, "total": total}

    score = score_verification(
        ScoringInput(
            has_valid_dates=has_valid_dates and dates_ordered,
            deadline_in_future=deadline_in_future or permanent_offer,
            dates_ordered=dates_ordered,
            keyword_hits=keyword_hits_from_fields(candidate.kind.value, candidate.fields),
            source_tier=evidence.source_tier,
            cross_source_count=evidence.cross_source_count,
            last_checked_at=evidence.last_checked_at or now,
            now=now,
            required_fields_present=present,
            required_fields_total=total,
            link_ok=evidence.link_ok,
        )
    )
    checks["score_total"] = score.total

    # Terminal statuses already set (expired / registration_closed)
    if status in {
        VerificationStatus.EXPIRED,
        VerificationStatus.REGISTRATION_CLOSED,
    }:
        return VerificationResult(
            status=status,
            score=score,
            checks=checks,
            reasons=reasons,
            publishable=status == VerificationStatus.REGISTRATION_CLOSED,
            needs_human_review=False,
        )

    if only_t3:
        reasons.append("tier3_only_requires_review")
        return VerificationResult(
            status=VerificationStatus.NEEDS_REVIEW,
            score=score,
            checks=checks,
            reasons=reasons,
            publishable=False,
            needs_human_review=True,
        )

    if not evidence.link_ok or not dates_ordered or present < max(3, total - 1):
        reasons.append("incomplete_or_failed_checks")
        return VerificationResult(
            status=VerificationStatus.NEEDS_REVIEW,
            score=score,
            checks=checks,
            reasons=reasons,
            publishable=False,
            needs_human_review=True,
        )

    # Publishable tiers 1/2 with good evidence
    tier_ok = evidence.source_tier in {"tier_1", "tier_2"}
    if tier_ok and score.total >= MIN_PUBLISH_SCORE and evidence.link_ok and (
        has_valid_dates or permanent_offer
    ):
        # Auto-publish policy: high confidence → verified; medium → likely
        if score.total >= MIN_VERIFIED_SCORE and present >= total - 1:
            status = VerificationStatus.VERIFIED_ACTIVE
            reasons.append("auto_verified")
        else:
            status = VerificationStatus.LIKELY_ACTIVE
            reasons.append("likely_active_partial_evidence")
        return VerificationResult(
            status=status,
            score=score,
            checks=checks,
            reasons=reasons,
            publishable=True,
            # LIKELY_ACTIVE means "published on partial evidence" by definition,
            # so it always earns a human check — the listing goes live, but an
            # admin gets asked to confirm it.
            needs_human_review=status == VerificationStatus.LIKELY_ACTIVE,
        )

    reasons.append("default_needs_review")
    return VerificationResult(
        status=VerificationStatus.NEEDS_REVIEW,
        score=score,
        checks=checks,
        reasons=reasons,
        publishable=False,
        needs_human_review=True,
    )
