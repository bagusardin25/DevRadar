"""Top-level API router composition."""

from fastapi import APIRouter

from app.api.admin import auth as admin_auth
from app.api.admin import review as admin_review
from app.api.public import ai_offers, hackathons, search, submissions

api_router = APIRouter()
api_router.include_router(hackathons.router)
api_router.include_router(ai_offers.router)
api_router.include_router(search.router)
api_router.include_router(submissions.router)
api_router.include_router(admin_auth.router)
api_router.include_router(admin_review.router)
