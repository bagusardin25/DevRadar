"""Fetcher + SSRF tests against a local HTTP server."""

from __future__ import annotations

import pytest

from app.ingestion.fetcher import (
    FetchError,
    FetchPolicy,
    browser_fallback_eligible,
    fetch_url,
)
from app.ingestion.ssrf import SSRFError, validate_url_for_fetch
from tests.ingestion.http_server import LocalHttpServer, make_handler


class TestSSRF:
    def test_blocks_localhost_hostname(self) -> None:
        with pytest.raises(SSRFError):
            validate_url_for_fetch("http://localhost/x")

    def test_blocks_private_literal(self) -> None:
        with pytest.raises(SSRFError):
            validate_url_for_fetch("http://192.168.0.5/")

    def test_blocks_metadata_ip(self) -> None:
        with pytest.raises(SSRFError):
            validate_url_for_fetch("http://169.254.169.254/latest/meta-data")

    def test_blocks_loopback(self) -> None:
        with pytest.raises(SSRFError):
            validate_url_for_fetch("http://127.0.0.1/")


class TestFetcher:
    @pytest.mark.asyncio
    async def test_fetches_html(self) -> None:
        handler = make_handler(
            routes={
                "/page": {
                    "status": 200,
                    "body": b"<html><title>T</title><body>Hi</body></html>",
                    "headers": {"Content-Type": "text/html"},
                }
            }
        )
        with LocalHttpServer(handler) as server:
            # 127.0.0.1 is blocked by SSRF — tests that need real fetch must
            # temporarily allow loopback OR we use a custom validate path.
            # For unit tests of HTTP mechanics we call fetch with mocked validation
            # by patching validate_url_for_fetch to allow the local server.
            from unittest.mock import patch

            async def _run() -> None:
                with patch(
                    "app.ingestion.fetcher.validate_url_for_fetch",
                    side_effect=lambda u: (u, "127.0.0.1", ["127.0.0.1"]),
                ):
                    doc = await fetch_url(f"{server.base_url}/page")
                    assert doc.status_code == 200
                    assert b"Hi" in doc.body
                    assert doc.content_hash
                    assert len(doc.content_hash) == 64

            await _run()

    @pytest.mark.asyncio
    async def test_follows_redirects_with_limit(self) -> None:
        from unittest.mock import patch

        handler = make_handler(
            routes={
                "/a": {"redirect": "/b", "status": 302},
                "/b": {"redirect": "/c", "status": 302},
                "/c": {
                    "status": 200,
                    "body": b"done",
                    "headers": {"Content-Type": "text/plain"},
                },
            }
        )
        with LocalHttpServer(handler) as server, patch(
            "app.ingestion.fetcher.validate_url_for_fetch",
            side_effect=lambda u: (u, "127.0.0.1", ["127.0.0.1"]),
        ):
            doc = await fetch_url(
                f"{server.base_url}/a",
                FetchPolicy(max_redirects=5),
            )
            assert doc.status_code == 200
            assert doc.body == b"done"
            assert len(doc.redirect_chain) == 2

    @pytest.mark.asyncio
    async def test_too_many_redirects(self) -> None:
        from unittest.mock import patch

        handler = make_handler(
            routes={
                "/r1": {"redirect": "/r2"},
                "/r2": {"redirect": "/r3"},
                "/r3": {"redirect": "/r4"},
            }
        )
        with LocalHttpServer(handler) as server, patch(
            "app.ingestion.fetcher.validate_url_for_fetch",
            side_effect=lambda u: (u, "127.0.0.1", ["127.0.0.1"]),
        ), pytest.raises(FetchError, match="redirect"):
            await fetch_url(
                f"{server.base_url}/r1",
                FetchPolicy(max_redirects=2),
            )

    @pytest.mark.asyncio
    async def test_oversized_body(self) -> None:
        from unittest.mock import patch

        big = b"x" * 10_000
        handler = make_handler(
            routes={
                "/big": {
                    "status": 200,
                    "body": big,
                    "headers": {"Content-Type": "text/plain"},
                }
            }
        )
        with LocalHttpServer(handler) as server, patch(
            "app.ingestion.fetcher.validate_url_for_fetch",
            side_effect=lambda u: (u, "127.0.0.1", ["127.0.0.1"]),
        ), pytest.raises(FetchError, match="max size"):
            await fetch_url(
                f"{server.base_url}/big",
                FetchPolicy(max_bytes=1000),
            )

    @pytest.mark.asyncio
    async def test_mime_rejection(self) -> None:
        from unittest.mock import patch

        handler = make_handler(
            routes={
                "/bin": {
                    "status": 200,
                    "body": b"\x00\x01",
                    "headers": {"Content-Type": "application/octet-stream"},
                }
            }
        )
        with LocalHttpServer(handler) as server, patch(
            "app.ingestion.fetcher.validate_url_for_fetch",
            side_effect=lambda u: (u, "127.0.0.1", ["127.0.0.1"]),
        ), pytest.raises(FetchError, match="Content type"):
            await fetch_url(f"{server.base_url}/bin")

    @pytest.mark.asyncio
    async def test_redirect_to_private_blocked(self) -> None:
        from unittest.mock import patch

        handler = make_handler(
            routes={
                "/go": {"redirect": "http://127.0.0.1/secret", "status": 302},
            }
        )
        with LocalHttpServer(handler) as server:
            # First hop allowed (patched); second hop uses real validation.
            def validate(u: str):
                if "127.0.0.1" in u and "/secret" in u:
                    from app.ingestion.ssrf import SSRFError

                    raise SSRFError(detail="Blocked IP address: 127.0.0.1")
                if u.startswith(server.base_url):
                    return u, "127.0.0.1", ["127.0.0.1"]
                from app.ingestion.ssrf import validate_url_for_fetch as real

                return real(u)

            with patch(
                "app.ingestion.fetcher.validate_url_for_fetch",
                side_effect=validate,
            ), pytest.raises(FetchError, match="Redirect target blocked"):
                await fetch_url(f"{server.base_url}/go")

    @pytest.mark.asyncio
    async def test_conditional_not_modified(self) -> None:
        from unittest.mock import patch

        handler = make_handler(
            routes={
                "/etag": {
                    "status": 200,
                    "body": b"v1",
                    "headers": {
                        "Content-Type": "text/plain",
                        "ETag": '"abc123"',
                    },
                }
            }
        )
        with LocalHttpServer(handler) as server, patch(
            "app.ingestion.fetcher.validate_url_for_fetch",
            side_effect=lambda u: (u, "127.0.0.1", ["127.0.0.1"]),
        ):
            doc = await fetch_url(
                f"{server.base_url}/etag",
                FetchPolicy(etag='"abc123"'),
            )
            assert doc.not_modified is True
            assert doc.status_code == 304

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        import time
        from unittest.mock import patch

        def slow_body(handler):  # type: ignore[no-untyped-def]
            time.sleep(2)
            return b"late"

        handler = make_handler(
            routes={
                "/slow": {
                    "status": 200,
                    "body": slow_body,
                    "headers": {"Content-Type": "text/plain"},
                }
            }
        )
        with LocalHttpServer(handler) as server, patch(
            "app.ingestion.fetcher.validate_url_for_fetch",
            side_effect=lambda u: (u, "127.0.0.1", ["127.0.0.1"]),
        ), pytest.raises(FetchError, match="timed out"):
            await fetch_url(
                f"{server.base_url}/slow",
                FetchPolicy(timeout_seconds=0.3),
            )


class TestBrowserEligibility:
    def test_spa_shell_detected(self) -> None:
        from app.ingestion.fetcher import FetchedDocument

        html = b'<html><body><div id="root"></div><script></script><script></script></body></html>'
        doc = FetchedDocument(
            url="http://x",
            final_url="http://x",
            status_code=200,
            content_type="text/html",
            body=html,
        )
        assert browser_fallback_eligible(doc) is True

    def test_static_page_not_browser(self) -> None:
        from app.ingestion.fetcher import FetchedDocument

        html = (
            b"<html><body><p>Lots of static content about a hackathon "
            b"deadline and prizes for everyone reading.</p></body></html>"
        )
        doc = FetchedDocument(
            url="http://x",
            final_url="http://x",
            status_code=200,
            content_type="text/html",
            body=html,
        )
        assert browser_fallback_eligible(doc) is False
