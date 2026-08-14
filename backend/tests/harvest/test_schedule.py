"""Beat schedule includes the 3× daily harvest."""

from __future__ import annotations

from celery.schedules import crontab

from app.worker.celery_app import celery_app


def test_harvest_is_on_the_beat_schedule() -> None:
    entry = celery_app.conf.beat_schedule["harvest-online-hackathons"]
    assert entry["task"] == "harvest.run_online_hackathons"
    schedule = entry["schedule"]
    assert isinstance(schedule, crontab)
    assert schedule.hour == {0, 8, 16}
    assert schedule.minute == {0}


def test_harvest_task_is_routed_to_fetch_queue() -> None:
    routes = celery_app.conf.task_routes
    assert routes["harvest.run_online_hackathons"]["queue"] == "fetch"
