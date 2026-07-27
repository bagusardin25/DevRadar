"""Celery tasks for document fetch and storage."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery.exceptions import Retry

import app.models  # noqa: F401  # Ensure worker ORM relationships are registered.
from app.catalog.enums import ListingKind, SubmissionState
from app.config import Settings, get_settings
from app.db import create_engine, create_session_maker
from app.ingestion.browser import should_use_browser
from app.ingestion.fetcher import FetchError, FetchPolicy, fetch_url
from app.ingestion.llm_provider import create_extractor
from app.ingestion.parser import parse_document
from app.ingestion.ssrf import SSRFError
from app.ingestion.storage import DocumentStorage, build_document_storage
from app.submissions.models import CommunitySubmission
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _fetch_and_store(
    url: str,
    *,
    storage: DocumentStorage,
    policy: FetchPolicy | None = None,
    etag: str | None = None,
    if_modified_since: str | None = None,
    listing_kind: str = "hackathon",
    run_extract: bool = True,
    include_excerpt: bool = False,
) -> dict[str, Any]:
    policy = policy or FetchPolicy()
    if etag:
        policy.etag = etag
    if if_modified_since:
        policy.if_modified_since = if_modified_since

    try:
        doc = await fetch_url(url, policy)
    except (SSRFError, FetchError) as exc:
        logger.info("fetch_failed", extra={"url": url, "error": str(exc)})
        return {
            "ok": False,
            "error": str(exc),
            "url": url,
        }

    if doc.not_modified:
        return {
            "ok": True,
            "not_modified": True,
            "url": url,
            "final_url": doc.final_url,
            "status_code": 304,
            "etag": doc.etag,
        }

    ref = await storage.store_document(doc)
    parsed = parse_document(doc.body, url=doc.final_url, content_type=doc.content_type)
    needs_browser = should_use_browser(doc, policy)

    extraction: dict[str, Any] | None = None
    if run_extract:
        settings = get_settings()
        extractor = create_extractor(settings)
        try:
            kind = ListingKind(listing_kind)
        except ValueError:
            kind = ListingKind.HACKATHON
        result = await extractor.extract(parsed, kind)
        extraction = {
            "method": result.method,
            "llm_attempted": result.llm_attempted,
            "usage": result.llm_usage.to_snapshot() if result.llm_usage else None,
            "errors": result.errors,
            "field_sources": result.field_sources,
            "fields": {
                k: (v.isoformat() if hasattr(v, "isoformat") else v)
                for k, v in result.fields.items()
            },
            "title": result.fields.get("title") or parsed.title,
        }

    payload: dict[str, Any] = {
        "ok": True,
        "not_modified": False,
        "url": url,
        "final_url": doc.final_url,
        "status_code": doc.status_code,
        "content_type": doc.content_type,
        "content_hash": ref.content_hash,
        "storage_key": ref.storage_key,
        "byte_size": ref.byte_size,
        "reused_existing": ref.reused_existing,
        "etag": doc.etag,
        "last_modified": doc.last_modified,
        "parser_version": parsed.parser_version,
        "title": (extraction or {}).get("title") or parsed.title,
        "text_length": len(parsed.text),
        "link_count": len(parsed.links),
        "needs_browser": needs_browser,
        "redirect_chain": doc.redirect_chain,
        "extraction": extraction,
        "listing_kind": listing_kind,
    }
    if include_excerpt:
        # Bounded, untrusted page context for the advisory model only. The
        # submission task removes it before its Celery result is persisted.
        payload["page_excerpt"] = parsed.text[:6_000]
    return payload


@celery_app.task(name="ingestion.fetch_document", bind=True)  # type: ignore[untyped-decorator]
def fetch_document(self: Any, request: dict[str, Any]) -> dict[str, Any]:
    """Fetch a URL, store by content hash, parse lightly.

    request keys:
      - url (required)
      - etag / if_modified_since (optional)
      - source_id / crawl_run_id (optional metadata)
      - idempotency_key (optional)
    """
    url = str(request["url"])
    settings = get_settings()
    storage = build_document_storage(settings)
    result: dict[str, Any] = _run(
        _fetch_and_store(
            url,
            storage=storage,
            etag=request.get("etag"),
            if_modified_since=request.get("if_modified_since"),
            listing_kind=str(request.get("listing_kind") or "hackathon"),
            run_extract=bool(request.get("run_extract", True)),
            include_excerpt=bool(request.get("include_excerpt", False)),
        )
    )
    result["source_id"] = request.get("source_id")
    result["crawl_run_id"] = request.get("crawl_run_id")
    result["idempotency_key"] = request.get("idempotency_key")
    result["task_id"] = getattr(self.request, "id", None)
    return result


_FINAL_SUBMISSION_STATES = frozenset(
    {
        SubmissionState.ACCEPTED,
        SubmissionState.REJECTED,
        SubmissionState.DUPLICATE,
        SubmissionState.AWAITING_ADMIN,
    }
)


async def _prepare_submission_fetch(
    submission_id: UUID | str,
    *,
    settings: Settings,
) -> dict[str, Any] | None:
    """Load authoritative submission data and mark the fetch attempt started."""
    sid = submission_id if isinstance(submission_id, UUID) else UUID(str(submission_id))
    engine = create_engine(settings)
    maker = create_session_maker(engine)
    try:
        async with maker() as session:
            submission = await session.get(CommunitySubmission, sid)
            if (
                submission is None
                or SubmissionState(submission.state) in _FINAL_SUBMISSION_STATES
            ):
                return None
            submission.state = SubmissionState.FETCHING
            submission.attempt_count = (submission.attempt_count or 0) + 1
            submission.last_error = None
            metadata = dict(submission.metadata_json or {})
            metadata["fetchStartedAt"] = datetime.now(UTC).isoformat()
            submission.metadata_json = metadata
            await session.commit()
            return _build_submission_fetch_request(submission)
    finally:
        await engine.dispose()


def _build_submission_fetch_request(
    submission: CommunitySubmission,
) -> dict[str, Any]:
    """Build the worker request from the DB row, preserving its claimed kind."""
    return {
        "url": submission.canonical_url,
        "listing_kind": submission.claimed_type or ListingKind.HACKATHON.value,
        "idempotency_key": submission.job_idempotency_key,
        "run_extract": True,
        "include_excerpt": True,
    }


async def _mark_submission_state(
    submission_id: UUID | str,
    state: SubmissionState,
    *,
    settings: Settings,
    error: str | None = None,
) -> None:
    sid = submission_id if isinstance(submission_id, UUID) else UUID(str(submission_id))
    engine = create_engine(settings)
    maker = create_session_maker(engine)
    try:
        async with maker() as session:
            submission = await session.get(CommunitySubmission, sid)
            if submission is None:
                return
            submission.state = state
            submission.last_error = error[:1000] if error else None
            metadata = dict(submission.metadata_json or {})
            metadata["lastStateAt"] = datetime.now(UTC).isoformat()
            submission.metadata_json = metadata
            await session.commit()
    finally:
        await engine.dispose()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="ingestion.fetch_submission",
    bind=True,
    max_retries=2,
)
def fetch_submission(self: Any, submission_id: str) -> dict[str, Any]:
    """Fetch, extract, verify, and pre-review one community submission."""
    from app.submissions.review_pipeline import finalize_submission_review

    settings = get_settings()
    fetch_request = _run(_prepare_submission_fetch(submission_id, settings=settings))
    if fetch_request is None:
        return {"ok": False, "skipped": True, "submission_id": submission_id}

    try:
        result = fetch_document(fetch_request)
        result = result if isinstance(result, dict) else dict(result)
        fetch_error = str(result.get("error") or "")[:1000]
        retries = int(getattr(self.request, "retries", 0) or 0)
        if not result.get("ok") and retries < int(self.max_retries or 0):
            _run(
                _mark_submission_state(
                    submission_id,
                    SubmissionState.QUEUED,
                    settings=settings,
                    error=fetch_error or "Submission fetch failed",
                )
            )
            raise self.retry(
                exc=RuntimeError(fetch_error or "Submission fetch failed"),
                countdown=min(60, 2 ** (retries + 1)),
            )

        _run(
            _mark_submission_state(
                submission_id,
                SubmissionState.REVIEWING,
                settings=settings,
                error=fetch_error or None,
            )
        )
        if settings.ai_review_enabled:
            review = _run(
                finalize_submission_review(submission_id, result, settings=settings)
            )
            if review is not None:
                result["ai_review"] = review
        else:
            _run(
                _mark_submission_state(
                    submission_id,
                    SubmissionState.AWAITING_ADMIN,
                    settings=settings,
                )
            )

        result.pop("page_excerpt", None)
        result["submission_id"] = submission_id
        return result
    except Retry:
        raise
    except Exception as exc:
        try:
            _run(
                _mark_submission_state(
                    submission_id,
                    SubmissionState.REVIEW_FAILED,
                    settings=settings,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
        except Exception:
            logger.exception(
                "submission_review_failure_state_update_failed",
                extra={"submission_id": submission_id},
            )
        logger.exception(
            "submission_ai_review_failed",
            extra={"submission_id": submission_id},
        )
        raise


@celery_app.task(name="ingestion.browser_fetch", bind=True)  # type: ignore[untyped-decorator]
def browser_fetch(self: Any, request: dict[str, Any]) -> dict[str, Any]:
    """Placeholder for Playwright worker — must not run with secrets."""
    return {
        "ok": False,
        "error": "Browser worker not implemented in this process",
        "url": request.get("url"),
        "task_id": getattr(self.request, "id", None),
    }


async def fetch_document_async(
    url: str,
    *,
    storage: DocumentStorage | None = None,
    policy: FetchPolicy | None = None,
) -> dict[str, Any]:
    """In-process async helper used by tests and future API orchestration."""
    settings = get_settings()
    store = storage or build_document_storage(settings)
    return await _fetch_and_store(url, storage=store, policy=policy)
