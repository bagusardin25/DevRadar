"""Exceptions raised inside the LLM router.

These never reach the API surface: both call sites (``Extractor`` and
``ReviewAdvisor``) already catch provider failures and fall back to their
deterministic paths. They exist so the router can classify what went wrong.
"""

from __future__ import annotations


class LLMRouterError(Exception):
    """Base class for router failures."""


class ProviderError(LLMRouterError):
    """A single provider attempt failed.

    ``message`` stays exactly what the provider said — classification matches
    substrings against it, so prefixing it with our own text would let a status
    line or an error code trip a marker it never should.
    """

    def __init__(self, provider: str, message: str, *, detail: str | None = None) -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"{provider}: {detail or message}")


class ProviderHTTPError(ProviderError):
    """Provider answered with a non-2xx status."""

    def __init__(
        self,
        provider: str,
        status: int,
        *,
        code: str = "",
        message: str = "",
        retry_after: float | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.retry_after = retry_after
        summary = " ".join(part for part in (f"HTTP {status}", code, message) if part)
        super().__init__(provider, message, detail=summary)


class ProviderResponseError(ProviderError):
    """Provider answered 2xx with something unusable (empty or truncated)."""


class NoProviderAvailableError(LLMRouterError):
    """No provider is configured — or eligible — for this operation."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"No LLM provider available for operation {operation!r}")


class AllProvidersFailedError(LLMRouterError):
    """Every eligible provider was skipped or failed."""

    def __init__(self, operation: str, attempts: list[str]) -> None:
        self.operation = operation
        self.attempts = attempts
        trail = "; ".join(attempts) if attempts else "no attempts"
        super().__init__(f"All LLM providers failed for {operation!r}: {trail}")
