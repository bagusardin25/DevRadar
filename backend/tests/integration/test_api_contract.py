"""Backend contract snapshots for frontend TypeScript shapes."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.catalog.enums import (
    HackathonMode,
    OfferType,
    VerificationStatus,
)
from app.catalog.public_schemas import (
    AIOfferPublic,
    DiscoverySourcePublic,
    HackathonPublic,
    ScoreBreakdownPublic,
    VerificationAuditPublic,
)


def test_hackathon_public_camel_case_keys() -> None:
    now = datetime.now(UTC)
    model = HackathonPublic(
        id=str(uuid4()),
        slug="sample-hack",
        title="Sample",
        organizer="Org",
        description="Desc",
        registration_open_at=now,
        registration_deadline=now,
        submission_deadline=now,
        mode=HackathonMode.ONLINE,
        eligible_countries=["Worldwide"],
        eligibility=["Developer"],
        team_min=1,
        team_max=4,
        prize_value=Decimal("1000"),
        prize_currency="USD",
        technologies=["Python"],
        official_url="https://example.com",
        discovery_sources=[
            DiscoverySourcePublic(
                type="devpost",
                url="https://devpost.com/x",
                fetched_at=now,
                tier="Tier 2 (Aggregator)",
            )
        ],
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        confidence_score=Decimal("0.9"),
        last_checked_at=now,
        suitable_reasons=["online"],
        audit=VerificationAuditPublic(
            last_checked_at=now,
            confidence_score=Decimal("0.9"),
            score_breakdown=ScoreBreakdownPublic(
                status_and_deadline=30,
                keyword_match=20,
                source_credibility=15,
                freshness=12,
                completeness=5,
            ),
            verifier_notes="ok",
            checked_urls=["https://example.com"],
            pipeline_step="verified",
        ),
    )
    data = model.model_dump(by_alias=True)
    for key in (
        "registrationDeadline",
        "submissionDeadline",
        "eligibleCountries",
        "teamMin",
        "prizeValue",
        "officialUrl",
        "discoverySources",
        "verificationStatus",
        "confidenceScore",
        "lastCheckedAt",
        "suitableReasons",
    ):
        assert key in data
    assert data["discoverySources"][0]["fetchedAt"]
    assert data["audit"]["scoreBreakdown"]["statusAndDeadline"] == 30


def test_ai_offer_public_camel_case_keys() -> None:
    now = datetime.now(UTC)
    model = AIOfferPublic(
        id=str(uuid4()),
        slug="sample-offer",
        product_name="Cloud",
        provider="Acme",
        offer_type=OfferType.FREE_CREDITS,
        offer_value="$100",
        target_users=["Developer"],
        requirements=[],
        starts_at=now,
        expires_at=None,
        supported_regions=["Worldwide"],
        official_terms_url="https://example.com/terms",
        claim_url="https://example.com/claim",
        verification_status=VerificationStatus.LIKELY_ACTIVE,
        confidence_score=Decimal("0.8"),
        last_checked_at=now,
        description="credits",
        tags=["AI"],
        discovery_sources=[],
        suitable_reasons=[],
        audit=VerificationAuditPublic(
            last_checked_at=now,
            confidence_score=Decimal("0.8"),
            score_breakdown=ScoreBreakdownPublic(),
            pipeline_step="verified",
        ),
    )
    data = model.model_dump(by_alias=True)
    for key in (
        "productName",
        "offerType",
        "offerValue",
        "targetUsers",
        "supportedRegions",
        "officialTermsUrl",
        "claimUrl",
        "verificationStatus",
        "confidenceScore",
    ):
        assert key in data
    assert data["expiresAt"] is None
