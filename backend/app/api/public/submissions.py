"""Public community submission endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Path, Request, Response, status

from app.api.client_ip import client_ip
from app.api.dependencies import SubmissionSvc
from app.api.limits import MAX_IDEMPOTENCY_KEY_LENGTH, MAX_TRACKING_ID_LENGTH
from app.submissions.schemas import (
    SubmissionCreateRequest,
    SubmissionReceipt,
    SubmissionStatusPublic,
)
from app.submissions.service import AbuseContext

router = APIRouter(prefix="/submissions", tags=["Submissions"])


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
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=MAX_IDEMPOTENCY_KEY_LENGTH),
    ] = None,
) -> SubmissionReceipt:
    abuse = AbuseContext(
        ip_address=client_ip(request, request.app.state.settings.trusted_proxy_hops),
        user_agent=request.headers.get("user-agent"),
        idempotency_key=idempotency_key,
    )
    receipt = await service.submit_candidate(body, abuse)
    response.headers["X-RateLimit-Limit"] = "10"
    response.headers["X-RateLimit-Policy"] = "10;w=3600"
    return receipt


@router.get("/{tracking_id}", response_model=SubmissionStatusPublic)
async def get_submission_status(
    tracking_id: Annotated[
        str,
        Path(min_length=1, max_length=MAX_TRACKING_ID_LENGTH),
    ],
    service: SubmissionSvc,
) -> SubmissionStatusPublic:
    return await service.get_public_submission_status(tracking_id)
