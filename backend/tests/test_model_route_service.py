from types import SimpleNamespace

from services.model_route_service import ModelRouteRegistry


def route(pattern, match_type, priority, upstream, bindings=None):
    return SimpleNamespace(
        model_pattern=pattern,
        match_type=match_type,
        priority=priority,
        upstream_api_config=upstream,
        route_applications=bindings or [],
    )


def test_best_match_prefers_priority_before_match_type():
    high_prefix = route("gpt-", "prefix", 200, "prefix")
    low_exact = route("gpt-4", "exact", 100, "exact")
    assert ModelRouteRegistry._best_match([low_exact, high_prefix], "gpt-4") is high_prefix


def test_best_match_prefers_exact_at_same_priority():
    prefix = route("gpt-", "prefix", 100, "prefix")
    exact = route("gpt-4", "exact", 100, "exact")
    assert ModelRouteRegistry._best_match([prefix, exact], "gpt-4") is exact


def test_best_match_is_case_insensitive():
    exact = route("GPT-4", "exact", 100, "exact")
    assert ModelRouteRegistry._best_match([exact], "gpt-4") is exact
