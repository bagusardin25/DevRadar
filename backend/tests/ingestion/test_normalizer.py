"""Normalizer unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.catalog.enums import ListingKind, OfferType
from app.ingestion.extractor import ExtractionResult, Extractor
from app.ingestion.normalizer import (
    normalize_countries,
    normalize_currency,
    normalize_extraction,
    normalize_mode,
    normalize_offer_type,
    normalize_url,
)
from app.ingestion.parser import parse_document

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "documents"


class TestNormalizeHelpers:
    def test_currency(self) -> None:
        assert normalize_currency("usd") == "USD"
        assert normalize_currency("$") == "USD"
        assert normalize_currency("eur") == "EUR"

    def test_countries(self) -> None:
        assert normalize_countries(["United States", "worldwide", "Indonesia"]) == [
            "US",
            "Worldwide",
            "ID",
        ]

    def test_mode(self) -> None:
        assert normalize_mode("virtual").value == "online"  # type: ignore[union-attr]
        assert normalize_mode("in-person").value == "in_person"  # type: ignore[union-attr]

    def test_offer_type(self) -> None:
        assert normalize_offer_type("free credits") == OfferType.FREE_CREDITS
        assert normalize_offer_type("free_tier") == OfferType.FREE_TIER

    def test_url_canonical(self) -> None:
        assert normalize_url("HTTPS://Example.COM/Path/?b=1&a=2#x") == (
            "https://example.com/Path/?a=2&b=1"
        )


class TestNormalizeExtraction:
    @pytest.mark.asyncio
    async def test_hackathon_utc_and_fields(self) -> None:
        raw = (FIXTURES / "hackathon_sample.html").read_bytes()
        parsed = parse_document(
            raw, url="https://example.com/hack", content_type="text/html"
        )
        result = await Extractor().extract(parsed, ListingKind.HACKATHON)
        candidate = normalize_extraction(result)
        assert candidate.kind == ListingKind.HACKATHON
        assert candidate.title
        sub = candidate.fields.get("submission_deadline")
        assert isinstance(sub, datetime)
        assert sub.tzinfo is not None
        assert candidate.fields.get("prize_currency") == "USD"
        assert candidate.canonical_url.startswith("https://")

    def test_conflicting_dates_swapped(self) -> None:
        result = ExtractionResult(
            schema_version="1.0.0",
            extractor_version="1.0.0",
            listing_kind=ListingKind.HACKATHON,
            fields={
                "title": "Weekend Code Jam",
                "organizer": "DevClub",
                "mode": "hybrid",
                "registration_deadline": datetime(2026, 11, 30, tzinfo=UTC),
                "submission_deadline": datetime(2026, 11, 1, tzinfo=UTC),
                "official_url": "https://devclub.example/jam",
                "team_min": 2,
                "team_max": 5,
            },
            method="rules",
        )
        candidate = normalize_extraction(result)
        reg = candidate.fields["registration_deadline"]
        sub = candidate.fields["submission_deadline"]
        assert reg <= sub
        assert "conflicting_dates_registration_after_submission" in candidate.warnings

    @pytest.mark.asyncio
    async def test_permanent_free_tier_null_expiry(self) -> None:
        raw = (FIXTURES / "free_tier_permanent.txt").read_bytes()
        parsed = parse_document(
            raw, url="https://acmeai.example/pricing", content_type="text/plain"
        )
        result = await Extractor().extract(parsed, ListingKind.AI_OFFER)
        candidate = normalize_extraction(result)
        assert candidate.fields.get("offer_type") == OfferType.FREE_TIER.value
        assert candidate.fields.get("expires_at") is None

    def test_naive_datetime_to_utc(self) -> None:
        result = ExtractionResult(
            schema_version="1.0.0",
            extractor_version="1.0.0",
            listing_kind=ListingKind.HACKATHON,
            fields={
                "title": "X",
                "organizer": "Org",
                "mode": "online",
                "submission_deadline": datetime(2026, 8, 1, 12, 0, 0),
                "official_url": "https://example.com/x",
                "prize_value": Decimal("100"),
                "prize_currency": "usd",
                "team_min": 1,
                "team_max": 1,
            },
            method="rules",
        )
        candidate = normalize_extraction(result)
        sub = candidate.fields["submission_deadline"]
        assert sub.tzinfo == UTC

    @pytest.mark.asyncio
    async def test_deterministic_twice(self) -> None:
        raw = (FIXTURES / "hackathon_sample.html").read_bytes()
        parsed = parse_document(
            raw, url="https://example.com/hack", content_type="text/html"
        )
        result = await Extractor().extract(parsed, ListingKind.HACKATHON)
        a = normalize_extraction(result)
        b = normalize_extraction(result)
        assert a.title == b.title
        assert a.fields == b.fields
        assert a.warnings == b.warnings
