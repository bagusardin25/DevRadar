"""Domain enums aligned with frontend `src/types/index.ts`."""

from enum import StrEnum


class ListingKind(StrEnum):
    """Top-level opportunity kind stored on `listings`."""

    HACKATHON = "hackathon"
    AI_OFFER = "ai_offer"
    # `ai_news` reserved for a future migration.


class VerificationStatus(StrEnum):
    """Verification state machine for published catalogue rows."""

    VERIFIED_ACTIVE = "verified_active"
    LIKELY_ACTIVE = "likely_active"
    NEEDS_REVIEW = "needs_review"
    REGISTRATION_CLOSED = "registration_closed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class HackathonMode(StrEnum):
    """Participation mode for a hackathon."""

    ONLINE = "online"
    HYBRID = "hybrid"
    IN_PERSON = "in_person"


class OfferType(StrEnum):
    """AI deal / offer classification."""

    FREE_CREDITS = "free_credits"
    FREE_TIER = "free_tier"
    TRIAL = "trial"
    STUDENT_PROGRAM = "student_program"
    OPEN_SOURCE_PROGRAM = "open_source_program"
    HACKATHON_CREDITS = "hackathon_credits"
    PROMO_CODE = "promo_code"
    FREE_MODEL = "free_model"
    SELF_HOSTED_WEIGHTS = "self_hosted_weights"


class EffortEstimate(StrEnum):
    """Rough effort band shown on hackathon cards."""

    DAYS_1_2 = "1-2 Days"
    WEEK_1 = "1 Week"
    WEEKS_1_2 = "1-2 Weeks"
    WEEKS_2_3 = "2-3 Weeks"
    MONTH_PLUS = "1 Month+"


class SourceTier(StrEnum):
    """Trust tier for a discovery / provenance source."""

    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class ConnectorType(StrEnum):
    """Ingestion connector identifier."""

    DEVPOST = "devpost"
    MLH = "mlh"
    HACKEREARTH = "hackerearth"
    RSS = "rss"
    OFFICIAL_SITE = "official_site"
    X_RECENT_SEARCH = "x_recent_search"
    REDDIT = "reddit"
    GITHUB = "github"
    MANUAL = "manual"
    COMMUNITY = "community"


class CrawlRunStatus(StrEnum):
    """Lifecycle of a crawl / poll run."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class CrawlTrigger(StrEnum):
    """What started a crawl run."""

    SCHEDULE = "schedule"
    MANUAL = "manual"
    SUBMISSION = "submission"
    LIVE_DISCOVERY = "live_discovery"
    RETRY = "retry"


class DocumentAvailability(StrEnum):
    """Whether raw source material is still available."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RETAINED = "retained"
    PURGED = "purged"


class ExtractionStatus(StrEnum):
    """Outcome of a structured extraction attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    SCHEMA_REJECTED = "schema_rejected"


class ReviewItemState(StrEnum):
    """Admin review queue state."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    MERGED = "merged"
    DEFERRED = "deferred"


class ReviewCandidateType(StrEnum):
    """What kind of candidate sits in the review queue."""

    LISTING = "listing"
    DISCOVERY_SIGNAL = "discovery_signal"
    COMMUNITY_SUBMISSION = "community_submission"
    EXTRACTION = "extraction"


class ActorType(StrEnum):
    """Who caused a verification or audit event."""

    SYSTEM = "system"
    ADMIN = "admin"
    PIPELINE = "pipeline"
    USER = "user"
