"""Threaded local HTTP server for fetcher tests (no external network)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

HandlerFactory = Callable[[], type[BaseHTTPRequestHandler]]


class LocalHttpServer:
    def __init__(self, handler_cls: type[BaseHTTPRequestHandler]) -> None:
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        self.port = self._httpd.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=2)

    def __enter__(self) -> LocalHttpServer:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


def make_handler(
    *,
    routes: dict[str, dict[str, Any]] | None = None,
    default_body: bytes = b"<html><title>OK</title><body>Hello</body></html>",
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler from a path → response map.

    Response dict keys: status, body, headers, redirect.
    """
    route_map = routes or {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            spec = route_map.get(path, {"status": 200, "body": default_body})
            status = int(spec.get("status", 200))
            if "redirect" in spec:
                self.send_response(status if status in {301, 302, 303, 307, 308} else 302)
                self.send_header("Location", spec["redirect"])
                for k, v in (spec.get("headers") or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                return
            body: bytes = spec.get("body", default_body)
            if callable(body):
                body = body(self)
            headers = dict(spec.get("headers") or {})
            headers.setdefault("Content-Type", "text/html; charset=utf-8")
            # Conditional GET
            inm = self.headers.get("If-None-Match")
            if inm and headers.get("ETag") and inm == headers.get("ETag"):
                self.send_response(304)
                self.send_header("ETag", headers["ETag"])
                self.end_headers()
                return
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler
