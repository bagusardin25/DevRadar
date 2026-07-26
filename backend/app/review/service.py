"""Admin review queue transitions with optimistic concurrency and audit log."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.models import AdminAuditLog
from app.auth.sessions import AdminIdentity
from app.catalog.builders import build_ai_offer_create, build_hackathon_create
from app.catalog.enums import (
    ActorType,
    ListingKind,
    ReviewCandidateType,
    ReviewItemState,
    SubmissionState,
    VerificationStatus,
)
from app.catalog.models import Listing
from app.catalog.repository import ListingRepository
from app.catalog.schemas import ListingCreateSchema
from app.errors import ConflictError, NotFoundError, ValidationError
from app.ingestion.models import VerificationEvent
from app.ingestion.pipeline import slugify_title
from app.review.models import ReviewItem
from app.review.schemas import (
    ApproveReviewRequest,
    MergeReviewRequest,
    RejectReviewRequest,
    ReviewItemPublic,
)
from app.submissions.models import CommunitySubmission

_MUTABLE_STATES = frozenset(
    {ReviewItemState.OPEN.value, ReviewItemState.IN_PROGRESS.value}
)

# An admin vouching for a URL is stronger than an unscored candidate but weaker
# than a full deterministic verification run, which can reach 1.0.
ADMIN_APPROVAL_CONFIDENCE = Decimal("0.75")

_URL_SNAPSHOT_KEYS = ("officialUrl", "url", "canonical_url", "claimUrl", "originalUrl")
_URL_FIELD_KEYS = ("official_url", "official_terms_url", "claim_url")


def _state_value(state: object) -> str:
    return state.value if hasattr(state, "value") else str(state)


def _resolve_listing_kind(
    snapshot: dict[str, Any], fields: dict[str, Any]
) -> ListingKind | None:
    for key in ("kind", "claimedType", "claimed_type"):
        raw = snapshot.get(key) or fields.get(key)
        if not raw:
            continue
        try:
            return ListingKind(str(raw))
        except ValueError:
            continue
    return None


def _pick_title(snapshot: dict[str, Any], fields: dict[str, Any]) -> str:
    for key in ("title", "claimedTitle", "claimed_title", "productName", "product_name"):
        value = snapshot.get(key) or fields.get(key)
        if value:
            return str(value).strip()
    return ""


def _pick_url(snapshot: dict[str, Any], fields: dict[str, Any]) -> str:
    for key in _URL_SNAPSHOT_KEYS:
        value = snapshot.get(key)
        if value:
            return str(value).strip()
    for key in _URL_FIELD_KEYS:
        value = fields.get(key)
        if value:
            return str(value).strip()
    return ""


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ListingRepository(session)

    async def list_items(
        self,
        *,
        state: ReviewItemState | None = None,
        limit: int = 50,
    ) -> tuple[list[ReviewItem], int]:
        filters = []
        if state is not None:
            filters.append(ReviewItem.state == state.value)
        base = select(ReviewItem).where(*filters) if filters else select(ReviewItem)
        rows = list((await self._session.execute(base)).scalars().all())
        total = len(rows)
        ordered = sorted(
            rows,
            key=lambda r: (-r.priority, r.created_at),
        )[: min(limit, 100)]
        return ordered, total

    async def get_item(self, item_id: UUID) -> ReviewItem:
        result = await self._session.execute(
            select(ReviewItem).where(ReviewItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundError(detail="Review item not found")
        return item

    async def approve_review_item(
        self,
        item_id: UUID,
        command: ApproveReviewRequest,
        admin: AdminIdentity,
        *,
        trace_id: str | None = None,
    ) -> ReviewItem:
        item = await self._load_for_mutation(item_id, command.expected_version)
        self._assert_mutable(item)
        before = self._snapshot(item)
        now = datetime.now(UTC)

        if command.corrections:
            snapshot = dict(item.candidate_snapshot or {})
            corrections = dict(command.corrections)
            # `fields` is merged key-by-key so an admin fixing one date does not
            # wipe everything extraction already found.
            if isinstance(corrections.get("fields"), dict):
                merged_fields = dict(snapshot.get("fields") or {})
                merged_fields.update(corrections.pop("fields"))
                snapshot["fields"] = merged_fields
            snapshot.update(corrections)
            item.candidate_snapshot = snapshot

        if item.listing_id is None:
            # Community submissions arrive with no catalogue row — the admin's
            # approval is what publishes them. Other queue-only candidate types
            # keep the older no-op-approve behavior; there is nothing to publish.
            if _state_value(item.candidate_type) == ReviewCandidateType.COMMUNITY_SUBMISSION.value:
                published = await self._publish_from_snapshot(item, admin, command, now)
                item.listing_id = published.id
        else:
            listing = await self._get_listing(item.listing_id)
            if listing is not None:
                prev = _state_value(listing.verification_status)
                listing.verification_status = VerificationStatus.VERIFIED_ACTIVE
                listing.published_at = now
                listing.last_checked_at = now
                if command.corrections.get("title"):
                    listing.title = str(command.corrections["title"])
                if command.corrections.get("description"):
                    listing.description = str(command.corrections["description"])
                self._session.add(
                    VerificationEvent(
                        listing_id=listing.id,
                        event_type="admin_approve",
                        previous_status=prev,
                        new_status=VerificationStatus.VERIFIED_ACTIVE,
                        notes=command.notes or "Approved by admin",
                        actor_type=ActorType.ADMIN,
                        actor_id=admin.github_id,
                        checked_urls=[],
                        score_breakdown=dict(listing.score_breakdown or {}),
                    )
                )

        item.state = ReviewItemState.APPROVED
        item.assigned_admin_id = admin.github_id
        item.resolution = {
            "action": "approve",
            "notes": command.notes,
            "corrections": command.corrections,
        }
        item.resolved_at = now
        item.version = item.version + 1
        await self._sync_submission_state(item, SubmissionState.ACCEPTED)

        self._write_audit(
            admin,
            action="review.approve",
            target_type="review_item",
            target_id=item.id,
            before=before,
            after=self._snapshot(item),
            trace_id=trace_id,
        )
        await self._session.flush()
        await self._session.refresh(item)
        return item

    async def reject_review_item(
        self,
        item_id: UUID,
        command: RejectReviewRequest,
        admin: AdminIdentity,
        *,
        trace_id: str | None = None,
    ) -> ReviewItem:
        item = await self._load_for_mutation(item_id, command.expected_version)
        self._assert_mutable(item)
        before = self._snapshot(item)

        item.state = ReviewItemState.REJECTED
        item.assigned_admin_id = admin.github_id
        item.resolution = {"action": "reject", "reason": command.reason}
        item.resolved_at = datetime.now(UTC)
        item.version = item.version + 1
        item.reason = command.reason
        await self._sync_submission_state(item, SubmissionState.REJECTED)

        self._write_audit(
            admin,
            action="review.reject",
            target_type="review_item",
            target_id=item.id,
            before=before,
            after=self._snapshot(item),
            trace_id=trace_id,
        )
        await self._session.flush()
        await self._session.refresh(item)
        return item

    async def merge_review_item(
        self,
        item_id: UUID,
        command: MergeReviewRequest,
        admin: AdminIdentity,
        *,
        trace_id: str | None = None,
    ) -> ReviewItem:
        item = await self._load_for_mutation(item_id, command.expected_version)
        self._assert_mutable(item)
        before = self._snapshot(item)

        target = await self._get_listing(command.target_listing_id)
        if target is None:
            raise NotFoundError(detail="Target listing not found")

        target_status = _state_value(target.verification_status)
        item.state = ReviewItemState.MERGED
        item.assigned_admin_id = admin.github_id
        item.listing_id = target.id
        item.resolution = {
            "action": "merge",
            "targetListingId": str(target.id),
            "notes": command.notes,
        }
        item.resolved_at = datetime.now(UTC)
        item.version = item.version + 1
        # The opportunity is in the catalogue, just under an existing row.
        await self._sync_submission_state(item, SubmissionState.ACCEPTED)

        self._session.add(
            VerificationEvent(
                listing_id=target.id,
                event_type="admin_merge",
                previous_status=None,
                new_status=target_status,
                notes=command.notes or f"Merged review item {item.id}",
                actor_type=ActorType.ADMIN,
                actor_id=admin.github_id,
                checked_urls=[],
                score_breakdown=dict(target.score_breakdown or {}),
            )
        )

        self._write_audit(
            admin,
            action="review.merge",
            target_type="review_item",
            target_id=item.id,
            before=before,
            after=self._snapshot(item),
            trace_id=trace_id,
        )
        await self._session.flush()
        await self._session.refresh(item)
        return item

    async def _publish_from_snapshot(
        self,
        item: ReviewItem,
        admin: AdminIdentity,
        command: ApproveReviewRequest,
        now: datetime,
    ) -> Listing:
        """Publish a listing from a queue-only candidate (no prior listing row).

        Community submissions arrive with a URL + optional title/type; the admin
        supplies whatever else is missing via ``corrections`` before approving.
        Everything the approve endpoint validates flows through here.
        """
        snapshot = dict(item.candidate_snapshot or {})
        fields = dict(snapshot.get("fields") or {})

        kind = _resolve_listing_kind(snapshot, fields)
        if kind is None:
            raise ValidationError(
                detail=(
                    "Cannot publish: 'kind' (hackathon | ai_offer) is required. "
                    "Pass it via corrections.kind on approve."
                )
            )

        title = _pick_title(snapshot, fields)
        if not title:
            raise ValidationError(
                detail=(
                    "Cannot publish: title is required. "
                    "Pass it via corrections.title on approve."
                )
            )

        url = _pick_url(snapshot, fields)
        if not url:
            raise ValidationError(
                detail=(
                    "Cannot publish: an official URL is required. "
                    "Pass it via corrections.fields.official_url on approve."
                )
            )

        description = str(snapshot.get("description") or fields.get("description") or "")
        source_hint = str(snapshot.get("source") or "review_publish")
        score_breakdown = {
            "source": source_hint,
            "publishedVia": "admin_approval",
            "reviewItemId": str(item.id),
            "adminId": admin.github_id,
            "notes": command.notes,
        }

        listing_data = ListingCreateSchema(
            kind=kind,
            slug=slugify_title(title),
            title=title,
            description=description,
            verification_status=VerificationStatus.VERIFIED_ACTIVE,
            confidence_score=ADMIN_APPROVAL_CONFIDENCE,
            score_breakdown=score_breakdown,
            published_at=now,
            last_checked_at=now,
        )

        if kind == ListingKind.HACKATHON:
            listing = await self._repo.create_hackathon(
                listing_data,
                build_hackathon_create(fields, official_url=url),
            )
        else:
            listing = await self._repo.create_ai_offer(
                listing_data,
                build_ai_offer_create(fields, official_url=url, title=title),
            )

        self._session.add(
            VerificationEvent(
                listing_id=listing.id,
                event_type="admin_approve_publish",
                previous_status=None,
                new_status=VerificationStatus.VERIFIED_ACTIVE,
                notes=command.notes or f"Published from review item {item.id}",
                actor_type=ActorType.ADMIN,
                actor_id=admin.github_id,
                checked_urls=[url],
                score_breakdown=score_breakdown,
            )
        )
        return listing

    async def _sync_submission_state(
        self, item: ReviewItem, new_state: SubmissionState
    ) -> None:
        """Reflect the admin's decision on the underlying community_submission.

        Silent no-op for non-submission items; the tracking-id endpoint reads
        this state so submitters see their tip's real fate.
        """
        if _state_value(item.candidate_type) != ReviewCandidateType.COMMUNITY_SUBMISSION.value:
            return
        if item.candidate_id is None:
            return
        submission = await self._session.get(CommunitySubmission, item.candidate_id)
        if submission is None:
            return
        submission.state = new_state

    async def _load_for_mutation(
        self, item_id: UUID, expected_version: int
    ) -> ReviewItem:
        item = await self.get_item(item_id)
        if item.version != expected_version:
            raise ConflictError(
                detail=(
                    f"Version conflict: expected {expected_version}, "
                    f"current {item.version}"
                )
            )
        return item

    @staticmethod
    def _assert_mutable(item: ReviewItem) -> None:
        state_val = _state_value(item.state)
        if state_val not in _MUTABLE_STATES:
            raise ConflictError(detail=f"Cannot mutate item in state {state_val}")

    async def _get_listing(self, listing_id: UUID) -> Listing | None:
        result = await self._session.execute(
            select(Listing)
            .where(Listing.id == listing_id)
            .options(
                selectinload(Listing.hackathon),
                selectinload(Listing.ai_offer),
            )
        )
        return result.scalar_one_or_none()

    def _write_audit(
        self,
        admin: AdminIdentity,
        *,
        action: str,
        target_type: str,
        target_id: UUID | None,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        trace_id: str | None,
    ) -> None:
        self._session.add(
            AdminAuditLog(
                actor_id=admin.github_id,
                actor_login=admin.login,
                action=action,
                target_type=target_type,
                target_id=target_id,
                before_json=before,
                after_json=after,
                request_trace_id=trace_id,
            )
        )

    @staticmethod
    def _snapshot(item: ReviewItem) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "state": _state_value(item.state),
            "version": item.version,
            "listing_id": str(item.listing_id) if item.listing_id else None,
            "reason": item.reason,
            "resolution": item.resolution,
        }

    @staticmethod
    def to_public(item: ReviewItem) -> ReviewItemPublic:
        return ReviewItemPublic.model_validate(item)
