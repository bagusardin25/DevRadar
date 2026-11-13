"""Every harvest source key is wired end to end (DB-free)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.catalog.enums import ConnectorType
from app.catalog.service import CONNECTOR_TO_DISCOVERY
from app.config import HARVEST_SOURCE_KEYS
from app.harvest.runner import HARVEST_SOURCES
from app.sources.connectors import CONNECTOR_TYPES, get_connector


def test_config_keys_match_runner_sources_in_order() -> None:
    assert tuple(HARVEST_SOURCES) == HARVEST_SOURCE_KEYS


def test_every_source_has_a_connector_and_connector_type() -> None:
    now = datetime(2026, 10, 10, tzinfo=UTC)
    for key, info in HARVEST_SOURCES.items():
        assert key in CONNECTOR_TYPES, key
        connector = get_connector(key, now=lambda: now)
        assert connector.name == key
        assert connector.connector_type == info.connector_type.value
        assert ConnectorType(key) is info.connector_type
        assert info.connector_type.value in CONNECTOR_TO_DISCOVERY


def test_source_names_are_unique() -> None:
    names = [info.name for info in HARVEST_SOURCES.values()]
    assert len(names) == len(set(names))
