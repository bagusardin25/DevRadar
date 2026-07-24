"""Import all ORM models so metadata is complete for Alembic and tests."""

from app.alerts.models import AlertSubscription, NotificationDelivery
from app.audit.models import AdminAuditLog
from app.auth.models import AdminUser
from app.catalog.models import AIOffer, Hackathon, Listing
from app.discovery.models import LiveDiscoveryRun
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
    "AdminUser",
    "AIOffer",
    "AlertSubscription",
    "CommunitySubmission",
    "NotificationDelivery",
    "CrawlRun",
    "DiscoverySignal",
    "ExtractionRun",
    "Hackathon",
    "Listing",
    "ListingSource",
    "LiveDiscoveryRun",
    "RawDocument",
    "ReviewItem",
    "Source",
    "SourceQuery",
    "VerificationEvent",
]
