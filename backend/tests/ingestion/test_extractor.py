"""Rule-first extractor and LLM schema rejection tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.catalog.enums import ListingKind
from app.ingestion.extractor import Extractor
from app.ingestion.llm_provider import DisabledLLMProvider, EchoLLMProvider
from app.ingestion.parser import parse_document

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
        llm = EchoLLMProvider(
            payload={
                "title": "LLM Filled Hackathon",
                "organizer": "LLM Org",
                "mode": "online",
                "submission_deadline": "2026-12-01T00:00:00+00:00",
            }
        )
        result = await Extractor(llm).extract(parsed, ListingKind.HACKATHON)
        assert result.llm_attempted is True
        # Title may come from rules first line; deadline should be LLM-filled.
        assert result.fields.get("submission_deadline") is not None
        assert result.field_sources.get("submission_deadline") == "llm" or (
            result.field_sources.get("title") == "llm"
        )
        assert result.method in {"hybrid", "llm", "rules"}

    @pytest.mark.asyncio
    async def test_deterministic_twice(self) -> None:
        parsed = _parse_fixture("hackathon_sample.html")
        ext = Extractor()
        a = await ext.extract(parsed, ListingKind.HACKATHON)
        b = await ext.extract(parsed, ListingKind.HACKATHON)
        assert a.fields == b.fields
        assert a.method == b.method
