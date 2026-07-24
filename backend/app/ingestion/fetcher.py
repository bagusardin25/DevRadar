"""Safe HTTP fetcher with SSRF checks, redirect limits, and size caps."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx

from app.errors import ValidationError
from app.ingestion.ssrf import SSRFError, validate_url_for_fetch

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB
DEFAULT_MAX_REDIRECTS = 5

ALLOWED_CONTENT_TYPE_PREFIXES = (
    "text/html",
    "text/plain",
    "application/xhtml",
    "application/xml",
    "text/xml",
    "application/json",
    "application/rss",
    "application/atom",
    "application/javascript",  # rare; blocked unless policy allows
)


@dataclass(slots=True)
class FetchPolicy:
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_bytes: int = DEFAULT_MAX_BYTES
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    allowed_content_type_prefixes: tuple[str, ...] = (
        "text/html",
        "text/plain",
        "application/xhtml",
        "application/xml",
        "text/xml",
        "application/json",
        "application/rss",
        "application/atom",
    )
    allow_browser_fallback: bool = True
    user_agent: str = "DevRadarBot/0.1 (+https://devradar.local; fetch)"
    # Conditional request cache hints
    etag: str | None = None
    if_modified_since: str | None = None


@dataclass(slots=True)
class FetchedDocument:
    url: str
    final_url: str
    status_code: int
    content_type: str | None
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)
    etag: str | None = None
    last_modified: str | None = None
    content_hash: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    redirect_chain: list[str] = field(default_factory=list)
    not_modified: bool = False

    def __post_init__(self) -> None:
        if not self.content_hash and self.body:
            self.content_hash = hashlib.sha256(self.body).hexdigest()


class FetchError(ValidationError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, errors=[{"field": "fetch", "message": detail}])


def _content_type_allowed(content_type: str | None, policy: FetchPolicy) -> bool:
    if not content_type:
        return True  # allow missing; parser will decide
    ct = content_type.split(";")[0].strip().lower()
    return any(ct.startswith(p) for p in policy.allowed_content_type_prefixes)


async def fetch_url(
    url: str,
    policy: FetchPolicy | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> FetchedDocument:
    """Fetch a URL with SSRF protection and streaming size enforcement.

    Re-validates host after every redirect. Does not follow redirects automatically
    so each hop can be policy-checked.
    """
    policy = policy or FetchPolicy()
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=policy.timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": policy.user_agent},
        )

    try:
        current, _host, _ips = validate_url_for_fetch(url)
        redirect_chain: list[str] = []
        headers: dict[str, str] = {}
        if policy.etag:
            headers["If-None-Match"] = policy.etag
        if policy.if_modified_since:
            headers["If-Modified-Since"] = policy.if_modified_since

        for _hop in range(policy.max_redirects + 1):
            validate_url_for_fetch(current)
            try:
                async with client.stream("GET", current, headers=headers) as response:
                    # Capture redirect without reading body
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError("Redirect without Location header")
                        next_url = urljoin(current, location)
                        redirect_chain.append(current)
                        # Block redirect into credentials or private targets
                        try:
                            next_url, _, _ = validate_url_for_fetch(next_url)
                        except SSRFError as exc:
                            raise FetchError(
                                f"Redirect target blocked: {exc.detail}"
                            ) from exc
                        current = next_url
                        if len(redirect_chain) > policy.max_redirects:
                            raise FetchError("Too many redirects")
                        continue

                    content_type = response.headers.get("content-type")
                    if not _content_type_allowed(content_type, policy):
                        raise FetchError(
                            f"Content type not allowed: {content_type or '(missing)'}"
                        )

                    if response.status_code == 304:
                        return FetchedDocument(
                            url=url,
                            final_url=current,
                            status_code=304,
                            content_type=content_type,
                            body=b"",
                            headers=dict(response.headers),
                            etag=response.headers.get("etag") or policy.etag,
                            last_modified=response.headers.get("last-modified")
                            or policy.if_modified_since,
                            content_hash="",
                            redirect_chain=redirect_chain,
                            not_modified=True,
                        )

                    if response.status_code >= 400:
                        # Consume small error body for diagnostics but cap it
                        err_chunks: list[bytes] = []
                        err_size = 0
                        async for chunk in response.aiter_bytes():
                            err_size += len(chunk)
                            if err_size <= 2048:
                                err_chunks.append(chunk)
                            if err_size > policy.max_bytes:
                                break
                        raise FetchError(f"HTTP {response.status_code} for {current}")

                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > policy.max_bytes:
                            raise FetchError(
                                f"Response exceeds max size of {policy.max_bytes} bytes"
                            )
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    return FetchedDocument(
                        url=url,
                        final_url=str(response.url) if response.url else current,
                        status_code=response.status_code,
                        content_type=content_type,
                        body=body,
                        headers={k.lower(): v for k, v in response.headers.items()},
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                        redirect_chain=redirect_chain,
                    )
            except httpx.TimeoutException as exc:
                raise FetchError(f"Fetch timed out after {policy.timeout_seconds}s") from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"HTTP error: {type(exc).__name__}") from exc

        raise FetchError("Too many redirects")
    finally:
        if owns_client:
            await client.aclose()


def browser_fallback_eligible(
    fetched: FetchedDocument | None,
    *,
    policy: FetchPolicy | None = None,
    html_hint: str | None = None,
) -> bool:
    """Whether a browser worker should re-fetch this page.

    Heuristic only — actual Playwright lives in an isolated worker process.
    """
    policy = policy or FetchPolicy()
    if not policy.allow_browser_fallback:
        return False
    if fetched is None:
        return False
    if fetched.not_modified or fetched.status_code != 200:
        return False
    ct = (fetched.content_type or "").lower()
    if "html" not in ct and not (html_hint or ""):
        return False
    text = (html_hint or fetched.body[:8000].decode("utf-8", errors="ignore")).lower()
    spa_signals = (
        'id="root"',
        'id="app"',
        "window.__next_data__",
        "ng-version",
        "data-reactroot",
        "__nuxt",
    )
    # Thin shell: little text content relative to script tags
    script_count = text.count("<script")
    body_text_len = len(
        "".join(ch for ch in text if ch.isalnum() or ch.isspace())
    )
    if any(sig in text for sig in spa_signals):
        return True
    return bool(script_count >= 5 and body_text_len < 500)
