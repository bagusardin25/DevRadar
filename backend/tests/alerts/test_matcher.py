"""Alert filter matcher tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.alerts.matcher import match_listing, normalize_alert_filters
from app.catalog.enums import ListingKind, VerificationStatus


def _listing(**kwargs: object):
    now = datetime.now(UTC)
    base = dict(
        id=uuid4(),
        kind=ListingKind.HACKATHON,
        title="Global AI Hackathon",
        description="online python",
        search_extra="AI Python",
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        hackathon=SimpleNamespace(
            submission_deadline=now + timedelta(days=7),
            registration_deadline=now + timedelta(days=5),
            mode="online",
            technologies=["Python", "PyTorch"],
            prize_value=Decimal("15000"),
            eligible_countries=["Global"],
            eligibility=["Students"],
            location=None,
        ),
        ai_offer=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _offer_listing(**kwargs: object):
    now = datetime.now(UTC)
    base = dict(
        id=uuid4(),
        kind=ListingKind.AI_OFFER,
        title="Free GPU Credits",
        description="startup credits",
        search_extra="GPU OpenAI",
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        hackathon=None,
        ai_offer=SimpleNamespace(
            expires_at=now + timedelta(days=10),
            tags=["OpenAI", "credits"],
            offer_type="free_credits",
            supported_regions=["US", "EU"],
            target_users=["startups"],
            offer_value="$1000",
            claim_url="https://example.com",
            provider="Acme",
        ),
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


class TestMatcher:
    def test_query_match(self) -> None:
        assert match_listing(_listing(), {"q": "AI"}) is True
        assert match_listing(_listing(), {"q": "blockchain"}) is False

    def test_status_filter(self) -> None:
        assert (
            match_listing(_listing(), {"status": "verified_active,likely_active"})
            is True
        )
        assert match_listing(_listing(), {"status": "expired"}) is False

    def test_closing_soon(self) -> None:
        assert match_listing(_listing(), {"onlyClosingSoon": True}) is True
        far = _listing(
            hackathon=SimpleNamespace(
                submission_deadline=datetime.now(UTC) + timedelta(days=60),
                registration_deadline=datetime.now(UTC) + timedelta(days=50),
                mode="online",
                technologies=["Python"],
                prize_value=Decimal("1000"),
                eligible_countries=[],
                eligibility=[],
                location=None,
            )
        )
        assert match_listing(far, {"onlyClosingSoon": True}) is False

    def test_kind_filter(self) -> None:
        assert match_listing(_listing(), {"kind": "hackathon"}) is True
        assert match_listing(_listing(), {"kind": "ai_offer"}) is False
        assert match_listing(_listing(), {"targetType": "ai_deal"}) is False

    def test_mode_filter(self) -> None:
        assert match_listing(_listing(), {"mode": "online"}) is True
        assert match_listing(_listing(), {"mode": "hybrid"}) is False

    def test_technology_filter(self) -> None:
        assert match_listing(_listing(), {"technology": "pytorch"}) is True
        assert match_listing(_listing(), {"technology": "solidity"}) is False
        assert match_listing(_listing(), {"technologies": ["Python"]}) is True

    def test_min_prize_and_big_prizes(self) -> None:
        assert match_listing(_listing(), {"minPrize": 10000}) is True
        assert match_listing(_listing(), {"minPrize": 50000}) is False
        assert match_listing(_listing(), {"onlyBigPrizes": True}) is True
        small = _listing(
            hackathon=SimpleNamespace(
                submission_deadline=datetime.now(UTC) + timedelta(days=7),
                registration_deadline=None,
                mode="online",
                technologies=[],
                prize_value=Decimal("500"),
                eligible_countries=[],
                eligibility=[],
                location=None,
            )
        )
        assert match_listing(small, {"onlyBigPrizes": True}) is False

    def test_offer_type_and_region(self) -> None:
        offer = _offer_listing()
        assert match_listing(offer, {"kind": "ai_offer", "offerType": "free_credits"}) is True
        assert match_listing(offer, {"offerType": "trial"}) is False
        assert match_listing(offer, {"region": "eu"}) is True
        assert match_listing(offer, {"region": "apac"}) is False

    def test_expired_status_never_matches(self) -> None:
        expired = _listing(verification_status=VerificationStatus.EXPIRED)
        assert match_listing(expired, {}) is False


class TestNormalizeFilters:
    def test_canonicalizes_client_payload(self) -> None:
        out = normalize_alert_filters(
            {
                "targetType": "ai_deal",
                "searchQuery": "LLM",
                "mode": "all",
                "onlyClosingSoon": True,
                "onlyBigPrizes": True,
                "technology": "Python",
            }
        )
        assert out["kind"] == "ai_offer"
        assert out["q"] == "LLM"
        assert "mode" not in out
        assert out["onlyClosingSoon"] is True
        assert out["onlyBigPrizes"] is True
        assert out["technology"] == "Python"
