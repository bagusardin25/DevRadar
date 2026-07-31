"""Admin visibility into LLM provider health and remaining free-tier budget.

Without this, "did the fallback actually fire?" can only be answered by reading
worker logs. The counters here are the same ones the router routes on, so what
an operator sees is what the next call will do.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import AdminUserRead, get_settings_dep
from app.catalog.schemas import CamelModel
from app.config import Settings
from app.llm.breaker import CircuitBreaker
from app.llm.limiter import LLMRateLimiter, effective_limit
from app.llm.registry import ProviderSpec, parse_provider_specs
from app.llm.state import KeyValueState, open_state

router = APIRouter(prefix="/admin/llm", tags=["Admin LLM"])

SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


class ProviderWindow(CamelModel):
    """Published ceiling, the 90% figure actually enforced, and current use."""

    limit: int | None = None
    effective: int | None = None
    used: int = 0
    remaining: int | None = None


class ProviderStatus(CamelModel):
    name: str
    model: str
    operations: list[str]
    priority: dict[str, int]
    weight: int
    json_mode: str
    circuit_open: bool
    failures: int
    trips: int
    rpm: ProviderWindow
    rpd: ProviderWindow
    tpm: ProviderWindow
    tpd: ProviderWindow


def _window(limit: int | None, used: int) -> ProviderWindow:
    ceiling = effective_limit(limit)
    return ProviderWindow(
        limit=limit,
        effective=ceiling,
        used=used,
        remaining=None if ceiling is None else max(0, ceiling - used),
    )


async def _status_for(
    spec: ProviderSpec,
    limiter: LLMRateLimiter,
    breaker: CircuitBreaker,
) -> ProviderStatus:
    usage = await limiter.usage(spec)
    state = await breaker.state_of(spec.name)
    operations = sorted(spec.operations)
    return ProviderStatus(
        name=spec.name,
        model=spec.model,
        operations=operations,
        priority={op: spec.priority_for(op) for op in operations},
        weight=spec.weight,
        json_mode=spec.capabilities.json_mode,
        circuit_open=await breaker.is_open(spec.name),
        failures=state.failures,
        trips=state.trips,
        rpm=_window(spec.limits.rpm, usage.rpm_used),
        rpd=_window(spec.limits.rpd, usage.rpd_used),
        tpm=_window(spec.limits.tpm, usage.tpm_used),
        tpd=_window(spec.limits.tpd, usage.tpd_used),
    )


@router.get("/providers")
async def list_llm_providers(
    request: Request,
    settings: SettingsDep,
    _admin: AdminUserRead,
) -> dict[str, Any]:
    """Health and remaining budget for every configured provider."""
    if not settings.llm_routing_enabled:
        return {"routingEnabled": False, "strategy": None, "providers": []}

    specs = parse_provider_specs(settings.llm_providers_json)
    override: KeyValueState | None = getattr(request.app.state, "llm_router_state", None)

    if override is not None:
        statuses = await _collect(specs, override)
    else:
        async with open_state(settings.redis_url) as state:
            statuses = await _collect(specs, state)

    return {
        "routingEnabled": True,
        "strategy": settings.llm_routing_strategy,
        "deadlineSeconds": settings.llm_deadline_seconds,
        "maxAttempts": settings.llm_max_attempts,
        "providers": [status.model_dump(by_alias=True) for status in statuses],
    }


async def _collect(
    specs: list[ProviderSpec], state: KeyValueState
) -> list[ProviderStatus]:
    limiter = LLMRateLimiter(state)
    breaker = CircuitBreaker(state)
    return [await _status_for(spec, limiter, breaker) for spec in specs]
