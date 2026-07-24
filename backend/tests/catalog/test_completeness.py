"""Completeness scoring unit tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.catalog.completeness import (
    ai_offer_completeness,
    hackathon_completeness,
    is_weak_official_url,
)
from app.catalog.enums import HackathonMode, ListingKind, OfferType, VerificationStatus
from app.catalog.models import AIOffer, Hackathon, Listing


def _listing(**kwargs: object) -> Listing:
    defaults = dict(
        id=uuid4(),
        kind=ListingKind.HACKATHON,
        slug="test-slug",
        title="A solid title",
        description="x" * 50,
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        confidence_score=Decimal("0.9"),
    )
    defaults.update(kwargs)
    return Listing(**defaults)  # type: ignore[arg-type]


def test_weak_url_detection() -> None:
    assert is_weak_official_url("https://x.com/foo/status/1")
    assert is_weak_official_url("https://devfolio.co/")
    assert is_weak_official_url("https://dorahacks.io")
    assert not is_weak_official_url("https://datahub.devpost.com/")
    assert not is_weak_official_url("https://lablab.ai/ai-hackathons/foo")


def test_hackathon_score_full() -> None:
    listing = _listing()
    now = datetime(2026, 7, 25, tzinfo=UTC)
    h = Hackathon(
        listing_id=listing.id,
        organizer="Org",
        registration_deadline=now + timedelta(days=5),
        submission_deadline=now + timedelta(days=10),
        mode=HackathonMode.ONLINE,
        eligible_countries=["Worldwide"],
        eligibility=["Developer"],
        team_min=1,
        team_max=4,
        prize_value=Decimal("1000"),
        prize_currency="USD",
        prize_label="$1,000 prize pool",
        technologies=["AI"],
        official_url="https://example.com/hack",
        suitable_reasons=[],
    )
    c = hackathon_completeness(listing, h, now=now)
    assert c["score"] == 100
    assert "closing_soon" in c["flags"]
    assert c["hasStrongUrl"] is True
    assert c["hasPrize"] is True


def test_hackathon_prize_tba_flag() -> None:
    listing = _listing()
    now = datetime(2026, 7, 25, tzinfo=UTC)
    h = Hackathon(
        listing_id=listing.id,
        organizer="Org",
        registration_deadline=now + timedelta(days=30),
        submission_deadline=now + timedelta(days=40),
        mode=HackathonMode.ONLINE,
        eligible_countries=["Worldwide"],
        eligibility=["Developer"],
        team_min=1,
        team_max=4,
        prize_value=Decimal("0"),
        prize_currency="USD",
        prize_label="Prize TBA · check site",
        technologies=["AI"],
        official_url="https://x.com/foo",
        suitable_reasons=[],
    )
    c = hackathon_completeness(listing, h, now=now)
    assert "prize_tba" in c["flags"]
    assert "weak_url" in c["flags"]
    assert c["score"] < 100


def test_ai_offer_no_expiry_flag() -> None:
    listing = _listing(kind=ListingKind.AI_OFFER, slug="offer")
    o = AIOffer(
        listing_id=listing.id,
        product_name="Studio",
        provider="Google",
        offer_type=OfferType.FREE_TIER,
        offer_value="Free tier",
        target_users=["Developer"],
        requirements=[],
        starts_at=None,
        expires_at=None,
        supported_regions=["Worldwide"],
        official_terms_url="https://aistudio.google.com/",
        claim_url="https://aistudio.google.com/",
        tags=["free"],
        suitable_reasons=[],
    )
    c = ai_offer_completeness(listing, o)
    assert "no_expiry" in c["flags"]
    assert c["score"] >= 80
