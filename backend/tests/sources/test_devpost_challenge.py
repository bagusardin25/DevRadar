"""Devpost listing API answering with a Cloudflare bot check (no network).

The listing API worked on 2026-11-09 and 2026-11-13 while event pages were
challenged; if the API is ever challenged too, the connector must stop and
flag itself blocked rather than parse the challenge.
"""

from __future__ import annotations

import pytest

from app.ingestion.fetcher import BotChallengeError
from app.sources.connectors.base import ConnectorQuery
from app.sources.connectors.devpost import DevpostConnector
from app.sources.connectors.directory_common import block_reason_for_error
from tests.challenge_pages import CHALLENGE_403, allow_fixture_hosts, mock_fetch_url


async def test_live_listing_challenge_blocks_the_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_fixture_hosts(monkeypatch)
    monkeypatch.setattr(
        "app.sources.connectors.directory_common.fetch_url", mock_fetch_url(CHALLENGE_403)
    )
    connector = DevpostConnector()

    page = await connector.discover(ConnectorQuery(module="hackathon", result_cap=10))

    assert page.items == []
    assert connector.blocked is True
    assert connector.degraded is None


async def test_injected_http_get_raising_a_challenge_blocks_the_connector() -> None:
    async def http_get(url: str) -> str:
        raise BotChallengeError(url, 200, "title:Just a moment...")

    connector = DevpostConnector(http_get=http_get)
    page = await connector.discover(ConnectorQuery(module="hackathon", result_cap=10))

    assert page.items == []
    assert connector.blocked is True


def test_block_reason_uses_the_challenge_reason() -> None:
    exc = BotChallengeError("https://devpost.com/api/hackathons", 403, "cf-mitigated:challenge")
    assert block_reason_for_error(exc) == "cf-mitigated:challenge"
