"""Provider registry built from LLM_PROVIDERS_JSON.

API keys are never stored in the JSON blob — an entry names the environment
variable holding its key (``api_key_env``) and the value is read separately.
That keeps the blob safe to log and out of the way of secret scanning.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace

from app.llm.capabilities import Capabilities, JsonMode, defaults_for

logger = logging.getLogger(__name__)

SUPPORTED_KINDS = frozenset({"openai_compat"})
KNOWN_OPERATIONS = frozenset({"extraction", "review"})

_VALID_JSON_MODES = frozenset({"json_schema", "json_object", "prompt"})

DEFAULT_PRIORITY = 100
DEFAULT_WEIGHT = 1
DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 30.0


@dataclass(frozen=True, slots=True)
class ProviderLimits:
    """Free-tier ceilings, as published by the provider. None means unmetered."""

    rpm: int | None = None
    rpd: int | None = None
    tpm: int | None = None
    tpd: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """One routable provider endpoint."""

    name: str
    kind: str
    base_url: str
    api_key: str
    model: str
    operations: frozenset[str]
    priority: int
    priority_overrides: Mapping[str, int]
    weight: int
    capabilities: Capabilities
    limits: ProviderLimits
    connect_timeout: float
    read_timeout: float

    def serves(self, operation: str) -> bool:
        return operation in self.operations

    def priority_for(self, operation: str) -> int:
        """Tier for one operation.

        One account has one quota, so a provider stays a single entry even when
        it should be first choice for review and last resort for extraction.
        Per-operation priority expresses that without splitting the budget.
        """
        return self.priority_overrides.get(operation, self.priority)


def parse_provider_specs(
    raw: str, *, env: Mapping[str, str] | None = None
) -> list[ProviderSpec]:
    """Parse LLM_PROVIDERS_JSON into specs, dropping entries with no key.

    Raises ValueError for structural problems (bad JSON, unknown kind, missing
    required field) so a broken deploy fails at startup. A missing API key is
    not structural — that provider is skipped with a warning so one unset
    secret cannot take the whole service down.
    """
    text = (raw or "").strip()
    if not text:
        return []

    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM_PROVIDERS_JSON is not valid JSON: {exc}") from exc

    if not isinstance(decoded, list):
        raise ValueError("LLM_PROVIDERS_JSON must be a JSON array of provider objects")

    source = os.environ if env is None else env
    specs: list[ProviderSpec] = []
    seen: set[str] = set()
    for index, entry in enumerate(decoded):
        if not isinstance(entry, dict):
            raise ValueError(f"LLM_PROVIDERS_JSON[{index}] must be an object")
        spec = _build_spec(entry, index, source)
        if spec is None:
            continue
        if spec.name in seen:
            raise ValueError(f"LLM_PROVIDERS_JSON has duplicate provider name {spec.name!r}")
        seen.add(spec.name)
        specs.append(spec)
    return specs


def _build_spec(
    entry: dict[str, object],
    index: int,
    env: Mapping[str, str],
) -> ProviderSpec | None:
    name = _require_str(entry, "name", index).lower()
    kind = _optional_str(entry, "kind").lower() or "openai_compat"
    if kind not in SUPPORTED_KINDS:
        raise ValueError(
            f"LLM_PROVIDERS_JSON[{index}] has unsupported kind {kind!r} "
            f"(supported: {', '.join(sorted(SUPPORTED_KINDS))})"
        )

    base_url = _require_str(entry, "base_url", index).rstrip("/")
    account_id = _optional_str(entry, "account_id")
    if "{account_id}" in base_url:
        if not account_id:
            raise ValueError(
                f"LLM_PROVIDERS_JSON[{index}] ({name}) base_url needs account_id"
            )
        base_url = base_url.replace("{account_id}", account_id)

    # Validate the whole entry before looking at secrets, so a typo still fails
    # loudly on a machine where that provider's key happens to be unset.
    model = _require_str(entry, "model", index)
    operations = _parse_operations(entry, index, name)
    priority, priority_overrides = _parse_priority(entry, index, name)
    capabilities = _parse_capabilities(entry, index, name)

    key_env = _optional_str(entry, "api_key_env") or f"{name.upper()}_API_KEY"
    api_key = (env.get(key_env) or "").strip()
    if not api_key:
        logger.warning(
            "llm_provider_skipped_missing_key",
            extra={"provider": name, "api_key_env": key_env},
        )
        return None

    return ProviderSpec(
        name=name,
        kind=kind,
        base_url=base_url,
        api_key=api_key,
        model=model,
        operations=operations,
        priority=priority,
        priority_overrides=priority_overrides,
        weight=max(1, _optional_int(entry, "weight", DEFAULT_WEIGHT)),
        capabilities=capabilities,
        limits=_parse_limits(entry),
        connect_timeout=_timeout(entry, "connect", DEFAULT_CONNECT_TIMEOUT),
        read_timeout=_timeout(entry, "read", DEFAULT_READ_TIMEOUT),
    )


def _parse_operations(entry: dict[str, object], index: int, name: str) -> frozenset[str]:
    raw = entry.get("operations")
    if raw is None:
        return frozenset(KNOWN_OPERATIONS)
    if not isinstance(raw, list) or not raw:
        raise ValueError(
            f"LLM_PROVIDERS_JSON[{index}] ({name}) operations must be a non-empty array"
        )
    operations = {str(item).strip().lower() for item in raw}
    unknown = operations - KNOWN_OPERATIONS
    if unknown:
        raise ValueError(
            f"LLM_PROVIDERS_JSON[{index}] ({name}) has unknown operations: "
            f"{', '.join(sorted(unknown))}"
        )
    return frozenset(operations)


def _parse_priority(
    entry: dict[str, object], index: int, name: str
) -> tuple[int, dict[str, int]]:
    """Read ``priority`` as either one number or a per-operation mapping."""
    raw = entry.get("priority")
    if raw is None:
        return DEFAULT_PRIORITY, {}
    if isinstance(raw, bool):
        raise ValueError(f"LLM_PROVIDERS_JSON[{index}] ({name}) priority must be a number")
    if isinstance(raw, (int, float)):
        return int(raw), {}
    if not isinstance(raw, dict):
        raise ValueError(
            f"LLM_PROVIDERS_JSON[{index}] ({name}) priority must be a number or an "
            "object keyed by operation"
        )

    default = DEFAULT_PRIORITY
    overrides: dict[str, int] = {}
    for key, value in raw.items():
        operation = str(key).strip().lower()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"LLM_PROVIDERS_JSON[{index}] ({name}) priority.{operation} must be a number"
            )
        if operation == "default":
            default = int(value)
        elif operation in KNOWN_OPERATIONS:
            overrides[operation] = int(value)
        else:
            raise ValueError(
                f"LLM_PROVIDERS_JSON[{index}] ({name}) priority has unknown "
                f"operation {operation!r}"
            )
    return default, overrides


def _parse_capabilities(entry: dict[str, object], index: int, name: str) -> Capabilities:
    caps = defaults_for(name)

    json_mode = _optional_str(entry, "json_mode").lower()
    if json_mode:
        if json_mode not in _VALID_JSON_MODES:
            raise ValueError(
                f"LLM_PROVIDERS_JSON[{index}] ({name}) has unknown json_mode {json_mode!r}"
            )
        caps = replace(caps, json_mode=_as_json_mode(json_mode))

    supports_temperature = entry.get("supports_temperature")
    if isinstance(supports_temperature, bool):
        caps = replace(caps, supports_temperature=supports_temperature)

    headers = entry.get("extra_headers")
    if isinstance(headers, dict):
        merged = {**caps.extra_headers}
        merged.update({str(k): str(v) for k, v in headers.items()})
        caps = replace(caps, extra_headers=merged)

    return caps


def _as_json_mode(value: str) -> JsonMode:
    # Guarded by _VALID_JSON_MODES above; narrows the literal type for mypy.
    if value == "json_schema":
        return "json_schema"
    if value == "json_object":
        return "json_object"
    return "prompt"


def _parse_limits(entry: dict[str, object]) -> ProviderLimits:
    raw = entry.get("limits")
    if not isinstance(raw, dict):
        return ProviderLimits()
    return ProviderLimits(
        rpm=_optional_positive(raw, "rpm"),
        rpd=_optional_positive(raw, "rpd"),
        tpm=_optional_positive(raw, "tpm"),
        tpd=_optional_positive(raw, "tpd"),
    )


def _timeout(entry: dict[str, object], key: str, default: float) -> float:
    raw = entry.get("timeout")
    if not isinstance(raw, dict):
        return default
    try:
        value = float(raw.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _require_str(entry: dict[str, object], key: str, index: int) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"LLM_PROVIDERS_JSON[{index}] is missing required field {key!r}")
    return value.strip()


def _optional_str(entry: dict[str, object], key: str) -> str:
    """Trimmed string value, case preserved.

    Case matters for env var names and account ids; callers that want a
    normalised token (kind, json_mode) lower it themselves.
    """
    value = entry.get(key)
    return value.strip() if isinstance(value, str) else ""


def _optional_int(entry: dict[str, object], key: str, default: int) -> int:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)


def _optional_positive(entry: dict[str, object], key: str) -> int | None:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = int(value)
    return number if number > 0 else None


def providers_for(specs: list[ProviderSpec], operation: str) -> list[list[ProviderSpec]]:
    """Group providers that serve ``operation`` into priority tiers.

    Tiers come back strongest first; providers inside a tier are rotated by the
    router rather than tried in a fixed order.
    """
    tiers: dict[int, list[ProviderSpec]] = {}
    for spec in specs:
        if spec.serves(operation):
            tiers.setdefault(spec.priority_for(operation), []).append(spec)
    return [
        sorted(tiers[priority], key=lambda spec: spec.name) for priority in sorted(tiers)
    ]
