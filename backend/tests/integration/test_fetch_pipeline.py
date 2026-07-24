"""End-to-end fetch → store → parse without external network."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.ingestion.fetcher import FetchPolicy
from app.ingestion.storage import InMemoryDocumentStorage
from app.ingestion.tasks import fetch_document_async
from tests.ingestion.http_server import LocalHttpServer, make_handler


@pytest.mark.asyncio
async def test_fetch_store_parse_pipeline() -> None:
    html = b"""
    <html><head><title>Pipeline Event</title></head>
    <body><p>Registration open worldwide.</p>
    <a href="/apply">Apply now</a></body></html>
    """
    handler = make_handler(
        routes={
            "/event": {
                "status": 200,
                "body": html,
                "headers": {"Content-Type": "text/html; charset=utf-8", "ETag": '"v1"'},
            }
        }
    )
    store = InMemoryDocumentStorage()
    with LocalHttpServer(handler) as server:
        url = f"{server.base_url}/event"
        with patch(
            "app.ingestion.fetcher.validate_url_for_fetch",
            side_effect=lambda u: (u, "127.0.0.1", ["127.0.0.1"]),
        ):
            result = await fetch_document_async(
                url, storage=store, policy=FetchPolicy()
            )
        assert result["ok"] is True
        assert result["reused_existing"] is False
        assert result["title"] == "Pipeline Event"
        assert result["link_count"] >= 1
        assert await store.exists(result["content_hash"])

        # Second fetch same body → reused object
        with patch(
            "app.ingestion.fetcher.validate_url_for_fetch",
            side_effect=lambda u: (u, "127.0.0.1", ["127.0.0.1"]),
        ):
            result2 = await fetch_document_async(url, storage=store)
        assert result2["reused_existing"] is True
        assert result2["content_hash"] == result["content_hash"]
        assert len(store.objects) == 1
