"""Submission-specific worker request construction."""

from app.catalog.enums import ListingKind
from app.ingestion.tasks import _build_submission_fetch_request
from app.submissions.models import CommunitySubmission


def _submission(kind: str | None) -> CommunitySubmission:
    return CommunitySubmission(
        tracking_id="tracking",
        original_url="https://example.com/offer",
        canonical_url="https://example.com/offer",
        claimed_type=kind,
        claimed_title="Offer",
        ip_hash="hash",
        job_idempotency_key="job-key",
        metadata_json={},
    )


def test_ai_offer_keeps_ai_offer_extraction_schema() -> None:
    request = _build_submission_fetch_request(
        _submission(ListingKind.AI_OFFER.value)
    )

    assert request["listing_kind"] == "ai_offer"
    assert request["include_excerpt"] is True


def test_missing_type_falls_back_to_hackathon() -> None:
    request = _build_submission_fetch_request(_submission(None))

    assert request["listing_kind"] == "hackathon"
