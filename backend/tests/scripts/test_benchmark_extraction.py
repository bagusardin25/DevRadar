"""Offline coverage for scripts/benchmark_extraction.py.

The harness normally talks to LLM providers, but its scoring, target discovery,
and the rules-only baseline are all exercisable without a network. These tests
lock the comparators (the part most likely to drift into being unfair to a
model) and prove the end-to-end run works against the real fixtures + golden
file using only the deterministic rule extractor.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

# The harness lives in backend/scripts, which is not an installed package.
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import benchmark_extraction as bench  # noqa: E402

from app.config import Settings  # noqa: E402


class TestScoreField:
    def test_date_matches_by_instant(self) -> None:
        produced = datetime(2026, 8, 25, 23, 59, tzinfo=UTC)
        assert bench.score_field("submission_deadline", produced, "2026-08-25T23:59:00Z") == 1.0

    def test_date_day_only_ignores_time(self) -> None:
        produced = datetime(2026, 11, 30, 12, 0, tzinfo=UTC)
        # Golden is a bare day, so the time component must not fail the match.
        assert bench.score_field("registration_deadline", produced, "2026-11-30") == 1.0

    def test_date_wrong_day_fails(self) -> None:
        produced = datetime(2026, 11, 29, tzinfo=UTC)
        assert bench.score_field("registration_deadline", produced, "2026-11-30") == 0.0

    def test_number_compares_numerically(self) -> None:
        assert bench.score_field("prize_value", Decimal("50000"), 50000) == 1.0
        assert bench.score_field("prize_value", Decimal("5"), 50000) == 0.0

    def test_offer_type_accepts_any_in_set(self) -> None:
        golden = ["free_credits", "promo_code"]
        assert bench.score_field("offer_type", "promo_code", golden) == 1.0
        assert bench.score_field("offer_type", "free_credits", golden) == 1.0
        assert bench.score_field("offer_type", "trial", golden) == 0.0

    def test_set_field_scored_by_recall(self) -> None:
        # One of two golden items present -> half credit; extras don't penalise.
        score = bench.score_field(
            "technologies", ["Python", "Rust", "CUDA"], ["Python", "React"]
        )
        assert score == pytest.approx(0.5)
        full = bench.score_field("technologies", ["python", "react"], ["Python", "React"])
        assert full == 1.0

    def test_fuzzy_field_allows_containment(self) -> None:
        assert bench.score_field("product_name", "CloudLLM Developer Credits", "CloudLLM") == 1.0
        assert bench.score_field("title", "Totally Unrelated", "CloudLLM") == 0.0

    def test_none_expected_requires_empty(self) -> None:
        # A permanent offer must NOT invent an expiry.
        assert bench.score_field("expires_at", None, None) == 1.0
        assert bench.score_field("expires_at", [], None) == 1.0
        assert bench.score_field(
            "expires_at", datetime(2026, 1, 1, tzinfo=UTC), None
        ) == 0.0

    def test_missing_value_scores_zero(self) -> None:
        assert bench.score_field("title", None, "Something") == 0.0
        assert bench.score_field("technologies", [], ["Python"]) == 0.0

    def test_url_field_is_exact(self) -> None:
        assert bench.score_field(
            "claim_url", "https://x.example/claim", "https://x.example/claim"
        ) == 1.0
        assert bench.score_field(
            "claim_url", "https://fixture.example/thing", "https://x.example/claim"
        ) == 0.0


class TestScoreFixture:
    def test_mean_and_breakdown(self) -> None:
        expected = {"title": "Acme", "prize_value": 100, "mode": "online"}
        produced = {"title": "Acme", "prize_value": 100, "mode": "hybrid"}
        mean, per_field = bench.score_fixture(produced, expected)
        assert per_field == {"title": 1.0, "prize_value": 1.0, "mode": 0.0}
        assert mean == pytest.approx(2 / 3)

    def test_none_produced_dict(self) -> None:
        mean, per_field = bench.score_fixture(None, {"title": "Acme"})
        assert per_field == {"title": 0.0}
        assert mean == 0.0


class TestDiscoverTargets:
    def _clean_settings(self, monkeypatch: pytest.MonkeyPatch, **overrides: object) -> Settings:
        for var in ("OPENAI_API_KEY", "LLM_API_KEY", "LLM_PROVIDERS_JSON", "LLM_MODEL"):
            monkeypatch.delenv(var, raising=False)
        params: dict[str, object] = {
            "llm_api_key": "",
            "llm_providers_json": "",
            "llm_routing_enabled": False,
        }
        params.update(overrides)
        return Settings(_env_file=None, **params)  # type: ignore[arg-type]

    def test_rules_only_when_no_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = self._clean_settings(monkeypatch)
        targets = bench.discover_targets(settings)
        assert [t.label for t in targets] == ["rules"]
        assert targets[0].is_rules

    def test_openai_baseline_added_with_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = self._clean_settings(
            monkeypatch, llm_api_key="sk-test", llm_model="gpt-4o-mini"
        )
        labels = [t.label for t in bench.discover_targets(settings)]
        assert labels == ["rules", "openai:gpt-4o-mini"]

    def test_provider_from_json_when_key_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FAKEPROV_API_KEY", "sk-fake")
        providers_json = (
            '[{"name":"fakeprov","base_url":"https://fake.example/v1",'
            '"model":"fake-1","operations":["extraction"]}]'
        )
        settings = self._clean_settings(monkeypatch, llm_providers_json=providers_json)
        targets = bench.discover_targets(settings)
        labels = [t.label for t in targets]
        assert "fakeprov:fake-1" in labels
        # Isolated single-provider target, ready to call but not called here.
        fake = next(t for t in targets if t.label == "fakeprov:fake-1")
        assert not fake.is_rules

    def test_provider_skipped_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Same JSON, but the key env var is unset -> registry drops it.
        monkeypatch.delenv("FAKEPROV_API_KEY", raising=False)
        providers_json = (
            '[{"name":"fakeprov","base_url":"https://fake.example/v1",'
            '"model":"fake-1","operations":["extraction"]}]'
        )
        settings = self._clean_settings(monkeypatch, llm_providers_json=providers_json)
        assert [t.label for t in bench.discover_targets(settings)] == ["rules"]

    def test_only_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = self._clean_settings(monkeypatch, llm_api_key="sk-test")
        targets = bench.discover_targets(settings, only=["rules"])
        assert [t.label for t in targets] == ["rules"]


class TestOfflineRun:
    """End-to-end over the real golden + fixtures, rules baseline only."""

    def _load_cases(self) -> list[bench._Case]:
        import json

        golden = json.loads(bench._DEFAULT_GOLDEN.read_text(encoding="utf-8"))
        return bench.load_cases(bench._DEFAULT_FIXTURES, golden)

    def test_cases_load_from_repo_fixtures(self) -> None:
        cases = self._load_cases()
        names = {case.name for case in cases}
        assert "hackathon_sample.html" in names
        assert "free_tier_permanent.txt" in names
        # The malformed-LLM fixture is not a document and must not be scored.
        assert "malformed_llm.json" not in names

    @pytest.mark.asyncio
    async def test_rules_baseline_scores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ("OPENAI_API_KEY", "LLM_API_KEY", "LLM_PROVIDERS_JSON"):
            monkeypatch.delenv(var, raising=False)
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            llm_api_key="",
            llm_providers_json="",
            llm_routing_enabled=False,
        )
        cases = self._load_cases()
        target = bench.BenchTarget("rules", True, bench.DisabledLLMProvider())

        reports = await bench.run_benchmark(
            settings, cases, [target], pipeline=True
        )
        assert len(reports) == 1
        rules = reports[0]
        assert rules.label == "rules"
        assert rules.fixtures_scored == rules.fixtures_total == len(cases)
        assert rules.errors == 0
        assert 0.0 < rules.accuracy <= 1.0
        # The rule extractor never calls an LLM, so the pipeline is all "rules".
        assert rules.method_counts == {"rules": len(cases)}

    @pytest.mark.asyncio
    async def test_known_fields_land_for_rules(self) -> None:
        cases = self._load_cases()
        target = bench.BenchTarget("rules", True, bench.DisabledLLMProvider())
        report = (await bench._run_target(target, cases, pipeline=False))

        hack = report.per_fixture_fields["hackathon_sample.html"]
        assert hack["submission_deadline"] == 1.0
        assert hack["prize_value"] == 1.0
        assert hack["mode"] == 1.0

        # Permanent free tier: rules leave expires_at empty, which is correct.
        free = report.per_fixture_fields["free_tier_permanent.txt"]
        assert free["expires_at"] == 1.0
        assert free["offer_type"] == 1.0
