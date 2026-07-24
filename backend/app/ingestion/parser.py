"""Deterministic HTML/text cleanup for fetched documents."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

PARSER_VERSION = "1.0.0"

_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript|svg|iframe)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")

# Boilerplate-ish class/id hints stripped before text extraction.
_NOISE_BLOCK_RE = re.compile(
    r"<(nav|footer|header|aside)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_COOKIE_RE = re.compile(
    r'<div[^>]*(cookie|consent|gdpr)[^>]*>.*?</div>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(slots=True)
class ParsedLink:
    href: str
    text: str = ""


@dataclass(slots=True)
class ParsedDocument:
    url: str
    title: str | None
    text: str
    links: list[ParsedLink] = field(default_factory=list)
    content_type: str | None = None
    parser_version: str = PARSER_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


class _LinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[ParsedLink] = []
        self.title_parts: list[str] = []
        self._in_title = False
        self._in_a = False
        self._a_href: str | None = None
        self._a_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "a":
            href = ad.get("href", "").strip()
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                self._in_a = True
                self._a_href = urljoin(self.base_url, href)
                self._a_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() == "a" and self._in_a and self._a_href:
            text = " ".join("".join(self._a_text).split())
            self.links.append(ParsedLink(href=self._a_href, text=text))
            self._in_a = False
            self._a_href = None
            self._a_text = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_a:
            self._a_text.append(data)


def _strip_noise(html: str) -> str:
    html = _COMMENT_RE.sub(" ", html)
    html = _SCRIPT_STYLE_RE.sub(" ", html)
    html = _NOISE_BLOCK_RE.sub(" ", html)
    html = _COOKIE_RE.sub(" ", html)
    return html


def _html_to_text(html: str) -> str:
    cleaned = _strip_noise(html)
    # Block boundaries → newlines
    cleaned = re.sub(
        r"</(p|div|section|article|li|tr|h[1-6]|br)>",
        "\n",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", cleaned)
    text = text.replace("\xa0", " ")
    text = _WS_RE.sub(" ", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


def parse_document(
    body: bytes,
    *,
    url: str,
    content_type: str | None = None,
) -> ParsedDocument:
    """Parse raw bytes into cleaned text + links.

    Deterministic for the same inputs (no timestamps / random IDs).
    """
    ct = (content_type or "").lower()
    # Decode with replacement for stability
    if "json" in ct:
        text = body.decode("utf-8", errors="replace").strip()
        return ParsedDocument(
            url=url,
            title=None,
            text=text,
            links=[],
            content_type=content_type,
            metadata={"kind": "json"},
        )

    raw = body.decode("utf-8", errors="replace")
    if "html" in ct or raw.lstrip()[:20].lower().startswith(
        ("<!doctype", "<html", "<head", "<body")
    ):
        extractor = _LinkExtractor(url)
        try:
            extractor.feed(raw)
            extractor.close()
        except Exception:
            # Malformed HTML still yields text extraction
            pass
        title = " ".join("".join(extractor.title_parts).split()) or None
        text = _html_to_text(raw)
        # Deduplicate links by href preserving order
        seen: set[str] = set()
        links: list[ParsedLink] = []
        for link in extractor.links:
            if link.href not in seen:
                seen.add(link.href)
                links.append(link)
        return ParsedDocument(
            url=url,
            title=title,
            text=text,
            links=links,
            content_type=content_type or "text/html",
            metadata={"kind": "html", "link_count": len(links)},
        )

    # Plain text fallback
    text = raw.strip()
    return ParsedDocument(
        url=url,
        title=None,
        text=text,
        links=[],
        content_type=content_type or "text/plain",
        metadata={"kind": "text"},
    )
