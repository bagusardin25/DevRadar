#!/usr/bin/env python3
"""Seed sources that Live Web Discovery can actually crawl.

Only two connectors have a real implementation: `official_site` (curated seed
URLs) and `rss` (a feed fetched live). The devpost/mlh/hackerearth connectors
are fixture-only stubs, so seeding them here would produce empty runs.

The built-in AI-offer seeds are the same official pricing/terms pages the
catalogue already rechecks daily — no new third-party exposure.

No hackathon seeds ship by default: this project has no verified list of stable
hackathon URLs, and inventing them would recreate the problem this script
exists to fix. Add your own:

Usage (from backend/):
  uv run python scripts/seed_discovery_sources.py
  uv run python scripts/seed_discovery_sources.py --dry-run
  uv run python scripts/seed_discovery_sources.py \
      --seed-url https://example.com/some-hackathon --module hackathon
  uv run python scripts/seed_discovery_sources.py \
      --rss "Example feed" https://example.com/feed.xml --module hackathon
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Import full model graph so SQLAlchemy relationship names resolve.
import app.models  # noqa: E402, F401
from app.catalog.enums import ConnectorType, SourceTier  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import create_engine, create_session_maker  # noqa: E402
from app.sources.models import Source, SourceQuery  # noqa: E402

DEFAULT_INTERVAL = 12 * 60 * 60

# Official pricing / terms pages already curated by scripts/refresh_ai_offers.py.
AI_OFFER_SEED_URLS = [
    "https://ai.google.dev/pricing",
    "https://console.groq.com/docs/rate-limits",
    "https://developers.cloudflare.com/workers-ai/platform/pricing/",
    "https://huggingface.co/docs/hub/spaces-overview",
    "https://vercel.com/pricing",
    "https://www.oracle.com/cloud/free/",
    "https://www.kaggle.com/docs/notebooks",
    "https://education.github.com/pack",
    "https://openai.com/chatgpt/pricing/",
    "https://claude.com/pricing",
]

BUILTIN_SOURCES: list[dict[str, Any]] = [
    {
        "name": "Official AI offer pages (discovery)",
        "connector_type": ConnectorType.OFFICIAL_SITE.value,
        "trust_tier": SourceTier.TIER_1.value,
        "base_url": None,
        "notes": "Tier-1 vendor pricing/terms pages used by live discovery.",
        "module": "ai_offer",
        "query_name": "curated-offer-pages",
        "query_config": {"seed_urls": AI_OFFER_SEED_URLS},
        "result_cap": len(AI_OFFER_SEED_URLS),
        "cost_budget": 100,
    },
]


async def _upsert_source(session: Any, spec: dict[str, Any], *, dry_run: bool) -> str:
    name = spec["name"]
    existing = (
        await session.execute(select(Source).where(Source.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        return f"skip  {name}"
    if dry_run:
        return f"dry   {name} ({len(spec['query_config'].get('seed_urls') or []) or 1} entries)"

    source = Source(
        name=name,
        connector_type=spec["connector_type"],
        trust_tier=spec["trust_tier"],
        base_url=spec.get("base_url"),
        enabled=True,
        notes=spec.get("notes"),
        polling_policy={"default_interval_seconds": DEFAULT_INTERVAL},
    )
    session.add(source)
    await session.flush()
    session.add(
        SourceQuery(
            source_id=source.id,
            module=spec["module"],
            name=spec["query_name"],
            query_config=spec["query_config"],
            schedule={"interval_seconds": DEFAULT_INTERVAL},
            result_cap=int(spec.get("result_cap") or 20),
            cost_budget=int(spec.get("cost_budget") or 100),
            enabled=True,
        )
    )
    await session.flush()
    return f"add   {name}"


def _extra_specs(args: argparse.Namespace) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    if args.seed_url:
        specs.append(
            {
                "name": args.seed_name or f"Custom {args.module} seed URLs",
                "connector_type": ConnectorType.OFFICIAL_SITE.value,
                "trust_tier": SourceTier.TIER_1.value,
                "base_url": None,
                "notes": "Operator-provided seed URLs for live discovery.",
                "module": args.module,
                "query_name": "custom-seed-urls",
                "query_config": {"seed_urls": list(args.seed_url)},
                "result_cap": len(args.seed_url),
                "cost_budget": 100,
            }
        )
    for name, url in args.rss or []:
        specs.append(
            {
                "name": name,
                "connector_type": ConnectorType.RSS.value,
                "trust_tier": SourceTier.TIER_2.value,
                "base_url": url,
                "notes": "Operator-provided RSS/Atom feed for live discovery.",
                "module": args.module,
                "query_name": "feed",
                "query_config": {"feed_url": url},
                "result_cap": 30,
                "cost_budget": 150,
            }
        )
    return specs


async def run(args: argparse.Namespace) -> int:
    engine = create_engine(get_settings())
    session_maker = create_session_maker(engine)
    specs = ([] if args.no_builtin else list(BUILTIN_SOURCES)) + _extra_specs(args)
    if not specs:
        print("Nothing to seed (used --no-builtin without --seed-url/--rss).")
        return 0

    lines: list[str] = []
    try:
        async with session_maker() as session:
            for spec in specs:
                lines.append(await _upsert_source(session, spec, dry_run=args.dry_run))
            if not args.dry_run:
                await session.commit()
    finally:
        await engine.dispose()

    for line in lines:
        print(line)
    print(f"Done. sources={len(lines)}{' (dry run)' if args.dry_run else ''}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed official_site / rss sources for live discovery"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-builtin",
        action="store_true",
        help="Skip the built-in AI offer seed pages",
    )
    parser.add_argument(
        "--module",
        default="hackathon",
        choices=["hackathon", "ai_offer"],
        help="Module for --seed-url / --rss entries (default: hackathon)",
    )
    parser.add_argument(
        "--seed-url",
        action="append",
        metavar="URL",
        help="Add a curated seed URL (repeatable)",
    )
    parser.add_argument(
        "--seed-name",
        help="Source name for the --seed-url group",
    )
    parser.add_argument(
        "--rss",
        action="append",
        nargs=2,
        metavar=("NAME", "URL"),
        help="Add an RSS/Atom feed (repeatable)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
