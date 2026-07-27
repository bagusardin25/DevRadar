"""Heuristic reviewer: grounded recommendations from verify() output."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.ai_review.heuristic import heuristic_review, unreachable_review
from app.ai_review.schemas import ReviewConcernSeverity, ReviewRecommendation
from app.catalog.enums import ListingKind, VerificationStatus
from app.ingestion.normalizer import CandidateListing
from app.ingestion.verifier import VerificationEvidence, verify

NOW = datetime(2026, 7, 27, tzinfo=UTC)


def _hackathon_fields(*, submission_offset_days: int) -> dict:
    return {
        "title": "Global AI Hack 2026",
        "organizer": "Org",
        "mode": "online",
        "official_url": "https://example.com/hack",
        "registration_deadline": NOW + timedelta(days=3),
        "submission_deadline": NOW + timedelta(days=submission_offset_days),
        "technologies": ["Python", "AI"],
        "prize_value": 25000,
        "prize_currency": "USD",
        "eligibility": ["Developers"],
        "eligible_countries": ["Worldwide"],
    }


def _verify(fields: dict, *, tier: str = "tier_2", only_tier3: bool = False):
    candidate = CandidateListing(
        kind=ListingKind.HACKATHON,
        title=fields["title"],
        description="An online hackathon",
        official_url=fields["official_url"],
        canonical_url=fields["official_url"],
        fields=dict(fields),
    )
    result = verify(
        candidate,
        VerificationEvidence(
            source_tier=tier,
            link_ok=True,
            cross_source_count=2,
            last_checked_at=NOW,
            only_tier3=only_tier3,
        ),
        now=NOW,
    )
    return candidate, result


def test_solid_listing_recommends_approve() -> None:
    candidate, result = _verify(_hackathon_fields(submission_offset_days=20), tier="tier_1")
    assert result.publishable is True
    review = heuristic_review(candidate, result)
    assert review.recommendation is ReviewRecommendation.APPROVE
    assert review.confidence == result.score.total
    assert review.engine == "heuristic"
    assert review.suggested_fields.get("title") == "Global AI Hack 2026"


def test_expired_listing_recommends_reject() -> None:
    candidate, result = _verify(_hackathon_fields(submission_offset_days=-5))
    assert result.status is VerificationStatus.EXPIRED
    review = heuristic_review(candidate, result)
    assert review.recommendation is ReviewRecommendation.REJECT
    assert review.confidence == 90
    assert any(c.severity is ReviewConcernSeverity.HIGH for c in review.concerns)


def test_tier3_only_needs_more_info() -> None:
    candidate, result = _verify(
        _hackathon_fields(submission_offset_days=20), tier="tier_3", only_tier3=True
    )
    review = heuristic_review(candidate, result)
    assert review.recommendation is ReviewRecommendation.NEEDS_MORE_INFO
    assert any("official" in c.message.lower() for c in review.concerns)


def test_unreachable_review_flags_high_concern() -> None:
    review = unreachable_review(
        title="Mystery Hack",
        kind=ListingKind.HACKATHON,
        url="https://example.com/down",
        detail="HTTP 503",
    )
    assert review.recommendation is ReviewRecommendation.NEEDS_MORE_INFO
    assert review.concerns[0].severity is ReviewConcernSeverity.HIGH
    assert "503" in review.concerns[0].message
    assert review.to_snapshot()["recommendation"] == "needs_more_info"
