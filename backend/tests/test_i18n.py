from types import SimpleNamespace

from utils.i18n import format_ban_reason, get_language_from_request, translate


def test_request_language_prefers_english_accept_language():
    request = SimpleNamespace(headers={"accept-language": "en-US,en;q=0.9"})
    assert get_language_from_request(request) == "en"


def test_ban_reason_localizes_risk_level():
    assert format_ban_reason(5, 3, "high_risk", "en") == (
        "Triggered 3 high risk(s) within 5 minutes"
    )


def test_translate_returns_template_when_parameters_are_incomplete():
    assert "{trigger_count}" in translate("ban_reason_template", "en", time_window=5)
