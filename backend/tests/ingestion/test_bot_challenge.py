"""Bot-check recognition in the shared fetcher and the ingestion task (no network)."""

from __future__ import annotations

from typing import Any

import pytest

from app.catalog.enums import SubmissionState
from app.config import Settings
from app.ingestion import tasks
from app.ingestion.fetcher import (
    BotChallengeError,
    FetchedDocument,
    FetchError,
    FetchPolicy,
    bot_challenge_reason,
    browser_fallback_eligible,
)
from tests.challenge_pages import (
    CHALLENGE_403,
    CHALLENGE_503,
    CHALLENGE_HEADERS,
    CHALLENGE_HTML,
    EVENT_200,
    EVENT_HTML,
    EVENT_URL,
    HTML,
    NOT_FOUND_404,
    allow_fixture_hosts,
    mock_fetch_url,
)

# --------------------------------------------------------------------------- #
# Detector
# --------------------------------------------------------------------------- #


def test_cf_mitigated_header_is_enough_at_any_status() -> None:
    assert bot_challenge_reason(403, CHALLENGE_HEADERS, b"") == "cf-mitigated:challenge"
    assert bot_challenge_reason(200, {"CF-Mitigated": "challenge"}, b"") == (
        "cf-mitigated:challenge"
    )


def test_challenge_title_on_an_error_status() -> None:
    status, headers, body = CHALLENGE_503
    assert bot_challenge_reason(status, headers, body) == "title:Just a moment..."
    assert bot_challenge_reason(403, {}, CHALLENGE_HTML) == "title:Just a moment..."


def test_challenge_marker_on_an_error_status() -> None:
    body = b"<html><body><script>window._cf_chl_opt={cType:'managed'}</script></body></html>"
    assert bot_challenge_reason(403, {}, body) == "marker:cf_chl_"


def test_plain_forbidden_is_not_a_challenge() -> None:
    body = b"<html><head><title>403 Forbidden</title></head><body>nginx</body></html>"
    assert bot_challenge_reason(403, {"server": "nginx"}, body) is None


def test_normal_devpost_page_is_not_a_challenge() -> None:
    # The page mentions a CAPTCHA and carries Cloudflare's ordinary
    # /cdn-cgi/challenge-platform/scripts/jsd beacon; neither makes it a wall.
    assert bot_challenge_reason(200, {"content-type": HTML}, EVENT_HTML) is None


def test_a_200_needs_title_and_marker() -> None:
    assert bot_challenge_reason(200, {}, b"<title>Just a moment...</title>") is None
    assert bot_challenge_reason(200, {}, CHALLENGE_HTML) == "title:Just a moment..."


def test_challenge_error_is_still_a_fetch_error() -> None:
    exc = BotChallengeError(EVENT_URL, 403, "cf-mitigated:challenge")
    assert isinstance(exc, FetchError)
    assert str(exc).startswith(f"HTTP 403 for {EVENT_URL}")
    assert (exc.status_code, exc.reason) == (403, "cf-mitigated:challenge")


# --------------------------------------------------------------------------- #
# fetch_url
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _fixture_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_fixture_hosts(monkeypatch)


async def test_fetch_url_raises_on_cloudflare_403() -> None:
    with pytest.raises(BotChallengeError) as caught:
        await mock_fetch_url(CHALLENGE_403)(EVENT_URL, FetchPolicy())
    assert caught.value.status_code == 403
    assert caught.value.reason == "cf-mitigated:challenge"


async def test_fetch_url_raises_on_cloudflare_503_without_header() -> None:
    with pytest.raises(BotChallengeError) as caught:
        await mock_fetch_url(CHALLENGE_503)(EVENT_URL, FetchPolicy())
    assert caught.value.status_code == 503
    assert caught.value.reason == "title:Just a moment..."


async def test_fetch_url_raises_on_a_challenge_served_with_200() -> None:
    reply = (200, {"content-type": HTML}, CHALLENGE_HTML)
    with pytest.raises(BotChallengeError) as caught:
        await mock_fetch_url(reply)(EVENT_URL, FetchPolicy())
    assert caught.value.status_code == 200


async def test_fetch_url_finds_the_title_in_a_large_first_chunk() -> None:
    # The old code kept only chunks while the running total stayed under 2 KiB,
    # so a big first chunk lost the title entirely.
    status, headers, body = CHALLENGE_503
    padded = body.replace(b"</head>", b"<style>" + b"x" * 9000 + b"</style></head>")
    with pytest.raises(BotChallengeError):
        await mock_fetch_url((status, headers, padded))(EVENT_URL, FetchPolicy())


async def test_fetch_url_header_wins_even_when_the_policy_rejects_html() -> None:
    json_only = FetchPolicy(allowed_content_type_prefixes=("application/json",))
    with pytest.raises(BotChallengeError) as caught:
        await mock_fetch_url(CHALLENGE_403)(EVENT_URL, json_only)
    assert caught.value.reason == "cf-mitigated:challenge"


async def test_fetch_url_still_returns_a_normal_page() -> None:
    doc = await mock_fetch_url(EVENT_200)(EVENT_URL, FetchPolicy())
    assert doc.status_code == 200
    assert b"Kiroween Online Hack 2026" in doc.body


async def test_fetch_url_plain_404_is_an_ordinary_fetch_error() -> None:
    with pytest.raises(FetchError) as caught:
        await mock_fetch_url(NOT_FOUND_404)(EVENT_URL, FetchPolicy())
    assert not isinstance(caught.value, BotChallengeError)


def test_browser_fallback_never_targets_a_challenge() -> None:
    doc = FetchedDocument(
        url=EVENT_URL,
        final_url=EVENT_URL,
        status_code=200,
        content_type=HTML,
        body=CHALLENGE_HTML,
        headers={"content-type": HTML},
    )
    assert browser_fallback_eligible(doc) is False


# --------------------------------------------------------------------------- #
# Ingestion task (community submissions and the fetch queue)
# --------------------------------------------------------------------------- #


class _Storage:
    def __init__(self) -> None:
        self.stored: list[FetchedDocument] = []

    async def store_document(self, doc: FetchedDocument) -> Any:
        self.stored.append(doc)

        class _Ref:
            content_hash = doc.content_hash
            storage_key = "k"
            byte_size = len(doc.body)
            reused_existing = False

        return _Ref()


async def test_fetch_and_store_records_a_block_and_stores_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tasks, "fetch_url", mock_fetch_url(CHALLENGE_403))
    storage = _Storage()
    result = await tasks._fetch_and_store(EVENT_URL, storage=storage, run_extract=False)  # type: ignore[arg-type]
    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["needs_human_check"] is True
    assert result["status_code"] == 403
    assert result["block_reason"] == "cf-mitigated:challenge"
    assert "title" not in result  # nothing parsed from the challenge
    assert storage.stored == []


async def test_fetch_and_store_still_parses_a_normal_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tasks, "fetch_url", mock_fetch_url(EVENT_200))
    storage = _Storage()
    result = await tasks._fetch_and_store(EVENT_URL, storage=storage, run_extract=False)  # type: ignore[arg-type]
    assert result["ok"] is True
    assert "blocked" not in result
    assert result["title"] == "Kiroween Online Hack 2026"
    assert len(storage.stored) == 1


def _run_submission_task(
    monkeypatch: pytest.MonkeyPatch, fetch_result: dict[str, Any]
) -> tuple[list[SubmissionState], list[dict[str, Any]]]:
    """Run ``ingestion.fetch_submission`` with every DB / broker edge stubbed."""
    import app.submissions.review_pipeline as review_pipeline

    states: list[SubmissionState] = []
    reviewed: list[dict[str, Any]] = []

    async def prepare(_sid: str, *, settings: Settings) -> dict[str, Any]:
        return {"url": EVENT_URL, "listing_kind": "hackathon"}

    async def mark(_sid: str, state: SubmissionState, **_: Any) -> None:
        states.append(state)

    async def finalize(_sid: str, result: dict[str, Any], **_: Any) -> dict[str, Any]:
        reviewed.append(result)
        return {"recommendation": "needs_more_info"}

    monkeypatch.setattr(tasks, "_prepare_submission_fetch", prepare)
    monkeypatch.setattr(tasks, "_mark_submission_state", mark)
    monkeypatch.setattr(tasks, "fetch_document", lambda _req: dict(fetch_result))
    monkeypatch.setattr(
        tasks,
        "get_settings",
        lambda: Settings(_env_file=None, app_env="test", ai_review_enabled=True),  # type: ignore[call-arg]
    )
    monkeypatch.setattr(review_pipeline, "finalize_submission_review", finalize)
    tasks.fetch_submission.run("00000000-0000-0000-0000-000000000001")
    return states, reviewed


def test_blocked_submission_goes_to_review_without_retrying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = {
        "ok": False,
        "blocked": True,
        "needs_human_check": True,
        "block_reason": "cf-mitigated:challenge",
        "status_code": 403,
        "error": "Blocked by a bot check (cf-mitigated:challenge); the page was not read",
        "url": EVENT_URL,
    }
    # A retry would raise celery's Retry here; reaching review proves there was none.
    states, reviewed = _run_submission_task(monkeypatch, blocked)
    assert states == [SubmissionState.REVIEWING]
    assert reviewed and reviewed[0]["blocked"] is True
