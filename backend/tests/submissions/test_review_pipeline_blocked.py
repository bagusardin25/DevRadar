"""A submitted Devpost link behind a Cloudflare bot check (no database)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.catalog.enums import (
    ReviewCandidateType,
    ReviewItemState,
    SubmissionState,
)
from app.config import Settings
from app.review.models import ReviewItem
from app.submissions.models import CommunitySubmission
from app.submissions.review_pipeline import apply_submission_review
from tests.challenge_pages import EVENT_URL

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)


class _One:
    def __init__(self, row: Any) -> None:
        self._row = row

    def scalar_one_or_none(self) -> Any:
        return self._row


class _Session:
    """Answers the submission lookup, then the review-item lookup."""

    def __init__(self, *rows: Any) -> None:
        self._rows = list(rows)

    async def execute(self, _statement: Any) -> _One:
        return _One(self._rows.pop(0))

    async def flush(self) -> None:
        return None


def _submission_and_item() -> tuple[CommunitySubmission, ReviewItem]:
    submission = CommunitySubmission(
        id=uuid4(),
        tracking_id="tracking",
        original_url=EVENT_URL,
        canonical_url=EVENT_URL,
        claimed_type="hackathon",
        claimed_title="Kiroween Online Hack 2026",
        ip_hash="hash",
        job_idempotency_key="job-key",
        metadata_json={},
        state=SubmissionState.REVIEWING,
    )
    item = ReviewItem(
        candidate_type=ReviewCandidateType.COMMUNITY_SUBMISSION,
        candidate_id=submission.id,
        candidate_snapshot={"title": "Kiroween Online Hack 2026"},
        reason="Community submission",
        priority=50,
        state=ReviewItemState.OPEN,
        version=1,
    )
    return submission, item


async def test_blocked_submission_gets_a_human_check_review_not_unreachable() -> None:
    submission, item = _submission_and_item()
    fetch_result = {
        "ok": False,
        "blocked": True,
        "needs_human_check": True,
        "block_reason": "cf-mitigated:challenge",
        "status_code": 403,
        "error": "Blocked by a bot check (cf-mitigated:challenge); the page was not read",
        "url": EVENT_URL,
    }

    review = await apply_submission_review(
        _Session(submission, item),  # type: ignore[arg-type]
        submission.id,
        fetch_result,
        settings=Settings(_env_file=None, app_env="test", llm_provider="disabled"),  # type: ignore[call-arg]
        now=NOW,
    )

    assert review is not None
    assert review["recommendation"] == "needs_more_info"
    assert "bot check" in review["summary"]
    assert "could not be fetched" not in review["summary"]
    snap = item.candidate_snapshot
    assert snap["pageBlocked"]["statusCode"] == 403
    assert snap["pageBlocked"]["needsHumanCheck"] is True
    assert "verification" not in snap  # nothing was verified from the challenge
    assert snap["title"] == "Kiroween Online Hack 2026"
    assert submission.state == SubmissionState.AWAITING_ADMIN
