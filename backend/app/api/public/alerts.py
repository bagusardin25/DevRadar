"""Public alert subscription endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.alerts.rate_limit import AlertSignupRateLimiter
from app.alerts.schemas import AlertCreateRequest, AlertCreateResponse
from app.alerts.service import AlertService
from app.api.client_ip import client_ip
from app.api.dependencies import DbSession
from app.config import Settings
from app.errors import ForbiddenError
from app.submissions.security import hash_email, hash_ip

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post("", response_model=AlertCreateResponse, status_code=202)
async def create_alert(
    body: AlertCreateRequest,
    request: Request,
    session: DbSession,
    http_response: Response,
) -> AlertCreateResponse:
    settings: Settings = request.app.state.settings
    # Reject obvious bots before they can consume quota for a shared client IP.
    if body.website:
        raise ForbiddenError(detail="Submission rejected")

    email_norm = str(body.email).strip().lower()
    limiter = AlertSignupRateLimiter(
        settings.redis_url,
        rate_limit_store=getattr(request.app.state, "alert_rate_limit_store", None),
    )
    await limiter.enforce(
        hash_ip(
            client_ip(request, settings.trusted_proxy_hops),
            settings.session_secret,
        ),
        hash_email(email_norm, settings.email_hmac_key),
    )
    service = AlertService(session, settings)
    result, _token = await service.create_subscription(body)
    http_response.headers["X-RateLimit-Limit"] = "10"
    http_response.headers["X-RateLimit-Policy"] = (
        "10;w=3600;scope=client, 3;w=3600;scope=email"
    )
    return result


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
