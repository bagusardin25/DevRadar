"""AI initial review — a CodeRabbit-style pre-review for the admin queue.

Given a normalized candidate and the deterministic verification result, produce
a human-readable assessment (recommendation + concerns + suggested fields) that
an admin reads before approving or rejecting. The heuristic reviewer always
runs; when an LLM provider is configured it enriches the narrative. The admin
remains the final decision-maker (human-in-the-loop).
"""

from __future__ import annotations

from app.ai_review.advisor import ReviewAdvisor, build_review_advisor
from app.ai_review.schemas import (
    AI_REVIEW_VERSION,
    AIReview,
    ReviewConcern,
    ReviewConcernSeverity,
    ReviewRecommendation,
)

__all__ = [
    "AI_REVIEW_VERSION",
    "AIReview",
    "ReviewAdvisor",
    "ReviewConcern",
    "ReviewConcernSeverity",
    "ReviewRecommendation",
    "build_review_advisor",
]
