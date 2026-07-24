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
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import Settings, get_settings
from app.db import create_engine, create_session_maker
from app.errors import AppError, app_error_handler


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Add X-Trace-Id header to every request/response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Use incoming trace ID or generate a new one
        trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response


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
        # Store engine and session_maker in app state for access in routes
        app.state.engine = engine
        app.state.session_maker = session_maker
        app.state.settings = _settings
        yield
        await engine.dispose()

    app = FastAPI(
        title="DevRadar API",
        description="Discover, verify, and monitor hackathons and AI offers",
        version="0.1.0",
        lifespan=lifespan,
    )

    # --- Middleware ---
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
