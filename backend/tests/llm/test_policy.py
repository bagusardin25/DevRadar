"""Error classification — the rule the whole fallback chain rests on."""

from __future__ import annotations

import httpx
import pytest

from app.llm.policy import (
    DISABLED_COOLDOWN_SECONDS,
    PAYMENT_COOLDOWN_SECONDS,
    QUOTA_COOLDOWN_SECONDS,
    Decision,
    classify_exception,
    classify_status,
)


class TestRateLimitVersusQuota:
    """The distinction that makes failover work at all.

    Both arrive as HTTP 429. A rate limit clears in seconds and is worth
    waiting out; an exhausted balance does not clear until the provider's
    window resets and must take the provider out of rotation.
    """

    def test_insufficient_quota_fails_over_with_long_cooldown(self) -> None:
        verdict = classify_status(429, code="insufficient_quota")
        assert verdict.decision is Decision.FAILOVER
        assert verdict.cooldown_seconds == QUOTA_COOLDOWN_SECONDS

    def test_quota_detected_from_message_when_code_is_absent(self) -> None:
        verdict = classify_status(
            429, message="You exceeded your current quota, please check your plan"
        )
        assert verdict.decision is Decision.FAILOVER
        assert verdict.cooldown_seconds == QUOTA_COOLDOWN_SECONDS

    def test_short_retry_after_waits_in_place(self) -> None:
        verdict = classify_status(429, code="rate_limit_exceeded", retry_after=2)
        assert verdict.decision is Decision.RETRY_SAME
        assert verdict.retry_after_seconds == 2

    def test_long_retry_after_fails_over_for_that_long(self) -> None:
        verdict = classify_status(429, code="rate_limit_exceeded", retry_after=30)
        assert verdict.decision is Decision.FAILOVER
        assert verdict.cooldown_seconds == 30

    def test_rate_limit_without_header_uses_default_cooldown(self) -> None:
        verdict = classify_status(429, code="rate_limit_exceeded")
        assert verdict.decision is Decision.FAILOVER
        assert verdict.cooldown_seconds == 60


class TestTerminalProviderStates:
    @pytest.mark.parametrize("status", [401, 403])
    def test_auth_failure_disables_provider(self, status: int) -> None:
        verdict = classify_status(status)
        assert verdict.decision is Decision.FAILOVER
        assert verdict.cooldown_seconds == DISABLED_COOLDOWN_SECONDS

    def test_missing_model_disables_provider(self) -> None:
        # Free model IDs are withdrawn without notice; retrying never helps.
        verdict = classify_status(404, message="model not found")
        assert verdict.decision is Decision.FAILOVER
        assert verdict.cooldown_seconds == DISABLED_COOLDOWN_SECONDS

    def test_payment_required_needs_an_operator(self) -> None:
        verdict = classify_status(402)
        assert verdict.decision is Decision.FAILOVER
        assert verdict.cooldown_seconds == PAYMENT_COOLDOWN_SECONDS


class TestBadRequests:
    def test_plain_400_is_fatal(self) -> None:
        # Our request is malformed: every other provider would reject it too.
        assert classify_status(400, message="invalid parameter").decision is Decision.FATAL

    def test_oversized_context_fails_over_instead(self) -> None:
        verdict = classify_status(
            400, message="This model's maximum context length is 8192 tokens"
        )
        assert verdict.decision is Decision.FAILOVER
        assert verdict.reason == "context_too_large"

    def test_413_fails_over(self) -> None:
        assert classify_status(413).decision is Decision.FAILOVER


class TestTransient:
    @pytest.mark.parametrize("status", [500, 502, 503, 504])
    def test_server_errors_retry_in_place(self, status: int) -> None:
        assert classify_status(status).decision is Decision.RETRY_SAME

    def test_request_timeout_status_retries(self) -> None:
        assert classify_status(408).decision is Decision.RETRY_SAME

    def test_unmapped_status_fails_over(self) -> None:
        assert classify_status(418).decision is Decision.FAILOVER


class TestExceptions:
    def test_timeout_retries_in_place(self) -> None:
        verdict = classify_exception(httpx.ReadTimeout("slow"))
        assert verdict.decision is Decision.RETRY_SAME

    def test_connection_failure_fails_over(self) -> None:
        verdict = classify_exception(httpx.ConnectError("refused"))
        assert verdict.decision is Decision.FAILOVER

    def test_unparseable_json_fails_over(self) -> None:
        verdict = classify_exception(ValueError("LLM response is not a JSON object"))
        assert verdict.decision is Decision.FAILOVER
        assert "ValueError" in verdict.reason
