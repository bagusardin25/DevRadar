"""Public alert subscription endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.alerts.schemas import AlertCreateRequest, AlertCreateResponse
from app.alerts.service import AlertService
from app.api.dependencies import DbSession
from app.config import Settings

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post("", response_model=AlertCreateResponse, status_code=202)
async def create_alert(
    body: AlertCreateRequest,
    request: Request,
    session: DbSession,
) -> AlertCreateResponse:
    settings: Settings = request.app.state.settings
    service = AlertService(session, settings)
    response, _token = await service.create_subscription(body)
    return response


@router.get("/confirm")
async def confirm_alert(
    request: Request,
    session: DbSession,
    token: str = Query(...),
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
    token: str = Query(...),
) -> dict[str, str]:
    settings: Settings = request.app.state.settings
    service = AlertService(session, settings)
    await service.unsubscribe(token)
    return {"status": "unsubscribed"}


@router.get("/unsubscribe")
async def unsubscribe_alert_get(
    request: Request,
    session: DbSession,
    token: str = Query(...),
) -> RedirectResponse:
    """One-click unsubscribe from email links (GET + redirect to frontend)."""
    settings: Settings = request.app.state.settings
    service = AlertService(session, settings)
    await service.unsubscribe(token)
    frontend = settings.frontend_url.rstrip("/")
    return RedirectResponse(url=f"{frontend}/?alert=unsubscribed", status_code=302)
