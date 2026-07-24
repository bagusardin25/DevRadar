"""Scoring pure-function tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.ingestion.scoring import ScoringInput, score_verification


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
        assert b.status_and_deadline <= 35
        assert b.keyword_match <= 25
        assert b.source_credibility <= 20
        assert b.freshness <= 15
        assert b.completeness <= 5

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
