"""Social provenance URLs must not spell out the poster's handle."""

from __future__ import annotations

import pytest

from app.catalog.service import _anonymize_social_url

CANONICAL = "https://x.com/i/web/status/1895019284"


class TestRewritesHandleForm:
    @pytest.mark.parametrize(
        "url",
        [
            "https://x.com/onlyonealexia/status/1895019284",
            "http://x.com/onlyonealexia/status/1895019284",
            "https://www.x.com/onlyonealexia/status/1895019284",
            "https://twitter.com/onlyonealexia/status/1895019284",
            "https://www.twitter.com/onlyonealexia/status/1895019284",
            # Mirror front-ends people paste in.
            "https://fxtwitter.com/onlyonealexia/status/1895019284",
            "https://vxtwitter.com/onlyonealexia/status/1895019284",
            # Legacy plural path.
            "https://twitter.com/onlyonealexia/statuses/1895019284",
            "https://X.com/OnlyOneAlexia/Status/1895019284",
        ],
    )
    def test_handle_is_stripped(self, url: str) -> None:
        assert _anonymize_social_url(url) == CANONICAL

    def test_query_and_fragment_are_dropped(self) -> None:
        url = "https://x.com/someone/status/1895019284?s=20&t=abc#reply"
        assert _anonymize_social_url(url) == CANONICAL

    def test_trailing_path_is_dropped(self) -> None:
        url = "https://x.com/someone/status/1895019284/photo/1"
        assert _anonymize_social_url(url) == CANONICAL


class TestLeavesEverythingElseAlone:
    def test_already_canonical_is_unchanged(self) -> None:
        assert _anonymize_social_url(CANONICAL) == CANONICAL

    @pytest.mark.parametrize(
        "url",
        [
            "https://devpost.com/hackathons/global-ai-agents-2026",
            "https://anthropic.com/hackathon-2026",
            "https://x.com/someone",
            "https://x.com/someone/status/not-a-number",
            # Look-alike host must not be treated as X.
            "https://notx.com/someone/status/1895019284",
            "",
        ],
    )
    def test_passes_through(self, url: str) -> None:
        assert _anonymize_social_url(url) == url
