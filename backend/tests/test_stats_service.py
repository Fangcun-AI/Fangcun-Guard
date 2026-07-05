from services.stats_service import StatsService


def test_stats_highest_risk_uses_shared_policy_order():
    assert StatsService._get_highest_risk_level(
        "low_risk", "high_risk", "medium_risk"
    ) == "high_risk"


def test_category_decoder_accepts_json_and_lists():
    assert StatsService._decode_categories('["A", "", "B"]') == ["A", "B"]
    assert StatsService._decode_categories(["A", None]) == ["A"]
    assert StatsService._decode_categories("not-json") == []


def test_empty_dashboard_shape_is_stable():
    empty = StatsService._get_empty_stats()

    assert empty["total_requests"] == 0
    assert empty["risk_distribution"] == {
        "high_risk": 0,
        "medium_risk": 0,
        "low_risk": 0,
        "no_risk": 0,
    }
