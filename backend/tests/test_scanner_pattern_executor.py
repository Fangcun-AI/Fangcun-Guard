from dataclasses import dataclass

from services.scanner_pattern_executor import ScannerPatternExecutor


@dataclass
class Result:
    scanner_tag: str
    scanner_name: str
    scanner_type: str
    risk_level: str
    matched: bool
    match_details: object = None


@dataclass
class Aggregate:
    overall_risk_level: str
    matched_scanners: list
    compliance_categories: list
    security_categories: list


def test_aggregation_uses_highest_level_and_security_partition():
    aggregate = ScannerPatternExecutor().aggregate_results(
        [
            Result("S4", "Minor Safety", "keyword", "medium_risk", True),
            Result("S9", "Prompt Attack", "regex", "high_risk", True),
            Result("S1", "Political", "genai", "low_risk", False),
        ],
        Aggregate,
    )

    assert aggregate.overall_risk_level == "high_risk"
    assert aggregate.compliance_categories == ["Minor Safety"]
    assert aggregate.security_categories == ["Prompt Attack"]
