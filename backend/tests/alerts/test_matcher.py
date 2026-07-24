"""Alert filter matcher tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.alerts.matcher import match_listing
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
                submission_deadline=datetime.now(UTC) + timedelta(days=60)
            )
        )
        assert match_listing(far, {"onlyClosingSoon": True}) is False

    def test_kind_filter(self) -> None:
        assert match_listing(_listing(), {"kind": "hackathon"}) is True
        assert match_listing(_listing(), {"kind": "ai_offer"}) is False
