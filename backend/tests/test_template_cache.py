from services.template_cache import TemplateCache


def test_template_cache_orders_categories_by_shared_risk_policy():
    assert TemplateCache._ordered_codes(
        ["Harm to Minors", "Prompt Attacks", "General Political Topics"]
    ) == ["S9", "S4", "S1"]


def test_template_cache_prefers_application_override():
    cache = TemplateCache()
    cache._template_cache = {
        "app-a": {"S9": {False: "application override", True: "application default"}},
        "__global__": {"S9": {True: "global default"}},
    }

    assert cache._answer_for_category("app-a", "S9") == "application override"


def test_template_cache_falls_back_to_global_default_answer():
    cache = TemplateCache()
    cache._template_cache = {"__global__": {"default": {True: "global answer"}}}

    assert cache._get_default_answer("app-a") == "global answer"
