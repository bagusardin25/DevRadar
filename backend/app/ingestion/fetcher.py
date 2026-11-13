"""Safe HTTP fetcher with SSRF checks, redirect limits, and size caps.

Bot checks (Cloudflare's "Just a moment..." page, AWS WAF, CAPTCHA walls) are
recognised here, once, for every caller: :func:`fetch_url` raises
:class:`BotChallengeError` instead of returning the challenge as a document.
A challenge is never worked around — no solver, no stealth browser, no proxy —
and it is never parsed as page content or read as a dead link. Callers record
the page as blocked and retry later or leave it to a human.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
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


class BotChallengeError(FetchError):
    """The site answered with a bot check instead of the page.

    The message keeps the ``HTTP <status> for <url>`` prefix of a plain
    :class:`FetchError`, so code matching on the status still works.
    """

    def __init__(self, url: str, status_code: int, reason: str) -> None:
        super().__init__(f"HTTP {status_code} for {url}: bot challenge ({reason})")
        self.url = url
        self.status_code = status_code
        self.reason = reason


# --------------------------------------------------------------------------- #
# Bot-challenge detection
# --------------------------------------------------------------------------- #

#: Statuses a challenge is served with: Cloudflare's managed challenge answers
#: 403, its older JavaScript challenge 503, rate-limit walls 429.
CHALLENGE_STATUS_CODES = frozenset({403, 429, 503})
#: Leading bytes of a response searched for challenge markers.
CHALLENGE_SNIFF_BYTES = 16_384

_TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_CHALLENGE_TITLE = re.compile(
    r"just a moment|attention required|verifying you are human|checking your browser"
    r"|human verification|captcha|access denied",
    re.IGNORECASE,
)
# Strings only challenge pages carry. "challenge-platform" is deliberately not
# one: Cloudflare injects /cdn-cgi/challenge-platform/scripts/jsd/main.js into
# ordinary pages as well.
_CHALLENGE_MARKERS = ("cf_chl_", "cf-chl", "chl_page", "awswaf")


def bot_challenge_reason(
    status_code: int,
    headers: Mapping[str, str] | None,
    body: bytes | str | None,
) -> str | None:
    """Return why a response is a bot check rather than the page, else ``None``.

    - ``cf-mitigated: challenge`` (Cloudflare's own signal) is enough at any
      status.
    - On 403 / 429 / 503 a challenge title ("Just a moment...") or a challenge
      marker in the body is enough.
    - On any other status (a 200) both a challenge title *and* a marker are
      needed, so a real page that merely mentions a CAPTCHA is not lost.
    """
    for key, value in (headers or {}).items():
        if key.lower() == "cf-mitigated" and "challenge" in str(value).lower():
            return "cf-mitigated:challenge"

    if isinstance(body, bytes):
        text = body[:CHALLENGE_SNIFF_BYTES].decode("utf-8", errors="ignore")
    else:
        text = (body or "")[:CHALLENGE_SNIFF_BYTES]
    lowered = text.lower()

    title = None
    match = _TITLE_TAG.search(text)
    if match and _CHALLENGE_TITLE.search(match.group(1)):
        title = " ".join(match.group(1).split())[:60]
    marker = next((m for m in _CHALLENGE_MARKERS if m in lowered), None)

    if status_code in CHALLENGE_STATUS_CODES:
        if title:
            return f"title:{title}"
        if marker:
            return f"marker:{marker}"
        return None
    if title and marker:
        return f"title:{title}"
    return None


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
                        reason = bot_challenge_reason(
                            response.status_code, response.headers, None
                        )
                        if reason is not None:
                            raise BotChallengeError(current, response.status_code, reason)
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
                        # Keep the head of the error body: enough to recognise
                        # a bot check, never parsed as content.
                        err_head = bytearray()
                        err_size = 0
                        async for chunk in response.aiter_bytes():
                            err_size += len(chunk)
                            if len(err_head) < CHALLENGE_SNIFF_BYTES:
                                err_head.extend(chunk[: CHALLENGE_SNIFF_BYTES - len(err_head)])
                            if err_size > policy.max_bytes or (
                                len(err_head) >= CHALLENGE_SNIFF_BYTES
                            ):
                                break
                        reason = bot_challenge_reason(
                            response.status_code, response.headers, bytes(err_head)
                        )
                        if reason is not None:
                            raise BotChallengeError(current, response.status_code, reason)
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
                    reason = bot_challenge_reason(response.status_code, response.headers, body)
                    if reason is not None:
                        raise BotChallengeError(current, response.status_code, reason)
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
    # A browser re-fetch must never be a way past a bot check.
    if bot_challenge_reason(fetched.status_code, fetched.headers, fetched.body) is not None:
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
