"""Submission dispatch uses Celery's broker protocol, never a raw Redis list."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.submissions import enqueue as enqueue_module
from app.submissions.enqueue import CelerySubmissionEnqueue
from app.worker.celery_app import celery_app


class _FakeRedis:
    def __init__(self, *, created: bool = True) -> None:
        self.created = created
        self.deleted: list[str] = []
        self.closed = False

    async def set(self, *_args, **_kwargs):
        return self.created

    async def delete(self, key: str) -> None:
        self.deleted.append(key)

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_dispatches_real_celery_message(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = _FakeRedis()
    sent: dict[str, object] = {}
    monkeypatch.setattr(
        enqueue_module.aioredis,
        "from_url",
        lambda *_args, **_kwargs: fake_redis,
    )

    def _send_task(name: str, **kwargs: object) -> None:
        sent["name"] = name
        sent.update(kwargs)

    monkeypatch.setattr(celery_app, "send_task", _send_task)
    submission_id = uuid4()
    result = await CelerySubmissionEnqueue("redis://unused").enqueue_fetch_submission(
        submission_id,
        "stable-job-key",
        "https://example.com/source",
    )

    assert result is True
    assert sent == {
        "name": "ingestion.fetch_submission",
        "args": [str(submission_id)],
        "task_id": "stable-job-key",
        "queue": "fetch",
    }
    assert fake_redis.closed is True


@pytest.mark.asyncio
async def test_failed_send_releases_idempotency_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = _FakeRedis()
    monkeypatch.setattr(
        enqueue_module.aioredis,
        "from_url",
        lambda *_args, **_kwargs: fake_redis,
    )

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(celery_app, "send_task", _fail)
    result = await CelerySubmissionEnqueue("redis://unused").enqueue_fetch_submission(
        uuid4(),
        "retryable-job-key",
        "https://example.com/source",
    )

    assert result is False
    assert fake_redis.deleted == [
        "devradar:job:idempotency:retryable-job-key"
    ]
