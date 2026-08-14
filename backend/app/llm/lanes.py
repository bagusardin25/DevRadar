"""Who may spend LLM quota, and how expensive that spend is allowed to be.

The router already splits work by *operation* (``extraction`` vs ``review``).
That is not enough: live discovery can fire ten extractions for one user click
and starve the low-volume, high-value path (community submit + admin review).

A *lane* is the caller. Defaults keep the expensive lane (discovery) on
rules-only, let background jobs call the model only when rules missed a
critical field, and keep full gap-fill for user submissions.
"""

from __future__ import annotations

from enum import StrEnum


class LLMLane(StrEnum):
    """Call site that may or may not be allowed to spend an LLM call."""

    SUBMISSION = "submission"
    DISCOVERY = "discovery"
    RECHECK = "recheck"
    CRAWL = "crawl"


class ExtractMode(StrEnum):
    """How aggressively the extractor may call the model."""

    OFF = "off"  # rules only; never spend a call
    CRITICAL = "critical"  # only when title/deadline (or offer title) is missing
    GAPS = "gaps"  # current behaviour: any useful empty field


# Default on/off per lane. Discovery is the quota killer (1 click → ≤20 calls).
DEFAULT_LANE_ENABLED: dict[LLMLane, bool] = {
    LLMLane.SUBMISSION: True,
    LLMLane.DISCOVERY: False,
    LLMLane.RECHECK: True,
    LLMLane.CRAWL: True,
}


def parse_lane(value: object, *, default: LLMLane = LLMLane.CRAWL) -> LLMLane:
    """Coerce a worker payload / env string to a lane; unknown → ``default``."""
    text = str(value or "").strip().lower()
    if not text:
        return default
    try:
        return LLMLane(text)
    except ValueError:
        return default


def extract_mode_for(lane: LLMLane, *, enabled: bool) -> ExtractMode:
    """Resolve extract intensity for one lane.

    Even when an operator flips discovery/recheck/crawl on, those lanes stay on
    ``critical`` so a well-parsed page never burns a token. Only a community
    submission (one URL, one human waiting) gets full gap-fill.
    """
    if not enabled:
        return ExtractMode.OFF
    if lane is LLMLane.SUBMISSION:
        return ExtractMode.GAPS
    return ExtractMode.CRITICAL
