from dataclasses import dataclass

from services.risk_policy import (
    SensitivityThresholds,
    highest_risk_level,
    parse_verdict_categories,
    partition_categories,
    risk_switch_dict_from_record,
    risk_switches_from_record,
)


@dataclass
class ThresholdRecord:
    low_sensitivity_threshold: float
    medium_sensitivity_threshold: float
    high_sensitivity_threshold: float


def test_verdict_parser_deduplicates_categories_in_stable_order():
    assert parse_verdict_categories("unsafe\n S9, S4, S9 ") == ("S9", "S4")
    assert parse_verdict_categories("safe") == ()
    assert parse_verdict_categories("unexpected") == ()


def test_partition_separates_security_and_compliance_risks():
    verdict = partition_categories(["S9", "S4", "S2"])

    assert verdict.security_level == "high_risk"
    assert verdict.security_categories == ("Prompt Attacks",)
    assert verdict.compliance_level == "high_risk"
    assert verdict.compliance_categories == ("Harm to Minors", "Sensitive Political Topics")


def test_highest_risk_level_handles_empty_and_unknown_values():
    assert highest_risk_level([]) == "no_risk"
    assert highest_risk_level(["unknown"]) == "no_risk"
    assert highest_risk_level(["unknown", "medium_risk", "low_risk"]) == "medium_risk"


def test_threshold_record_preserves_explicit_zero_values():
    thresholds = SensitivityThresholds.from_record(ThresholdRecord(0.0, 0.2, 0.4))

    assert thresholds.as_dict() == {"low": 0.0, "medium": 0.2, "high": 0.4}
    assert thresholds.threshold_for("invalid") == 0.2


def test_default_switch_helpers_cover_all_risk_codes():
    switches = risk_switches_from_record()
    config = risk_switch_dict_from_record()

    assert len(switches) == 21
    assert set(switches.values()) == {True}
    assert config["s1_enabled"] is True
    assert config["s21_enabled"] is True
