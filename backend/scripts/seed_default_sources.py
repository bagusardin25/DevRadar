#!/usr/bin/env python3
"""Seed default Tier-2 aggregator sources + scheduled queries (Devpost, MLH).

OSS default path: enable free/public aggregators without X paid API.

Usage (from backend/):
  uv run python scripts/seed_default_sources.py
  uv run python scripts/seed_default_sources.py --dry-run
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

# 12h poll by default — gentle on third parties.
DEFAULT_INTERVAL = 12 * 60 * 60

SOURCES: list[dict[str, Any]] = [
    {
        "name": "Devpost (directory)",
        "connector_type": ConnectorType.DEVPOST.value,
        "trust_tier": SourceTier.TIER_2.value,
        "base_url": "https://devpost.com/hackathons",
        "notes": "Tier-2 aggregator. Fixture-friendly offline; live crawl when worker enabled.",
        "queries": [
            {
                "module": "hackathon",
                "name": "open-hackathons",
                "query_config": {"query_text": "", "themes": ["ai", "open"]},
                "result_cap": 40,
                "cost_budget": 200,
            }
        ],
    },
    {
        "name": "MLH (events)",
        "connector_type": ConnectorType.MLH.value,
        "trust_tier": SourceTier.TIER_2.value,
        "base_url": "https://mlh.io/seasons",
        "notes": "Tier-2 student-oriented hackathon calendar.",
        "queries": [
            {
                "module": "hackathon",
                "name": "season-events",
                "query_config": {"query_text": ""},
                "result_cap": 40,
                "cost_budget": 200,
            }
        ],
    },
    {
        "name": "HackerEarth (challenges)",
        "connector_type": ConnectorType.HACKEREARTH.value,
        "trust_tier": SourceTier.TIER_2.value,
        "base_url": "https://www.hackerearth.com/challenges/",
        "notes": "Tier-2 challenges directory.",
        "queries": [
            {
                "module": "hackathon",
                "name": "open-challenges",
                "query_config": {"query_text": ""},
                "result_cap": 30,
                "cost_budget": 150,
            }
        ],
    },
]


async def _get_or_create_source(session: Any, spec: dict[str, Any], *, dry_run: bool) -> str:
    result = await session.execute(select(Source).where(Source.name == spec["name"]))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return f"skip  source {spec['name']}"
    if dry_run:
        return f"dry   source {spec['name']}"
    source = Source(
        name=spec["name"],
        connector_type=spec["connector_type"],
        trust_tier=spec["trust_tier"],
        base_url=spec.get("base_url"),
        enabled=True,
        notes=spec.get("notes"),
        polling_policy={"default_interval_seconds": DEFAULT_INTERVAL},
    )
    session.add(source)
    await session.flush()
    for q in spec.get("queries") or []:
        session.add(
            SourceQuery(
                source_id=source.id,
                module=q["module"],
                name=q["name"],
                query_config=q.get("query_config") or {},
                schedule={"interval_seconds": DEFAULT_INTERVAL},
                result_cap=int(q.get("result_cap") or 40),
                cost_budget=int(q.get("cost_budget") or 100),
                enabled=True,
            )
        )
    await session.flush()
    return f"add   source {spec['name']} + {len(spec.get('queries') or [])} queries"


async def run(*, dry_run: bool) -> int:
    settings = get_settings()
    engine = create_engine(settings)
    session_maker = create_session_maker(engine)
    lines: list[str] = []
    try:
        if dry_run:
            for s in SOURCES:
                lines.append(f"dry   source {s['name']}")
            for line in lines:
                print(line)
            return 0
        async with session_maker() as session:
            for spec in SOURCES:
                lines.append(await _get_or_create_source(session, spec, dry_run=False))
            await session.commit()
    finally:
        await engine.dispose()
    for line in lines:
        print(line)
    print(f"Done. sources={len(lines)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed default Devpost/MLH/HackerEarth sources")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(dry_run=args.dry_run)))


if __name__ == "__main__":
    main()
