"""Source connectors registry."""

from app.sources.connectors.base import SourceConnector
from app.sources.connectors.devpost import DevpostConnector
from app.sources.connectors.hackerearth import HackerEarthConnector
from app.sources.connectors.mlh import MLHConnector
from app.sources.connectors.official_site import OfficialSiteConnector
from app.sources.connectors.rss import RSSConnector

# x_recent_search requires an XApiClient — construct via XRecentSearchConnector(...)
CONNECTOR_TYPES = {
    "devpost": DevpostConnector,
    "mlh": MLHConnector,
    "hackerearth": HackerEarthConnector,
    "rss": RSSConnector,
    "official_site": OfficialSiteConnector,
}


def get_connector(connector_type: str, **kwargs: object) -> SourceConnector:
    cls = CONNECTOR_TYPES.get(connector_type)
    if cls is None:
        raise KeyError(f"Unknown connector type: {connector_type}")
    instance: SourceConnector = cls(**kwargs)  # type: ignore[misc]
    return instance
