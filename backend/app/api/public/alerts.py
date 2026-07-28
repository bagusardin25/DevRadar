"""Public alert subscription endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.alerts.schemas import AlertCreateRequest, AlertCreateResponse
from app.alerts.service import (
    ALERT_RATE_LIMIT_MAX_PER_EMAIL,
    ALERT_RATE_LIMIT_MAX_PER_IP,
    ALERT_RATE_LIMIT_WINDOW_SECONDS,
    AlertService,
)
from app.api.client_ip import client_ip
from app.api.dependencies import DbSession
from app.api.limits import MAX_ALERT_TOKEN_LENGTH
from app.config import Settings

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post("", response_model=AlertCreateResponse, status_code=202)
async def create_alert(
    body: AlertCreateRequest,
    request: Request,
    session: DbSession,
    response: Response,
) -> AlertCreateResponse:
    settings: Settings = request.app.state.settings
    service = AlertService(
        session,
        settings,
        rate_limit_store=getattr(request.app.state, "alert_rate_limit_store", None),
    )
    result, _token = await service.create_subscription(
        body,
        ip_address=client_ip(request, settings.trusted_proxy_hops),
    )
    response.headers["X-RateLimit-Limit"] = str(ALERT_RATE_LIMIT_MAX_PER_EMAIL)
    response.headers["X-RateLimit-Policy"] = (
        f"{ALERT_RATE_LIMIT_MAX_PER_EMAIL};w={ALERT_RATE_LIMIT_WINDOW_SECONDS}, "
        f"{ALERT_RATE_LIMIT_MAX_PER_IP};w={ALERT_RATE_LIMIT_WINDOW_SECONDS}"
    )
    return result


@router.get("/confirm")
async def confirm_alert(
    request: Request,
    session: DbSession,
    token: Annotated[
        str,
        Query(min_length=1, max_length=MAX_ALERT_TOKEN_LENGTH),
    ],
) -> RedirectResponse:
    settings: Settings = request.app.state.settings
    service = AlertService(session, settings)
    await service.confirm_subscription(token)
    frontend = settings.frontend_url.rstrip("/")
    return RedirectResponse(url=f"{frontend}/?alert=confirmed", status_code=302)


@router.post("/unsubscribe")
async def unsubscribe_alert(
    request: Request,
    session: DbSession,
    token: Annotated[
        str,
        Query(min_length=1, max_length=MAX_ALERT_TOKEN_LENGTH),
    ],
) -> dict[str, str]:
    settings: Settings = request.app.state.settings
    service = AlertService(session, settings)
    await service.unsubscribe(token)
    return {"status": "unsubscribed"}


@router.get("/unsubscribe")
async def unsubscribe_alert_get(
    request: Request,
    session: DbSession,
    token: Annotated[
        str,
        Query(min_length=1, max_length=MAX_ALERT_TOKEN_LENGTH),
    ],
) -> RedirectResponse:
    """One-click unsubscribe from email links (GET + redirect to frontend)."""
    settings: Settings = request.app.state.settings
    service = AlertService(session, settings)
    await service.unsubscribe(token)
    frontend = settings.frontend_url.rstrip("/")
    return RedirectResponse(url=f"{frontend}/?alert=unsubscribed", status_code=302)
