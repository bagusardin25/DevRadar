"""Per-directory health for the multi-source harvest.

Most directory endpoints are undocumented and change without notice. A source
that silently starts returning nothing looks exactly like a quiet week, so this
module reads each source's recent harvest ``CrawlRun`` rows and flags:

- ``never_run``  — no harvest run recorded yet
- ``blocked``    — the latest run hit a bot wall (never worked around)
- ``failing``    — ``FAILING_STREAK`` or more failed runs in a row
- ``degraded``   — the latest run was partial (shape change, fetch errors)
- ``silent``     — the latest run found nothing while earlier runs found rows,
                   the usual symptom of a changed payload shape
- ``stale``      — no successful run for ``STALE_AFTER``

It only reads; nothing here changes a source or a run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.enums import CrawlRunStatus, CrawlTrigger
from app.harvest.runner import HARVEST_SOURCES
from app.ingestion.models import CrawlRun
from app.sources.models import Source

#: Recent runs read per source.
RUNS_PER_SOURCE = 9
FAILING_STREAK = 3
STALE_AFTER = timedelta(hours=48)
_OK = (CrawlRunStatus.SUCCEEDED.value, CrawlRunStatus.PARTIAL.value)


@dataclass(frozen=True, slots=True)
class RunView:
    """The parts of a ``CrawlRun`` health looks at."""

    status: str
    started_at: datetime | None
    discovered: int
    error: str | None = None


@dataclass(slots=True)
class SourceHealth:
    key: str
    label: str
    enabled: bool
    flags: list[str] = field(default_factory=list)
    last_status: str | None = None
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_discovered: int | None = None
    typical_discovered: float | None = None
    consecutive_failures: int = 0
    last_error: str | None = None

    @property
    def healthy(self) -> bool:
        return not self.enabled or set(self.flags) <= {"never_run"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "enabled": self.enabled,
            "healthy": self.healthy,
            "flags": list(self.flags),
            "lastStatus": self.last_status,
            "lastRunAt": self.last_run_at.isoformat() if self.last_run_at else None,
            "lastSuccessAt": self.last_success_at.isoformat() if self.last_success_at else None,
            "lastDiscovered": self.last_discovered,
            "typicalDiscovered": self.typical_discovered,
            "consecutiveFailures": self.consecutive_failures,
            "lastError": self.last_error,
        }


def assess(
    key: str,
    runs: list[RunView],
    *,
    now: datetime,
    enabled: bool = True,
) -> SourceHealth:
    """Health of one source from its runs, newest first."""
    info = HARVEST_SOURCES[key]
    health = SourceHealth(key=key, label=info.label, enabled=enabled)
    if not runs:
        health.flags.append("never_run")
        return health

    latest = runs[0]
    health.last_status = latest.status
    health.last_run_at = latest.started_at
    health.last_discovered = latest.discovered
    health.last_error = latest.error

    for run in runs:
        if run.status != CrawlRunStatus.FAILED.value:
            break
        health.consecutive_failures += 1

    successes = [run for run in runs if run.status in _OK]
    if successes:
        health.last_success_at = successes[0].started_at
    earlier = [run.discovered for run in successes if run is not latest]
    if earlier:
        health.typical_discovered = float(median(earlier))

    if latest.status == CrawlRunStatus.FAILED.value and latest.error == "blocked":
        health.flags.append("blocked")
    if health.consecutive_failures >= FAILING_STREAK:
        health.flags.append("failing")
    if latest.status == CrawlRunStatus.PARTIAL.value:
        health.flags.append("degraded")
    if (
        latest.status in _OK
        and latest.discovered == 0
        and health.typical_discovered
        and health.typical_discovered > 0
    ):
        health.flags.append("silent")
    if health.last_success_at is None or now - health.last_success_at > STALE_AFTER:
        health.flags.append("stale")
    return health


async def harvest_source_health(
    session: AsyncSession,
    *,
    enabled_keys: list[str],
    now: datetime | None = None,
) -> list[SourceHealth]:
    """Health of every known harvest source, in ``HARVEST_SOURCES`` order."""
    now = now or datetime.now(UTC)
    names = {info.name: key for key, info in HARVEST_SOURCES.items()}
    rows = (
        (await session.execute(select(Source).where(Source.name.in_(list(names)))))
        .scalars()
        .all()
    )
    source_ids = {names[row.name]: row.id for row in rows}

    report: list[SourceHealth] = []
    for key in HARVEST_SOURCES:
        runs: list[RunView] = []
        source_id = source_ids.get(key)
        if source_id is not None:
            recent = (
                (
                    await session.execute(
                        select(CrawlRun)
                        .where(
                            CrawlRun.source_id == source_id,
                            CrawlRun.trigger == CrawlTrigger.HARVEST.value,
                        )
                        .order_by(CrawlRun.started_at.desc())
                        .limit(RUNS_PER_SOURCE)
                    )
                )
                .scalars()
                .all()
            )
            runs = [
                RunView(
                    status=str(run.status),
                    started_at=run.started_at,
                    discovered=int(run.discovered_count or 0),
                    error=run.error_summary,
                )
                for run in recent
            ]
        report.append(assess(key, runs, now=now, enabled=key in enabled_keys))
    return report
