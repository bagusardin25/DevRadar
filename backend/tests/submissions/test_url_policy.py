"""Malformed and boundary URL policy cases."""

from __future__ import annotations

import pytest

from app.errors import ValidationError
from app.submissions.url_policy import canonicalize_url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com:99999/opportunity",
        "https://example.com:not-a-port/opportunity",
        "https://[::1",
    ],
)
def test_malformed_host_or_port_is_validation_error(url: str) -> None:
    with pytest.raises(ValidationError):
        canonicalize_url(url)


def test_default_https_port_is_removed() -> None:
    result = canonicalize_url("https://example.com:443/opportunity")
    assert result.canonical == "https://example.com/opportunity"
