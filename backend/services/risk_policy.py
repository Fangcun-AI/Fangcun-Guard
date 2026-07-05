from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Tuple

RISK_CODES = tuple(f"S{index}" for index in range(1, 22))
RISK_SWITCH_FIELDS = tuple(f"{code.lower()}_enabled" for code in RISK_CODES)
SENSITIVITY_CONFIG_FIELDS = frozenset(
    {
        "low_sensitivity_threshold",
        "medium_sensitivity_threshold",
        "high_sensitivity_threshold",
        "sensitivity_trigger_level",
    }
)

CATEGORY_RISK_LEVELS = {
    "S1": "low_risk",
    "S2": "high_risk",
    "S3": "high_risk",
    "S4": "medium_risk",
    "S5": "high_risk",
    "S6": "medium_risk",
    "S7": "medium_risk",
    "S8": "low_risk",
    "S9": "high_risk",
    "S10": "low_risk",
    "S11": "low_risk",
    "S12": "low_risk",
    "S13": "low_risk",
    "S14": "low_risk",
    "S15": "high_risk",
    "S16": "medium_risk",
    "S17": "high_risk",
    "S18": "low_risk",
    "S19": "low_risk",
    "S20": "low_risk",
    "S21": "low_risk",
}

CATEGORY_LABELS = {
    "S1": "General Political Topics",
    "S2": "Sensitive Political Topics",
    "S3": "Insult to National Symbols or Leaders",
    "S4": "Harm to Minors",
    "S5": "Violent Crime",
    "S6": "Non-Violent Crime",
    "S7": "Pornography",
    "S8": "Hate & Discrimination",
    "S9": "Prompt Attacks",
    "S10": "Profanity",
    "S11": "Privacy Invasion",
    "S12": "Commercial Violations",
    "S13": "Intellectual Property Infringement",
    "S14": "Harassment",
    "S15": "Weapons of Mass Destruction",
    "S16": "Self-Harm",
    "S17": "Sexual Crimes",
    "S18": "Threats",
    "S19": "Professional Financial Advice",
    "S20": "Professional Medical Advice",
    "S21": "Professional Legal Advice",
}

RISK_LEVEL_ORDER = ("no_risk", "low_risk", "medium_risk", "high_risk")
RISK_LEVEL_SCORES = {level: score for score, level in enumerate(RISK_LEVEL_ORDER)}
SECURITY_CATEGORY_CODES = frozenset({"S9"})
DEFAULT_TRIGGER_LEVEL = "medium"


def highest_risk_level(levels: Iterable[str]) -> str:
    known_levels = (level for level in levels if level in RISK_LEVEL_SCORES)
    return max(known_levels, key=RISK_LEVEL_SCORES.get, default="no_risk")


def parse_verdict_categories(response: str) -> Tuple[str, ...]:
    lines = response.strip().splitlines()
    if len(lines) < 2 or lines[0] != "unsafe":
        return ()

    categories = []
    seen = set()
    for raw_category in lines[1].split(","):
        category = raw_category.strip()
        if category and category not in seen:
            categories.append(category)
            seen.add(category)
    return tuple(categories)


@dataclass(frozen=True)
class PartitionedVerdict:
    compliance_level: str
    compliance_categories: Tuple[str, ...]
    security_level: str
    security_categories: Tuple[str, ...]


def partition_categories(categories: Iterable[str]) -> PartitionedVerdict:
    compliance_categories = []
    compliance_levels = []
    security_categories = []
    security_levels = []

    for category in categories:
        label = CATEGORY_LABELS.get(category, category)
        risk_level = CATEGORY_RISK_LEVELS.get(category, "medium_risk")
        if category in SECURITY_CATEGORY_CODES:
            security_categories.append(label)
            security_levels.append(risk_level)
        else:
            compliance_categories.append(label)
            compliance_levels.append(risk_level)

    return PartitionedVerdict(
        compliance_level=highest_risk_level(compliance_levels),
        compliance_categories=tuple(compliance_categories),
        security_level=highest_risk_level(security_levels),
        security_categories=tuple(security_categories),
    )


def risk_switches_from_record(record: Optional[object] = None) -> dict:
    return {
        code: bool(getattr(record, field, True))
        for code, field in zip(RISK_CODES, RISK_SWITCH_FIELDS)
    }


def risk_switch_dict_from_record(record: Optional[object] = None) -> dict:
    switches = risk_switches_from_record(record)
    return {code.lower() + "_enabled": enabled for code, enabled in switches.items()}


def normalize_trigger_level(level: Optional[str]) -> str:
    return level if level in {"low", "medium", "high"} else DEFAULT_TRIGGER_LEVEL


def _record_value(record: Optional[object], field: str, default: float) -> float:
    value = getattr(record, field, None)
    return default if value is None else value


@dataclass(frozen=True)
class SensitivityThresholds:
    low: float = 0.95
    medium: float = 0.60
    high: float = 0.40

    @classmethod
    def from_record(cls, record: Optional[object]) -> "SensitivityThresholds":
        return cls(
            low=_record_value(record, "low_sensitivity_threshold", cls.low),
            medium=_record_value(record, "medium_sensitivity_threshold", cls.medium),
            high=_record_value(record, "high_sensitivity_threshold", cls.high),
        )

    @classmethod
    def from_mapping(cls, values: Mapping[str, float]) -> "SensitivityThresholds":
        return cls(
            low=values.get("low", cls.low),
            medium=values.get("medium", cls.medium),
            high=values.get("high", cls.high),
        )

    def as_dict(self) -> dict:
        return {"low": self.low, "medium": self.medium, "high": self.high}

    def as_config_dict(self, trigger_level: Optional[str] = None) -> dict:
        return {
            "low_sensitivity_threshold": self.low,
            "medium_sensitivity_threshold": self.medium,
            "high_sensitivity_threshold": self.high,
            "sensitivity_trigger_level": normalize_trigger_level(trigger_level),
        }

    def threshold_for(self, trigger_level: Optional[str]) -> float:
        return getattr(self, normalize_trigger_level(trigger_level))
