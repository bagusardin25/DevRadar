"""API coverage for authenticated catalogue CRUD."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from app.auth.google import FakeGoogleOAuthClient, GoogleUser
from app.auth.sessions import CSRF_HEADER, SESSION_COOKIE, InMemorySessionStore
from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        admin_google_emails=["admin@example.com"],
        frontend_url="http://localhost:5173",
        cors_origins=["http://localhost:5173"],
        google_client_id="test-client",
        google_client_secret="test-secret",
    )


@pytest.fixture
async def api_client(settings: Settings):
    app = create_app(settings)
    app.state.session_store = InMemorySessionStore()
    app.state.google_oauth = FakeGoogleOAuthClient(
        users_by_code={
            "good-code": GoogleUser(
                id="catalog-admin",
                email="admin@example.com",
                email_verified=True,
            )
        }
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        yield client


async def _login(client: httpx.AsyncClient) -> tuple[dict[str, str], dict[str, str]]:
    start = await client.get("/api/v1/admin/auth/google/start")
    callback = await client.get(
        "/api/v1/admin/auth/google/callback",
        params={"code": "good-code", "state": start.json()["state"]},
    )
    cookie = callback.cookies[SESSION_COOKIE]
    cookies = {SESSION_COOKIE: cookie}
    me = await client.get("/api/v1/admin/auth/me", cookies=cookies)
    headers = {
        CSRF_HEADER: me.json()["csrfToken"],
        "Origin": "http://localhost:5173",
    }
    return cookies, headers


def _hackathon_payload(slug: str) -> dict[str, object]:
    return {
        "listing": {
            "slug": slug,
            "title": "Admin Managed Hackathon",
            "description": "Created from the operator catalogue manager.",
            "verificationStatus": "verified_active",
            "confidenceScore": 0.96,
        },
        "hackathon": {
            "organizer": "DevRadar Labs",
            "organizerLogo": "https://example.com/logo.png",
            "registrationOpenAt": "2026-07-01T00:00:00Z",
            "registrationDeadline": "2026-08-15T23:59:00Z",
            "submissionDeadline": "2026-08-20T23:59:00Z",
            "mode": "online",
            "location": "Worldwide",
            "eligibleCountries": ["Worldwide"],
            "eligibility": ["Developers"],
            "teamMin": 1,
            "teamMax": 5,
            "prizeValue": 25000,
            "prizeCurrency": "USD",
            "prizeLabel": "$25K prize pool",
            "technologies": ["AI", "Python"],
            "officialUrl": "https://example.com/admin-hackathon",
            "suitableReasons": ["Online", "Open worldwide"],
            "effortEstimate": "1-2 Weeks",
        },
    }


def _ai_offer_payload(slug: str) -> dict[str, object]:
    return {
        "listing": {
            "slug": slug,
            "title": "Admin AI Credits",
            "description": "Developer credits managed by an operator.",
            "verificationStatus": "verified_active",
            "confidenceScore": 0.91,
        },
        "aiOffer": {
            "productName": "Builder Cloud AI",
            "provider": "Builder Cloud",
            "providerLogo": "https://example.com/provider.png",
            "offerType": "free_credits",
            "offerValue": "$100 credits",
            "targetUsers": ["Developers", "Students"],
            "requirements": ["Verified email"],
            "startsAt": "2026-07-01T00:00:00Z",
            "expiresAt": "2026-12-31T23:59:00Z",
            "supportedRegions": ["Worldwide"],
            "officialTermsUrl": "https://example.com/terms",
            "claimUrl": "https://example.com/claim",
            "tags": ["credits", "ai"],
            "suitableReasons": ["No credit card"],
        },
    }


class TestAdminCatalogueAPI:
    async def test_reads_and_writes_require_admin_session(self, api_client) -> None:
        listed = await api_client.get("/api/v1/admin/catalogue/hackathons")
        assert listed.status_code == 401

        cookies, _headers = await _login(api_client)
        no_csrf = await api_client.post(
            "/api/v1/admin/catalogue/hackathons",
            json=_hackathon_payload(f"no-csrf-{uuid4().hex[:8]}"),
            cookies=cookies,
            headers={"Origin": "http://localhost:5173"},
        )
        assert no_csrf.status_code == 403

    async def test_hackathon_crud(self, api_client) -> None:
        cookies, headers = await _login(api_client)
        slug = f"admin-hack-{uuid4().hex[:8]}"
        created = await api_client.post(
            "/api/v1/admin/catalogue/hackathons",
            json=_hackathon_payload(slug),
            cookies=cookies,
            headers=headers,
        )
        assert created.status_code == 201
        body = created.json()
        listing_id = body["listing"]["id"]
        assert body["listing"]["slug"] == slug
        assert body["hackathon"]["teamMax"] == 5

        listed = await api_client.get(
            "/api/v1/admin/catalogue/hackathons",
            params={"q": slug},
            cookies=cookies,
        )
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

        update_payload = _hackathon_payload(slug)
        update_payload["listing"]["title"] = "Updated Admin Hackathon"  # type: ignore[index]
        update_payload["hackathon"]["prizeLabel"] = "Updated prize"  # type: ignore[index]
        updated = await api_client.put(
            f"/api/v1/admin/catalogue/hackathons/{listing_id}",
            json=update_payload,
            cookies=cookies,
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["listing"]["title"] == "Updated Admin Hackathon"
        assert updated.json()["hackathon"]["prizeLabel"] == "Updated prize"

        public = await api_client.get(f"/api/v1/hackathons/{slug}")
        assert public.status_code == 200
        assert public.json()["title"] == "Updated Admin Hackathon"

        deleted = await api_client.delete(
            f"/api/v1/admin/catalogue/hackathons/{listing_id}",
            cookies=cookies,
            headers=headers,
        )
        assert deleted.status_code == 204
        assert (await api_client.get(f"/api/v1/hackathons/{slug}")).status_code == 404

    async def test_ai_offer_crud(self, api_client) -> None:
        cookies, headers = await _login(api_client)
        slug = f"admin-offer-{uuid4().hex[:8]}"
        created = await api_client.post(
            "/api/v1/admin/catalogue/ai-offers",
            json=_ai_offer_payload(slug),
            cookies=cookies,
            headers=headers,
        )
        assert created.status_code == 201
        body = created.json()
        listing_id = body["listing"]["id"]
        assert body["aiOffer"]["offerValue"] == "$100 credits"

        listed = await api_client.get(
            "/api/v1/admin/catalogue/ai-offers",
            params={"q": "Builder Cloud"},
            cookies=cookies,
        )
        assert listed.status_code == 200
        assert any(item["listing"]["id"] == listing_id for item in listed.json()["items"])

        update_payload = _ai_offer_payload(slug)
        update_payload["aiOffer"]["offerValue"] = "$200 credits"  # type: ignore[index]
        updated = await api_client.put(
            f"/api/v1/admin/catalogue/ai-offers/{listing_id}",
            json=update_payload,
            cookies=cookies,
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["aiOffer"]["offerValue"] == "$200 credits"

        public = await api_client.get(f"/api/v1/ai-offers/{slug}")
        assert public.status_code == 200
        assert public.json()["offerValue"] == "$200 credits"

        deleted = await api_client.delete(
            f"/api/v1/admin/catalogue/ai-offers/{listing_id}",
            cookies=cookies,
            headers=headers,
        )
        assert deleted.status_code == 204
        assert (await api_client.get(f"/api/v1/ai-offers/{slug}")).status_code == 404
