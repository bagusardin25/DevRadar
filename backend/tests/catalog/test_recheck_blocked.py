"""Monitoring recheck of a Devpost listing behind a Cloudflare bot check (no database)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.catalog import recheck
from app.catalog.enums import HackathonMode, ListingKind, VerificationStatus
from app.catalog.models import Hackathon, Listing
from app.config import Settings
from app.ingestion.models import VerificationEvent
from tests.challenge_pages import (
    CHALLENGE_403,
    CHALLENGE_503,
    EVENT_200,
    EVENT_URL,
    allow_fixture_hosts,
    mock_fetch_url,
)

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
CURATED_DESCRIPTION = "Curated description of the Kiroween online hackathon. " * 2


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class _Session:
    def __init__(self, listings: list[Listing] | None = None) -> None:
        self.added: list[Any] = []
        self._listings = listings or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, _statement: Any) -> _Result:
        return _Result(self._listings)

    async def flush(self) -> None:
        return None


def _listing() -> Listing:
    listing = Listing(
        id=uuid4(),
        kind=ListingKind.HACKATHON,
        slug="kiroween-online-hack-2026",
        title="Kiroween Online Hack 2026",
        description=CURATED_DESCRIPTION,
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        confidence_score=Decimal("0.9"),
    )
    listing.hackathon = Hackathon(
        listing_id=listing.id,
        organizer="Example Labs",
        mode=HackathonMode.ONLINE,
        official_url=EVENT_URL,
        submission_deadline=datetime(2026, 12, 5, 23, 59, 59, tzinfo=UTC),
        prize_value=Decimal("10000"),
        prize_currency="USD",
        team_min=1,
        team_max=4,
        technologies=[],
        eligibility=[],
        eligible_countries=["Worldwide"],
    )
    return listing


def _settings() -> Settings:
    return Settings(_env_file=None, app_env="test", llm_provider="disabled")  # type: ignore[call-arg]


@pytest.fixture(autouse=True)
def _fixture_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_fixture_hosts(monkeypatch)


@pytest.mark.parametrize("reply", [CHALLENGE_403, CHALLENGE_503], ids=["403", "503"])
async def test_blocked_recheck_records_a_block_and_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, reply: Any
) -> None:
    monkeypatch.setattr(recheck, "fetch_url", mock_fetch_url(reply))
    listing = _listing()
    session = _Session()

    result = await recheck.recheck_listing(
        session,  # type: ignore[arg-type]
        listing,
        settings=_settings(),
        now=NOW,
    )

    assert result.blocked is True
    assert result.ok is False
    assert result.status_code == reply[0]
    assert result.error is not None and result.error.startswith("blocked:")
    # Not dead, not expired, not rewritten from the challenge page.
    assert listing.verification_status == VerificationStatus.VERIFIED_ACTIVE
    assert listing.title == "Kiroween Online Hack 2026"
    assert listing.description == CURATED_DESCRIPTION
    assert listing.hackathon.submission_deadline == datetime(2026, 12, 5, 23, 59, 59, tzinfo=UTC)

    (event,) = [obj for obj in session.added if isinstance(obj, VerificationEvent)]
    assert event.event_type == "official_url_recheck_blocked"
    assert event.previous_status == event.new_status == VerificationStatus.VERIFIED_ACTIVE
    assert event.score_breakdown["needsHumanCheck"] is True
    assert event.score_breakdown["httpStatus"] == reply[0]


async def test_normal_page_recheck_still_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recheck, "fetch_url", mock_fetch_url(EVENT_200))
    listing = _listing()
    session = _Session()

    result = await recheck.recheck_listing(
        session,  # type: ignore[arg-type]
        listing,
        settings=_settings(),
        now=NOW,
    )

    assert result.ok is True
    assert result.blocked is False
    assert result.status_code == 200
    (event,) = [obj for obj in session.added if isinstance(obj, VerificationEvent)]
    assert event.event_type == "official_url_recheck"


async def test_recheck_summary_counts_blocked_apart_from_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(recheck, "fetch_url", mock_fetch_url(CHALLENGE_403))
    session = _Session([_listing()])

    summary = await recheck.recheck_catalogue(
        session,  # type: ignore[arg-type]
        kind=ListingKind.HACKATHON,
        settings=_settings(),
    )

    assert summary.scanned == 1
    assert summary.blocked == 1
    assert summary.failed == 0
    assert summary.ok == 0
