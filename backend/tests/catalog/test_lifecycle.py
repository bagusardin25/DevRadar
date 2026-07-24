"""Unit tests for catalogue lifecycle transitions."""

from datetime import UTC, datetime, timedelta

from app.catalog.enums import VerificationStatus
from app.catalog.lifecycle import desired_ai_offer_status, desired_hackathon_status


def test_registration_closed_when_reg_passed_but_submission_future() -> None:
    now = datetime(2026, 7, 25, tzinfo=UTC)
    reg = now - timedelta(days=1)
    sub = now + timedelta(days=7)
    assert (
        desired_hackathon_status(
            VerificationStatus.VERIFIED_ACTIVE,
            registration_deadline=reg,
            submission_deadline=sub,
            now=now,
        )
        == VerificationStatus.REGISTRATION_CLOSED
    )


def test_expired_when_submission_passed() -> None:
    now = datetime(2026, 7, 25, tzinfo=UTC)
    past = now - timedelta(days=2)
    assert (
        desired_hackathon_status(
            VerificationStatus.LIKELY_ACTIVE,
            registration_deadline=past,
            submission_deadline=past,
            now=now,
        )
        == VerificationStatus.EXPIRED
    )


def test_no_change_when_still_open() -> None:
    now = datetime(2026, 7, 25, tzinfo=UTC)
    future = now + timedelta(days=10)
    assert (
        desired_hackathon_status(
            VerificationStatus.VERIFIED_ACTIVE,
            registration_deadline=future,
            submission_deadline=future,
            now=now,
        )
        is None
    )


def test_ai_offer_expired() -> None:
    now = datetime(2026, 7, 25, tzinfo=UTC)
    assert (
        desired_ai_offer_status(
            VerificationStatus.VERIFIED_ACTIVE,
            expires_at=now - timedelta(hours=1),
            now=now,
        )
        == VerificationStatus.EXPIRED
    )


def test_cancelled_not_touched() -> None:
    now = datetime(2026, 7, 25, tzinfo=UTC)
    assert (
        desired_hackathon_status(
            VerificationStatus.CANCELLED,
            registration_deadline=now - timedelta(days=1),
            submission_deadline=now - timedelta(days=1),
            now=now,
        )
        is None
    )
