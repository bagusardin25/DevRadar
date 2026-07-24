"""Celery application for DevRadar workers.

Queue separation (Task 6+):
- fetch: HTTP fetch jobs
- browser: Playwright jobs (isolated env — no secrets)
- extract / verify / notify / maintenance: later tasks
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "devradar",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.ingestion.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="fetch",
    task_routes={
        "ingestion.fetch_document": {"queue": "fetch"},
        "ingestion.fetch_submission": {"queue": "fetch"},
        "ingestion.browser_fetch": {"queue": "browser"},
    },
    # Browser queue should run in a separate worker process with restricted env.
    task_annotations={
        "ingestion.browser_fetch": {"rate_limit": "10/m"},
    },
)
