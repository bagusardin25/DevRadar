"""Celery tasks for alert scanning (placeholder hooks)."""

from __future__ import annotations

from typing import Any

from app.worker.celery_app import celery_app


@celery_app.task(name="alerts.scan_matches")  # type: ignore[untyped-decorator]
def scan_matches(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Scheduled scan entrypoint — workers load DB and deliver matches."""
    return {"ok": True, "scanned": 0, "payload": payload or {}}
