"""Operator webhook signing and delivery tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.alerts.webhook import build_webhook_body, deliver_webhook, sign_body
from app.catalog.enums import ListingKind, VerificationStatus
from app.config import Settings


def _listing() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        slug="test-hack",
        title="Test Hack",
        description="desc",
        kind=ListingKind.HACKATHON,
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        confidence_score=0.9,
        search_extra="",
        hackathon=SimpleNamespace(
            mode="online",
            prize_value=1000,
            prize_currency="USD",
            prize_label="",
            technologies=["Python"],
            registration_deadline=None,
            submission_deadline=None,
            official_url="https://example.com",
            organizer="Org",
            eligible_countries=[],
            eligibility=[],
            location=None,
        ),
        ai_offer=None,
    )


class TestWebhookHelpers:
    def test_sign_body(self) -> None:
        sig = sign_body(b'{"a":1}', "secret")
        assert len(sig) == 64
        assert sig == sign_body(b'{"a":1}', "secret")
        assert sig != sign_body(b'{"a":2}', "secret")

    def test_build_body(self) -> None:
        body = build_webhook_body(_listing())  # type: ignore[arg-type]
        assert body["event"] == "listing.match"
        assert body["listing"]["slug"] == "test-hack"
        assert body["listing"]["hackathon"]["mode"] == "online"


class TestDeliverWebhook:
    @pytest.mark.asyncio
    async def test_skips_when_url_empty(self) -> None:
        settings = Settings(webhook_url="")
        result = await deliver_webhook(settings, _listing())  # type: ignore[arg-type]
        assert result["skipped"] is True

    @pytest.mark.asyncio
    async def test_posts_json_with_signature(self) -> None:
        captured: dict[str, httpx.Request] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            settings = Settings(
                webhook_url="https://hooks.example.test/devradar",
                webhook_secret="whsec_test",
                webhook_filter_json="",
            )
            result = await deliver_webhook(
                settings, _listing(), client=client  # type: ignore[arg-type]
            )
        assert result["ok"] is True
        req = captured["request"]
        assert "application/json" in req.headers.get("content-type", "")
        assert req.headers.get("x-devradar-signature", "").startswith("sha256=")

    @pytest.mark.asyncio
    async def test_filter_mismatch_skips(self) -> None:
        called = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            called["n"] += 1
            return httpx.Response(200)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            settings = Settings(
                webhook_url="https://hooks.example.test/devradar",
                webhook_filter_json='{"kind":"ai_offer"}',
            )
            result = await deliver_webhook(
                settings, _listing(), client=client  # type: ignore[arg-type]
            )
        assert result["skipped"] is True
        assert result["reason"] == "filter_mismatch"
        assert called["n"] == 0
