"""Source registry service for admin and scheduler."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import ConnectorType, SourceTier
from app.errors import NotFoundError, ValidationError
from app.sources.models import Source, SourceQuery


class SourceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_sources(self, *, enabled_only: bool = False) -> list[Source]:
        stmt = select(Source).order_by(Source.name)
        if enabled_only:
            stmt = stmt.where(Source.enabled.is_(True))
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_source(self, source_id: UUID) -> Source:
        result = await self._session.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            raise NotFoundError(detail="Source not found")
        return source

    async def create_source(
        self,
        *,
        name: str,
        connector_type: str,
        trust_tier: str,
        base_url: str | None = None,
        enabled: bool = True,
        credential_ref: str | None = None,
        polling_policy: dict[str, Any] | None = None,
        fetch_policy: dict[str, Any] | None = None,
    ) -> Source:
        try:
            ConnectorType(connector_type)
            SourceTier(trust_tier)
        except ValueError as exc:
            raise ValidationError(detail=f"Invalid connector or tier: {exc}") from exc
        source = Source(
            name=name,
            connector_type=connector_type,
            trust_tier=trust_tier,
            base_url=base_url,
            enabled=enabled,
            credential_ref=credential_ref,
            polling_policy=polling_policy or {},
            fetch_policy=fetch_policy or {},
        )
        self._session.add(source)
        await self._session.flush()
        return source

    async def update_source(
        self,
        source_id: UUID,
        **fields: Any,
    ) -> Source:
        source = await self.get_source(source_id)
        # Never accept raw secrets
        fields.pop("api_key", None)
        fields.pop("secret", None)
        fields.pop("password", None)
        for key, value in fields.items():
            if value is not None and hasattr(source, key):
                setattr(source, key, value)
        await self._session.flush()
        return source

    async def list_queries(self, source_id: UUID) -> list[SourceQuery]:
        result = await self._session.execute(
            select(SourceQuery)
            .where(SourceQuery.source_id == source_id)
            .order_by(SourceQuery.name)
        )
        return list(result.scalars().all())

    async def create_query(
        self,
        source_id: UUID,
        *,
        module: str,
        name: str,
        query_config: dict[str, Any] | None = None,
        schedule: dict[str, Any] | None = None,
        result_cap: int = 50,
        cost_budget: int = 100,
        enabled: bool = True,
    ) -> SourceQuery:
        await self.get_source(source_id)
        q = SourceQuery(
            source_id=source_id,
            module=module,
            name=name,
            query_config=query_config or {},
            schedule=schedule or {"interval_seconds": 86400},
            result_cap=result_cap,
            cost_budget=cost_budget,
            enabled=enabled,
        )
        self._session.add(q)
        await self._session.flush()
        return q
