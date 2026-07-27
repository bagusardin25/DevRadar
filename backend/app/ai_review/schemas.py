"""Value objects for the AI initial review."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.llm_usage import LLMCallUsage

AI_REVIEW_VERSION = "1.0.0"


class ReviewRecommendation(StrEnum):
    """What the AI suggests the admin do — never auto-applied."""

    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_MORE_INFO = "needs_more_info"


class ReviewConcernSeverity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


#: Sort order so the admin sees the most serious concern first.
_SEVERITY_RANK = {
    ReviewConcernSeverity.HIGH: 0,
    ReviewConcernSeverity.MEDIUM: 1,
    ReviewConcernSeverity.LOW: 2,
}


@dataclass(slots=True)
class ReviewConcern:
    severity: ReviewConcernSeverity
    message: str

    def to_snapshot(self) -> dict[str, str]:
        return {"severity": self.severity.value, "message": self.message}


@dataclass(slots=True)
class AIReview:
    """Structured pre-review attached to a review item's snapshot."""

    recommendation: ReviewRecommendation
    confidence: int  # 0–100, higher = more confident in the recommendation
    summary: str
    concerns: list[ReviewConcern] = field(default_factory=list)
    suggested_fields: dict[str, Any] = field(default_factory=dict)
    engine: str = "heuristic"  # "heuristic" | "openai:<model>"
    model: str | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: str = AI_REVIEW_VERSION
    llm_usage: LLMCallUsage | None = None

    def sorted_concerns(self) -> list[ReviewConcern]:
        return sorted(self.concerns, key=lambda c: _SEVERITY_RANK[c.severity])

    def to_snapshot(self) -> dict[str, Any]:
        """camelCase payload embedded in ReviewItem.candidate_snapshot['aiReview']."""
        return {
            "recommendation": self.recommendation.value,
            "confidence": int(max(0, min(100, self.confidence))),
            "summary": self.summary,
            "concerns": [c.to_snapshot() for c in self.sorted_concerns()],
            "suggestedFields": self.suggested_fields,
            "engine": self.engine,
            "model": self.model,
            "generatedAt": self.generated_at.astimezone(UTC).isoformat(),
            "version": self.version,
        }
