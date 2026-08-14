"""Celery application for DevRadar workers.

Queue separation (Task 6+):
- fetch: HTTP fetch jobs
- browser: Playwright jobs (isolated env — no secrets)
- extract / verify / notify / maintenance: later tasks
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "devradar",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.ingestion.tasks",
        "app.catalog.tasks",
        "app.alerts.tasks",
        "app.discovery.tasks",
        "app.harvest.tasks",
    ],
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
        "catalog.lifecycle_sweep": {"queue": "fetch"},
        "catalog.recheck_official_urls": {"queue": "fetch"},
        "alerts.scan_matches": {"queue": "fetch"},
        "alerts.deliver_webhook": {"queue": "fetch"},
        "discovery.run_live_discovery": {"queue": "fetch"},
        "harvest.run_online_hackathons": {"queue": "fetch"},
    },
    # Browser queue should run in a separate worker process with restricted env.
    task_annotations={
        "ingestion.browser_fetch": {"rate_limit": "10/m"},
        "catalog.recheck_official_urls": {"rate_limit": "30/h"},
        "alerts.scan_matches": {"rate_limit": "30/h"},
        # User-triggered, but still a safety valve on top of the per-IP limit.
        "discovery.run_live_discovery": {"rate_limit": "20/m"},
        "harvest.run_online_hackathons": {"rate_limit": "6/h"},
    },
    # Optional beat schedule (enable with celery beat).
    beat_schedule={
        "catalog-lifecycle-hourly": {
            "task": "catalog.lifecycle_sweep",
            "schedule": 3600.0,
        },
        # Re-fetch AI offer official pages daily (rules-only if LLM disabled).
        "catalog-recheck-ai-offers-daily": {
            "task": "catalog.recheck_official_urls",
            "schedule": 86400.0,
            "kwargs": {"kind": "ai_offer", "limit": 25},
        },
        # Match new listings to confirmed email alerts + operator webhook.
        "alerts-scan-matches-hourly": {
            "task": "alerts.scan_matches",
            "schedule": 3600.0,
            "kwargs": {"payload": {"lookback_hours": 48, "limit_listings": 100}},
        },
        # 07:00 / 15:00 / 23:00 WIB (00:00 / 08:00 / 16:00 UTC) — pagi, siang, malam.
        "harvest-online-hackathons": {
            "task": "harvest.run_online_hackathons",
            "schedule": crontab(hour="0,8,16", minute=0),
        },
    },
)
