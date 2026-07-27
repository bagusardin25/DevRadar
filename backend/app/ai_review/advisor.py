"""ReviewAdvisor — heuristic baseline enriched by an optional LLM narrative.

The heuristic review is the trustworthy floor: it is grounded in the
deterministic verifier. The LLM may improve the wording and add concerns, but
guardrails keep it from overriding hard facts (e.g. it can never turn an
expired/cancelled REJECT into an APPROVE).
"""

from __future__ import annotations

import logging
from typing import Any

from app.ai_review.heuristic import heuristic_review
from app.ai_review.llm import (
    DisabledReviewLLM,
    ReviewLLM,
    ReviewLLMRequest,
    build_review_llm,
)
from app.ai_review.schemas import (
    AIReview,
    ReviewConcern,
    ReviewConcernSeverity,
    ReviewRecommendation,
)
from app.config import Settings
from app.ingestion.normalizer import CandidateListing
from app.ingestion.verifier import VerificationResult
from app.llm_usage import LLMCallUsage

logger = logging.getLogger(__name__)

_MAX_SUMMARY = 800
_MAX_MESSAGE = 400
_MAX_CONCERNS = 12
_ACCEPTED_VALUE_TYPES = (str, int, float, bool, list, dict, type(None))


def _coerce_recommendation(raw: Any) -> ReviewRecommendation | None:
    if not isinstance(raw, str):
        return None
    try:
        return ReviewRecommendation(raw.strip().lower())
    except ValueError:
        return None


def _coerce_confidence(raw: Any) -> int | None:
    try:
        value = int(round(float(raw)))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, value))


def _coerce_concerns(raw: Any) -> list[ReviewConcern]:
    if not isinstance(raw, list):
        return []
    out: list[ReviewConcern] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        if not isinstance(message, str) or not message.strip():
            continue
        sev_raw = str(entry.get("severity", "low")).strip().lower()
        try:
            severity = ReviewConcernSeverity(sev_raw)
        except ValueError:
            severity = ReviewConcernSeverity.LOW
        out.append(ReviewConcern(severity=severity, message=message.strip()[:_MAX_MESSAGE]))
    return out


def _coerce_suggested(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, _ACCEPTED_VALUE_TYPES):
            continue
        out[key] = value[:_MAX_MESSAGE] if isinstance(value, str) else value
    return out


class ReviewAdvisor:
    def __init__(
        self,
        review_llm: ReviewLLM | None = None,
        *,
        engine_label: str = "heuristic",
        model: str | None = None,
    ) -> None:
        self._llm = review_llm or DisabledReviewLLM()
        self._engine_label = engine_label
        self._model = model

    async def review(
        self,
        candidate: CandidateListing,
        result: VerificationResult,
        *,
        page_excerpt: str = "",
    ) -> AIReview:
        base = heuristic_review(candidate, result)
        if isinstance(self._llm, DisabledReviewLLM):
            return base

        try:
            llm_response = await self._llm.review_json(
                ReviewLLMRequest(
                    listing_kind=candidate.kind.value,
                    title=candidate.title,
                    url=candidate.canonical_url or candidate.official_url,
                    extracted_fields=base.suggested_fields,
                    verification={
                        "status": result.status.value,
                        "score": result.score.total,
                        "reasons": list(result.reasons),
                    },
                    page_excerpt=page_excerpt,
                )
            )
        except Exception:
            logger.exception("ai_review_llm_failed")
            return base
        raw = llm_response.payload
        if not raw:
            return base
        return self._merge(base, raw, llm_response.usage)

    def _merge(
        self,
        base: AIReview,
        raw: dict[str, Any],
        usage: LLMCallUsage | None,
    ) -> AIReview:
        # Guardrail: a terminal REJECT (expired/cancelled) is fact-driven and
        # must not be softened by the model.
        recommendation = base.recommendation
        if recommendation is not ReviewRecommendation.REJECT:
            llm_rec = _coerce_recommendation(raw.get("recommendation"))
            if llm_rec is not None:
                recommendation = llm_rec

        confidence = _coerce_confidence(raw.get("confidence"))
        summary_raw = raw.get("summary")
        summary = (
            summary_raw.strip()[:_MAX_SUMMARY]
            if isinstance(summary_raw, str) and summary_raw.strip()
            else base.summary
        )

        # Grounded heuristic concerns stay; LLM concerns append (deduped).
        concerns = list(base.concerns)
        seen = {c.message.strip().lower() for c in concerns}
        for concern in _coerce_concerns(raw.get("concerns")):
            key = concern.message.strip().lower()
            if key not in seen:
                seen.add(key)
                concerns.append(concern)
        concerns = concerns[:_MAX_CONCERNS]

        suggested = {**base.suggested_fields, **_coerce_suggested(raw.get("suggested_fields"))}

        return AIReview(
            recommendation=recommendation,
            confidence=confidence if confidence is not None else base.confidence,
            summary=summary,
            concerns=concerns,
            suggested_fields=suggested,
            engine=self._engine_label,
            model=self._model,
            llm_usage=usage,
        )


def build_review_advisor(settings: Settings) -> ReviewAdvisor:
    """Wire an advisor from settings (LLM optional; heuristic always works)."""
    review_llm = build_review_llm(settings)
    if isinstance(review_llm, DisabledReviewLLM):
        return ReviewAdvisor(review_llm)
    model = (settings.llm_model or "gpt-4o-mini").strip()
    return ReviewAdvisor(review_llm, engine_label=f"openai:{model}", model=model)
