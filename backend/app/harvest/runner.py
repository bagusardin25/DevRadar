"""Harvest open *online* hackathons into the admin review queue.

Never publishes. Directory hits are fetched, extracted (crawl lane), checked
by the deterministic verifier + AI advisor, then parked as OPEN review items
for a human. Dedupes against the catalogue and the open queue.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai_review.advisor import build_review_advisor
from app.catalog.enums import (
    ConnectorType,
    CrawlRunStatus,
    CrawlTrigger,
    HackathonMode,
    ListingKind,
    ReviewCandidateType,
    ReviewItemState,
    SourceTier,
)
from app.catalog.models import Listing
from app.config import Settings
from app.discovery.http import build_fetch_policy, fetch_document
from app.ingestion.llm_provider import create_extractor
from app.ingestion.models import CrawlRun
from app.ingestion.normalizer import SourceContext, normalize_extraction
from app.ingestion.parser import parse_document
from app.ingestion.pipeline import _jsonable
from app.ingestion.verifier import VerificationEvidence, verify
from app.llm.lanes import LLMLane
from app.review.models import ReviewItem
from app.sources.connectors.base import ConnectorQuery, DiscoveryCandidate
from app.sources.connectors.devpost import DevpostConnector
from app.sources.models import Source
from app.submissions.review_pipeline import _PRIORITY
from app.submissions.url_policy import canonicalize_url

logger = logging.getLogger(__name__)

HARVEST_SOURCE_NAME = "Devpost (online harvest)"
DEFAULT_CAP = 20
# Safety bound on directory pages walked per run (40 rows per page on Devpost).
MAX_DIRECTORY_PAGES = 25

_QUEUE_STATES = (ReviewItemState.OPEN.value, ReviewItemState.IN_PROGRESS.value)


@dataclass(slots=True)
class HarvestSummary:
    discovered: int = 0
    queued: int = 0
    skipped_duplicate: int = 0
    skipped_offline: int = 0
    skipped_fetch: int = 0
    failed: int = 0
    review_item_ids: list[str] = field(default_factory=list)
    crawl_run_id: str | None = None

    def as_meta(self) -> dict[str, Any]:
        return {
            "discovered": self.discovered,
            "queued": self.queued,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_offline": self.skipped_offline,
            "skipped_fetch": self.skipped_fetch,
            "failed": self.failed,
            "review_item_ids": list(self.review_item_ids),
            "crawl_run_id": self.crawl_run_id,
        }


async def run_online_hackathon_harvest(
    session: AsyncSession,
    settings: Settings,
    *,
    cap: int | None = None,
    now: datetime | None = None,
    connector: DevpostConnector | None = None,
    fetch_page: Any = None,
) -> HarvestSummary:
    """Discover online Devpost hackathons and queue them for admin review."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    limit = max(1, min(int(cap or settings.harvest_devpost_cap or DEFAULT_CAP), 50))
    summary = HarvestSummary()

    if not settings.harvest_enabled:
        logger.info("harvest_disabled")
        return summary

    source = await _ensure_harvest_source(session)
    window_key = _window_key(now)
    existing = (
        await session.execute(select(CrawlRun).where(CrawlRun.idempotency_key == window_key))
    ).scalar_one_or_none()
    if existing is not None:
        logger.info("harvest_window_already_ran", extra={"window": window_key})
        summary.crawl_run_id = str(existing.id)
        return summary

    run = CrawlRun(
        source_id=source.id,
        trigger=CrawlTrigger.HARVEST,
        status=CrawlRunStatus.RUNNING,
        started_at=now,
        idempotency_key=window_key,
        discovered_count=0,
        fetched_count=0,
        failed_count=0,
        cost_units=0,
    )
    session.add(run)
    await session.flush()

    summary.crawl_run_id = str(run.id)
    client = connector or DevpostConnector()
    fetcher = fetch_page or fetch_document
    policy = build_fetch_policy(settings)
    extractor = create_extractor(settings, lane=LLMLane.CRAWL)
    advisor = build_review_advisor(settings)

    try:
        known = await _known_urls(session)
        candidates, discovered, duplicates = await collect_new_candidates(
            client, known=known, limit=limit
        )
        summary.discovered = discovered
        summary.skipped_duplicate = duplicates
        run.discovered_count = summary.discovered

        for hit in candidates:
            try:
                outcome = await _ingest_one(
                    session,
                    hit,
                    settings=settings,
                    source=source,
                    extractor=extractor,
                    advisor=advisor,
                    fetcher=fetcher,
                    policy=policy,
                    known=known,
                    now=now,
                )
            except Exception:
                logger.exception("harvest_candidate_failed", extra={"url": hit.url})
                summary.failed += 1
                continue
            if isinstance(outcome, tuple) and outcome[0] == "queued":
                summary.queued += 1
                summary.review_item_ids.append(outcome[1])
                run.fetched_count += 1
            elif outcome == "duplicate":
                summary.skipped_duplicate += 1
            elif outcome == "offline":
                summary.skipped_offline += 1
            elif outcome == "fetch":
                summary.skipped_fetch += 1
                run.failed_count += 1
            else:
                summary.failed += 1
                run.failed_count += 1

        run.cost_units = run.fetched_count + run.failed_count
        run.status = (
            CrawlRunStatus.PARTIAL
            if summary.failed or summary.skipped_fetch
            else CrawlRunStatus.SUCCEEDED
        )
        run.finished_at = datetime.now(UTC)
        await session.flush()
    except Exception as exc:
        run.status = CrawlRunStatus.FAILED
        run.error_summary = f"{type(exc).__name__}: {exc}"[:500]
        run.finished_at = datetime.now(UTC)
        await session.flush()
        raise

    logger.info("harvest_completed", extra=summary.as_meta())
    return summary


async def collect_new_candidates(
    client: Any,
    *,
    known: set[str],
    limit: int,
    max_pages: int = MAX_DIRECTORY_PAGES,
) -> tuple[list[DiscoveryCandidate], int, int]:
    """Walk the directory until ``limit`` *new* events are found or it runs out.

    The cap bounds how many events are fetched and reviewed per run; events
    already in the catalogue or queue must not use it up, otherwise every run
    re-sees the same first page and later events are never reached.
    Returns (new candidates, rows discovered, duplicates skipped).
    """
    fresh: list[DiscoveryCandidate] = []
    seen: set[str] = set()
    discovered = duplicates = 0
    cursor: str | None = None
    for _ in range(max(1, max_pages)):
        page = await client.discover(
            ConnectorQuery(module="hackathon", result_cap=40), cursor
        )
        for hit in page.items:
            discovered += 1
            try:
                key = canonicalize_url(hit.url).canonical
            except Exception:
                key = hit.url.rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            if key in known:
                duplicates += 1
                continue
            fresh.append(hit)
            if len(fresh) >= limit:
                return fresh, discovered, duplicates
        cursor = page.next_cursor
        if not cursor:
            break
    return fresh, discovered, duplicates


async def _ingest_one(
    session: AsyncSession,
    hit: DiscoveryCandidate,
    *,
    settings: Settings,
    source: Source,
    extractor: Any,
    advisor: Any,
    fetcher: Any,
    policy: Any,
    known: set[str],
    now: datetime,
) -> str | tuple[str, str]:
    try:
        canonical = canonicalize_url(hit.url).canonical
    except Exception:
        return "failed"
    if canonical in known:
        return "duplicate"

    doc = await fetcher(hit.url, policy)
    if doc is None:
        return "fetch"

    parsed = parse_document(
        doc.body,
        url=doc.final_url or hit.url,
        content_type=doc.content_type,
    )
    extraction = await extractor.extract(parsed, ListingKind.HACKATHON)
    if not extraction.fields.get("mode") and (hit.metadata or {}).get("mode") == "online":
        extraction.fields["mode"] = HackathonMode.ONLINE.value
        extraction.field_sources["mode"] = "directory"
    if not extraction.fields.get("title") and hit.title:
        extraction.fields["title"] = hit.title
        extraction.field_sources.setdefault("title", "directory")
    if not extraction.fields.get("prize_value") and hit.metadata.get("prize_value"):
        extraction.fields["prize_value"] = hit.metadata["prize_value"]
        extraction.field_sources.setdefault("prize_value", "directory")
    if not extraction.fields.get("organizer") and hit.metadata.get("organization"):
        extraction.fields["organizer"] = hit.metadata["organization"]
        extraction.field_sources.setdefault("organizer", "directory")
    if not extraction.fields.get("technologies") and hit.metadata.get("themes"):
        extraction.fields["technologies"] = list(hit.metadata["themes"])
        extraction.field_sources.setdefault("technologies", "directory")

    candidate = normalize_extraction(
        extraction,
        SourceContext(
            source_id=source.id,
            source_url=doc.final_url or hit.url,
            trust_tier=SourceTier.TIER_2.value,
            connector_type=ConnectorType.DEVPOST.value,
        ),
    )
    mode = candidate.fields.get("mode")
    mode_value = mode.value if hasattr(mode, "value") else str(mode or "")
    if mode_value == HackathonMode.IN_PERSON.value:
        return "offline"

    evidence = VerificationEvidence(
        source_tier=SourceTier.TIER_2.value,
        link_ok=True,
        cross_source_count=1,
        last_checked_at=now,
        only_tier3=False,
    )
    result = verify(candidate, evidence, now=now)
    excerpt = (parsed.text or "")[:6_000]
    ai_review = await advisor.review(candidate, result, page_excerpt=excerpt)

    item = ReviewItem(
        candidate_type=ReviewCandidateType.LISTING,
        candidate_snapshot={
            "title": candidate.title,
            "kind": candidate.kind.value,
            "description": candidate.description,
            "officialUrl": candidate.official_url,
            "canonical_url": candidate.canonical_url,
            "source": "harvest_devpost",
            "harvest": True,
            "fields": _jsonable(candidate.fields),
            "fieldSources": dict(candidate.field_sources),
            "aiReview": ai_review.to_snapshot(),
            "verification": {
                "status": result.status.value,
                "reasons": list(result.reasons),
                "checks": result.checks,
                "score": result.score.total,
            },
            "directory": {
                "externalId": hit.external_id,
                "organization": hit.metadata.get("organization"),
                "dates": hit.metadata.get("submission_period_dates"),
                "timeLeft": hit.metadata.get("time_left_to_submission"),
            },
            "extraction": {
                "method": candidate.extraction_method,
                "schemaVersion": candidate.schema_version,
                "warnings": list(candidate.warnings),
            },
        },
        reason=(
            f"Harvest (online Devpost): AI {ai_review.recommendation.value.replace('_', ' ')} "
            f"({ai_review.confidence}/100)"
        )[:500],
        priority=_PRIORITY.get(ai_review.recommendation.value, 50),
        state=ReviewItemState.OPEN,
        source_id=source.id,
    )
    session.add(item)
    await session.flush()
    known.add(canonical)
    return ("queued", str(item.id))


async def _ensure_harvest_source(session: AsyncSession) -> Source:
    result = await session.execute(
        select(Source).where(Source.name == HARVEST_SOURCE_NAME)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    source = Source(
        name=HARVEST_SOURCE_NAME,
        connector_type=ConnectorType.DEVPOST,
        trust_tier=SourceTier.TIER_2,
        base_url="https://devpost.com/hackathons?challenge_type%5B%5D=online",
        enabled=True,
        notes="Auto-created for the 3× daily online hackathon harvest.",
        polling_policy={"default_interval_seconds": 8 * 3600},
    )
    session.add(source)
    await session.flush()
    return source


async def _known_urls(session: AsyncSession) -> set[str]:
    known: set[str] = set()
    listings = list(
        (
            await session.execute(
                select(Listing).options(selectinload(Listing.hackathon))
            )
        )
        .scalars()
        .all()
    )
    for listing in listings:
        if listing.hackathon is not None:
            _add_url(known, listing.hackathon.official_url)

    items = list(
        (
            await session.execute(
                select(ReviewItem).where(
                    ReviewItem.candidate_type == ReviewCandidateType.LISTING,
                    ReviewItem.state.in_(_QUEUE_STATES),
                )
            )
        )
        .scalars()
        .all()
    )
    for item in items:
        snap = item.candidate_snapshot or {}
        fields = snap.get("fields") if isinstance(snap.get("fields"), dict) else {}
        for raw in (
            snap.get("officialUrl"),
            snap.get("canonical_url"),
            snap.get("url"),
            (fields or {}).get("official_url"),
        ):
            _add_url(known, raw)
    return known


def _add_url(known: set[str], raw: object) -> None:
    text = str(raw or "").strip()
    if not text:
        return
    try:
        known.add(canonicalize_url(text).canonical)
    except Exception:
        known.add(text.rstrip("/").lower())


def _window_key(now: datetime) -> str:
    """One harvest per 8-hour slot (00–08, 08–16, 16–24 UTC)."""
    slot = (now.hour // 8) * 8
    stamp = now.strftime("%Y%m%d") + f"T{slot:02d}"
    return hashlib.sha256(f"harvest|devpost|online|{stamp}".encode()).hexdigest()
