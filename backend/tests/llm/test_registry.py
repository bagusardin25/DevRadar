"""Provider registry parsing and tiering."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.llm.registry import parse_provider_specs, providers_for
from tests.llm.conftest import make_spec

ENV = {"GROQ_API_KEY": "gsk-test", "GEMINI_API_KEY": "gm-test"}


def _entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
    }
    base.update(overrides)
    return base


def _parse(*entries: dict[str, Any], env: dict[str, str] | None = None) -> Any:
    return parse_provider_specs(json.dumps(list(entries)), env=env or ENV)


class TestParsing:
    def test_empty_config_yields_no_providers(self) -> None:
        assert parse_provider_specs("", env=ENV) == []
        assert parse_provider_specs("   ", env=ENV) == []

    def test_defaults_are_applied(self) -> None:
        (spec,) = _parse(_entry())
        assert spec.name == "groq"
        assert spec.kind == "openai_compat"
        assert spec.base_url == "https://api.groq.com/openai/v1"
        assert spec.api_key == "gsk-test"
        assert spec.priority == 100
        assert spec.weight == 1
        assert spec.operations == frozenset({"extraction", "review"})
        assert spec.read_timeout == 30.0

    def test_api_key_env_defaults_to_provider_name(self) -> None:
        (spec,) = _parse(_entry(api_key_env=None))
        assert spec.api_key == "gsk-test"

    def test_missing_key_skips_provider_without_failing(self) -> None:
        # One unset secret must not take the whole service down.
        specs = _parse(_entry(name="mistral", api_key_env="MISTRAL_API_KEY"), _entry())
        assert [spec.name for spec in specs] == ["groq"]

    def test_limits_and_timeouts_are_read(self) -> None:
        (spec,) = _parse(
            _entry(
                limits={"rpm": 30, "rpd": 1000, "tpm": 12000, "tpd": 100000},
                timeout={"connect": 3, "read": 15},
            )
        )
        assert (spec.limits.rpm, spec.limits.rpd) == (30, 1000)
        assert (spec.limits.tpm, spec.limits.tpd) == (12000, 100000)
        assert (spec.connect_timeout, spec.read_timeout) == (3.0, 15.0)

    def test_cloudflare_account_id_is_substituted(self) -> None:
        (spec,) = _parse(
            _entry(
                name="cloudflare",
                api_key_env="GROQ_API_KEY",
                base_url="https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
                account_id="acc123",
            )
        )
        assert spec.base_url.endswith("/accounts/acc123/ai/v1")


class TestCapabilities:
    def test_known_provider_gets_its_defaults(self) -> None:
        (spec,) = _parse(_entry())
        assert spec.capabilities.json_mode == "json_schema"
        assert spec.capabilities.supports_temperature is False

    def test_unknown_provider_gets_conservative_baseline(self) -> None:
        (spec,) = _parse(_entry(name="gemini", api_key_env="GEMINI_API_KEY"))
        assert spec.capabilities.json_mode == "json_schema"

        (other,) = _parse(_entry(name="somenew", api_key_env="GROQ_API_KEY"))
        assert other.capabilities.json_mode == "json_object"
        assert other.capabilities.supports_temperature is True

    def test_explicit_overrides_win(self) -> None:
        (spec,) = _parse(
            _entry(json_mode="prompt", supports_temperature=True, extra_headers={"X-A": "1"})
        )
        assert spec.capabilities.json_mode == "prompt"
        assert spec.capabilities.supports_temperature is True
        assert spec.capabilities.extra_headers["X-A"] == "1"


class TestStructuralErrors:
    """A broken provider list is a deploy error, not a silent degradation."""

    def test_invalid_json(self) -> None:
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_provider_specs("{nope", env=ENV)

    def test_not_an_array(self) -> None:
        with pytest.raises(ValueError, match="must be a JSON array"):
            parse_provider_specs('{"name": "groq"}', env=ENV)

    def test_missing_required_field(self) -> None:
        with pytest.raises(ValueError, match="missing required field 'model'"):
            _parse(_entry(model=None))

    def test_unsupported_kind(self) -> None:
        with pytest.raises(ValueError, match="unsupported kind"):
            _parse(_entry(kind="anthropic_native"))

    def test_unknown_operation(self) -> None:
        with pytest.raises(ValueError, match="unknown operations: summarise"):
            _parse(_entry(operations=["summarise"]))

    def test_duplicate_provider_name(self) -> None:
        with pytest.raises(ValueError, match="duplicate provider name"):
            _parse(_entry(), _entry())

    def test_account_id_template_without_account_id(self) -> None:
        with pytest.raises(ValueError, match="needs account_id"):
            _parse(_entry(base_url="https://x.test/{account_id}/v1"))


class TestTiering:
    def test_groups_by_priority_and_filters_by_operation(self) -> None:
        specs = [
            make_spec("groq", priority=10),
            make_spec("gemini", priority=10),
            make_spec("openai", priority=20, operations=("extraction", "review")),
            make_spec("mistral", priority=30, operations=("review",)),
        ]
        tiers = providers_for(specs, "extraction")
        assert [[spec.name for spec in tier] for tier in tiers] == [
            ["gemini", "groq"],
            ["openai"],
        ]

    def test_operation_with_no_provider_yields_no_tiers(self) -> None:
        assert providers_for([make_spec("groq", operations=("extraction",))], "review") == []


class TestPerOperationPriority:
    """One account has one quota, so it stays one entry across operations."""

    def test_scalar_priority_applies_to_every_operation(self) -> None:
        (spec,) = _parse(_entry(priority=15))
        assert spec.priority_for("extraction") == 15
        assert spec.priority_for("review") == 15

    def test_mapping_gives_each_operation_its_own_tier(self) -> None:
        (spec,) = _parse(_entry(priority={"review": 10, "extraction": 30}))
        assert spec.priority_for("review") == 10
        assert spec.priority_for("extraction") == 30

    def test_mapping_default_covers_unlisted_operations(self) -> None:
        (spec,) = _parse(_entry(priority={"default": 50, "review": 10}))
        assert spec.priority_for("review") == 10
        assert spec.priority_for("extraction") == 50

    def test_unknown_operation_in_priority_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="priority has unknown operation"):
            _parse(_entry(priority={"summarise": 10}))

    def test_non_numeric_priority_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="priority must be a number"):
            _parse(_entry(priority="high"))

    def test_one_provider_lands_in_different_tiers_per_operation(self) -> None:
        specs = [
            make_spec(
                "openai",
                priority=30,
                priority_overrides={"review": 10},
                operations=("extraction", "review"),
            ),
            make_spec("groq", priority=20, operations=("extraction", "review")),
        ]
        assert [[s.name for s in tier] for tier in providers_for(specs, "review")] == [
            ["openai"],
            ["groq"],
        ]
        assert [[s.name for s in tier] for tier in providers_for(specs, "extraction")] == [
            ["groq"],
            ["openai"],
        ]
