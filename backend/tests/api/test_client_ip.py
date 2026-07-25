"""Client IP resolution — the bucket key every anonymous rate limit depends on."""

from __future__ import annotations

from starlette.requests import Request

from app.api.client_ip import FALLBACK_IP, client_ip


def make_request(peer: str | None = None, xff: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": headers,
            "client": (peer, 54321) if peer else None,
        }
    )


class TestDirectExposure:
    """hops=0 — no proxy in front, so the header carries no authority."""

    def test_uses_socket_peer(self) -> None:
        req = make_request(peer="203.0.113.9")
        assert client_ip(req, 0) == "203.0.113.9"

    def test_ignores_forwarded_header_entirely(self) -> None:
        req = make_request(peer="203.0.113.9", xff="198.51.100.7")
        assert client_ip(req, 0) == "203.0.113.9"

    def test_falls_back_when_no_peer(self) -> None:
        assert client_ip(make_request(), 0) == FALLBACK_IP


class TestBehindOneProxy:
    """hops=1 — the load balancer appends the real client last."""

    def test_reads_entry_the_proxy_appended(self) -> None:
        req = make_request(peer="10.0.0.1", xff="203.0.113.9")
        assert client_ip(req, 1) == "203.0.113.9"

    def test_spoofed_prefix_does_not_win(self) -> None:
        # Caller sent "1.2.3.4"; the proxy appended their real address after it.
        req = make_request(peer="10.0.0.1", xff="1.2.3.4, 203.0.113.9")
        assert client_ip(req, 1) == "203.0.113.9"

    def test_long_spoofed_chain_does_not_win(self) -> None:
        req = make_request(
            peer="10.0.0.1", xff="9.9.9.1, 9.9.9.2, 9.9.9.3, 203.0.113.9"
        )
        assert client_ip(req, 1) == "203.0.113.9"

    def test_missing_header_falls_back_to_peer(self) -> None:
        req = make_request(peer="10.0.0.1")
        assert client_ip(req, 1) == "10.0.0.1"

    def test_tolerates_whitespace_and_empty_entries(self) -> None:
        req = make_request(peer="10.0.0.1", xff=" 1.2.3.4 ,, 203.0.113.9 ")
        assert client_ip(req, 1) == "203.0.113.9"


class TestBehindTwoProxies:
    def test_counts_back_from_the_right(self) -> None:
        req = make_request(peer="10.0.0.2", xff="203.0.113.9, 10.0.0.1")
        assert client_ip(req, 2) == "203.0.113.9"

    def test_spoofed_prefix_does_not_win(self) -> None:
        req = make_request(peer="10.0.0.2", xff="1.2.3.4, 203.0.113.9, 10.0.0.1")
        assert client_ip(req, 2) == "203.0.113.9"


class TestMisconfiguration:
    def test_chain_shorter_than_configured_falls_back_to_peer(self) -> None:
        # Claiming 3 hops when only one proxy appended: trusting parts[0] here
        # would return the caller-supplied value.
        req = make_request(peer="10.0.0.1", xff="1.2.3.4")
        assert client_ip(req, 3) == "10.0.0.1"

    def test_header_of_only_separators_falls_back_to_peer(self) -> None:
        req = make_request(peer="10.0.0.1", xff=" , , ")
        assert client_ip(req, 1) == "10.0.0.1"
