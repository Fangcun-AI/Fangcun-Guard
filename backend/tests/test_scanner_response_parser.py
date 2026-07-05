from dataclasses import dataclass

from services.scanner_response_parser import ScannerResponseParser, drop_think_tags


@dataclass
class Result:
    scanner_tag: str
    scanner_name: str
    scanner_type: str
    risk_level: str
    matched: bool
    match_details: object = None


SCANNERS = [
    {"tag": "S4", "name": "Minor Safety", "risk_level": "medium_risk"},
    {"tag": "S9", "name": "Prompt Attack", "risk_level": "high_risk"},
]


def test_drop_think_tags_removes_hidden_reasoning():
    assert drop_think_tags("<think>private</think>unsafe\nS9") == "unsafe\nS9"


def test_parser_matches_only_returned_unsafe_tags():
    results = ScannerResponseParser().parse_model_response(
        SCANNERS, "unsafe\nS9", 0.8, Result
    )

    assert [result.matched for result in results] == [False, True]


def test_parser_maps_qwen_categories_and_unknowns_stably():
    parsed = ScannerResponseParser().try_parse_qwen3guard_format(
        "Safety: Unsafe\nCategories: jailbreak, harm to minors, something new"
    )

    assert parsed == (False, ["S4", "S9"])


def test_window_aggregation_keeps_maximum_sensitivity():
    results = ScannerResponseParser().aggregate_window_results(
        SCANNERS,
        [(0, "unsafe\nS9", 0.4), (1, "unsafe\nS9", 0.9), (2, "safe", None)],
        Result,
    )

    assert results[1].matched is True
    assert results[1].match_details == "Matched in 2/3 windows, max sensitivity: 0.9000"


def test_generic_parser_treats_explicit_safe_as_safe():
    parser = ScannerResponseParser()

    safe = parser.parse_generic_safe_unsafe(SCANNERS, "safe", None, Result)
    unsafe = parser.parse_generic_safe_unsafe(SCANNERS, "unsafe", None, Result)

    assert all(not result.matched for result in safe)
    assert all(result.matched for result in unsafe)
