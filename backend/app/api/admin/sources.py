"""Admin source configuration routes (no credential secrets exposed)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field

from app.api.dependencies import AdminUser, AdminUserRead, DbSession, get_settings_dep
from app.catalog.schemas import CamelModel
from app.config import Settings
from app.harvest.health import harvest_source_health
from app.sources.service import SourceService

router = APIRouter(prefix="/admin/sources", tags=["Admin Sources"])

SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


class SourcePublic(CamelModel):
    id: UUID
    name: str
    connector_type: str
    trust_tier: str
    base_url: str | None = None
    enabled: bool
    credential_ref: str | None = None
    polling_policy: dict[str, Any] = Field(default_factory=dict)
    fetch_policy: dict[str, Any] = Field(default_factory=dict)


class SourceCreateRequest(CamelModel):
    name: str
    connector_type: str
    trust_tier: str
    base_url: str | None = None
    enabled: bool = True
    credential_ref: str | None = None
    polling_policy: dict[str, Any] = Field(default_factory=dict)
    fetch_policy: dict[str, Any] = Field(default_factory=dict)


class SourceUpdateRequest(CamelModel):
    name: str | None = None
    enabled: bool | None = None
    base_url: str | None = None
    credential_ref: str | None = None
    polling_policy: dict[str, Any] | None = None
    fetch_policy: dict[str, Any] | None = None


def _public(s: Any) -> SourcePublic:
    return SourcePublic(
        id=s.id,
        name=s.name,
        connector_type=str(s.connector_type),
        trust_tier=str(s.trust_tier),
        base_url=s.base_url,
        enabled=s.enabled,
        credential_ref=s.credential_ref,
        polling_policy=s.polling_policy or {},
        fetch_policy=s.fetch_policy or {},
    )


@router.get("")
async def list_sources(
    session: DbSession,
    _admin: AdminUserRead,
) -> dict[str, Any]:
    items = await SourceService(session).list_sources()
    return {"items": [_public(s) for s in items]}


@router.post("", status_code=201)
async def create_source(
    body: SourceCreateRequest,
    session: DbSession,
    _admin: AdminUser,
) -> SourcePublic:
    source = await SourceService(session).create_source(**body.model_dump())
    return _public(source)


# Declared before ``/{source_id}`` so the path is not parsed as a UUID.
@router.get("/harvest-health")
async def harvest_health(
    session: DbSession,
    settings: SettingsDep,
    _admin: AdminUserRead,
) -> dict[str, Any]:
    """Recent-run health of every harvest directory (read-only)."""
    report = await harvest_source_health(session, enabled_keys=settings.harvest_sources)
    return {
        "items": [health.as_dict() for health in report],
        "unhealthy": [health.key for health in report if not health.healthy],
    }


@router.get("/{source_id}")
async def get_source(
    source_id: UUID,
    session: DbSession,
    _admin: AdminUserRead,
) -> SourcePublic:
    source = await SourceService(session).get_source(source_id)
    return _public(source)


@router.patch("/{source_id}")
async def update_source(
    source_id: UUID,
    body: SourceUpdateRequest,
    session: DbSession,
    _admin: AdminUser,
) -> SourcePublic:
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    source = await SourceService(session).update_source(source_id, **data)
    return _public(source)
