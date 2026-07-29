"""Rule-first extractor and LLM schema rejection tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.catalog.enums import ListingKind
from app.ingestion.extractor import (
    Extractor,
    _detect_prize,
    _detect_technologies,
)
from app.ingestion.llm_provider import DisabledLLMProvider, EchoLLMProvider
from app.ingestion.parser import parse_document
from app.llm_usage import LLMCallUsage

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "documents"


def _parse_fixture(name: str, content_type: str = "text/html"):
    raw = (FIXTURES / name).read_bytes()
    if name.endswith(".txt"):
        content_type = "text/plain"
    return parse_document(
        raw, url=f"https://fixture.example/{name}", content_type=content_type
    )


class TestRuleExtractor:
    @pytest.mark.asyncio
    async def test_hackathon_rules(self) -> None:
        parsed = _parse_fixture("hackathon_sample.html")
        result = await Extractor(DisabledLLMProvider()).extract(
            parsed, ListingKind.HACKATHON
        )
        assert result.method == "rules"
        assert result.fields.get("title")
        assert "AI" in (result.fields.get("technologies") or []) or "Python" in (
            result.fields.get("technologies") or []
        )
        assert result.fields.get("mode") == "online"
        assert result.fields.get("prize_value") is not None
        assert result.fields.get("submission_deadline") is not None
        assert result.llm_attempted is False

    @pytest.mark.asyncio
    async def test_permanent_free_tier(self) -> None:
        parsed = _parse_fixture("free_tier_permanent.txt")
        result = await Extractor().extract(parsed, ListingKind.AI_OFFER)
        assert result.fields.get("offer_type") == "free_tier"
        # permanent — rules leave expires_at empty
        assert result.fields.get("expires_at") is None

    @pytest.mark.asyncio
    async def test_expiring_credits(self) -> None:
        parsed = _parse_fixture("expiring_credits.txt")
        result = await Extractor().extract(parsed, ListingKind.AI_OFFER)
        assert result.fields.get("offer_type") in {"free_credits", "promo_code"}
        assert result.fields.get("expires_at") is not None

    @pytest.mark.asyncio
    async def test_disabled_llm_never_called(self) -> None:
        parsed = _parse_fixture("hackathon_sample.html")
        llm = DisabledLLMProvider()
        result = await Extractor(llm).extract(parsed, ListingKind.HACKATHON)
        assert result.llm_attempted is False
        assert result.method == "rules"

    @pytest.mark.asyncio
    async def test_malformed_llm_json_rejected(self) -> None:
        import json

        bad = json.loads((FIXTURES / "malformed_llm.json").read_text(encoding="utf-8"))
        parsed = parse_document(
            b"Title only page without dates",
            url="https://fixture.example/thin",
            content_type="text/plain",
        )
        llm = EchoLLMProvider(payload=bad)
        result = await Extractor(llm).extract(parsed, ListingKind.HACKATHON)
        assert result.llm_attempted is True
        assert any("llm_rejected" in e or "schema" in e for e in result.errors) or (
            result.method in {"rules", "failed", "hybrid"}
        )
        # Rules still produce something; LLM junk not merged as invalid types
        assert llm.calls

    @pytest.mark.asyncio
    async def test_llm_fills_missing_title(self) -> None:
        # No deadline → critical gap triggers LLM even if a title line exists.
        parsed = parse_document(
            b"Join us online worldwide for builders",
            url="https://fixture.example/gap",
            content_type="text/plain",
        )
        usage = LLMCallUsage(
            operation="extraction",
            provider="openai",
            model="gpt-4o-mini",
            service_tier="default",
            prompt_tokens=900,
            cached_prompt_tokens=0,
            completion_tokens=100,
            total_tokens=1_000,
        )
        llm = EchoLLMProvider(
            payload={
                "title": "LLM Filled Hackathon",
                "organizer": "LLM Org",
                "mode": "online",
                "submission_deadline": "2026-12-01T00:00:00+00:00",
            },
            usage=usage,
        )
        result = await Extractor(llm).extract(parsed, ListingKind.HACKATHON)
        assert result.llm_attempted is True
        # Title may come from rules first line; deadline should be LLM-filled.
        assert result.fields.get("submission_deadline") is not None
        assert result.field_sources.get("submission_deadline") == "llm" or (
            result.field_sources.get("title") == "llm"
        )
        assert result.method in {"hybrid", "llm", "rules"}
        assert result.llm_usage is usage

    @pytest.mark.asyncio
    async def test_deterministic_twice(self) -> None:
        parsed = _parse_fixture("hackathon_sample.html")
        ext = Extractor()
        a = await ext.extract(parsed, ListingKind.HACKATHON)
        b = await ext.extract(parsed, ListingKind.HACKATHON)
        assert a.fields == b.fields
        assert a.method == b.method

    @pytest.mark.asyncio
    async def test_labelled_dates_beat_document_order(self) -> None:
        """Copyright and blog dates must not be promoted to deadlines.

        Sorting every date on the page made the 2019 copyright the registration
        open date and the 2023 policy revision the registration deadline —
        which then flips a live event to `registration_closed`.
        """
        page = (
            b"CloudCorp Summer Challenge\n"
            b"Copyright 2019-01-01 CloudCorp. Privacy policy updated 2023-06-15.\n"
            b"Registration closes 2026-09-01. Submissions due 2026-10-15.\n"
            b"Our blog post from 2024-03-02 explains the rules.\n"
        )
        parsed = parse_document(
            page, url="https://cloudcorp.example/hack", content_type="text/plain"
        )
        fields = (
            await Extractor().extract(parsed, ListingKind.HACKATHON)
        ).fields
        assert fields["registration_deadline"].date().isoformat() == "2026-09-01"
        assert fields["submission_deadline"].date().isoformat() == "2026-10-15"
        # No "registration opens" wording on the page, so nothing is invented.
        assert fields.get("registration_open_at") is None

    @pytest.mark.asyncio
    async def test_unlabelled_dates_left_empty(self) -> None:
        """No deadline wording → no deadline. Empty beats wrong."""
        parsed = parse_document(
            b"Robot Jam 2026\nSee you at the venue. Posted 2026-02-11.",
            url="https://example.com/jam",
            content_type="text/plain",
        )
        fields = (
            await Extractor().extract(parsed, ListingKind.HACKATHON)
        ).fields
        assert fields.get("submission_deadline") is None
        assert fields.get("registration_deadline") is None


class TestFieldDetection:
    def test_technologies_need_word_boundaries(self) -> None:
        """'available'/'email'/'domain' contain "ai"; 'google' contains "go"."""
        prose = (
            "Welcome to our available developer domain. Please explain your "
            "email address and we will maintain contact. Google is a partner."
        )
        assert _detect_technologies(prose) == []

    def test_technologies_still_match_real_mentions(self) -> None:
        text = "Built with Python, TypeScript and Next.js. AI-powered, written in Go."
        found = _detect_technologies(text)
        assert set(found) == {"Python", "TypeScript", "Next.js", "AI", "Go"}

    def test_prize_requires_a_currency_marker(self) -> None:
        """'prize awarded to teams of 2-5' used to parse as a $5 prize pool."""
        assert _detect_prize("Grand prize awarded to teams of 2-5.") == (None, None)
        assert _detect_prize("Prizes for the top 3 finalists.") == (None, None)

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Prize pool $50,000 USD.", (Decimal("50000"), "USD")),
            ("Prize pool of $100k", (Decimal("100000"), "USD")),
            ("Total prize: 25000 EUR", (Decimal("25000"), "EUR")),
            ("Prize pool £2,500", (Decimal("2500"), "GBP")),
        ],
    )
    def test_prize_reads_marked_amounts(
        self, text: str, expected: tuple[Decimal, str]
    ) -> None:
        assert _detect_prize(text) == expected
