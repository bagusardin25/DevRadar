"""FastAPI application factory and middleware configuration."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.limits import MAX_TRACE_ID_LENGTH
from app.api.router import api_router
from app.config import Settings, get_settings
from app.db import create_engine, create_session_maker
from app.errors import AppError, app_error_handler


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Add X-Trace-Id header to every request/response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Bound reflected input so a direct Uvicorn deployment cannot be used
        # to inject pathological trace values into logs and response headers.
        incoming = request.headers.get("x-trace-id", "").strip()
        trace_id = (
            incoming
            if incoming and len(incoming) <= MAX_TRACE_ID_LENGTH and incoming.isprintable()
            else str(uuid.uuid4())
        )
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response


class RequestBodyLimitMiddleware:
    """Reject oversized fixed-length and streamed request bodies with 413."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: int,
        read_timeout_seconds: float,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.read_timeout_seconds = read_timeout_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length:
            try:
                declared = int(content_length)
            except ValueError:
                declared = 0
            if declared > self.max_body_bytes:
                await self._reject(scope, receive, send)
                return

        # Pre-buffer at most the configured limit, then replay one body message
        # to Starlette. Raising from receive is not sufficient: Starlette turns
        # receive failures during JSON parsing into a generic 400 before outer
        # middleware can convert them to 413.
        body = bytearray()
        disconnected = False
        try:
            async with asyncio.timeout(self.read_timeout_seconds):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        disconnected = True
                        break
                    body.extend(message.get("body", b""))
                    if len(body) > self.max_body_bytes:
                        await self._reject(scope, receive, send)
                        return
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await self._reject_timeout(scope, receive, send)
            return

        delivered = False

        async def replay_receive() -> Message:
            nonlocal delivered
            if delivered or disconnected:
                return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "type": "https://devradar.local/problems/payload-too-large",
                "title": "Payload Too Large",
                "status": 413,
                "detail": f"Request body exceeds {self.max_body_bytes} bytes",
            },
            media_type="application/problem+json",
        )
        await response(scope, receive, send)

    async def _reject_timeout(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=408,
            content={
                "type": "https://devradar.local/problems/request-timeout",
                "title": "Request Timeout",
                "status": 408,
                "detail": "Request body was not received within the allowed time",
            },
            media_type="application/problem+json",
        )
        await response(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    # Store settings for use in lifespan and routes
    _settings = settings
    engine = create_engine(_settings)
    session_maker = create_session_maker(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    # OpenAPI UI is useful in development/test; hide it in production to reduce
    # the public attack surface (operators can still use /health/* and the API).
    expose_docs = not _settings.is_production
    app = FastAPI(
        title="DevRadar API",
        description="Discover, verify, and monitor hackathons and AI offers",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    # Available immediately (including ASGI tests without lifespan startup).
    app.state.engine = engine
    app.state.session_maker = session_maker
    app.state.settings = _settings

    # --- Middleware ---
    # Added first so CORS and trace handling wrap limit rejections too (Starlette
    # middleware registration order is the reverse of request execution order).
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_bytes=_settings.max_request_body_bytes,
        read_timeout_seconds=_settings.request_body_read_timeout_seconds,
    )
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Exception Handlers ---
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    # --- Public API ---
    app.include_router(api_router, prefix=_settings.api_base_path)

    # --- Health Routes ---
    @app.get("/health/live", tags=["Health"])
    async def health_live() -> dict[str, str]:
        """Liveness probe: checks process health only."""
        return {"status": "ok"}

    @app.get("/health/ready", tags=["Health"])
    async def health_ready(request: Request) -> JSONResponse:
        """Readiness probe: checks PostgreSQL and Redis connectivity."""
        checks: dict[str, str] = {}
        all_ok = True

        # Check PostgreSQL
        try:
            async with asyncio.timeout(5.0):
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            checks["postgres"] = "ok"
        except Exception as exc:
            checks["postgres"] = f"failed: {type(exc).__name__}"
            all_ok = False

        # Check Redis
        try:
            async with asyncio.timeout(5.0):
                r = aioredis.from_url(_settings.redis_url)
                try:
                    await r.ping()
                    checks["redis"] = "ok"
                finally:
                    # redis-py 5+ prefers aclose(); stubs may only declare close().
                    aclose = getattr(r, "aclose", None)
                    if aclose is not None:
                        await aclose()
                    else:
                        await r.close()

        except Exception as exc:
            checks["redis"] = f"failed: {type(exc).__name__}"
            all_ok = False

        status_code = 200 if all_ok else 503
        body: dict[str, Any] = {
            "status": "ok" if all_ok else "degraded",
            "checks": checks,
        }
        return JSONResponse(status_code=status_code, content=body)

    return app


# Module-level app instance for uvicorn
app = create_app()
