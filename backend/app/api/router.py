"""Top-level API router composition."""

from fastapi import APIRouter

from app.api.admin import auth as admin_auth
from app.api.admin import catalogue as admin_catalogue
from app.api.admin import pipeline as admin_pipeline
from app.api.admin import review as admin_review
from app.api.admin import sources as admin_sources
from app.api.public import ai_offers, alerts, discovery, hackathons, search, submissions

api_router = APIRouter()
api_router.include_router(hackathons.router)
api_router.include_router(ai_offers.router)
api_router.include_router(search.router)
api_router.include_router(submissions.router)
api_router.include_router(alerts.router)
api_router.include_router(discovery.router)
api_router.include_router(admin_auth.router)
api_router.include_router(admin_catalogue.router)
api_router.include_router(admin_review.router)
api_router.include_router(admin_sources.router)
api_router.include_router(admin_pipeline.router)
