"""API tests for admin review mutations."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.google import FakeGoogleOAuthClient, GoogleUser
from app.auth.sessions import CSRF_HEADER, SESSION_COOKIE, InMemorySessionStore
from app.catalog.enums import ReviewCandidateType, ReviewItemState, VerificationStatus
from app.config import Settings
from app.db import create_engine, create_session_maker
from app.main import create_app
from app.review.models import ReviewItem
from tests.factories import seed_hackathon


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
async def db_session() -> AsyncSession:
    settings = Settings()
    engine = create_engine(settings)
    maker = create_session_maker(engine)
    async with maker() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def api_client(settings: Settings):
    store = InMemorySessionStore()
    oauth = FakeGoogleOAuthClient(
        users_by_code={
            "good-code": GoogleUser(
                id="111", email="admin@example.com", email_verified=True
            )
        }
    )
    app = create_app(settings)
    app.state.session_store = store
    app.state.google_oauth = oauth
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        follow_redirects=False,
    ) as client:
        yield client


async def _login(client: httpx.AsyncClient) -> tuple[str, str]:
    start = await client.get("/api/v1/admin/auth/google/start")
    state = start.json()["state"]
    cb = await client.get(
        "/api/v1/admin/auth/google/callback",
        params={"code": "good-code", "state": state},
    )
    cookie = cb.cookies[SESSION_COOKIE]
    me = await client.get(
        "/api/v1/admin/auth/me",
        cookies={SESSION_COOKIE: cookie},
    )
    return cookie, me.json()["csrfToken"]


class TestReviewAPI:
    async def test_list_requires_auth(self, api_client) -> None:
        response = await api_client.get("/api/v1/admin/review-items")
        assert response.status_code == 401

    async def test_approve_reject_merge_flow(
        self, api_client, db_session: AsyncSession
    ) -> None:
        cookie, csrf = await _login(api_client)
        headers = {
            CSRF_HEADER: csrf,
            "Origin": "http://localhost:5173",
        }
        cookies = {SESSION_COOKIE: cookie}

        listing = await seed_hackathon(
            db_session,
            slug=f"api-rv-{uuid4().hex[:8]}",
            title="API Review Listing",
            status=VerificationStatus.NEEDS_REVIEW,
        )
        item = ReviewItem(
            candidate_type=ReviewCandidateType.LISTING,
            candidate_snapshot={"title": "API Review Listing"},
            reason="auto score incomplete",
            priority=20,
            state=ReviewItemState.OPEN,
            listing_id=listing.id,
            version=1,
        )
        db_session.add(item)
        await db_session.commit()

        listed = await api_client.get(
            "/api/v1/admin/review-items",
            cookies=cookies,
        )
        assert listed.status_code == 200
        assert listed.json()["total"] >= 1

        detail = await api_client.get(
            f"/api/v1/admin/review-items/{item.id}",
            cookies=cookies,
        )
        assert detail.status_code == 200
        assert detail.json()["version"] == 1

        # Stale version
        conflict = await api_client.post(
            f"/api/v1/admin/review-items/{item.id}/approve",
            json={"expectedVersion": 99},
            cookies=cookies,
            headers=headers,
        )
        assert conflict.status_code == 409

        # Missing CSRF
        no_csrf = await api_client.post(
            f"/api/v1/admin/review-items/{item.id}/approve",
            json={"expectedVersion": 1},
            cookies=cookies,
            headers={"Origin": "http://localhost:5173"},
        )
        assert no_csrf.status_code == 403

        approved = await api_client.post(
            f"/api/v1/admin/review-items/{item.id}/approve",
            json={"expectedVersion": 1, "notes": "Looks good"},
            cookies=cookies,
            headers=headers,
        )
        assert approved.status_code == 200
        body = approved.json()
        assert body["item"]["state"] == "approved"
        assert body["item"]["version"] == 2

        # Second item for reject
        item2 = ReviewItem(
            candidate_type=ReviewCandidateType.COMMUNITY_SUBMISSION,
            candidate_snapshot={"url": "https://example.com/x"},
            reason="suspicious",
            state=ReviewItemState.OPEN,
            version=1,
        )
        db_session.add(item2)
        await db_session.commit()

        rejected = await api_client.post(
            f"/api/v1/admin/review-items/{item2.id}/reject",
            json={"expectedVersion": 1, "reason": "Not relevant"},
            cookies=cookies,
            headers=headers,
        )
        assert rejected.status_code == 200
        assert rejected.json()["item"]["state"] == "rejected"

        # Merge
        target = await seed_hackathon(
            db_session,
            slug=f"api-mg-{uuid4().hex[:8]}",
            title="Merge Target API",
            status=VerificationStatus.VERIFIED_ACTIVE,
        )
        item3 = ReviewItem(
            candidate_type=ReviewCandidateType.LISTING,
            candidate_snapshot={},
            reason="dup",
            state=ReviewItemState.OPEN,
            version=1,
        )
        db_session.add(item3)
        await db_session.commit()

        merged = await api_client.post(
            f"/api/v1/admin/review-items/{item3.id}/merge",
            json={
                "expectedVersion": 1,
                "targetListingId": str(target.id),
                "notes": "same hackathon",
            },
            cookies=cookies,
            headers=headers,
        )
        assert merged.status_code == 200
        assert merged.json()["item"]["state"] == "merged"

        await db_session.delete(item)
        await db_session.delete(item2)
        await db_session.delete(item3)
        await db_session.delete(listing)
        await db_session.delete(target)
        await db_session.commit()
