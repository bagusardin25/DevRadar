"""Lane policy: who may spend an LLM call, and how aggressively."""

from __future__ import annotations

from app.config import Settings
from app.llm.lanes import (
    DEFAULT_LANE_ENABLED,
    ExtractMode,
    LLMLane,
    extract_mode_for,
    parse_lane,
)


def test_discovery_is_off_by_default() -> None:
    assert DEFAULT_LANE_ENABLED[LLMLane.DISCOVERY] is False
    assert DEFAULT_LANE_ENABLED[LLMLane.SUBMISSION] is True


def test_parse_lane_falls_back_for_unknown() -> None:
    assert parse_lane("submission") is LLMLane.SUBMISSION
    assert parse_lane("DISCOVERY") is LLMLane.DISCOVERY
    assert parse_lane("nope") is LLMLane.CRAWL
    assert parse_lane(None, default=LLMLane.SUBMISSION) is LLMLane.SUBMISSION


def test_enabled_submission_gets_full_gap_fill() -> None:
    assert extract_mode_for(LLMLane.SUBMISSION, enabled=True) is ExtractMode.GAPS


def test_enabled_background_lanes_stay_critical() -> None:
    for lane in (LLMLane.DISCOVERY, LLMLane.RECHECK, LLMLane.CRAWL):
        assert extract_mode_for(lane, enabled=True) is ExtractMode.CRITICAL


def test_disabled_lane_is_always_off() -> None:
    for lane in LLMLane:
        assert extract_mode_for(lane, enabled=False) is ExtractMode.OFF


def test_settings_defaults_match_the_policy() -> None:
    settings = Settings(_env_file=None)  # type: ignore[arg-type]
    assert settings.llm_lane_enabled(LLMLane.SUBMISSION) is True
    assert settings.llm_lane_enabled(LLMLane.DISCOVERY) is False
    assert settings.extract_mode_for("submission") == "gaps"
    assert settings.extract_mode_for("discovery") == "off"
    assert settings.extract_mode_for("recheck") == "critical"
    assert settings.extract_mode_for("crawl") == "critical"
    assert settings.llm_review_reserve_ratio == 0.20


def test_create_extractor_discovery_lane_is_rules_only_by_default() -> None:
    from app.ingestion.extractor import Extractor
    from app.ingestion.llm_provider import DisabledLLMProvider, create_extractor

    settings = Settings(_env_file=None)  # type: ignore[arg-type]
    extractor = create_extractor(settings, lane="discovery")
    assert isinstance(extractor, Extractor)
    assert isinstance(extractor._llm, DisabledLLMProvider)
    assert extractor._extract_mode.value == "off"
