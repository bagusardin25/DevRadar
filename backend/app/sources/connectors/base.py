"""Connector protocol for curated opportunity sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class DiscoveryCandidate:
    """Minimal discovery hit before detail fetch."""

    external_id: str
    url: str
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveryPage:
    items: list[DiscoveryCandidate]
    next_cursor: str | None = None


@dataclass(slots=True)
class FetchRequest:
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConnectorQuery:
    """Normalized query config for a source_queries row."""

    module: str  # hackathon | ai_offer
    query_text: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    result_cap: int = 50


class SourceConnector(Protocol):
    name: str
    connector_type: str

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage: ...

    async def fetch_detail(self, candidate: DiscoveryCandidate) -> FetchRequest: ...
