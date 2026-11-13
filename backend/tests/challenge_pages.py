"""Fixture responses for Devpost bot-check tests (no network).

``*.devpost.com`` event pages sometimes answer scripts with Cloudflare's
"Just a moment..." challenge (seen 2026-11-09, gone again 2026-11-13). It is
intermittent, so tests replay recorded-shape fixtures through the real
:func:`app.ingestion.fetcher.fetch_url` over an ``httpx.MockTransport``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.ingestion.fetcher import FetchedDocument, FetchPolicy, fetch_url

FIXTURES = Path(__file__).parent / "fixtures" / "devpost"
CHALLENGE_HTML = (FIXTURES / "cloudflare_challenge.html").read_bytes()
EVENT_HTML = (FIXTURES / "event_page.html").read_bytes()

EVENT_URL = "https://kiroween.devpost.com/"
HTML = "text/html; charset=UTF-8"
CHALLENGE_HEADERS = {"content-type": HTML, "cf-mitigated": "challenge", "server": "cloudflare"}

#: (status, headers, body)
Reply = tuple[int, dict[str, str], bytes]

CHALLENGE_403: Reply = (403, CHALLENGE_HEADERS, CHALLENGE_HTML)
# Older JavaScript challenge: 503, no cf-mitigated header, title only.
CHALLENGE_503: Reply = (
    503,
    {"content-type": HTML, "server": "cloudflare"},
    b"<!DOCTYPE html><html><head><title>Just a moment...</title></head>"
    b"<body><noscript>Enable JavaScript and cookies to continue</noscript></body></html>",
)
EVENT_200: Reply = (200, {"content-type": HTML}, EVENT_HTML)
NOT_FOUND_404: Reply = (404, {"content-type": HTML}, b"<html><title>Not Found</title></html>")


def allow_fixture_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip DNS in the SSRF guard: the fixture hosts are never contacted."""

    def _validate(url: str) -> tuple[str, str, list[str]]:
        return url, httpx.URL(url).host, ["93.184.216.34"]

    monkeypatch.setattr("app.ingestion.fetcher.validate_url_for_fetch", _validate)


def mock_fetch_url(
    reply: Reply,
    calls: list[str] | None = None,
) -> Callable[..., Awaitable[FetchedDocument]]:
    """A stand-in for ``fetch_url`` that runs the real one over a fixture reply."""
    status, headers, body = reply

    def _handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        return httpx.Response(status, headers=headers, content=body)

    async def _fetch(url: str, policy: FetchPolicy | None = None, **_: Any) -> FetchedDocument:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(_handler), follow_redirects=False
        ) as client:
            return await fetch_url(url, policy, client=client)

    return _fetch
