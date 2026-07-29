"""Execute a queued live discovery run end to end.

Pipeline per candidate: fetch → parse → extract → normalize → verify → persist.
Every stage reuses the existing ingestion components; this module only
orchestrates them and records honest counters on the run row.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import ListingKind, VerificationStatus
from app.config import Settings
from app.discovery.constants import (
    DEFAULT_MODULE,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
)
from app.discovery.http import build_fetch_policy, fetch_document
from app.discovery.models import LiveDiscoveryRun
from app.discovery.seeds import SeedCandidate, resolve_seed_candidates
from app.ingestion.llm_provider import create_extractor
from app.ingestion.normalizer import SourceContext, normalize_extraction
from app.ingestion.parser import parse_document
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.verifier import VerificationEvidence

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_MODULE",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_QUEUED",
    "STATUS_RUNNING",
    "DiscoverySummary",
    "execute_discovery_run",
]

#: Statuses that mean the listing is live in the public catalogue.
_PUBLISHED = frozenset(
    {
        VerificationStatus.VERIFIED_ACTIVE,
        VerificationStatus.LIKELY_ACTIVE,
        VerificationStatus.REGISTRATION_CLOSED,
    }
)


@dataclass(slots=True)
class DiscoverySummary:
    candidates: int = 0
    fetched: int = 0
    published: int = 0
    needs_review: int = 0
    #: Subset of `published` that went live on partial evidence and opened a
    #: review item. Counted separately so a run never reports a clean publish
    #: for something still waiting on a human.
    flagged_for_review: int = 0
    failed: int = 0
    cost_units: int = 0
    unsupported_connectors: list[str] = field(default_factory=list)
    feeds_failed: list[str] = field(default_factory=list)
    verified_listing_ids: list[str] = field(default_factory=list)

    def as_meta(self) -> dict[str, Any]:
        return {
            "candidates": self.candidates,
            "fetched": self.fetched,
            "published": self.published,
            "needs_review": self.needs_review,
            "flagged_for_review": self.flagged_for_review,
            "failed": self.failed,
            "unsupported_connectors": self.unsupported_connectors,
            "feeds_failed": self.feeds_failed,
        }


def _listing_kind(module: str) -> ListingKind:
    return (
        ListingKind.AI_OFFER
        if module.strip().lower() == ListingKind.AI_OFFER.value
        else ListingKind.HACKATHON
    )


def _idempotency_key(canonical_url: str) -> str:
    """Stable per-URL key so repeat runs never duplicate a listing."""
    material = f"live_discovery|{canonical_url.strip().lower()}"
    return hashlib.sha256(material.encode()).hexdigest()


async def _process_candidate(
    session: AsyncSession,
    pipeline: IngestionPipeline,
    seed: SeedCandidate,
    *,
    settings: Settings,
    policy: Any,
    now: datetime,
    summary: DiscoverySummary,
) -> None:
    doc = await fetch_document(seed.url, policy)
    summary.cost_units += 1
    if doc is None:
        summary.failed += 1
        return
    summary.fetched += 1

    parsed = parse_document(
        doc.body,
        url=doc.final_url or seed.url,
        content_type=doc.content_type,
    )
    kind = _listing_kind(seed.module)
    extractor = create_extractor(settings)
    extraction = await extractor.extract(parsed, kind)

    candidate = normalize_extraction(
        extraction,
        SourceContext(
            source_id=seed.source_id,
            source_url=doc.final_url or seed.url,
            trust_tier=seed.trust_tier,
            connector_type=seed.connector_type,
        ),
    )

    evidence = VerificationEvidence(
        source_tier=seed.trust_tier or "tier_2",
        link_ok=True,
        cross_source_count=1,
        last_checked_at=now,
        only_tier3=str(seed.trust_tier) == "tier_3",
    )

    outcome = await pipeline.process_candidate(
        candidate,
        evidence,
        idempotency_key=_idempotency_key(candidate.canonical_url or seed.url),
        now=now,
    )

    if outcome.listing_id is not None and outcome.status in _PUBLISHED:
        summary.published += 1
        summary.verified_listing_ids.append(str(outcome.listing_id))
        if outcome.review_item_id is not None:
            summary.flagged_for_review += 1
    else:
        summary.needs_review += 1


async def execute_discovery_run(
    session: AsyncSession,
    run: LiveDiscoveryRun,
    *,
    settings: Settings,
    now: datetime | None = None,
) -> DiscoverySummary:
    """Run discovery for `run`, mutating it to a terminal status."""
    now = now or datetime.now(UTC)
    policy = build_fetch_policy(settings)
    summary = DiscoverySummary()

    run.status = STATUS_RUNNING
    run.started_at = now
    await session.flush()

    try:
        resolution = await resolve_seed_candidates(
            session,
            query_text=run.query,
            connector_types=list(run.connector_types or []),
            cap=int(run.result_cap or 10),
            policy=policy,
            module=str((run.meta_json or {}).get("module") or DEFAULT_MODULE),
        )
        summary.candidates = len(resolution.candidates)
        summary.cost_units += resolution.fetches
        summary.unsupported_connectors = resolution.unsupported
        summary.feeds_failed = resolution.feeds_failed

        pipeline = IngestionPipeline(session)
        for seed in resolution.candidates:
            try:
                await _process_candidate(
                    session,
                    pipeline,
                    seed,
                    settings=settings,
                    policy=policy,
                    now=now,
                    summary=summary,
                )
            except Exception:
                # One bad page must not sink the run.
                logger.exception("discovery_candidate_failed", extra={"url": seed.url})
                summary.failed += 1
    except Exception as exc:
        logger.exception("discovery_run_failed", extra={"run_id": str(run.id)})
        run.status = STATUS_FAILED
        run.error_summary = f"{type(exc).__name__}: {exc}"[:500]
        run.finished_at = datetime.now(UTC)
        run.cost_units = summary.cost_units
        run.meta_json = {**(run.meta_json or {}), **summary.as_meta()}
        await session.flush()
        return summary

    run.status = STATUS_COMPLETED
    run.finished_at = datetime.now(UTC)
    run.cost_units = summary.cost_units
    run.verified_listing_ids = list(summary.verified_listing_ids)
    run.error_summary = _error_summary(summary)
    run.meta_json = {**(run.meta_json or {}), **summary.as_meta()}
    await session.flush()

    logger.info("discovery_run_completed", extra={"run_id": str(run.id), **summary.as_meta()})
    return summary


def _error_summary(summary: DiscoverySummary) -> str | None:
    """Explain an empty result instead of reporting a silent success."""
    if summary.candidates > 0:
        return None
    if summary.unsupported_connectors:
        joined = ", ".join(sorted(set(summary.unsupported_connectors)))
        return (
            f"No crawler implemented for: {joined}. "
            "Configure an official_site or rss source to discover listings."
        )
    if summary.feeds_failed:
        return f"All {len(summary.feeds_failed)} configured feed(s) failed to fetch."
    return "No discovery sources configured (need an enabled official_site or rss source)."
