"""Staged duplicate detection — LLM suggestions never auto-merge."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal
from uuid import UUID

from app.catalog.enums import ListingKind
from app.ingestion.normalizer import CandidateListing
from app.submissions.url_policy import canonicalize_url

DEDUPLICATOR_VERSION = "1.0.0"

MatchType = Literal[
    "none",
    "exact_url",
    "title_organizer",
    "title_provider",
    "llm_suggestion",
]


@dataclass(slots=True)
class ExistingCandidate:
    """Minimal existing listing projection for matching."""

    id: UUID
    kind: ListingKind
    title: str
    canonical_url: str
    organizer_or_provider: str = ""


@dataclass(slots=True)
class DuplicateDecision:
    is_duplicate: bool
    match_type: MatchType
    existing_id: UUID | None
    similarity: float
    auto_merge: bool
    notes: str = ""
    # LLM may suggest a match; never set auto_merge True for that path.
    llm_suggested_id: UUID | None = None


def _norm_text(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm_text(a), _norm_text(b)).ratio()


def _safe_canonical(url: str) -> str:
    try:
        return canonicalize_url(url).canonical
    except Exception:
        return url.strip().lower()


def find_duplicate(
    candidate: CandidateListing,
    existing: Sequence[ExistingCandidate],
    *,
    llm_suggested_id: UUID | None = None,
    title_threshold: float = 0.88,
) -> DuplicateDecision:
    """Staged matching: exact URL → title/org similarity → optional LLM hint.

    LLM suggestions are recorded but **never** auto-merge.
    """
    kind_existing = [e for e in existing if e.kind == candidate.kind]
    cand_url = _safe_canonical(candidate.canonical_url)

    # 1) Exact canonical URL
    for e in kind_existing:
        if _safe_canonical(e.canonical_url) == cand_url and cand_url:
            return DuplicateDecision(
                is_duplicate=True,
                match_type="exact_url",
                existing_id=e.id,
                similarity=1.0,
                auto_merge=True,
                notes="Exact canonical URL match",
            )

    # 2) Title + organizer/provider similarity
    cand_org = ""
    if candidate.kind == ListingKind.HACKATHON:
        cand_org = str(candidate.fields.get("organizer") or "")
        match_type: MatchType = "title_organizer"
    else:
        cand_org = str(candidate.fields.get("provider") or "")
        match_type = "title_provider"

    best: ExistingCandidate | None = None
    best_score = 0.0
    for e in kind_existing:
        title_sim = _similarity(candidate.title, e.title)
        org_sim = (
            _similarity(cand_org, e.organizer_or_provider)
            if cand_org and e.organizer_or_provider
            else 0.0
        )
        # Weighted: title dominates; org boosts
        score = title_sim * 0.75 + org_sim * 0.25
        if org_sim >= 0.9 and title_sim >= 0.75:
            score = max(score, 0.92)
        if score > best_score:
            best_score = score
            best = e

    if best is not None and best_score >= title_threshold:
        return DuplicateDecision(
            is_duplicate=True,
            match_type=match_type,
            existing_id=best.id,
            similarity=round(best_score, 4),
            auto_merge=True,
            notes="Title/organizer similarity above threshold",
        )

    # 3) LLM suggestion — never auto-merge
    if llm_suggested_id is not None:
        return DuplicateDecision(
            is_duplicate=True,
            match_type="llm_suggestion",
            existing_id=llm_suggested_id,
            similarity=0.0,
            auto_merge=False,
            notes="LLM suggested duplicate; requires human review",
            llm_suggested_id=llm_suggested_id,
        )

    return DuplicateDecision(
        is_duplicate=False,
        match_type="none",
        existing_id=None,
        similarity=round(best_score, 4) if best else 0.0,
        auto_merge=False,
        notes="No duplicate found",
    )
