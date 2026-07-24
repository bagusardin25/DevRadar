"""Admin GitHub OAuth and session endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from app.api.dependencies import AuthSvc
from app.review.schemas import AdminMeResponse

router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])


@router.get("/github/start")
async def github_oauth_start(service: AuthSvc) -> dict[str, str]:
    url, state = await service.start_github_oauth()
    return {"authorizeUrl": url, "state": state}


@router.get("/github/callback")
async def github_oauth_callback(
    request: Request,
    service: AuthSvc,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    settings = request.app.state.settings
    frontend = settings.frontend_url.rstrip("/")
    if error:
        return RedirectResponse(
            url=f"{frontend}/?admin_auth=error&reason={error}",
            status_code=302,
        )
    response = RedirectResponse(
        url=f"{frontend}/?admin_auth=ok",
        status_code=302,
    )
    await service.complete_github_oauth(
        code=code or "",
        state=state or "",
        response=response,
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    service: AuthSvc,
) -> dict[str, str]:
    # Logout requires a valid session + CSRF.
    await service.require_admin(request, require_csrf=True)
    await service.logout(request, response)
    return {"status": "ok"}


@router.get("/me", response_model=AdminMeResponse)
async def me(request: Request, service: AuthSvc) -> AdminMeResponse:
    identity = await service.require_admin(request, require_csrf=False)
    return AdminMeResponse(
        github_id=identity.github_id,
        login=identity.login,
        csrf_token=identity.csrf_token,
    )
