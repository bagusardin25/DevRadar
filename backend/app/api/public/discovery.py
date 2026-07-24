"""Public live discovery endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field

from app.api.dependencies import DbSession
from app.catalog.schemas import CamelModel
from app.discovery.service import LiveDiscoveryService

router = APIRouter(prefix="/discovery-runs", tags=["Discovery"])


class DiscoveryStartRequest(CamelModel):
    query: str = Field(min_length=1, max_length=200)
    connectors: list[str] = Field(default_factory=lambda: ["devpost"])
    result_cap: int = Field(default=10, ge=1, le=20)
    # Explicit opt-in required
    confirm_live_discovery: bool = False


class DiscoveryReceiptResponse(CamelModel):
    id: UUID
    status: str
    message: str


class DiscoveryStatusResponse(CamelModel):
    id: UUID
    status: str
    query: str
    verified_listing_ids: list[str] = Field(default_factory=list)
    cost_units: int = 0


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "0.0.0.0"


@router.post("", response_model=DiscoveryReceiptResponse, status_code=202)
async def start_discovery(
    body: DiscoveryStartRequest,
    request: Request,
    session: DbSession,
) -> DiscoveryReceiptResponse:
    from app.errors import ValidationError

    if not body.confirm_live_discovery:
        raise ValidationError(
            detail="Explicit opt-in required",
            errors=[{"field": "confirmLiveDiscovery", "message": "must be true"}],
        )
    settings = request.app.state.settings
    rate_store = getattr(request.app.state, "discovery_rate_limit_store", None)
    if rate_store is None:
        rate_store = {}
        request.app.state.discovery_rate_limit_store = rate_store
    svc = LiveDiscoveryService(
        session, settings.session_secret, rate_limit_store=rate_store
    )
    receipt = await svc.start(
        query=body.query,
        ip_address=_client_ip(request),
        connectors=body.connectors,
        result_cap=body.result_cap,
    )
    return DiscoveryReceiptResponse(
        id=receipt.id, status=receipt.status, message=receipt.message
    )


@router.get("/{run_id}", response_model=DiscoveryStatusResponse)
async def get_discovery(
    run_id: UUID,
    request: Request,
    session: DbSession,
) -> DiscoveryStatusResponse:
    settings = request.app.state.settings
    svc = LiveDiscoveryService(session, settings.session_secret, rate_limit_store={})
    run = await svc.get(run_id)
    # Public status never exposes unverified intermediate results — only verified IDs.
    return DiscoveryStatusResponse(
        id=run.id,
        status=str(run.status),
        query=run.query,
        verified_listing_ids=list(run.verified_listing_ids or []),
        cost_units=run.cost_units,
    )
