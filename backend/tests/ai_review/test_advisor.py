"""ReviewAdvisor: LLM enrichment with deterministic guardrails."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.ai_review.advisor import ReviewAdvisor
from app.ai_review.llm import EchoReviewLLM
from app.ai_review.schemas import ReviewRecommendation
from app.catalog.enums import ListingKind, VerificationStatus
from app.ingestion.normalizer import CandidateListing
from app.ingestion.verifier import VerificationEvidence, verify
from app.llm_usage import LLMCallUsage

NOW = datetime(2026, 7, 27, tzinfo=UTC)


def _candidate(fields: dict) -> CandidateListing:
    return CandidateListing(
        kind=ListingKind.HACKATHON,
        title=fields["title"],
        description="",
        official_url=fields["official_url"],
        canonical_url=fields["official_url"],
        fields=dict(fields),
    )


def _needs_review():
    fields = {
        "title": "Ambiguous Hack",
        "organizer": "Org",
        "mode": "online",
        "official_url": "https://example.com/hack",
        "registration_deadline": NOW + timedelta(days=3),
        "submission_deadline": NOW + timedelta(days=20),
        "technologies": ["Python"],
    }
    candidate = _candidate(fields)
    result = verify(
        candidate,
        VerificationEvidence(
            source_tier="tier_3", only_tier3=True, link_ok=True, last_checked_at=NOW
        ),
        now=NOW,
    )
    assert result.status is VerificationStatus.NEEDS_REVIEW
    return candidate, result


def _expired():
    fields = {
        "title": "Old Hack",
        "organizer": "Org",
        "mode": "online",
        "official_url": "https://example.com/old",
        "submission_deadline": NOW - timedelta(days=10),
    }
    candidate = _candidate(fields)
    result = verify(
        candidate,
        VerificationEvidence(source_tier="tier_2", link_ok=True, last_checked_at=NOW),
        now=NOW,
    )
    assert result.status is VerificationStatus.EXPIRED
    return candidate, result


@pytest.mark.asyncio
async def test_llm_enriches_non_terminal_review() -> None:
    candidate, result = _needs_review()
    usage = LLMCallUsage(
        operation="review",
        provider="openai",
        model="gpt-4o-mini",
        service_tier="default",
        prompt_tokens=800,
        cached_prompt_tokens=0,
        completion_tokens=200,
        total_tokens=1_000,
    )
    echo = EchoReviewLLM(
        {
            "recommendation": "reject",
            "confidence": 33,
            "summary": "Model flagged the page.",
            "concerns": [{"severity": "high", "message": "Looks like a phishing clone."}],
            "suggested_fields": {"title": "Corrected Title"},
        },
        usage=usage,
    )
    advisor = ReviewAdvisor(echo, engine_label="openai:test", model="test")
    review = await advisor.review(candidate, result)

    assert echo.calls, "LLM should be consulted for a non-terminal review"
    assert review.recommendation is ReviewRecommendation.REJECT
    assert review.confidence == 33
    assert review.summary == "Model flagged the page."
    assert review.engine == "openai:test"
    assert any("phishing" in c.message for c in review.concerns)
    # Grounded heuristic concerns are preserved alongside the LLM's.
    assert any("official" in c.message.lower() for c in review.concerns)
    assert review.suggested_fields["title"] == "Corrected Title"
    assert review.llm_usage is usage


@pytest.mark.asyncio
async def test_guardrail_keeps_terminal_reject() -> None:
    candidate, result = _expired()
    echo = EchoReviewLLM({"recommendation": "approve", "confidence": 95, "summary": "Looks fine!"})
    advisor = ReviewAdvisor(echo, engine_label="openai:test", model="test")
    review = await advisor.review(candidate, result)
    # An expired/cancelled REJECT is fact-driven and must not be softened.
    assert review.recommendation is ReviewRecommendation.REJECT


@pytest.mark.asyncio
async def test_llm_error_falls_back_to_heuristic() -> None:
    candidate, result = _needs_review()
    advisor = ReviewAdvisor(EchoReviewLLM(error=RuntimeError("boom")), engine_label="openai:test")
    review = await advisor.review(candidate, result)
    assert review.engine == "heuristic"


@pytest.mark.asyncio
async def test_disabled_llm_is_pure_heuristic() -> None:
    candidate, result = _needs_review()
    advisor = ReviewAdvisor()  # DisabledReviewLLM
    review = await advisor.review(candidate, result)
    assert review.engine == "heuristic"
    assert review.recommendation is ReviewRecommendation.NEEDS_MORE_INFO
