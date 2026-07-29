#!/usr/bin/env python3
"""Re-fetch official URLs for catalogue listings and merge extracted fields.

Works without OpenAI (rules-only). With LLM_PROVIDER=openai + key, hybrid fill-in
updates missing fields from page text.

Usage (from backend/):
  uv run python scripts/recheck_listings.py
  uv run python scripts/recheck_listings.py --kind ai_offer --limit 15
  uv run python scripts/recheck_listings.py --kind hackathon --limit 10
  uv run python scripts/recheck_listings.py --slug google-gemini-api-free-tier
  uv run python scripts/recheck_listings.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import app.models  # noqa: E402, F401
from app.catalog.enums import ListingKind  # noqa: E402
from app.catalog.recheck import recheck_catalogue  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import create_engine, create_session_maker  # noqa: E402


async def run(
    *,
    kind: str | None,
    limit: int,
    slugs: list[str] | None,
    dry_run: bool,
) -> int:
    settings = get_settings()
    kind_enum = None if kind in (None, "all") else ListingKind(kind)

    print(
        f"Recheck kind={kind or 'all'} limit={limit} "
        f"llm={settings.llm_provider} dry_run={dry_run}"
    )
    if dry_run:
        print("Dry-run: would recheck oldest-checked active listings (no network writes planned).")
        print("Omit --dry-run to fetch and update.")
        return 0

    engine = create_engine(settings)
    session_maker = create_session_maker(engine)
    try:
        async with session_maker() as session:
            summary = await recheck_catalogue(
                session,
                kind=kind_enum,
                limit=limit,
                only_slugs=slugs,
                settings=settings,
            )
            await session.commit()
    finally:
        await engine.dispose()

    for r in summary.results:
        if r.ok:
            fields = ",".join(r.updated_fields) if r.updated_fields else "-"
            print(f"OK   {r.slug:40} method={r.method:12} fields={fields} url={r.url[:60]}")
        else:
            print(f"FAIL {r.slug:40} err={r.error}")
    print(
        f"Done scanned={summary.scanned} ok={summary.ok} "
        f"failed={summary.failed} skipped={summary.skipped}"
    )
    return 0 if summary.failed == 0 else 2


def main() -> None:
    p = argparse.ArgumentParser(description="Recheck official URLs for catalogue listings")
    p.add_argument(
        "--kind",
        choices=["ai_offer", "hackathon", "all"],
        default="ai_offer",
        help="Listing kind to recheck (default: ai_offer)",
    )
    p.add_argument("--limit", type=int, default=20)
    p.add_argument(
        "--slug",
        action="append",
        dest="slugs",
        help="Only recheck these slugs (repeatable)",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    raise SystemExit(
        asyncio.run(
            run(
                kind=args.kind,
                limit=args.limit,
                slugs=args.slugs,
                dry_run=args.dry_run,
            )
        )
    )


if __name__ == "__main__":
    main()
