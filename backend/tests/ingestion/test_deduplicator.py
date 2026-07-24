"""Deduplicator staged matching tests."""

from __future__ import annotations

from uuid import uuid4

from app.catalog.enums import ListingKind
from app.ingestion.deduplicator import ExistingCandidate, find_duplicate
from app.ingestion.normalizer import CandidateListing


def _candidate(
    *,
    title: str,
    url: str,
    kind: ListingKind = ListingKind.HACKATHON,
    org: str = "Org",
) -> CandidateListing:
    fields = (
        {"organizer": org}
        if kind == ListingKind.HACKATHON
        else {"provider": org, "product_name": title}
    )
    return CandidateListing(
        kind=kind,
        title=title,
        description="",
        official_url=url,
        canonical_url=url,
        fields=fields,
    )


def _existing(
    *,
    title: str,
    url: str,
    org: str = "Org",
    kind: ListingKind = ListingKind.HACKATHON,
) -> ExistingCandidate:
    return ExistingCandidate(
        id=uuid4(),
        kind=kind,
        title=title,
        canonical_url=url,
        organizer_or_provider=org,
    )


class TestDeduplicator:
    def test_exact_url(self) -> None:
        url = "https://example.com/event/abc"
        existing = _existing(title="Other Title", url=url)
        cand = _candidate(title="New Title", url=url)
        decision = find_duplicate(cand, [existing])
        assert decision.is_duplicate is True
        assert decision.match_type == "exact_url"
        assert decision.auto_merge is True
        assert decision.existing_id == existing.id

    def test_title_organizer_similarity(self) -> None:
        existing = _existing(
            title="Global AI Agents Challenge 2026",
            url="https://a.example/1",
            org="Anthropic",
        )
        cand = _candidate(
            title="Global AI Agents Challenge 2026",
            url="https://b.example/2",
            org="Anthropic Labs",
        )
        decision = find_duplicate(cand, [existing])
        assert decision.is_duplicate is True
        assert decision.match_type == "title_organizer"
        assert decision.auto_merge is True

    def test_no_match(self) -> None:
        existing = _existing(
            title="Blockchain Summit",
            url="https://a.example/1",
            org="CryptoCo",
        )
        cand = _candidate(
            title="Pottery Workshop",
            url="https://b.example/2",
            org="ArtHouse",
        )
        decision = find_duplicate(cand, [existing])
        assert decision.is_duplicate is False
        assert decision.match_type == "none"
        assert decision.auto_merge is False

    def test_llm_suggestion_never_auto_merge(self) -> None:
        suggested = uuid4()
        cand = _candidate(title="Unique Event XYZ", url="https://c.example/3")
        decision = find_duplicate(cand, [], llm_suggested_id=suggested)
        assert decision.is_duplicate is True
        assert decision.match_type == "llm_suggestion"
        assert decision.auto_merge is False
        assert decision.llm_suggested_id == suggested
        assert decision.existing_id == suggested

    def test_kind_mismatch_ignored(self) -> None:
        existing = _existing(
            title="Same Title",
            url="https://a.example/1",
            org="Org",
            kind=ListingKind.AI_OFFER,
        )
        cand = _candidate(title="Same Title", url="https://b.example/2", org="Org")
        decision = find_duplicate(cand, [existing])
        assert decision.is_duplicate is False

    def test_deterministic_twice(self) -> None:
        existing = _existing(
            title="Weekend Code Jam",
            url="https://a.example/1",
            org="DevClub",
        )
        cand = _candidate(
            title="Weekend Code Jam",
            url="https://b.example/2",
            org="DevClub",
        )
        a = find_duplicate(cand, [existing])
        b = find_duplicate(cand, [existing])
        assert a == b
