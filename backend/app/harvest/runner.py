"""Harvest open *online* hackathons into the admin review queue.

Reads several public directories (Devpost, Devfolio, MLH, lablab.ai; see
``HARVEST_SOURCES``). Never publishes. Directory hits are fetched, extracted
(crawl lane), checked by the deterministic verifier + AI advisor, then parked
as OPEN review items for a human. Dedupes against the catalogue, the open
queue and across sources.
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
from app.sources.connectors import get_connector
from app.sources.connectors.base import ConnectorQuery, DiscoveryCandidate
from app.sources.connectors.directory_common import ranges_overlap, title_key
from app.sources.models import Source
from app.submissions.review_pipeline import _PRIORITY
from app.submissions.url_policy import canonicalize_url

logger = logging.getLogger(__name__)

# Kept for backwards compatibility with callers that import it.
HARVEST_SOURCE_NAME = "Devpost (online harvest)"
DEFAULT_CAP = 20
# Safety bound on directory pages walked per run (40 rows per page on Devpost).
MAX_DIRECTORY_PAGES = 25
# Cross-source title matches need at least this many characters in the key, so
# short generic names ("hack", "ai") never merge distinct events.
MIN_TITLE_KEY_CHARS = 6


@dataclass(frozen=True, slots=True)
class HarvestSourceInfo:
    name: str
    connector_type: ConnectorType
    base_url: str
    label: str


HARVEST_SOURCES: dict[str, HarvestSourceInfo] = {
    "devpost": HarvestSourceInfo(
        name=HARVEST_SOURCE_NAME,
        connector_type=ConnectorType.DEVPOST,
        base_url="https://devpost.com/hackathons?challenge_type%5B%5D=online",
        label="Devpost",
    ),
    "devfolio": HarvestSourceInfo(
        name="Devfolio (online harvest)",
        connector_type=ConnectorType.DEVFOLIO,
        base_url="https://devfolio.co/hackathons",
        label="Devfolio",
    ),
    "mlh": HarvestSourceInfo(
        name="MLH (online harvest)",
        connector_type=ConnectorType.MLH,
        base_url="https://www.mlh.com/seasons",
        label="MLH",
    ),
    "lablab": HarvestSourceInfo(
        name="lablab.ai (online harvest)",
        connector_type=ConnectorType.LABLAB,
        base_url="https://lablab.ai/ai-hackathons",
        label="lablab.ai",
    ),
}

_QUEUE_STATES = (ReviewItemState.OPEN.value, ReviewItemState.IN_PROGRESS.value)


@dataclass(slots=True)
class SourceCounts:
    discovered: int = 0
    queued: int = 0
    skipped_duplicate: int = 0
    skipped_cross_source: int = 0
    skipped_offline: int = 0
    skipped_fetch: int = 0
    failed: int = 0
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "discovered": self.discovered,
            "queued": self.queued,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_cross_source": self.skipped_cross_source,
            "skipped_offline": self.skipped_offline,
            "skipped_fetch": self.skipped_fetch,
            "failed": self.failed,
            "error": self.error,
        }


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
    per_source: dict[str, SourceCounts] = field(default_factory=dict)

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
            "sources": {key: counts.as_dict() for key, counts in self.per_source.items()},
        }


@dataclass(slots=True)
class SourceBatch:
    """What one source yielded in a run."""

    fresh: list[DiscoveryCandidate] = field(default_factory=list)
    # Rows the source returned that are already in the catalogue / queue. They
    # still take part in cross-source title matching.
    seen_known: list[DiscoveryCandidate] = field(default_factory=list)
    discovered: int = 0
    duplicates: int = 0


def _per_source_limit(key: str, settings: Settings, cap: int | None) -> int:
    if cap:
        value = int(cap)
    elif key == "devpost":
        value = int(settings.harvest_devpost_cap or DEFAULT_CAP)
    else:
        value = int(settings.harvest_source_cap)
    return max(1, min(value, 50))


def _build_connectors(settings: Settings, now: datetime) -> dict[str, Any]:
    connectors: dict[str, Any] = {}
    for key in settings.harvest_sources:
        if key not in HARVEST_SOURCES:
            logger.warning("harvest_unknown_source", extra={"source": key})
            continue
        connectors[key] = get_connector(key, now=lambda: now)
    return connectors


async def run_online_hackathon_harvest(
    session: AsyncSession,
    settings: Settings,
    *,
    cap: int | None = None,
    now: datetime | None = None,
    connector: Any = None,
    connectors: dict[str, Any] | None = None,
    fetch_page: Any = None,
) -> HarvestSummary:
    """Discover online hackathons in every enabled directory and queue them.

    ``connector`` (legacy) harvests Devpost only; ``connectors`` maps source
    keys to connector instances; otherwise ``settings.harvest_sources`` decides.
    """
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    summary = HarvestSummary()

    if not settings.harvest_enabled:
        logger.info("harvest_disabled")
        return summary

    if connector is not None:
        clients: dict[str, Any] = {"devpost": connector}
    elif connectors is not None:
        clients = dict(connectors)
    else:
        clients = _build_connectors(settings, now)
    unknown = [key for key in clients if key not in HARVEST_SOURCES]
    if unknown:
        raise ValueError(f"Unknown harvest source(s): {', '.join(unknown)}")
    if not clients:
        logger.info("harvest_no_sources")
        return summary

    # One source + one CrawlRun per source per 8-hour window.
    sources: dict[str, Source] = {}
    runs: dict[str, CrawlRun] = {}
    first_run_id: str | None = None
    for key in clients:
        source = await _ensure_harvest_source(session, key)
        window_key = _window_key(now, key)
        existing = (
            await session.execute(
                select(CrawlRun).where(CrawlRun.idempotency_key == window_key)
            )
        ).scalar_one_or_none()
        if existing is not None:
            logger.info("harvest_window_already_ran", extra={"window": window_key})
            first_run_id = first_run_id or str(existing.id)
            continue
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
        sources[key] = source
        runs[key] = run
        first_run_id = first_run_id or str(run.id)
        summary.per_source[key] = SourceCounts()
    summary.crawl_run_id = first_run_id
    if not runs:
        return summary

    fetcher = fetch_page or fetch_document
    policy = build_fetch_policy(settings)
    extractor = create_extractor(settings, lane=LLMLane.CRAWL)
    advisor = build_review_advisor(settings)
    failed_runs: set[str] = set()
    degraded_runs: set[str] = set()

    try:
        known = await _known_urls(session)

        # 1. Discover, source by source (priority order).
        batches: dict[str, SourceBatch] = {}
        for key in runs:
            counts = summary.per_source[key]
            client = clients[key]
            try:
                batch = await collect_source(
                    client,
                    known=known,
                    limit=_per_source_limit(key, settings, cap),
                )
            except Exception as exc:
                logger.exception("harvest_source_failed", extra={"source": key})
                counts.error = type(exc).__name__
                failed_runs.add(key)
                continue
            degraded = getattr(client, "degraded", None)
            if getattr(client, "blocked", False):
                counts.error = "blocked"
                failed_runs.add(key)
            elif degraded:
                counts.error = str(degraded)
                degraded_runs.add(key)
            batches[key] = batch
            counts.discovered = batch.discovered
            counts.skipped_duplicate = batch.duplicates
            runs[key].discovered_count = batch.discovered

        # 2. Cross-source dedupe, then a total ceiling shared round-robin.
        selected, cross_dupes = merge_batches(batches, settings.harvest_total_cap)
        for key, count in cross_dupes.items():
            summary.per_source[key].skipped_cross_source = count

        # 3. Ingest.
        for key, hit in selected:
            counts = summary.per_source[key]
            run = runs[key]
            try:
                outcome = await _ingest_one(
                    session,
                    hit,
                    settings=settings,
                    source_key=key,
                    source=sources[key],
                    extractor=extractor,
                    advisor=advisor,
                    fetcher=fetcher,
                    policy=policy,
                    known=known,
                    now=now,
                )
            except Exception:
                logger.exception("harvest_candidate_failed", extra={"url": hit.url})
                counts.failed += 1
                continue
            if isinstance(outcome, tuple) and outcome[0] == "queued":
                counts.queued += 1
                summary.review_item_ids.append(outcome[1])
                run.fetched_count += 1
            elif outcome == "duplicate":
                counts.skipped_duplicate += 1
            elif outcome == "offline":
                counts.skipped_offline += 1
            elif outcome == "fetch":
                counts.skipped_fetch += 1
                run.failed_count += 1
            else:
                counts.failed += 1
                run.failed_count += 1

        for key, run in runs.items():
            counts = summary.per_source[key]
            run.cost_units = run.fetched_count + run.failed_count
            if key in failed_runs:
                run.status = CrawlRunStatus.FAILED
                run.error_summary = (counts.error or "failed")[:500]
            elif key in degraded_runs:
                run.status = CrawlRunStatus.PARTIAL
                run.error_summary = (counts.error or "degraded")[:500]
            elif counts.failed or counts.skipped_fetch:
                run.status = CrawlRunStatus.PARTIAL
            else:
                run.status = CrawlRunStatus.SUCCEEDED
            run.finished_at = datetime.now(UTC)
            summary.discovered += counts.discovered
            summary.queued += counts.queued
            summary.skipped_duplicate += counts.skipped_duplicate + counts.skipped_cross_source
            summary.skipped_offline += counts.skipped_offline
            summary.skipped_fetch += counts.skipped_fetch
            summary.failed += counts.failed
        await session.flush()
    except Exception as exc:
        for run in runs.values():
            run.status = CrawlRunStatus.FAILED
            run.error_summary = f"{type(exc).__name__}: {exc}"[:500]
            run.finished_at = datetime.now(UTC)
        await session.flush()
        raise

    logger.info("harvest_completed", extra=summary.as_meta())
    return summary


def _canonical_key(url: str) -> str:
    try:
        return canonicalize_url(url).canonical
    except Exception:
        return url.rstrip("/").lower()


async def collect_source(
    client: Any,
    *,
    known: set[str],
    limit: int,
    max_pages: int = MAX_DIRECTORY_PAGES,
) -> SourceBatch:
    """Walk one directory until ``limit`` *new* events are found or it runs out.

    The cap bounds how many events are fetched and reviewed per run; events
    already in the catalogue or queue must not use it up, otherwise every run
    re-sees the same first page and later events are never reached.
    """
    batch = SourceBatch()
    seen: set[str] = set()
    cursor: str | None = None
    for _ in range(max(1, max_pages)):
        page = await client.discover(
            ConnectorQuery(module="hackathon", result_cap=40), cursor
        )
        for hit in page.items:
            batch.discovered += 1
            key = _canonical_key(hit.url)
            if key in seen:
                continue
            seen.add(key)
            if key in known:
                batch.duplicates += 1
                batch.seen_known.append(hit)
                continue
            batch.fresh.append(hit)
            if len(batch.fresh) >= limit:
                return batch
        cursor = page.next_cursor
        if not cursor:
            break
    return batch


async def collect_new_candidates(
    client: Any,
    *,
    known: set[str],
    limit: int,
    max_pages: int = MAX_DIRECTORY_PAGES,
) -> tuple[list[DiscoveryCandidate], int, int]:
    """Single-source wrapper: (new candidates, rows discovered, duplicates)."""
    batch = await collect_source(client, known=known, limit=limit, max_pages=max_pages)
    return batch.fresh, batch.discovered, batch.duplicates


def _same_event(a: DiscoveryCandidate, b: DiscoveryCandidate) -> bool:
    """Cross-source match: equal title key and overlapping dates."""
    key = title_key(a.title)
    if len(key) < MIN_TITLE_KEY_CHARS or key != title_key(b.title):
        return False
    a_meta, b_meta = a.metadata or {}, b.metadata or {}
    if not a_meta.get("starts_at") or not b_meta.get("starts_at"):
        return False
    return ranges_overlap(
        a_meta.get("starts_at"),
        a_meta.get("ends_at"),
        b_meta.get("starts_at"),
        b_meta.get("ends_at"),
    )


def merge_batches(
    batches: dict[str, SourceBatch], total_cap: int
) -> tuple[list[tuple[str, DiscoveryCandidate]], dict[str, int]]:
    """Drop cross-source duplicates, then pick up to ``total_cap`` round-robin.

    ``batches`` is in priority order: an earlier source wins a duplicate. A
    fresh hit is dropped when its canonical URL was already accepted, or when
    another source holds the same event (equal title key with overlapping
    dates) either as an accepted hit or as a row already known to the
    catalogue / queue.
    """
    cross_dupes: dict[str, int] = {}
    urls: set[str] = set()
    accepted: dict[str, list[DiscoveryCandidate]] = {key: [] for key in batches}
    for key, batch in batches.items():
        for hit in batch.fresh:
            url_key = _canonical_key(hit.url)
            duplicate = url_key in urls
            if not duplicate:
                for other, other_batch in batches.items():
                    if other == key:
                        continue
                    pool = [*other_batch.seen_known, *accepted[other]]
                    if any(_same_event(hit, row) for row in pool):
                        duplicate = True
                        break
            if duplicate:
                cross_dupes[key] = cross_dupes.get(key, 0) + 1
                continue
            urls.add(url_key)
            accepted[key].append(hit)

    selected: list[tuple[str, DiscoveryCandidate]] = []
    positions = dict.fromkeys(accepted, 0)
    while len(selected) < total_cap:
        progressed = False
        for key, hits in accepted.items():
            if positions[key] < len(hits) and len(selected) < total_cap:
                selected.append((key, hits[positions[key]]))
                positions[key] += 1
                progressed = True
        if not progressed:
            break
    return selected, cross_dupes


async def _ingest_one(
    session: AsyncSession,
    hit: DiscoveryCandidate,
    *,
    settings: Settings,
    source_key: str,
    source: Source,
    extractor: Any,
    advisor: Any,
    fetcher: Any,
    policy: Any,
    known: set[str],
    now: datetime,
) -> str | tuple[str, str]:
    info = HARVEST_SOURCES[source_key]
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
    directory_mode = (hit.metadata or {}).get("mode")
    if not extraction.fields.get("mode") and directory_mode in (
        HackathonMode.ONLINE.value,
        HackathonMode.HYBRID.value,
    ):
        extraction.fields["mode"] = directory_mode
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
            connector_type=info.connector_type.value,
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
            "source": f"harvest_{source_key}",
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
                "source": source_key,
                "externalId": hit.external_id,
                "organization": hit.metadata.get("organization"),
                "dates": hit.metadata.get("submission_period_dates"),
                "timeLeft": hit.metadata.get("time_left_to_submission"),
                "startsAt": hit.metadata.get("starts_at"),
                "endsAt": hit.metadata.get("ends_at"),
                "directoryUrl": hit.metadata.get("directory_url"),
            },
            "extraction": {
                "method": candidate.extraction_method,
                "schemaVersion": candidate.schema_version,
                "warnings": list(candidate.warnings),
            },
        },
        reason=(
            f"Harvest (online {info.label}): AI "
            f"{ai_review.recommendation.value.replace('_', ' ')} "
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


async def _ensure_harvest_source(session: AsyncSession, key: str = "devpost") -> Source:
    info = HARVEST_SOURCES[key]
    result = await session.execute(select(Source).where(Source.name == info.name))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    source = Source(
        name=info.name,
        connector_type=info.connector_type,
        trust_tier=SourceTier.TIER_2,
        base_url=info.base_url,
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


def _window_key(now: datetime, source_key: str = "devpost") -> str:
    """One harvest per source per 8-hour slot (00:00-08:00, 08:00-16:00, 16:00-24:00 UTC)."""
    slot = (now.hour // 8) * 8
    stamp = now.strftime("%Y%m%d") + f"T{slot:02d}"
    return hashlib.sha256(f"harvest|{source_key}|online|{stamp}".encode()).hexdigest()
