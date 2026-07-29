"""Deterministic verification confidence scoring (points out of 100)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

SCORING_VERSION = "2.0.0"

# Component maxima (must sum to 100).
#
# v2 rebalance: freshness used to be worth 15 points but every production caller
# scores a document it *just* fetched, so it always paid out full marks — 15
# points of pure constant inflating every total. Corroboration had the same
# problem: `cross_source_count` is 1 at both call sites, so the old
# `count * 3` formula handed out a flat +3 to everything.
#
# Freshness is now a small tie-breaker, corroboration only pays when a second
# source actually agrees, and the points freed up went to signals that vary:
# source tier and field completeness.
MAX_STATUS_DEADLINE = 35
MAX_KEYWORD = 25
MAX_SOURCE = 25
MAX_FRESHNESS = 5
MAX_COMPLETENESS = 10

# Source credibility splits into tier (what kind of source) + corroboration
# (how many independent sources agree). They sum to MAX_SOURCE.
MAX_SOURCE_TIER = 15
MAX_CORROBORATION = 10
_TIER_POINTS = {"tier_1": 15, "tier_2": 10, "tier_3": 4}
#: Points per corroborating source *beyond the first*. A lone source proves
#: nothing about agreement, so it earns zero here.
_CORROBORATION_PER_SOURCE = 5


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    status_and_deadline: int
    keyword_match: int
    source_credibility: int
    freshness: int
    completeness: int
    version: str = SCORING_VERSION

    @property
    def total(self) -> int:
        return (
            self.status_and_deadline
            + self.keyword_match
            + self.source_credibility
            + self.freshness
            + self.completeness
        )

    @property
    def confidence(self) -> float:
        return round(self.total / 100.0, 3)

    def as_dict(self) -> dict[str, int]:
        return {
            "statusAndDeadline": self.status_and_deadline,
            "keywordMatch": self.keyword_match,
            "sourceCredibility": self.source_credibility,
            "freshness": self.freshness,
            "completeness": self.completeness,
        }


@dataclass(slots=True)
class ScoringInput:
    """Evidence bundle for scoring (pure data)."""

    has_valid_dates: bool
    deadline_in_future: bool
    dates_ordered: bool
    keyword_hits: int  # 0–5 scale of category fit signals
    source_tier: str  # tier_1 | tier_2 | tier_3
    #: Total independent sources backing this candidate, *including* the one it
    #: came from. 1 = no corroboration and scores zero for it.
    cross_source_count: int
    #: When the evidence was observed (fetched), not when scoring ran.
    #: None = unknown, which scores zero rather than full marks.
    last_checked_at: datetime | None
    now: datetime
    required_fields_present: int
    required_fields_total: int
    link_ok: bool


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def score_verification(inp: ScoringInput) -> ScoreBreakdown:
    """Pure function: same input → same breakdown. LLM confidence is not used."""
    # Status / deadline (0–35)
    status = 0
    if inp.has_valid_dates and inp.dates_ordered:
        status += 15
    if inp.deadline_in_future:
        status += 15
    if inp.link_ok:
        status += 5
    status = _clamp(status, 0, MAX_STATUS_DEADLINE)

    # Keyword / category (0–25)
    keyword = _clamp(inp.keyword_hits * 5, 0, MAX_KEYWORD)

    # Source credibility (0–25): tier + corroboration from *other* sources.
    tier_pts = _clamp(_TIER_POINTS.get(inp.source_tier, 4), 0, MAX_SOURCE_TIER)
    corroborating = max(0, inp.cross_source_count - 1)
    cross = _clamp(corroborating * _CORROBORATION_PER_SOURCE, 0, MAX_CORROBORATION)
    source = _clamp(tier_pts + cross, 0, MAX_SOURCE)

    # Freshness (0–5). `last_checked_at` is when the evidence was *observed*,
    # not when the scorer ran. Unknown means unknown: it earns nothing rather
    # than being treated as brand new.
    freshness = 0
    if inp.last_checked_at is not None:
        age_hours = (inp.now - inp.last_checked_at).total_seconds() / 3600.0
        if age_hours <= 24:
            freshness = 5
        elif age_hours <= 24 * 7:
            freshness = 3
        elif age_hours <= 24 * 30:
            freshness = 1
        else:
            freshness = 0
    freshness = _clamp(freshness, 0, MAX_FRESHNESS)

    # Completeness (0–10)
    if inp.required_fields_total <= 0:
        completeness = 0
    else:
        ratio = inp.required_fields_present / inp.required_fields_total
        completeness = _clamp(int(round(ratio * MAX_COMPLETENESS)), 0, MAX_COMPLETENESS)

    breakdown = ScoreBreakdown(
        status_and_deadline=status,
        keyword_match=keyword,
        source_credibility=source,
        freshness=freshness,
        completeness=completeness,
    )
    assert breakdown.total == (
        breakdown.status_and_deadline
        + breakdown.keyword_match
        + breakdown.source_credibility
        + breakdown.freshness
        + breakdown.completeness
    )
    assert 0 <= breakdown.total <= 100
    return breakdown


def keyword_hits_from_fields(kind: str, fields: dict[str, Any]) -> int:
    hits = 0
    if kind == "hackathon":
        if fields.get("technologies"):
            hits += 1
        if fields.get("mode"):
            hits += 1
        if fields.get("prize_value"):
            hits += 1
        if fields.get("eligibility") or fields.get("eligible_countries"):
            hits += 1
        title = (fields.get("title") or "").lower()
        if any(w in title for w in ("hack", "challenge", "competition", "bounty")):
            hits += 1
    else:
        if fields.get("offer_type"):
            hits += 1
        if fields.get("provider"):
            hits += 1
        if fields.get("offer_value"):
            hits += 1
        if fields.get("tags"):
            hits += 1
        if fields.get("claim_url") or fields.get("official_terms_url"):
            hits += 1
    return _clamp(hits, 0, 5)
