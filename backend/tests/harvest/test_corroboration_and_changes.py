"""Cross-directory corroboration, directory dates and change detection (DB-free)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import app.models  # noqa: F401
from app.catalog.enums import ReviewCandidateType, SourceTier
from app.harvest import runner
from app.harvest.runner import (
    KnownListing,
    SourceBatch,
    apply_directory_dates,
    corroborating_sources,
    detect_directory_changes,
    flag_directory_changes,
    merge_batches,
)
from app.review.models import ReviewItem
from app.sources.connectors.base import DiscoveryCandidate
from app.sources.models import Source


def _hit(
    source: str,
    url: str,
    title: str = "Global Agents Hackathon",
    *,
    starts: str | None = "2026-10-20T00:00:00Z",
    ends: str | None = "2026-11-20T00:00:00Z",
    registration_ends: str | None = None,
) -> DiscoveryCandidate:
    return DiscoveryCandidate(
        external_id=url,
        url=url,
        title=title,
        metadata={
            "source": source,
            "mode": "online",
            "starts_at": starts,
            "ends_at": ends,
            "registration_ends_at": registration_ends,
        },
    )


# --------------------------------------------------------------------------- #
# Corroboration
# --------------------------------------------------------------------------- #


def test_duplicate_from_lower_priority_source_corroborates_the_winner() -> None:
    winner = _hit("devpost", "https://agents.devpost.com/")
    batches = {
        "devpost": SourceBatch(fresh=[winner]),
        "dorahacks": SourceBatch(fresh=[_hit("dorahacks", "https://dorahacks.io/hackathon/agents")]),
        "devfolio": SourceBatch(fresh=[_hit("devfolio", "https://agents.devfolio.co/")]),
    }
    selected, cross = merge_batches(batches, total_cap=40)

    assert [key for key, _ in selected] == ["devpost"]
    assert cross == {"dorahacks": 1, "devfolio": 1}
    also = winner.metadata["also_listed_on"]
    assert [entry["source"] for entry in also] == ["dorahacks", "devfolio"]
    assert also[0]["url"] == "https://dorahacks.io/hackathon/agents"
    assert corroborating_sources(winner) == 3


def test_same_url_on_two_directories_corroborates() -> None:
    winner = _hit("devpost", "https://agents.example.com/", title="Agents")
    batches = {
        "devpost": SourceBatch(fresh=[winner]),
        "hackclub": SourceBatch(fresh=[_hit("hackclub", "https://agents.example.com", title="x")]),
    }
    merge_batches(batches, total_cap=40)
    assert corroborating_sources(winner) == 2


def test_match_against_known_row_does_not_corroborate_anything() -> None:
    fresh = _hit("devfolio", "https://agents.devfolio.co/")
    batches = {
        "devpost": SourceBatch(seen_known=[_hit("devpost", "https://agents.devpost.com/")]),
        "devfolio": SourceBatch(fresh=[fresh]),
    }
    selected, cross = merge_batches(batches, total_cap=40)
    assert selected == [] and cross == {"devfolio": 1}
    assert "also_listed_on" not in fresh.metadata


def test_each_corroborating_source_counts_once() -> None:
    hit = _hit("devpost", "https://a.devpost.com/")
    hit.metadata["also_listed_on"] = [
        {"source": "devfolio"},
        {"source": "devfolio"},
        {"source": "devpost"},
        "junk",
    ]
    assert corroborating_sources(hit) == 2
    assert corroborating_sources(_hit("devpost", "https://b.devpost.com/")) == 1


# --------------------------------------------------------------------------- #
# Directory dates
# --------------------------------------------------------------------------- #


def _extraction(**fields: Any) -> SimpleNamespace:
    return SimpleNamespace(fields=dict(fields), field_sources={})


def test_directory_dates_fill_gaps() -> None:
    extraction = _extraction()
    conflicts = apply_directory_dates(
        extraction,
        {"ends_at": "2026-11-20T00:00:00Z", "registration_ends_at": "2026-11-01T00:00:00Z"},
        authoritative=False,
    )
    assert conflicts == []
    assert extraction.fields["submission_deadline"].startswith("2026-11-20T00:00:00")
    assert extraction.fields["registration_deadline"].startswith("2026-11-01T00:00:00")
    assert extraction.field_sources == {
        "registration_deadline": "directory",
        "submission_deadline": "directory",
    }


def test_directory_dates_within_a_day_agree() -> None:
    extraction = _extraction(submission_deadline="2026-11-20T23:59:00+00:00")
    conflicts = apply_directory_dates(
        extraction, {"ends_at": "2026-11-20T00:00:00Z"}, authoritative=True
    )
    assert conflicts == []
    assert extraction.fields["submission_deadline"] == "2026-11-20T23:59:00+00:00"


def test_hosting_directory_wins_a_date_conflict() -> None:
    extraction = _extraction(submission_deadline="2026-12-31T00:00:00Z")
    conflicts = apply_directory_dates(
        extraction, {"ends_at": "2026-11-20T00:00:00Z"}, authoritative=True
    )
    assert conflicts == ["submission_deadline"]
    assert extraction.fields["submission_deadline"].startswith("2026-11-20")
    assert extraction.field_sources["submission_deadline"] == "directory"


def test_non_hosting_directory_only_reports_a_conflict() -> None:
    extraction = _extraction(submission_deadline="2026-12-31T00:00:00Z")
    conflicts = apply_directory_dates(
        extraction, {"ends_at": "2026-11-20T00:00:00Z"}, authoritative=False
    )
    assert conflicts == ["submission_deadline"]
    assert extraction.fields["submission_deadline"] == "2026-12-31T00:00:00Z"
    assert extraction.field_sources == {}


def test_unparseable_directory_date_is_ignored() -> None:
    extraction = _extraction()
    assert apply_directory_dates(extraction, {"ends_at": "soon"}, authoritative=True) == []
    assert extraction.fields == {}


# --------------------------------------------------------------------------- #
# Change detection
# --------------------------------------------------------------------------- #


def _known(**overrides: Any) -> KnownListing:
    data: dict[str, Any] = {
        "listing_id": uuid4(),
        "title": "Global Agents Hackathon",
        "submission_deadline": datetime(2026, 11, 20, tzinfo=UTC),
        "registration_deadline": None,
    }
    data.update(overrides)
    return KnownListing(**data)


def test_detects_a_moved_deadline() -> None:
    hit = _hit("devpost", "https://agents.devpost.com/", ends="2026-12-04T00:00:00Z")
    changes = detect_directory_changes(hit, _known())
    assert changes == [
        {
            "field": "submission_deadline",
            "from": "2026-11-20T00:00:00+00:00",
            "to": "2026-12-04T00:00:00+00:00",
        }
    ]


def test_detects_a_newly_announced_registration_deadline() -> None:
    hit = _hit(
        "devpost",
        "https://agents.devpost.com/",
        registration_ends="2026-11-10T00:00:00Z",
    )
    changes = detect_directory_changes(hit, _known())
    assert [c["field"] for c in changes] == ["registration_deadline"]
    assert changes[0]["from"] is None


def test_unchanged_or_already_flagged_dates_are_quiet() -> None:
    hit = _hit("devpost", "https://agents.devpost.com/", ends="2026-11-20T12:00:00Z")
    assert detect_directory_changes(hit, _known()) == []

    moved = _hit("devpost", "https://agents.devpost.com/", ends="2026-12-04T00:00:00Z")
    known = _known(pending={"submission_deadline:2026-12-04T00:00:00+00:00"})
    assert detect_directory_changes(moved, known) == []


class _MemorySession:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None


def _source() -> Source:
    source = Source(
        name="Devpost (online harvest)",
        connector_type="devpost",
        trust_tier=SourceTier.TIER_2,
        base_url="https://devpost.com/",
    )
    source.id = uuid4()
    return source


async def test_flag_directory_changes_opens_one_review_item_per_listing() -> None:
    session = _MemorySession()
    known = _known()
    moved = _hit("devpost", "https://agents.devpost.com/", ends="2026-12-04T00:00:00Z")
    listings = {runner._canonical_key(moved.url): known}

    flagged = await flag_directory_changes(
        session,  # type: ignore[arg-type]
        source_key="devpost",
        source=_source(),
        batch=SourceBatch(seen_known=[moved]),
        listings=listings,
    )

    assert flagged == 1
    [item] = session.added
    assert isinstance(item, ReviewItem)
    assert item.candidate_type == ReviewCandidateType.LISTING
    assert item.listing_id == known.listing_id
    assert item.priority == runner.CHANGE_PRIORITY
    assert item.candidate_snapshot["directoryChange"]["changes"][0]["field"] == (
        "submission_deadline"
    )
    assert "Directory change on Devpost" in item.reason

    # The same move seen again in a later run is not flagged twice.
    again = await flag_directory_changes(
        session,  # type: ignore[arg-type]
        source_key="devpost",
        source=_source(),
        batch=SourceBatch(seen_known=[moved]),
        listings=listings,
    )
    assert again == 0 and len(session.added) == 1


async def test_non_hosting_sources_never_flag_changes() -> None:
    session = _MemorySession()
    moved = _hit("mlh", "https://agents.example.com/", ends="2026-12-04T00:00:00Z")
    flagged = await flag_directory_changes(
        session,  # type: ignore[arg-type]
        source_key="mlh",
        source=_source(),
        batch=SourceBatch(seen_known=[moved]),
        listings={runner._canonical_key(moved.url): _known()},
    )
    assert flagged == 0 and session.added == []
