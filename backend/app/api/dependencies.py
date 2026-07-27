"""FastAPI dependencies for request-scoped resources."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthService, resolve_google_oauth, resolve_session_store
from app.auth.sessions import AdminIdentity
from app.catalog.service import CatalogueService
from app.config import Settings
from app.review.service import ReviewService
from app.submissions.enqueue import CelerySubmissionEnqueue
from app.submissions.service import SubmissionService


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async SQLAlchemy session.

    Runs any `after_commit_hooks` registered on `session.info` after a
    successful commit (used for enqueue-after-commit job dispatch).
    """
    session_maker = request.app.state.session_maker
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
            hooks: list[Callable[[], Awaitable[None]]] = list(
                session.info.get("after_commit_hooks", [])
            )
            for hook in hooks:
                await hook()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_catalogue_service(session: DbSession) -> CatalogueService:
    return CatalogueService(session)


Catalogue = Annotated[CatalogueService, Depends(get_catalogue_service)]


async def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


async def get_submission_service(
    request: Request,
    session: DbSession,
) -> SubmissionService:
    settings: Settings = request.app.state.settings
    enqueue = getattr(request.app.state, "submission_enqueue", None)
    if enqueue is None:
        enqueue = CelerySubmissionEnqueue(settings.redis_url)
    rate_limit_store = getattr(request.app.state, "submission_rate_limit_store", None)
    return SubmissionService(
        session,
        settings,
        enqueue,
        rate_limit_store=rate_limit_store,
    )


SubmissionSvc = Annotated[SubmissionService, Depends(get_submission_service)]


async def get_auth_service(
    request: Request,
    session: DbSession,
) -> AuthService:
    settings: Settings = request.app.state.settings
    store = resolve_session_store(request, settings)
    oauth = resolve_google_oauth(request, settings)
    return AuthService(session, settings, store, oauth)


AuthSvc = Annotated[AuthService, Depends(get_auth_service)]


async def get_review_service(session: DbSession) -> ReviewService:
    return ReviewService(session)


ReviewSvc = Annotated[ReviewService, Depends(get_review_service)]


async def require_admin_read(
    request: Request,
    auth: AuthSvc,
) -> AdminIdentity:
    """Authenticated admin for GET endpoints (no CSRF)."""
    return await auth.require_admin(request, require_csrf=False)


async def require_admin_write(
    request: Request,
    auth: AuthSvc,
) -> AdminIdentity:
    """Authenticated admin for mutations (CSRF + Origin)."""
    return await auth.require_admin(request, require_csrf=True)


AdminUser = Annotated[AdminIdentity, Depends(require_admin_write)]
AdminUserRead = Annotated[AdminIdentity, Depends(require_admin_read)]
