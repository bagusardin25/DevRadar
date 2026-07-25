"""Resolve candidate URLs for a live discovery run.

Only connectors that can genuinely produce candidates from configuration are
supported here:

- ``official_site`` — curated seed URLs stored in ``source_queries.query_config``
- ``rss``           — a feed URL fetched live, then parsed for item links

The aggregator connectors (devpost / mlh / hackerearth) are fixture-only stubs
with no crawling implementation, so asking for them yields nothing. Callers get
that back explicitly via :attr:`SeedResolution.unsupported` instead of silently
reporting an empty run as a success.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.http import decode_body, fetch_document
from app.ingestion.fetcher import FetchPolicy
from app.sources.connectors import get_connector
from app.sources.connectors.base import ConnectorQuery
from app.sources.models import Source, SourceQuery

logger = logging.getLogger(__name__)

#: Connector types the live discovery worker can actually execute.
SUPPORTED_CONNECTORS = ("official_site", "rss")


@dataclass(slots=True)
class SeedCandidate:
    url: str
    connector_type: str
    trust_tier: str
    module: str
    title: str | None = None
    source_id: UUID | None = None


@dataclass(slots=True)
class SeedResolution:
    candidates: list[SeedCandidate] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    feeds_failed: list[str] = field(default_factory=list)
    #: Feed fetches performed while resolving seeds (billed as cost units).
    fetches: int = 0


def _dedupe_key(url: str) -> str:
    return url.strip().rstrip("/").lower()


async def _feed_xml(
    source: Source,
    query: SourceQuery,
    policy: FetchPolicy,
) -> tuple[str | None, str | None, bool]:
    """Return (xml, failed_url, fetched) for an RSS source."""
    config = query.query_config or {}
    inline = config.get("feed_xml")
    if inline:
        # Pre-recorded feed (tests / offline fixtures) — no network needed.
        return str(inline), None, False

    feed_url = str(config.get("feed_url") or source.base_url or "").strip()
    if not feed_url:
        return None, None, False

    doc = await fetch_document(feed_url, policy)
    if doc is None:
        return None, feed_url, True
    return decode_body(doc), None, True


async def resolve_seed_candidates(
    session: AsyncSession,
    *,
    query_text: str,
    connector_types: list[str],
    cap: int,
    policy: FetchPolicy,
    module: str | None = None,
) -> SeedResolution:
    """Expand the requested connectors into concrete candidate URLs.

    `module` ("hackathon" / "ai_offer") keeps a hackathon search from crawling
    AI-offer sources and vice versa.
    """
    resolution = SeedResolution()

    requested = [c.strip().lower() for c in connector_types if c.strip()]
    supported = [c for c in requested if c in SUPPORTED_CONNECTORS]
    resolution.unsupported = [c for c in requested if c not in SUPPORTED_CONNECTORS]
    if not supported:
        return resolution

    stmt = (
        select(SourceQuery, Source)
        .join(Source, Source.id == SourceQuery.source_id)
        .where(
            Source.enabled.is_(True),
            SourceQuery.enabled.is_(True),
            Source.connector_type.in_(supported),
        )
        .order_by(Source.name)
    )
    if module:
        stmt = stmt.where(SourceQuery.module == module)

    rows = list((await session.execute(stmt)).all())

    seen: set[str] = set()
    for query, source in rows:
        if len(resolution.candidates) >= cap:
            break

        connector_type = str(source.connector_type)
        config = dict(query.query_config or {})

        if connector_type == "rss":
            xml, failed_url, fetched = await _feed_xml(source, query, policy)
            if fetched:
                resolution.fetches += 1
            if failed_url:
                resolution.feeds_failed.append(failed_url)
            if not xml:
                continue
            config["feed_xml"] = xml

        try:
            connector = get_connector(connector_type)
        except KeyError:
            resolution.unsupported.append(connector_type)
            continue

        remaining = cap - len(resolution.candidates)
        page = await connector.discover(
            ConnectorQuery(
                module=query.module,
                query_text=query_text,
                config=config,
                result_cap=remaining,
            )
        )

        for item in page.items:
            url = (item.url or "").strip()
            if not url:
                continue
            key = _dedupe_key(url)
            if key in seen:
                continue
            seen.add(key)
            resolution.candidates.append(
                SeedCandidate(
                    url=url,
                    connector_type=connector_type,
                    trust_tier=str(source.trust_tier),
                    module=query.module,
                    title=item.title,
                    source_id=source.id,
                )
            )
            if len(resolution.candidates) >= cap:
                break

    logger.info(
        "discovery_seeds_resolved",
        extra={
            "candidates": len(resolution.candidates),
            "unsupported": resolution.unsupported,
            "feeds_failed": len(resolution.feeds_failed),
        },
    )
    return resolution
