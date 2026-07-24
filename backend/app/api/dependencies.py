"""FastAPI dependencies for request-scoped resources."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.service import CatalogueService


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async SQLAlchemy session."""
    session_maker = request.app.state.session_maker
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_catalogue_service(session: DbSession) -> CatalogueService:
    return CatalogueService(session)


Catalogue = Annotated[CatalogueService, Depends(get_catalogue_service)]
