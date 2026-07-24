"""Pipeline orchestration + idempotency tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import ListingKind, VerificationStatus
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.ingestion.normalizer import CandidateListing
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.verifier import VerificationEvidence

NOW = datetime(2026, 7, 15, tzinfo=UTC)


@pytest.fixture
async def session() -> AsyncSession:
    settings = Settings()
    engine = create_engine(settings)
    maker = create_session_maker(engine)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


def _candidate() -> CandidateListing:
    return CandidateListing(
        kind=ListingKind.HACKATHON,
        title=f"Pipeline Hack {uuid4().hex[:6]}",
        description="A solid online hackathon",
        official_url="https://example.com/pipeline-hack",
        canonical_url="https://example.com/pipeline-hack",
        fields={
            "title": "Pipeline Hack",
            "organizer": "PipeOrg",
            "mode": "online",
            "official_url": "https://example.com/pipeline-hack",
            "registration_deadline": NOW + timedelta(days=5),
            "submission_deadline": NOW + timedelta(days=20),
            "technologies": ["Python", "AI"],
            "prize_value": 25000,
            "prize_currency": "USD",
            "team_min": 1,
            "team_max": 4,
            "eligible_countries": ["Worldwide"],
            "eligibility": ["Developer"],
        },
    )


class TestPipeline:
    @pytest.mark.asyncio
    async def test_publish_creates_listing(self, session: AsyncSession) -> None:
        pipe = IngestionPipeline(session)
        key = f"job-{uuid4().hex}"
        out = await pipe.process_candidate(
            _candidate(),
            VerificationEvidence(source_tier="tier_1", link_ok=True, cross_source_count=2),
            idempotency_key=key,
            now=NOW,
        )
        assert out.idempotent_replay is False
        assert out.listing_id is not None
        assert out.status in {
            VerificationStatus.VERIFIED_ACTIVE,
            VerificationStatus.LIKELY_ACTIVE,
        }
        assert out.created_listing is True

    @pytest.mark.asyncio
    async def test_tier3_creates_review(self, session: AsyncSession) -> None:
        pipe = IngestionPipeline(session)
        out = await pipe.process_candidate(
            _candidate(),
            VerificationEvidence(source_tier="tier_3", only_tier3=True, link_ok=True),
            idempotency_key=f"t3-{uuid4().hex}",
            now=NOW,
        )
        assert out.status == VerificationStatus.NEEDS_REVIEW
        assert out.created_review is True
        assert out.review_item_id is not None

    @pytest.mark.asyncio
    async def test_idempotent_replay(self, session: AsyncSession) -> None:
        pipe = IngestionPipeline(session)
        key = f"idem-{uuid4().hex}"
        cand = _candidate()
        evidence = VerificationEvidence(source_tier="tier_1", link_ok=True, cross_source_count=2)
        first = await pipe.process_candidate(cand, evidence, idempotency_key=key, now=NOW)
        await session.flush()
        second = await pipe.process_candidate(cand, evidence, idempotency_key=key, now=NOW)
        assert second.idempotent_replay is True
        assert (
            first.listing_id == second.listing_id
            or first.review_item_id == second.review_item_id
        )
