"""Import all ORM models so metadata is complete for Alembic and tests."""

from app.audit.models import AdminAuditLog
from app.catalog.models import AIOffer, Hackathon, Listing
from app.ingestion.models import (
    CrawlRun,
    DiscoverySignal,
    ExtractionRun,
    ListingSource,
    RawDocument,
    VerificationEvent,
)
from app.review.models import ReviewItem
from app.sources.models import Source, SourceQuery
from app.submissions.models import CommunitySubmission

__all__ = [
    "AdminAuditLog",
    "AIOffer",
    "CommunitySubmission",
    "CrawlRun",
    "DiscoverySignal",
    "ExtractionRun",
    "Hackathon",
    "Listing",
    "ListingSource",
    "RawDocument",
    "ReviewItem",
    "Source",
    "SourceQuery",
    "VerificationEvent",
]
