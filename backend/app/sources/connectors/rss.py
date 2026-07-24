"""Generic RSS/Atom connector using recorded feed XML fixtures."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
    FetchRequest,
)


class RSSConnector:
    name = "rss"
    connector_type = "rss"

    def __init__(self, feed_xml: str | None = None) -> None:
        self._feed_xml = feed_xml or ""

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        xml = query.config.get("feed_xml") or self._feed_xml
        if not xml:
            return DiscoveryPage(items=[], next_cursor=None)
        root = ET.fromstring(xml)
        items: list[DiscoveryCandidate] = []
        # RSS 2.0
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or link).strip()
            if not link:
                continue
            if query.query_text and query.query_text.lower() not in title.lower():
                continue
            items.append(
                DiscoveryCandidate(
                    external_id=guid,
                    url=link,
                    title=title or None,
                    metadata={"source": "rss"},
                )
            )
        # Atom
        if not items:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("a:entry", ns) or root.findall("entry"):
                title = (
                    entry.findtext("a:title", default="", namespaces=ns)
                    or entry.findtext("title")
                    or ""
                ).strip()
                link_el = entry.find("a:link", ns) or entry.find("link")
                href = ""
                if link_el is not None:
                    href = link_el.get("href") or (link_el.text or "")
                if href:
                    items.append(
                        DiscoveryCandidate(
                            external_id=href,
                            url=href,
                            title=title or None,
                            metadata={"source": "atom"},
                        )
                    )
        start = int(cursor or 0)
        cap = query.result_cap
        page = items[start : start + cap]
        nxt = str(start + cap) if start + cap < len(items) else None
        return DiscoveryPage(items=page, next_cursor=nxt)

    async def fetch_detail(self, candidate: DiscoveryCandidate) -> FetchRequest:
        return FetchRequest(url=candidate.url, metadata={"connector": self.name})
