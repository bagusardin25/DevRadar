"""Admin review queue transitions with optimistic concurrency and audit log."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.models import AdminAuditLog
from app.auth.sessions import AdminIdentity
from app.catalog.enums import ActorType, ReviewItemState, VerificationStatus
from app.catalog.models import Listing
from app.errors import ConflictError, NotFoundError
from app.ingestion.models import VerificationEvent
from app.review.models import ReviewItem
from app.review.schemas import (
    ApproveReviewRequest,
    MergeReviewRequest,
    RejectReviewRequest,
    ReviewItemPublic,
)

_MUTABLE_STATES = frozenset(
    {ReviewItemState.OPEN.value, ReviewItemState.IN_PROGRESS.value}
)


def _state_value(state: object) -> str:
    return state.value if hasattr(state, "value") else str(state)


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
            snapshot.update(command.corrections)
            item.candidate_snapshot = snapshot

        if item.listing_id is not None:
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
