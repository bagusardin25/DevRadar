"""Verification state machine tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.catalog.enums import ListingKind, VerificationStatus
from app.ingestion.normalizer import CandidateListing
from app.ingestion.verifier import VerificationEvidence, verify

NOW = datetime(2026, 7, 15, tzinfo=UTC)


def _hack(**field_over: object) -> CandidateListing:
    fields = {
        "title": "Test Hack",
        "organizer": "Org",
        "mode": "online",
        "official_url": "https://example.com/h",
        "registration_deadline": NOW + timedelta(days=5),
        "submission_deadline": NOW + timedelta(days=20),
        "technologies": ["Python"],
        "prize_value": 1000,
        "team_min": 1,
        "team_max": 4,
        "eligible_countries": ["Worldwide"],
    }
    fields.update(field_over)
    return CandidateListing(
        kind=ListingKind.HACKATHON,
        title=str(fields["title"]),
        description="desc",
        official_url="https://example.com/h",
        canonical_url="https://example.com/h",
        fields=fields,
    )


def _offer(**field_over: object) -> CandidateListing:
    fields = {
        "product_name": "Cloud",
        "provider": "Acme",
        "offer_type": "free_credits",
        "claim_url": "https://example.com/c",
        "official_terms_url": "https://example.com/t",
        "expires_at": NOW + timedelta(days=30),
        "offer_value": "$100",
        "tags": ["AI"],
    }
    fields.update(field_over)
    return CandidateListing(
        kind=ListingKind.AI_OFFER,
        title="Cloud credits",
        description="d",
        official_url="https://example.com/c",
        canonical_url="https://example.com/c",
        fields=fields,
    )


class TestVerifier:
    def test_tier3_only_needs_review(self) -> None:
        r = verify(
            _hack(),
            VerificationEvidence(source_tier="tier_3", only_tier3=True, link_ok=True),
            now=NOW,
        )
        assert r.status == VerificationStatus.NEEDS_REVIEW
        assert r.publishable is False
        assert r.needs_human_review is True

    def test_tier1_high_score_verified(self) -> None:
        r = verify(
            _hack(),
            VerificationEvidence(source_tier="tier_1", link_ok=True, cross_source_count=2),
            now=NOW,
        )
        assert r.status in {
            VerificationStatus.VERIFIED_ACTIVE,
            VerificationStatus.LIKELY_ACTIVE,
        }
        assert r.publishable is True

    def test_expired_submission(self) -> None:
        r = verify(
            _hack(submission_deadline=NOW - timedelta(days=1)),
            VerificationEvidence(source_tier="tier_1", link_ok=True),
            now=NOW,
        )
        assert r.status == VerificationStatus.EXPIRED

    def test_registration_closed(self) -> None:
        r = verify(
            _hack(
                registration_deadline=NOW - timedelta(days=1),
                submission_deadline=NOW + timedelta(days=10),
            ),
            VerificationEvidence(source_tier="tier_1", link_ok=True),
            now=NOW,
        )
        assert r.status == VerificationStatus.REGISTRATION_CLOSED

    def test_cancelled(self) -> None:
        r = verify(
            _hack(),
            VerificationEvidence(official_cancellation=True),
            now=NOW,
        )
        assert r.status == VerificationStatus.CANCELLED

    def test_bad_link_needs_review(self) -> None:
        r = verify(
            _hack(),
            VerificationEvidence(source_tier="tier_1", link_ok=False),
            now=NOW,
        )
        assert r.status == VerificationStatus.NEEDS_REVIEW

    def test_dates_out_of_order(self) -> None:
        r = verify(
            _hack(
                registration_deadline=NOW + timedelta(days=30),
                submission_deadline=NOW + timedelta(days=5),
            ),
            VerificationEvidence(source_tier="tier_1", link_ok=True),
            now=NOW,
        )
        assert r.status == VerificationStatus.NEEDS_REVIEW
        assert any("order" in x for x in r.reasons)

    def test_permanent_free_tier(self) -> None:
        r = verify(
            _offer(offer_type="free_tier", expires_at=None),
            VerificationEvidence(source_tier="tier_1", link_ok=True),
            now=NOW,
        )
        assert r.status in {
            VerificationStatus.VERIFIED_ACTIVE,
            VerificationStatus.LIKELY_ACTIVE,
            VerificationStatus.NEEDS_REVIEW,
        }

    def test_offer_expired(self) -> None:
        r = verify(
            _offer(expires_at=NOW - timedelta(days=2)),
            VerificationEvidence(source_tier="tier_1", link_ok=True),
            now=NOW,
        )
        assert r.status == VerificationStatus.EXPIRED

    def test_clock_injection_deterministic(self) -> None:
        a = verify(_hack(), VerificationEvidence(source_tier="tier_2"), now=NOW)
        b = verify(_hack(), VerificationEvidence(source_tier="tier_2"), now=NOW)
        assert a.status == b.status
        assert a.score == b.score
