"""TAIKAI directory connector.

``https://taikai.network/en/hackathons`` is a server-rendered Next.js (pages
router) page. Besides the cards it ships ``<script id="__NEXT_DATA__">`` whose
``props.apolloState`` is the normalised Apollo cache of the listing query: one
``Challenge:<id>`` entry per card, with ``__ref`` links to ``Organization``,
``PrizeCurrency``, ``ChallengeStep`` and ``Industry`` entries. We read that
instead of scraping cards (the JSON-LD ``ItemList`` holds only URLs).

What the listing does **not** carry:

* **Mode.** There is no online/in-person field. A row is queued only when its
  name or short description says so (``Online``, ``Virtual``, ``Remote``,
  ``Online + IRL``, ``Online participation possible`` ...); anything else is
  skipped as ``unknown_mode`` rather than guessed.
* **A real start/end.** ``steps`` only holds a ``startDate`` per milestone, so
  ``starts_at`` is the earliest milestone (the challenge opening) and
  ``ends_at`` the end of the UTC day of the latest milestone. That window
  always overlaps the real event, which is what cross-source dedupe needs.
* **Pagination links.** The page lists the 20 newest challenges (``order``
  descending, ``isClosed`` ones included); open challenges come first, so one
  page is enough for a harvest.

Prize: ``prize`` is the whole-unit amount shown on the card (``prizeDecimals``
is display-only). It becomes ``prize_value`` only for USD; otherwise the raw
amount and currency go in ``prize_text``.

Future option: TAIKAI also serves an anonymous GraphQL API
(``POST https://api.taikai.network/api/graphql`` with ``challenges(where:
{isPublic: {equals: true}, endParticipantRegistrationDate: {gt: $now}},
orderBy: {endParticipantRegistrationDate: asc}, perPage: 100) {slug name
shortDescription endParticipantRegistrationDate prize prizeCurrency {name}
organization {slug} steps {startDate}}``) which would give a real registration
deadline. The shared fetcher is GET-only, so it is deliberately not used here.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
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
    parse_instant,
)

logger = logging.getLogger(__name__)

TAIKAI_LISTING_URL = "https://taikai.network/en/hackathons"
EVENT_URL = "https://taikai.network/en/{org}/hackathons/{slug}"
MAX_BYTES = 2_097_152

_NEXT_DATA = re.compile(
    r"<script[^>]*\bid=\"__NEXT_DATA__\"[^>]*>(.*?)</script>", re.DOTALL
)
_PATH_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_REMOTE = r"(?:online|virtual|remote)"
_SEP = r"\s*(?:\+|&|/|and|with|plus)\s*"
_PRESENT = r"(?:irl|in[- ]?person|on[- ]?site|onsite|physical|offline|live venue)"
_HYBRID = re.compile(
    rf"\bhybrid\b|\b{_REMOTE}{_SEP}{_PRESENT}\b|\b{_PRESENT}{_SEP}{_REMOTE}\b"
    r"|\bonline (?:participation|attendance|option)s? (?:is |are )?"
    r"(?:possible|available|allowed|welcome)",
    re.IGNORECASE,
)
_ONLINE = re.compile(r"\b(?:online|virtual|virtually|remote|remotely)\b", re.IGNORECASE)
_IN_PERSON = re.compile(rf"\b{_PRESENT}\b", re.IGNORECASE)


def extract_challenges(page_html: str) -> list[dict[str, Any]] | None:
    """Return the listing's challenges with their refs resolved, else ``None``."""
    match = _NEXT_DATA.search(page_html)
    if match is None:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    props = data.get("props") if isinstance(data, dict) else None
    state = props.get("apolloState") if isinstance(props, dict) else None
    if not isinstance(state, dict):
        return None

    ordered: list[Any] = []
    root = state.get("ROOT_QUERY")
    if isinstance(root, dict):
        for key, value in root.items():
            if key.startswith("challenges(") and isinstance(value, list):
                ordered = value
                break
    if not ordered:
        ordered = [
            {"__ref": key} for key in state if str(key).startswith("Challenge:")
        ]

    rows: list[dict[str, Any]] = []
    for ref in ordered:
        entry = _deref(state, ref)
        if not isinstance(entry, dict) or "slug" not in entry or "name" not in entry:
            continue
        rows.append(
            {
                **entry,
                "organization": _deref(state, entry.get("organization")),
                "prizeCurrency": _deref(state, entry.get("prizeCurrency")),
                "publishInfo": _deref(state, entry.get("publishInfo")),
                "steps": [_deref(state, s) for s in _as_list(entry.get("steps"))],
                "industries": [
                    _deref(state, i) for i in _as_list(entry.get("industries"))
                ],
            }
        )
    return rows or None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _deref(state: dict[str, Any], value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("__ref"), str):
        return state.get(value["__ref"])
    return value


def mode_from_text(text: str) -> str | None:
    """``online`` / ``hybrid`` when ``text`` clearly says so, else ``None``."""
    if _HYBRID.search(text):
        return "hybrid"
    if _ONLINE.search(text) and not _IN_PERSON.search(text):
        return "online"
    return None


def _milestones(row: dict[str, Any]) -> list[datetime]:
    found: list[datetime] = []
    for step in _as_list(row.get("steps")):
        parsed = parse_instant(step.get("startDate")) if isinstance(step, dict) else None
        if parsed is not None:
            found.append(parsed)
    return found


def _prize(row: dict[str, Any]) -> tuple[float | None, str | None]:
    amount = row.get("prize")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        return None, None
    currency = row.get("prizeCurrency")
    code = str(currency.get("name") or "").strip() if isinstance(currency, dict) else ""
    text = f"{amount:,.0f} {code}".strip()
    return (float(amount) if code.upper() == "USD" else None), text


class TaikaiConnector(DirectoryConnector):
    name = "taikai"
    connector_type = "taikai"

    async def discover(
        self, query: ConnectorQuery, cursor: str | None = None
    ) -> DiscoveryPage:
        if self._fixtures is not None:
            return self._discover_fixtures(query, cursor)
        return await self._discover_live(query)

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

    async def _discover_live(self, query: ConnectorQuery) -> DiscoveryPage:
        try:
            page_html = await self.load_text(TAIKAI_LISTING_URL, MAX_BYTES)
        except SourceBlocked as blocked:
            return self.block(TAIKAI_LISTING_URL, blocked.reason)
        except Exception as exc:
            return self.failed(TAIKAI_LISTING_URL, exc)

        rows = extract_challenges(page_html)
        if rows is None:
            logger.warning(
                "taikai_payload_missing",
                extra={"found_next_data": "__NEXT_DATA__" in page_html},
            )
            self.degraded = "taikai_payload_missing"
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
        row_id = row.get("id") or row.get("slug")
        if row.get("isClosed") is True or row.get("isPublic") is False:
            return None
        publish = row.get("publishInfo")
        state = publish.get("state") if isinstance(publish, dict) else None
        if state and str(state).upper() != "ACTIVE":
            return None

        title = str(row.get("name") or "").strip()
        slug = str(row.get("slug") or "").strip()
        organization = row.get("organization")
        org_slug = str(organization.get("slug") or "").strip() if isinstance(
            organization, dict
        ) else ""
        if not title or not _PATH_PART.match(slug) or not _PATH_PART.match(org_slug):
            self.skipped("missing_title_or_bad_slug", row_id)
            return None

        moments = _milestones(row)
        starts_at = iso_utc(min(moments)) if moments else None
        ends_at = (
            iso_utc(max(moments).replace(hour=23, minute=59, second=59))
            if moments
            else None
        )
        if self.ended(ends_at):
            return None

        mode = mode_from_text(f"{title}\n{row.get('shortDescription') or ''}")
        if mode is None:
            self.skipped("unknown_mode", row_id)
            return None

        prize_value, prize_text = _prize(row)
        org_name = str(organization.get("name") or "").strip() if isinstance(
            organization, dict
        ) else ""
        themes = [
            str(i["title"])
            for i in _as_list(row.get("industries"))
            if isinstance(i, dict) and i.get("title")
        ]
        url = EVENT_URL.format(org=org_slug, slug=slug)
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
                "organization": org_name or org_slug,
                "location": "Online" if mode == "online" else "Hybrid",
                "themes": themes,
                "directory_url": url,
                "registration_ends_at": None,
            },
        )
