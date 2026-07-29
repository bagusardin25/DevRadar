"""Scoring pure-function tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.ingestion.scoring import (
    MAX_COMPLETENESS,
    MAX_FRESHNESS,
    MAX_KEYWORD,
    MAX_SOURCE,
    MAX_STATUS_DEADLINE,
    ScoringInput,
    score_verification,
)


def _inp(**kwargs: object) -> ScoringInput:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    base = dict(
        has_valid_dates=True,
        deadline_in_future=True,
        dates_ordered=True,
        keyword_hits=3,
        source_tier="tier_1",
        cross_source_count=1,
        last_checked_at=now,
        now=now,
        required_fields_present=5,
        required_fields_total=5,
        link_ok=True,
    )
    base.update(kwargs)
    return ScoringInput(**base)  # type: ignore[arg-type]


class TestScoring:
    def test_components_sum_to_total(self) -> None:
        b = score_verification(_inp())
        assert b.total == (
            b.status_and_deadline
            + b.keyword_match
            + b.source_credibility
            + b.freshness
            + b.completeness
        )
        assert 0 <= b.total <= 100
        # Assert against the constants, not copies of them: hardcoding the
        # maxima here is what let this test lock in the old weighting.
        assert b.status_and_deadline <= MAX_STATUS_DEADLINE
        assert b.keyword_match <= MAX_KEYWORD
        assert b.source_credibility <= MAX_SOURCE
        assert b.freshness <= MAX_FRESHNESS
        assert b.completeness <= MAX_COMPLETENESS

    def test_maxima_sum_to_100(self) -> None:
        assert (
            MAX_STATUS_DEADLINE
            + MAX_KEYWORD
            + MAX_SOURCE
            + MAX_FRESHNESS
            + MAX_COMPLETENESS
        ) == 100

    def test_boundaries_min(self) -> None:
        b = score_verification(
            _inp(
                has_valid_dates=False,
                deadline_in_future=False,
                dates_ordered=False,
                keyword_hits=0,
                source_tier="tier_3",
                cross_source_count=0,
                last_checked_at=None,
                required_fields_present=0,
                link_ok=False,
            )
        )
        assert b.total == 0 or b.total >= 0
        assert b.total <= 20  # tier3 alone may give small source pts

    def test_high_score_tier1(self) -> None:
        b = score_verification(_inp(keyword_hits=5, cross_source_count=2))
        assert b.total >= 70
        assert b.confidence == round(b.total / 100, 3)

    def test_deterministic(self) -> None:
        a = score_verification(_inp())
        b = score_verification(_inp())
        assert a == b

    def test_freshness_decay(self) -> None:
        now = datetime(2026, 7, 1, tzinfo=UTC)
        fresh = score_verification(_inp(now=now, last_checked_at=now))
        stale = score_verification(
            _inp(now=now, last_checked_at=now - timedelta(days=40))
        )
        assert fresh.freshness > stale.freshness

    def test_unknown_freshness_scores_zero(self) -> None:
        """Unknown observation time must not be paid out as freshly checked."""
        assert score_verification(_inp(last_checked_at=None)).freshness == 0

    def test_lone_source_earns_no_corroboration(self) -> None:
        """A single source agrees with nothing, so it gets the tier points only."""
        alone = score_verification(_inp(cross_source_count=1))
        corroborated = score_verification(_inp(cross_source_count=2))
        assert alone.source_credibility < corroborated.source_credibility
        # Zero and one source are equivalent: neither has a second opinion.
        assert (
            score_verification(_inp(cross_source_count=0)).source_credibility
            == alone.source_credibility
        )

    def test_corroboration_caps(self) -> None:
        many = score_verification(_inp(cross_source_count=50))
        assert many.source_credibility <= MAX_SOURCE
