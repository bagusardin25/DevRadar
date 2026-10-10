"""Public score breakdowns must accept everything the scorer can produce.

Seeded listings scored completeness=10 against a stale le=5 bound, so every
catalogue list call returned 500 in production.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.catalog.service import _score_breakdown
from app.ingestion.scoring import (
    MAX_COMPLETENESS,
    MAX_FRESHNESS,
    MAX_KEYWORD,
    MAX_SOURCE,
    MAX_STATUS_DEADLINE,
    ScoringInput,
    score_verification,
)


def test_breakdown_at_scorer_maxima_serializes() -> None:
    raw = {
        "statusAndDeadline": MAX_STATUS_DEADLINE,
        "keywordMatch": MAX_KEYWORD,
        "sourceCredibility": MAX_SOURCE,
        "freshness": MAX_FRESHNESS,
        "completeness": MAX_COMPLETENESS,
    }

    public = _score_breakdown(raw)

    assert public.model_dump(by_alias=True) == raw


def test_fully_evidenced_score_round_trips_through_public_schema() -> None:
    now = datetime.now(UTC)
    scored = score_verification(
        ScoringInput(
            has_valid_dates=True,
            deadline_in_future=True,
            dates_ordered=True,
            keyword_hits=5,
            source_tier="tier_1",
            cross_source_count=5,
            last_checked_at=now,
            now=now,
            required_fields_present=8,
            required_fields_total=8,
            link_ok=True,
        )
    )

    public = _score_breakdown(scored.as_dict())

    assert public.model_dump(by_alias=True) == scored.as_dict()
    assert public.completeness == MAX_COMPLETENESS
