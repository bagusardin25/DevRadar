"""Celery tasks for document fetch and storage."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import get_settings
from app.ingestion.browser import should_use_browser
from app.ingestion.fetcher import FetchError, FetchPolicy, fetch_url
from app.ingestion.parser import parse_document
from app.ingestion.ssrf import SSRFError
from app.ingestion.storage import DocumentStorage, build_document_storage
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

    return {
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
        "title": parsed.title,
        "text_length": len(parsed.text),
        "link_count": len(parsed.links),
        "needs_browser": needs_browser,
        "redirect_chain": doc.redirect_chain,
    }


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
        )
    )
    result["source_id"] = request.get("source_id")
    result["crawl_run_id"] = request.get("crawl_run_id")
    result["idempotency_key"] = request.get("idempotency_key")
    result["task_id"] = getattr(self.request, "id", None)
    return result


@celery_app.task(name="ingestion.fetch_submission", bind=True)  # type: ignore[untyped-decorator]
def fetch_submission(self: Any, request: dict[str, Any]) -> dict[str, Any]:
    """Fetch a community submission URL (same pipeline as fetch_document)."""
    result = fetch_document(request)
    return result if isinstance(result, dict) else dict(result)


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
