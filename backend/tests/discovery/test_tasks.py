"""Worker entrypoint guards.

These exercise the Celery task body, which owns its own session and commits for
real — so each test removes the row it created.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db import create_engine, create_session_maker
from app.discovery.models import LiveDiscoveryRun
from app.discovery.tasks import _execute


@pytest.fixture
async def maker(settings: Settings) -> AsyncIterator[async_sessionmaker]:
    engine = create_engine(settings)
    yield create_session_maker(engine)
    await engine.dispose()


async def _delete_run(maker: async_sessionmaker, run_id) -> None:
    async with maker() as s:
        await s.execute(delete(LiveDiscoveryRun).where(LiveDiscoveryRun.id == run_id))
        await s.commit()


class TestRunLiveDiscoveryTask:
    async def test_unknown_run_id_is_reported_not_raised(self) -> None:
        result = await _execute(str(uuid4()))
        assert result["ok"] is False
        assert result["reason"] == "run_not_found"

    async def test_already_finished_run_is_not_reprocessed(
        self, maker: async_sessionmaker
    ) -> None:
        async with maker() as s:
            run = LiveDiscoveryRun(
                query="already done",
                status="completed",
                connector_types=["official_site"],
                result_cap=1,
                request_hash=uuid4().hex,
                ip_hash="test-ip-hash",
                verified_listing_ids=[],
                meta_json={},
            )
            s.add(run)
            await s.commit()
            run_id = run.id

        try:
            result = await _execute(str(run_id))
            assert result["skipped"] is True
            assert result["reason"] == "status_completed"
        finally:
            await _delete_run(maker, run_id)

    async def test_queued_run_reaches_a_terminal_status(
        self, maker: async_sessionmaker
    ) -> None:
        """No sources for this module → completes with an explanation, not a hang."""
        async with maker() as s:
            run = LiveDiscoveryRun(
                query="nothing configured",
                status="queued",
                connector_types=["devpost"],
                result_cap=1,
                request_hash=uuid4().hex,
                ip_hash="test-ip-hash",
                verified_listing_ids=[],
                meta_json={"module": "hackathon"},
            )
            s.add(run)
            await s.commit()
            run_id = run.id

        try:
            result = await _execute(str(run_id))
            assert result["ok"] is True
            assert result["status"] == "completed"
            assert result["candidates"] == 0

            # The commit inside the task is what the API poller reads back.
            async with maker() as s:
                stored = await s.get(LiveDiscoveryRun, run_id)
                assert stored is not None
                assert stored.status == "completed"
                assert stored.finished_at is not None
                assert "devpost" in (stored.error_summary or "")
        finally:
            await _delete_run(maker, run_id)
