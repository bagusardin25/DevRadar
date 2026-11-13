"""Harvest source health assessment (DB-free)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.harvest.health import FAILING_STREAK, RunView, assess

NOW = datetime(2026, 10, 10, 16, 0, tzinfo=UTC)


def _run(
    hours_ago: int, status: str = "succeeded", discovered: int = 12, error: str | None = None
) -> RunView:
    return RunView(
        status=status,
        started_at=NOW - timedelta(hours=hours_ago),
        discovered=discovered,
        error=error,
    )


def test_never_run_is_not_unhealthy() -> None:
    health = assess("dorahacks", [], now=NOW)
    assert health.flags == ["never_run"]
    assert health.healthy
    assert health.label == "DoraHacks"


def test_steady_source_is_healthy() -> None:
    health = assess("devpost", [_run(0), _run(8), _run(16)], now=NOW)
    assert health.flags == []
    assert health.healthy
    assert health.last_discovered == 12
    assert health.typical_discovered == 12
    assert health.last_success_at == NOW


def test_blocked_latest_run() -> None:
    health = assess(
        "dorahacks", [_run(0, "failed", 0, "blocked"), _run(8)], now=NOW
    )
    assert "blocked" in health.flags
    assert health.consecutive_failures == 1
    assert not health.healthy


def test_failure_streak_and_staleness() -> None:
    runs = [_run(8 * n, "failed", 0, "TimeoutError") for n in range(FAILING_STREAK)]
    runs.append(_run(72))
    health = assess("unstop", runs, now=NOW)
    assert health.consecutive_failures == FAILING_STREAK
    assert {"failing", "stale"} <= set(health.flags)
    assert health.last_error == "TimeoutError"


def test_silent_source_after_finding_rows_before() -> None:
    health = assess("devfolio", [_run(0, discovered=0), _run(8, discovered=9)], now=NOW)
    assert health.flags == ["silent"]
    assert not health.healthy


def test_always_empty_source_is_not_silent() -> None:
    health = assess("commudle", [_run(0, discovered=0), _run(8, discovered=0)], now=NOW)
    assert health.flags == []


def test_partial_run_is_degraded_but_counts_as_success() -> None:
    health = assess("taikai", [_run(0, "partial", 4, "taikai_directory_failed")], now=NOW)
    assert health.flags == ["degraded"]
    assert health.last_success_at == NOW


def test_disabled_source_is_never_reported_unhealthy() -> None:
    health = assess("hackclub", [_run(0, "failed", 0, "blocked")], now=NOW, enabled=False)
    assert "blocked" in health.flags
    assert health.healthy
    assert health.as_dict()["enabled"] is False
