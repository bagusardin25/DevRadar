"""Public live discovery endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field

from app.api.client_ip import client_ip
from app.api.dependencies import DbSession
from app.catalog.schemas import CamelModel
from app.discovery.constants import DEFAULT_MODULE
from app.discovery.enqueue import CeleryDiscoveryEnqueue, DiscoveryEnqueuePort
from app.discovery.service import LiveDiscoveryService

router = APIRouter(prefix="/discovery-runs", tags=["Discovery"])


class DiscoveryStartRequest(CamelModel):
    query: str = Field(min_length=1, max_length=200)
    connectors: list[str] = Field(default_factory=lambda: ["official_site", "rss"])
    result_cap: int = Field(default=10, ge=1, le=20)
    module: str = DEFAULT_MODULE
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
    # Honest progress counters so the UI never claims work that did not happen.
    candidates: int = 0
    fetched: int = 0
    published: int = 0
    needs_review: int = 0
    failed: int = 0
    error_summary: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


def _resolve_enqueue(request: Request) -> DiscoveryEnqueuePort:
    enqueue: DiscoveryEnqueuePort | None = getattr(
        request.app.state, "discovery_enqueue", None
    )
    return enqueue if enqueue is not None else CeleryDiscoveryEnqueue()


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
    # Only tests install an in-process store; production counts in Redis so the
    # quota survives restarts and is shared across workers.
    rate_store = getattr(request.app.state, "discovery_rate_limit_store", None)
    svc = LiveDiscoveryService(
        session,
        settings.session_secret,
        redis_url=settings.redis_url,
        rate_limit_store=rate_store,
        enqueue=_resolve_enqueue(request),
    )
    receipt = await svc.start(
        query=body.query,
        ip_address=client_ip(request, settings.trusted_proxy_hops),
        connectors=body.connectors,
        result_cap=body.result_cap,
        module=body.module,
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
    # Read-only path: no rate-limit backend needed.
    svc = LiveDiscoveryService(session, settings.session_secret, rate_limit_store={})
    run = await svc.get(run_id)
    # Public status never exposes unverified intermediate results — only verified IDs.
    meta = run.meta_json or {}
    return DiscoveryStatusResponse(
        id=run.id,
        status=str(run.status),
        query=run.query,
        verified_listing_ids=list(run.verified_listing_ids or []),
        cost_units=run.cost_units,
        candidates=int(meta.get("candidates") or 0),
        fetched=int(meta.get("fetched") or 0),
        published=int(meta.get("published") or 0),
        needs_review=int(meta.get("needs_review") or 0),
        failed=int(meta.get("failed") or 0),
        error_summary=run.error_summary,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )
