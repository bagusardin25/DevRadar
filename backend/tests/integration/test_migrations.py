"""Integration tests for Alembic migrations and schema shape."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

# Ensure all models register on Base.metadata.
import app.models  # noqa: F401
from app.config import Settings
from app.db import Base, create_engine

BACKEND_ROOT = Path(__file__).resolve().parents[2]


async def _table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as conn:
        def _get(sync_conn):  # type: ignore[no-untyped-def]
            return set(inspect(sync_conn).get_table_names())

        return await conn.run_sync(_get)


async def _index_names(engine: AsyncEngine, table: str) -> set[str]:
    async with engine.connect() as conn:
        def _get(sync_conn):  # type: ignore[no-untyped-def]
            return {idx["name"] for idx in inspect(sync_conn).get_indexes(table)}

        return await conn.run_sync(_get)


class TestSchemaPresence:
    async def test_core_tables_exist(self) -> None:
        engine = create_engine(Settings())
        try:
            names = await _table_names(engine)
            expected = {
                "listings",
                "hackathons",
                "ai_offers",
                "sources",
                "source_queries",
                "crawl_runs",
                "raw_documents",
                "discovery_signals",
                "listing_sources",
                "extraction_runs",
                "verification_events",
                "review_items",
                "admin_audit_log",
                "alembic_version",
            }
            missing = expected - names
            assert not missing, f"Missing tables: {missing}"
        finally:
            await engine.dispose()

    async def test_listings_has_search_and_trgm_indexes(self) -> None:
        engine = create_engine(Settings())
        try:
            indexes = await _index_names(engine, "listings")
            assert "ix_listings_search_document" in indexes
            assert "ix_listings_title_trgm" in indexes
            assert "ix_listings_kind_status_published" in indexes
        finally:
            await engine.dispose()

    async def test_hackathon_check_constraints_present(self) -> None:
        engine = create_engine(Settings())
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid = 'hackathons'::regclass
                          AND contype = 'c'
                        """
                    )
                )
                names = {row[0] for row in result}
            assert "ck_hackathons_team_min_positive" in names
            assert "ck_hackathons_team_max_gte_min" in names
            assert "ck_hackathons_prize_non_negative" in names
        finally:
            await engine.dispose()

    async def test_extensions_enabled(self) -> None:
        engine = create_engine(Settings())
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT extname FROM pg_extension")
                )
                exts = {row[0] for row in result}
            assert "pg_trgm" in exts
            assert "citext" in exts
        finally:
            await engine.dispose()

    async def test_metadata_matches_expected_models(self) -> None:
        model_tables = set(Base.metadata.tables.keys())
        expected = {
            "listings",
            "hackathons",
            "ai_offers",
            "sources",
            "source_queries",
            "crawl_runs",
            "raw_documents",
            "discovery_signals",
            "listing_sources",
            "extraction_runs",
            "verification_events",
            "review_items",
            "admin_audit_log",
        }
        assert expected.issubset(model_tables)


class TestMigrationRoundTrip:
    def test_downgrade_and_upgrade(self) -> None:
        """Downgrade to base then upgrade head; schema remains usable."""
        env = None
        downgrade = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "base"],
            cwd=BACKEND_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert downgrade.returncode == 0, downgrade.stderr + downgrade.stdout

        upgrade = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert upgrade.returncode == 0, upgrade.stderr + upgrade.stdout

    def test_alembic_check_clean(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "check"],
            cwd=BACKEND_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr + result.stdout
