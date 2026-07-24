"""Public community submission endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, status

from app.api.dependencies import SubmissionSvc
from app.submissions.schemas import (
    SubmissionCreateRequest,
    SubmissionReceipt,
    SubmissionStatusPublic,
)
from app.submissions.service import AbuseContext

router = APIRouter(prefix="/submissions", tags=["Submissions"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "0.0.0.0"


@router.post(
    "",
    response_model=SubmissionReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_submission(
    body: SubmissionCreateRequest,
    request: Request,
    service: SubmissionSvc,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SubmissionReceipt:
    abuse = AbuseContext(
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        idempotency_key=idempotency_key,
    )
    receipt = await service.submit_candidate(body, abuse)
    response.headers["X-RateLimit-Limit"] = "10"
    response.headers["X-RateLimit-Policy"] = "10;w=3600"
    return receipt


@router.get("/{tracking_id}", response_model=SubmissionStatusPublic)
async def get_submission_status(
    tracking_id: str,
    service: SubmissionSvc,
) -> SubmissionStatusPublic:
    return await service.get_public_submission_status(tracking_id)
