"""Opt-in allowance for fake-IP DNS proxies (198.18.0.0/15) in the SSRF guard."""

from __future__ import annotations

import socket

import pytest

from app.ingestion import ssrf


def _resolve_to(monkeypatch: pytest.MonkeyPatch, addr: str) -> None:
    def fake_getaddrinfo(host: str, *_args: object, **_kwargs: object) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (addr, 0))]

    monkeypatch.setattr(ssrf.socket, "getaddrinfo", fake_getaddrinfo)


def test_fake_ip_range_is_blocked_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _resolve_to(monkeypatch, "198.18.0.20")
    monkeypatch.setattr(ssrf, "_fake_ip_proxy_allowed", lambda: False)
    with pytest.raises(ssrf.SSRFError):
        ssrf.resolve_and_validate_host("devpost.com")


def test_fake_ip_range_allowed_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    _resolve_to(monkeypatch, "198.18.0.20")
    monkeypatch.setattr(ssrf, "_fake_ip_proxy_allowed", lambda: True)
    assert ssrf.resolve_and_validate_host("devpost.com") == ["198.18.0.20"]


def test_opt_in_does_not_open_other_private_ranges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ssrf, "_fake_ip_proxy_allowed", lambda: True)
    for addr in ("10.0.0.5", "127.0.0.1", "169.254.169.254", "192.168.1.1"):
        _resolve_to(monkeypatch, addr)
        with pytest.raises(ssrf.SSRFError):
            ssrf.resolve_and_validate_host("example.com")


def test_opt_in_does_not_allow_literal_fake_ip_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ssrf, "_fake_ip_proxy_allowed", lambda: True)
    with pytest.raises(ssrf.SSRFError):
        ssrf.resolve_and_validate_host("198.18.0.20")
