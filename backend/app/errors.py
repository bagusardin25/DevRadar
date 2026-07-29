"""RFC 9457 Problem Detail responses and custom exception classes."""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ProblemDetail(BaseModel):
    """RFC 9457 Problem Detail response body."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    trace_id: str | None = None
    errors: list[dict[str, Any]] | None = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class AppError(Exception):
    """Base application error that maps to an RFC 9457 problem response."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str,
        type_: str = "about:blank",
        errors: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type = type_
        self.errors = errors
        self.headers = headers or {}
        super().__init__(detail)


class NotFoundError(AppError):
    """Resource not found (404)."""

    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(status=404, title="Not Found", detail=detail)


class ValidationError(AppError):
    """Validation failure (422)."""

    def __init__(
        self,
        detail: str = "Validation failed",
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(status=422, title="Validation Error", detail=detail, errors=errors)


class ConflictError(AppError):
    """Resource conflict (409)."""

    def __init__(self, detail: str = "Resource conflict") -> None:
        super().__init__(status=409, title="Conflict", detail=detail)


class UnauthorizedError(AppError):
    """Authentication required (401)."""

    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(status=401, title="Unauthorized", detail=detail)


class ForbiddenError(AppError):
    """Access forbidden (403)."""

    def __init__(self, detail: str = "Access forbidden") -> None:
        super().__init__(status=403, title="Forbidden", detail=detail)


class RateLimitError(AppError):
    """Too many requests (429)."""

    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        *,
        retry_after: int | None = None,
    ) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
        super().__init__(
            status=429,
            title="Too Many Requests",
            detail=detail,
            headers=headers,
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert AppError exceptions to RFC 9457 problem responses."""
    trace_id = getattr(request.state, "trace_id", None)
    problem = ProblemDetail(
        type=exc.type,
        title=exc.title,
        status=exc.status,
        detail=exc.detail,
        instance=str(request.url),
        trace_id=trace_id,
        errors=exc.errors,
    )
    return JSONResponse(
        status_code=exc.status,
        content=problem.model_dump(by_alias=True, exclude_none=True),
        headers={"Content-Type": "application/problem+json", **exc.headers},
    )
