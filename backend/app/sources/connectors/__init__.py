"""Source connectors registry."""

from app.sources.connectors.base import SourceConnector
from app.sources.connectors.commudle import CommudleConnector
from app.sources.connectors.devfolio import DevfolioConnector
from app.sources.connectors.devpost import DevpostConnector
from app.sources.connectors.dorahacks import DoraHacksConnector
from app.sources.connectors.ethglobal import EthglobalConnector
from app.sources.connectors.hack2skill import Hack2SkillConnector
from app.sources.connectors.hackathon_com import HackathonComConnector
from app.sources.connectors.hackclub import HackClubConnector
from app.sources.connectors.hackerearth import HackerEarthConnector
from app.sources.connectors.hackquest import HackQuestConnector
from app.sources.connectors.lablab import LablabConnector
from app.sources.connectors.mlh import MLHConnector
from app.sources.connectors.official_site import OfficialSiteConnector
from app.sources.connectors.rss import RSSConnector
from app.sources.connectors.taikai import TaikaiConnector
from app.sources.connectors.unstop import UnstopConnector
from app.sources.connectors.x_recent_search import FakeXApiClient, XRecentSearchConnector

CONNECTOR_TYPES = {
    "devpost": DevpostConnector,
    "devfolio": DevfolioConnector,
    "dorahacks": DoraHacksConnector,
    "unstop": UnstopConnector,
    "lablab": LablabConnector,
    "ethglobal": EthglobalConnector,
    "taikai": TaikaiConnector,
    "hackquest": HackQuestConnector,
    "hack2skill": Hack2SkillConnector,
    "hackathon_com": HackathonComConnector,
    "commudle": CommudleConnector,
    "hackclub": HackClubConnector,
    "mlh": MLHConnector,
    "hackerearth": HackerEarthConnector,
    "rss": RSSConnector,
    "official_site": OfficialSiteConnector,
    "x_recent_search": XRecentSearchConnector,
}


def get_connector(connector_type: str, **kwargs: object) -> SourceConnector:
    cls = CONNECTOR_TYPES.get(connector_type)
    if cls is None:
        raise KeyError(f"Unknown connector type: {connector_type}")
    # XRecentSearchConnector requires a client argument; provide a fake for offline use.
    if connector_type == "x_recent_search" and "client" not in kwargs:
        kwargs["client"] = FakeXApiClient()
    instance: SourceConnector = cls(**kwargs)  # type: ignore[misc]
    return instance
