"""Unit tests for recheck field merge helpers."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.catalog.enums import HackathonMode, ListingKind, OfferType, VerificationStatus
from app.catalog.models import AIOffer, Hackathon, Listing
from app.catalog.recheck import _merge_ai_offer, _merge_hackathon


def test_merge_ai_offer_updates_value_and_tags() -> None:
    listing = Listing(
        id=uuid4(),
        kind=ListingKind.AI_OFFER,
        slug="t",
        title="Old",
        description="old desc " + "x" * 40,
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        confidence_score=Decimal("0.9"),
    )
    offer = AIOffer(
        listing_id=listing.id,
        product_name="Old product",
        provider="OldCo",
        offer_type=OfferType.FREE_TIER,
        offer_value="old value",
        target_users=["Developer"],
        requirements=[],
        starts_at=None,
        expires_at=None,
        supported_regions=["Worldwide"],
        official_terms_url="https://example.com/terms",
        claim_url="https://example.com/claim",
        tags=["old"],
        suitable_reasons=[],
    )
    listing.ai_offer = offer
    # Curated product_name is protected; offer_value updates when free-tier-like
    updated = _merge_ai_offer(
        listing,
        {
            "product_name": "New product",
            "offer_value": "10,000 Neurons/day free",
            "tags": ["free", "edge"],
            "official_terms_url": "https://example.com/new-terms",
        },
    )
    assert "product_name" not in updated  # already filled
    assert "offer_value" in updated
    assert offer.offer_value == "10,000 Neurons/day free"
    assert offer.product_name == "Old product"
    # tags not empty → not overwritten
    assert offer.tags == ["old"]


def test_merge_hackathon_prize() -> None:
    listing = Listing(
        id=uuid4(),
        kind=ListingKind.HACKATHON,
        slug="h",
        title="Hack",
        description="d" * 50,
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        confidence_score=Decimal("0.9"),
    )
    h = Hackathon(
        listing_id=listing.id,
        organizer="Org",
        registration_deadline=datetime(2026, 8, 1, tzinfo=UTC),
        submission_deadline=datetime(2026, 8, 10, tzinfo=UTC),
        mode=HackathonMode.ONLINE,
        eligible_countries=["Worldwide"],
        eligibility=["Developer"],
        team_min=1,
        team_max=4,
        prize_value=Decimal("0"),
        prize_currency="USD",
        prize_label="",
        technologies=["AI"],
        official_url="https://example.com/hack",
        suitable_reasons=[],
    )
    listing.hackathon = h
    updated = _merge_hackathon(
        listing,
        {"prize_value": 5000, "prize_currency": "USD", "technologies": ["AI", "Rust"]},
    )
    assert "prize_value" in updated
    assert h.prize_value == Decimal("5000")
    assert "prize_label" in updated
    assert "5000" in h.prize_label or "5,000" in h.prize_label
