#!/usr/bin/env python3
"""Compare extraction accuracy across LLM providers on the document fixtures.

This is the measurement gate for the rollout in docs/LLM_MULTIPROVIDER_PLAN.md:
before free-tier providers take extraction traffic away from gpt-4o-mini, we need
evidence they read the same fields off a page. The harness runs every configured
provider over tests/fixtures/documents/ and scores each field against a golden
answer key (scripts/benchmark_extraction_golden.json).

Two views come out of one run:

* LLM-only accuracy (default) — the extraction prompt is sent straight to each
  provider, the JSON is validated against the same schema production uses, and
  every field is scored against golden. This isolates model quality: every
  provider is exercised on every fixture, so the numbers are directly
  comparable. A ``rules`` row (the deterministic extractor, no LLM) is included
  as the reference floor.
* Pipeline outcome (``--pipeline``) — the full rules-first Extractor is run with
  each provider as its LLM, reporting the method mix (rules / llm / hybrid /
  failed) and the shipped field accuracy. This is what actually reaches the
  catalogue, and it shows the ``method="failed"`` signal the weight ramp watches.

Every provider is isolated: a single-provider LLMRouter with in-process state,
so failover never masks one model's weakness with another's answer, and no Redis
is required.

Providers are discovered the same way the app resolves them:

* ``rules`` is always present (no key, runs offline).
* Each entry in ``LLM_PROVIDERS_JSON`` that serves ``extraction`` and has its API
  key set becomes a target (this is how Groq / Gemini join once registered).
* ``LLM_API_KEY`` / ``OPENAI_API_KEY`` adds the single-provider gpt-4o-mini
  baseline, so the comparison runs today before any free-tier account exists.

Usage (from backend/):
  uv run python scripts/benchmark_extraction.py
  uv run python scripts/benchmark_extraction.py --list
  uv run python scripts/benchmark_extraction.py --verbose
  uv run python scripts/benchmark_extraction.py --pipeline
  uv run python scripts/benchmark_extraction.py --provider rules --provider openai
  uv run python scripts/benchmark_extraction.py --json > bench.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.catalog.enums import ListingKind  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.ingestion.extraction_schemas import (  # noqa: E402
    EXTRACTION_SCHEMA_VERSION,
    validate_extraction_payload,
)
from app.ingestion.extractor import Extractor  # noqa: E402
from app.ingestion.llm_provider import (  # noqa: E402
    DisabledLLMProvider,
    ExtractionRequest,
    LLMProvider,
    OpenAILLMProvider,
    RoutedLLMProvider,
)
from app.ingestion.parser import parse_document  # noqa: E402
from app.llm.registry import parse_provider_specs  # noqa: E402
from app.llm.router import LLMRouter  # noqa: E402
from app.llm.state import MemoryState  # noqa: E402

_DEFAULT_GOLDEN = Path(__file__).with_name("benchmark_extraction_golden.json")
_DEFAULT_FIXTURES = _BACKEND_ROOT / "tests" / "fixtures" / "documents"


def _load_env_file(path: Path) -> None:
    """Populate os.environ from a .env file so provider *_API_KEY vars are seen.

    pydantic-settings reads .env into the Settings object, but the provider
    registry resolves each key from os.environ — that is where the keys live in
    a real deployment. Locally they sit only in the .env file, so without this
    the benchmark would silently discover no free-tier providers. Never
    overrides a value already exported in the real environment.
    """
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency of pydantic-settings
        return
    load_dotenv(path, override=False)

# How each golden field is compared. A field's name — not its value's type —
# picks the comparator, so the golden file stays plain data.
_DATE_FIELDS = frozenset(
    {
        "registration_open_at",
        "registration_deadline",
        "submission_deadline",
        "starts_at",
        "expires_at",
    }
)
_NUMBER_FIELDS = frozenset({"prize_value", "team_min", "team_max"})
# Rules and models legitimately disagree on how to label the same offer
# (free_credits vs promo_code), so accept any value in the golden set.
_ONE_OF_FIELDS = frozenset({"offer_type"})
# List fields are scored by recall: every golden item must appear, but extra
# plausible items (a model naming one more real technology) are not punished.
_SET_FIELDS = frozenset(
    {
        "technologies",
        "tags",
        "eligible_countries",
        "eligibility",
        "supported_regions",
        "target_users",
        "requirements",
    }
)
# Plain-text URLs are only recoverable by a model reading the page; the rule
# extractor cannot see them, which is itself a useful thing to measure.
_URL_FIELDS = frozenset({"official_url", "claim_url", "official_terms_url"})
# Prose the model may phrase differently — a containment match is fair here.
_FUZZY_FIELDS = frozenset(
    {"title", "product_name", "organizer", "offer_value", "location", "description"}
)


# --- scoring ---------------------------------------------------------------


def _norm(value: object) -> str:
    return str(value).strip().lower()


def _is_empty(value: object) -> bool:
    return value is None or value == "" or value == []


def _coerce_dt(value: object) -> datetime | None:
    """Parse either a datetime or an ISO string into a UTC-aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _score_date(produced: object, golden: object) -> float:
    want = _coerce_dt(golden)
    got = _coerce_dt(produced)
    if want is None or got is None:
        return 0.0
    golden_text = str(golden).strip()
    day_only = "t" not in golden_text.lower() and " " not in golden_text
    if day_only:
        return 1.0 if got.date() == want.date() else 0.0
    return 1.0 if got == want else 0.0


def _score_number(produced: object, golden: object) -> float:
    try:
        return 1.0 if Decimal(str(produced)) == Decimal(str(golden)) else 0.0
    except (InvalidOperation, TypeError, ValueError):
        return 0.0


def _score_exact(produced: object, golden: object) -> float:
    return 1.0 if _norm(produced) == _norm(golden) else 0.0


def _score_one_of(produced: object, golden: object) -> float:
    accepted = golden if isinstance(golden, list) else [golden]
    got = _norm(produced)
    return 1.0 if any(got == _norm(item) for item in accepted) else 0.0


def _score_fuzzy(produced: object, golden: object) -> float:
    got, want = _norm(produced), _norm(golden)
    if not got or not want:
        return 0.0
    return 1.0 if (want in got or got in want) else 0.0


def _score_set_recall(produced: object, golden: object) -> float:
    wanted = golden if isinstance(golden, list) else [golden]
    if not wanted:
        return 1.0
    if isinstance(produced, (list, tuple)):
        items = [_norm(item) for item in produced]
    elif _is_empty(produced):
        items = []
    else:
        items = [_norm(produced)]
    hits = 0
    for want in wanted:
        needle = _norm(want)
        if any(needle in item or item in needle for item in items):
            hits += 1
    return hits / len(wanted)


def score_field(name: str, produced: object, golden: object) -> float:
    """Score one field in [0, 1]. golden=None means the field must stay empty."""
    if golden is None:
        return 1.0 if _is_empty(produced) else 0.0
    if _is_empty(produced):
        return 0.0
    if name in _DATE_FIELDS:
        return _score_date(produced, golden)
    if name in _NUMBER_FIELDS:
        return _score_number(produced, golden)
    if name in _ONE_OF_FIELDS:
        return _score_one_of(produced, golden)
    if name in _SET_FIELDS:
        return _score_set_recall(produced, golden)
    if name in _FUZZY_FIELDS:
        return _score_fuzzy(produced, golden)
    # _URL_FIELDS and anything unlisted: exact match.
    return _score_exact(produced, golden)


def score_fixture(
    produced: dict[str, Any] | None, expected: dict[str, Any]
) -> tuple[float, dict[str, float]]:
    """Mean field score plus the per-field breakdown for one fixture."""
    per_field = {
        name: score_field(name, (produced or {}).get(name), golden)
        for name, golden in expected.items()
    }
    mean = sum(per_field.values()) / len(per_field) if per_field else 0.0
    return mean, per_field


# --- targets ---------------------------------------------------------------


@dataclass(slots=True)
class BenchTarget:
    """One thing to benchmark: the rule extractor or one isolated provider."""

    label: str
    is_rules: bool
    llm: LLMProvider


def discover_targets(
    settings: Settings, *, only: list[str] | None = None
) -> list[BenchTarget]:
    """Resolve benchmark targets from settings, mirroring app provider wiring.

    Each routed provider is isolated in its own single-provider router with
    in-process state, so failover cannot substitute another model's answer and
    the run needs no Redis. Providers are read from LLM_PROVIDERS_JSON regardless
    of LLM_ROUTING_ENABLED — the point is to measure the models before switching
    routing on.
    """
    targets: list[BenchTarget] = [
        BenchTarget("rules", True, DisabledLLMProvider())
    ]

    for spec in parse_provider_specs(settings.llm_providers_json):
        if not spec.serves("extraction"):
            continue
        router = LLMRouter(
            [spec],
            state=MemoryState(),
            redis_url="",
            strategy="priority",
            deadline_seconds=settings.llm_deadline_seconds,
            max_attempts=1,
        )
        targets.append(
            BenchTarget(f"{spec.name}:{spec.model}", False, RoutedLLMProvider(router))
        )

    # Single-provider OpenAI baseline (works today, before any free account).
    api_key = (settings.llm_api_key or "").strip()
    model = (settings.llm_model or "gpt-4o-mini").strip()
    legacy_label = f"openai:{model}"
    if api_key and legacy_label not in {target.label for target in targets}:
        targets.append(
            BenchTarget(
                legacy_label, False, OpenAILLMProvider(api_key=api_key, model=model)
            )
        )

    if only:
        wanted = {value.lower() for value in only}
        targets = [
            target
            for target in targets
            if target.label.lower() in wanted
            or target.label.split(":", 1)[0].lower() in wanted
        ]
    return targets


# --- running ---------------------------------------------------------------


@dataclass(slots=True)
class TargetReport:
    label: str
    is_rules: bool
    fixtures_scored: int
    fixtures_total: int
    accuracy: float
    schema_failures: int
    errors: int
    avg_latency_ms: int
    avg_tokens: int
    per_fixture: dict[str, float] = field(default_factory=dict)
    per_fixture_fields: dict[str, dict[str, float]] = field(default_factory=dict)
    error_detail: dict[str, str] = field(default_factory=dict)
    method_counts: dict[str, int] = field(default_factory=dict)
    pipeline_accuracy: float | None = None


@dataclass(slots=True)
class _Case:
    name: str
    parsed: Any
    kind: ListingKind
    expected: dict[str, Any]


async def _llm_only_fields(
    target: BenchTarget, case: _Case
) -> tuple[dict[str, Any] | None, str, bool, int, int]:
    """Return (fields, error, schema_failed, latency_ms, tokens) for one call.

    ``fields`` is None only when the provider call itself failed (network,
    quota, all-providers-failed); a schema rejection returns empty fields with
    ``schema_failed`` set, matching how production discards malformed LLM output.
    """
    if target.is_rules:
        result = await Extractor(target.llm).extract(case.parsed, case.kind)
        return result.fields, "", False, 0, 0

    request = ExtractionRequest(
        listing_kind=case.kind.value,
        text=case.parsed.text or "",
        url=case.parsed.url,
        schema_version=EXTRACTION_SCHEMA_VERSION,
    )
    start = _now_ms()
    try:
        result = await target.llm.extract_json(request)
    except Exception as exc:  # provider/transport/all-failed
        return None, f"{type(exc).__name__}: {exc}", False, _now_ms() - start, 0
    latency = _now_ms() - start
    tokens = result.usage.total_tokens if result.usage else 0

    try:
        validated = validate_extraction_payload(case.kind.value, result.payload)
    except Exception as exc:  # extra keys / wrong types — production rejects too
        return {}, f"schema_rejected: {type(exc).__name__}", True, latency, tokens
    return validated.model_dump(exclude_none=True), "", False, latency, tokens


async def _run_target(
    target: BenchTarget, cases: list[_Case], *, pipeline: bool
) -> TargetReport:
    scores: list[float] = []
    latencies: list[int] = []
    token_counts: list[int] = []
    schema_failures = 0
    errors = 0
    per_fixture: dict[str, float] = {}
    per_fixture_fields: dict[str, dict[str, float]] = {}
    error_detail: dict[str, str] = {}

    for case in cases:
        fields, err, schema_failed, latency, tokens = await _llm_only_fields(
            target, case
        )
        if fields is None:
            errors += 1
            error_detail[case.name] = err
            continue
        if schema_failed:
            schema_failures += 1
            error_detail[case.name] = err
        accuracy, breakdown = score_fixture(fields, case.expected)
        scores.append(accuracy)
        per_fixture[case.name] = accuracy
        per_fixture_fields[case.name] = breakdown
        if not target.is_rules:
            latencies.append(latency)
            token_counts.append(tokens)

    method_counts: dict[str, int] = {}
    pipeline_accuracy: float | None = None
    if pipeline:
        pipeline_scores: list[float] = []
        for case in cases:
            try:
                result = await Extractor(target.llm).extract(case.parsed, case.kind)
            except Exception as exc:
                method_counts["error"] = method_counts.get("error", 0) + 1
                error_detail.setdefault(case.name, f"pipeline: {type(exc).__name__}")
                continue
            method_counts[result.method] = method_counts.get(result.method, 0) + 1
            accuracy, _ = score_fixture(result.fields, case.expected)
            pipeline_scores.append(accuracy)
        pipeline_accuracy = (
            sum(pipeline_scores) / len(pipeline_scores) if pipeline_scores else 0.0
        )

    return TargetReport(
        label=target.label,
        is_rules=target.is_rules,
        fixtures_scored=len(scores),
        fixtures_total=len(cases),
        accuracy=sum(scores) / len(scores) if scores else 0.0,
        schema_failures=schema_failures,
        errors=errors,
        avg_latency_ms=round(sum(latencies) / len(latencies)) if latencies else 0,
        avg_tokens=round(sum(token_counts) / len(token_counts)) if token_counts else 0,
        per_fixture=per_fixture,
        per_fixture_fields=per_fixture_fields,
        error_detail=error_detail,
        method_counts=method_counts,
        pipeline_accuracy=pipeline_accuracy,
    )


def _now_ms() -> int:
    import time

    return int(time.perf_counter() * 1000)


def load_cases(
    fixtures_dir: Path, golden: dict[str, Any]
) -> list[_Case]:
    """Parse each fixture named in the golden file into a scorable case."""
    cases: list[_Case] = []
    for name, spec in golden.items():
        if name.startswith("_"):
            continue  # `_comment` and friends
        path = fixtures_dir / name
        raw = path.read_bytes()
        parsed = parse_document(
            raw,
            url=f"https://fixture.example/{name}",
            content_type=spec.get("content_type", "text/html"),
        )
        cases.append(
            _Case(
                name=name,
                parsed=parsed,
                kind=ListingKind(spec["listing_kind"]),
                expected=spec["expected"],
            )
        )
    return cases


async def run_benchmark(
    settings: Settings,
    cases: list[_Case],
    targets: list[BenchTarget],
    *,
    pipeline: bool,
) -> list[TargetReport]:
    return [await _run_target(target, cases, pipeline=pipeline) for target in targets]


# --- rendering -------------------------------------------------------------


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _missed_fields(breakdown: dict[str, float]) -> str:
    missed = [
        f"{name}={score:.2f}" if 0.0 < score < 1.0 else name
        for name, score in breakdown.items()
        if score < 1.0
    ]
    return ", ".join(missed) if missed else "-"


def render_report(
    reports: list[TargetReport],
    cases: list[_Case],
    settings: Settings,
    *,
    golden_path: Path,
    verbose: bool,
    pipeline: bool,
) -> str:
    total_fields = sum(len(case.expected) for case in cases)
    width = max((len(r.label) for r in reports), default=8)
    width = max(width, 20)
    lines: list[str] = []

    lines.append("DevRadar extraction benchmark")
    lines.append(
        f"  fixtures: {len(cases)}   golden fields: {total_fields}   "
        f"golden: {golden_path.name}"
    )
    lines.append(
        f"  routing_enabled={settings.llm_routing_enabled}  "
        f"strategy={settings.llm_routing_strategy}"
    )
    lines.append(f"  targets: {', '.join(r.label for r in reports)}")
    if not any(not r.is_rules for r in reports):
        lines.append(
            "  (no LLM keys found — set OPENAI_API_KEY for the gpt-4o-mini "
            "baseline, or LLM_PROVIDERS_JSON + keys for free tiers)"
        )
    lines.append("")

    header = (
        f"{'target':<{width}}  {'scored':>7}  {'accuracy':>8}  "
        f"{'schema':>6}  {'errors':>6}  {'avg_ms':>7}  {'tokens':>7}"
    )
    lines.append("== LLM-only extraction accuracy (vs golden) ==")
    lines.append(header)
    lines.append("-" * len(header))
    for report in reports:
        scored = f"{report.fixtures_scored}/{report.fixtures_total}"
        if report.is_rules:
            schema = errors = avg_ms = tokens = "-"
        else:
            schema = str(report.schema_failures)
            errors = str(report.errors)
            avg_ms = str(report.avg_latency_ms)
            tokens = str(report.avg_tokens)
        lines.append(
            f"{report.label:<{width}}  {scored:>7}  {_pct(report.accuracy):>8}  "
            f"{schema:>6}  {errors:>6}  {avg_ms:>7}  {tokens:>7}"
        )
    lines.append("")

    if pipeline:
        lines.append("== Full pipeline: rules + provider (what ships) ==")
        p_header = f"{'target':<{width}}  {'method mix':<28}  {'accuracy':>8}"
        lines.append(p_header)
        lines.append("-" * len(p_header))
        for report in reports:
            mix = (
                " ".join(f"{k}:{v}" for k, v in sorted(report.method_counts.items()))
                or "-"
            )
            acc = _pct(report.pipeline_accuracy) if report.pipeline_accuracy is not None else "-"
            lines.append(f"{report.label:<{width}}  {mix:<28}  {acc:>8}")
        lines.append("")

    if verbose:
        lines.append("== Per-fixture detail (LLM-only) ==")
        for report in reports:
            lines.append(f"[{report.label}]")
            for case in cases:
                if case.name in report.per_fixture:
                    acc = report.per_fixture[case.name]
                    missed = _missed_fields(report.per_fixture_fields[case.name])
                    lines.append(
                        f"  {case.name:<28} {_pct(acc):>7}   missed: {missed}"
                    )
                else:
                    detail = report.error_detail.get(case.name, "no result")
                    lines.append(f"  {case.name:<28} {'ERR':>7}   {detail}")
            lines.append("")

    errored = [r for r in reports if r.error_detail and not r.is_rules]
    if errored and not verbose:
        lines.append("Notes:")
        for report in errored:
            for name, detail in report.error_detail.items():
                lines.append(f"  {report.label} / {name}: {detail}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --- entrypoint ------------------------------------------------------------


async def _main(args: argparse.Namespace) -> int:
    _load_env_file(_BACKEND_ROOT / ".env")
    settings = get_settings()
    golden_path = Path(args.golden)
    fixtures_dir = Path(args.fixtures_dir)
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    cases = load_cases(fixtures_dir, golden)
    targets = discover_targets(settings, only=args.providers)

    if not any(case for case in cases):
        print("No fixtures found; check --golden / --fixtures-dir.", file=sys.stderr)
        return 2

    if args.list:
        for target in targets:
            kind = "rules" if target.is_rules else "llm"
            print(f"{target.label}\t{kind}")
        return 0

    reports = await run_benchmark(settings, cases, targets, pipeline=args.pipeline)

    if args.json:
        payload = {
            "fixtures": [case.name for case in cases],
            "routingEnabled": settings.llm_routing_enabled,
            "reports": [asdict(report) for report in reports],
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print(
        render_report(
            reports,
            cases,
            settings,
            golden_path=golden_path,
            verbose=args.verbose,
            pipeline=args.pipeline,
        ),
        end="",
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark LLM extraction accuracy on document fixtures."
    )
    parser.add_argument("--golden", default=str(_DEFAULT_GOLDEN))
    parser.add_argument("--fixtures-dir", default=str(_DEFAULT_FIXTURES))
    parser.add_argument(
        "--provider",
        action="append",
        dest="providers",
        help="Only benchmark these targets (by label or provider name; repeatable)",
    )
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="Also run the full rules+LLM Extractor and report the method mix",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show per-fixture field detail"
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of tables"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List discovered targets and exit (no API calls)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
