from types import SimpleNamespace

import services.response_template_service as template_module
from services.response_template_service import ResponseTemplateService


class RecordingTemplateService(ResponseTemplateService):
    def __init__(self):
        self.calls = []

    def _create(self, **values):
        self.calls.append(values)
        return values


def test_custom_template_routes_through_shared_creator():
    scanner = SimpleNamespace(tag="S100", name="Custom", default_risk_level="medium_risk")
    service = RecordingTemplateService()

    result = service.create_template_for_custom_scanner(scanner, "app-a", "tenant-a")

    assert result["scanner_type"] == "custom_scanner"
    assert result["identifier"] == "S100"
    assert result["risk_level"] == "medium_risk"


def test_blacklist_template_uses_high_risk_default():
    service = RecordingTemplateService()

    result = service.create_template_for_blacklist(
        SimpleNamespace(name="Restricted"), "app-a", "tenant-a"
    )

    assert result["scanner_type"] == "blacklist"
    assert result["risk_level"] == "high_risk"


def test_official_content_uses_shared_category_label():
    original_translation = template_module.get_translation
    template_module.get_translation = lambda language, *keys: f"{language}:{{scanner_name}}"
    try:
        content = ResponseTemplateService(None)._get_default_content_for_official_scanner("S9")
    finally:
        template_module.get_translation = original_translation

    assert content == {"en": "en:Prompt Attacks", "zh": "zh:Prompt Attacks"}
