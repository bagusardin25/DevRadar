"""Parser cleanup tests."""

from __future__ import annotations

from app.ingestion.parser import PARSER_VERSION, parse_document


class TestParser:
    def test_strips_scripts_and_extracts_text(self) -> None:
        html = b"""
        <html><head><title>Hackathon 2026</title>
        <script>evil()</script><style>.x{}</style></head>
        <body>
          <nav>Home About</nav>
          <article><h1>Build with AI</h1><p>Win prizes.</p>
          <a href="/rules">Rules</a>
          <a href="https://example.com/apply">Apply</a>
          </article>
          <footer>copyright</footer>
        </body></html>
        """
        parsed = parse_document(
            html, url="https://example.com/hack", content_type="text/html"
        )
        assert parsed.title == "Hackathon 2026"
        assert "evil" not in parsed.text
        assert "Build with AI" in parsed.text
        assert "Win prizes" in parsed.text
        assert parsed.parser_version == PARSER_VERSION
        hrefs = {ln.href for ln in parsed.links}
        assert "https://example.com/rules" in hrefs
        assert "https://example.com/apply" in hrefs

    def test_deterministic_output(self) -> None:
        html = b"<html><title>T</title><body><p>Hello</p></body></html>"
        a = parse_document(html, url="https://x.test/", content_type="text/html")
        b = parse_document(html, url="https://x.test/", content_type="text/html")
        assert a.text == b.text
        assert a.title == b.title
        assert a.parser_version == b.parser_version

    def test_json_passthrough(self) -> None:
        body = b'{"name": "offer"}'
        parsed = parse_document(
            body, url="https://x.test/api", content_type="application/json"
        )
        assert '"name"' in parsed.text
        assert parsed.metadata["kind"] == "json"

    def test_plain_text(self) -> None:
        parsed = parse_document(
            b"just text", url="https://x.test/t", content_type="text/plain"
        )
        assert parsed.text == "just text"
