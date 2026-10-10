"""HackQuest directory connector.

``https://www.hackquest.io/robots.txt`` disallows ``/api/``, so the JSON API
behind the site is **never** called. Only the public HTML page
``/hackathons`` is read: it is a Next.js (App Router) page whose first slice of
hackathons travels inside the React Server Component flight data
(``self.__next_f.push([1, "..."])``), as ``{"data": [...], "total": n}``.

By policy this is the *server-embedded slice only* (a handful of rows). The
"load more" listing is fetched client side from the disallowed API and is
deliberately out of reach. The page is a single page: no paging.

Every step validates its shape and degrades to an empty page (with a warning)
instead of raising. Offline tests pass ``fixtures`` (raw rows) or ``http_get``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.sources.connectors.base import (
    ConnectorQuery,
    DiscoveryCandidate,
    DiscoveryPage,
)
from app.sources.connectors.directory_common import (
    DirectoryConnector,
    SourceBlocked,
    iso_utc,
    matches_query,
)
from app.sources.connectors.lablab import MAX_DECODED_CHARS, decode_rsc_text

logger = logging.getLogger(__name__)

HACKQUEST_HOST = "https://www.hackquest.io"
HACKQUEST_URL = f"{HACKQUEST_HOST}/hackathons"
MAX_BYTES = 3_145_728

_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_DATA_OBJECT = re.compile(r'\{"data":\s*\[')
USD_LIKE = frozenset({"USD", "USDC", "USDT"})

_MODES = {
    "ONLINE": "online",
    "VIRTUAL": "online",
    "HYBRID": "hybrid",
    "OFFLINE": "in_person",
    "IN_PERSON": "in_person",
    "ONSITE": "in_person",
}


def extract_hackathon_rows(text: str) -> list[dict[str, Any]] | None:
    """Find the hackathon rows in decoded flight text, or ``None`` if absent.

    The flight stream holds several ``{"data": [...]}`` objects (some are empty
    placeholders); the first one whose rows look like hackathons is returned.
    """
    for match in _DATA_OBJECT.finditer(text):
        try:
            value, _end = json.JSONDecoder().raw_decode(text, match.start())
        except ValueError:
            continue
        data = value.get("data") if isinstance(value, dict) else None
        if not isinstance(data, list):
            continue
        rows = [
            row
            for row in data
            if isinstance(row, dict) and "alias" in row and "name" in row
        ]
        if rows:
            return rows
    return None


def _mode_from(value: Any) -> str | None:
    key = re.sub(r"[\s-]+", "_", str(value or "").strip().upper())
    return _MODES.get(key)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", ""))
    except ValueError:
        return None


def prize_fields(row: dict[str, Any]) -> tuple[float | int | None, str | None]:
    """Return ``(prize_value, prize_text)``.

    The value is a number only when every reward currency is clearly a dollar
    (USD / USDC / USDT); the raw text is always kept.
    """
    rewards = row.get("rewards")
    entries = [r for r in rewards if isinstance(r, dict)] if isinstance(rewards, list) else []
    currencies = {str(r.get("currency") or "").strip().upper() for r in entries}
    total = _number(row.get("totalRewards"))
    if row.get("totalRewards") in (None, "") and entries:
        parts = [_number(r.get("totalRewards")) for r in entries]
        if all(part is not None for part in parts):
            total = sum(part for part in parts if part is not None)

    raw = row.get("totalRewards")
    shown = str(raw).strip() if raw not in (None, "") else None
    if shown is None and total is not None:
        shown = f"{total:g}"
    sorted_currencies = sorted(c for c in currencies if c)
    prize_text = (
        " ".join(part for part in (shown, "/".join(sorted_currencies)) if part) or None
    )

    if total is None or total <= 0:
        return None, prize_text
    if currencies and currencies <= USD_LIKE:
        return (int(total) if total == int(total) else total), prize_text
    return None, prize_text


def _themes(row: dict[str, Any]) -> list[str]:
    themes: list[str] = []
    info = row.get("info")
    stack = info.get("teachStack") if isinstance(info, dict) else None
    values: list[Any] = list(stack) if isinstance(stack, list) else []
    ecosystem = row.get("ecosystem")
    if isinstance(ecosystem, list):
        values += [e.get("type") for e in ecosystem if isinstance(e, dict)]
    for value in values:
        if not isinstance(value, str):
            continue
        name = value.strip()
        if name and name.lower() != "all" and name not in themes:
            themes.append(name)
    return themes


class HackQuestConnector(DirectoryConnector):
    name = "hackquest"
    connector_type = "hackquest"

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        if self._fixtures is not None:
            return self._discover_fixtures(query, cursor)
        return await self._discover_live(query)

    # -- fixtures ---------------------------------------------------------- #

    def _discover_fixtures(
        self, query: ConnectorQuery, cursor: str | None
    ) -> DiscoveryPage:
        assert self._fixtures is not None
        start = int(cursor or 0)
        cap = max(1, query.result_cap)
        items = self._parse_rows(self._fixtures, query)
        page = items[start : start + cap]
        next_cursor = str(start + cap) if start + cap < len(items) else None
        return DiscoveryPage(items=page, next_cursor=next_cursor)

    # -- live -------------------------------------------------------------- #

    async def _discover_live(self, query: ConnectorQuery) -> DiscoveryPage:
        try:
            page_html = await self.load_text(HACKQUEST_URL, MAX_BYTES)
        except SourceBlocked as blocked:
            return self.block(HACKQUEST_URL, blocked.reason)
        except Exception as exc:
            return self.failed(HACKQUEST_URL, exc)

        text, pushes = decode_rsc_text(page_html)
        rows = None if len(text) > MAX_DECODED_CHARS else extract_hackathon_rows(text)
        if rows is None:
            logger.warning(
                "hackquest_payload_missing",
                extra={"pushes": pushes, "decoded_len": len(text)},
            )
            self.degraded = "hackquest_payload_missing"
            return DiscoveryPage(items=[], next_cursor=None)
        return DiscoveryPage(items=self._parse_rows(rows, query), next_cursor=None)

    # -- rows -------------------------------------------------------------- #

    def _parse_rows(
        self, rows: list[Any], query: ConnectorQuery
    ) -> list[DiscoveryCandidate]:
        items: list[DiscoveryCandidate] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = self._candidate_from_row(row)
            if item is None or item.external_id in seen:
                continue
            if not matches_query(item.title, query.query_text):
                continue
            seen.add(item.external_id)
            items.append(item)
        return items

    def _candidate_from_row(self, row: dict[str, Any]) -> DiscoveryCandidate | None:
        alias = str(row.get("alias") or "").strip()
        row_id = row.get("id") or alias
        title = str(row.get("name") or "").strip()
        if not row_id or not title or not _ALIAS.match(alias):
            self.skipped("missing_id_title_or_bad_alias", row_id)
            return None
        if row.get("status") not in (None, "publish"):
            return None  # draft / unpublished

        info = row.get("info")
        info = info if isinstance(info, dict) else {}
        mode = _mode_from(info.get("mode"))
        if mode is None:
            self.skipped("unknown_mode", row_id)
            return None
        if mode == "in_person":
            return None  # online-only discover

        timeline = row.get("timeline")
        timeline = timeline if isinstance(timeline, dict) else {}
        starts_raw = timeline.get("submissionOpen") or timeline.get("registrationOpen")
        ends_raw = timeline.get("submissionClose") or timeline.get("rewardTime")
        reg_end_raw = timeline.get("registrationClose")
        starts_at, ends_at = iso_utc(starts_raw), iso_utc(ends_raw)
        registration_ends_at = iso_utc(reg_end_raw)
        if (
            (starts_raw is not None and starts_at is None)
            or (ends_raw is not None and ends_at is None)
            or (reg_end_raw is not None and registration_ends_at is None)
        ):
            self.skipped("bad_dates", row_id)
            return None
        if self.ended(ends_at):
            return None

        prize_value, prize_text = prize_fields(row)
        host = info.get("host")
        organization = host.strip() if isinstance(host, str) and host.strip() else None
        url = f"{HACKQUEST_URL}/{alias}"
        return DiscoveryCandidate(
            external_id=str(row_id),
            url=url,
            title=title,
            metadata={
                "source": self.name,
                "mode": mode,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "prize_value": prize_value,
                "prize_text": prize_text,
                "organization": organization,
                "location": "Online" if mode == "online" else "Hybrid",
                "themes": _themes(row),
                "directory_url": url,
                "registration_ends_at": registration_ends_at,
            },
        )
