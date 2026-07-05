"""Small runtime translation catalog for ban-policy messages."""

from typing import Optional

TRANSLATIONS = {
    "zh": {
        "ban_reason_template": "在 {time_window} 分钟内触发 {trigger_count} 次{risk_level}风险",
        "risk_levels": {"low_risk": "低", "medium_risk": "中", "high_risk": "高"},
    },
    "en": {
        "ban_reason_template": "Triggered {trigger_count} {risk_level} risk(s) within {time_window} minutes",
        "risk_levels": {
            "low_risk": "low",
            "medium_risk": "medium",
            "high_risk": "high",
        },
    },
}


def _catalog(language: str) -> dict:
    return TRANSLATIONS.get(language, TRANSLATIONS["zh"])


def get_language_from_request(request=None, tenant_id: Optional[str] = None) -> str:
    accept_language = request.headers.get("accept-language", "") if request else ""
    return "en" if "en" in accept_language.lower() else "zh"


def translate(key: str, language: str = "zh", **kwargs) -> str:
    text = _catalog(language).get(key, key)
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError):
        return text


def get_risk_level_text(risk_level: str, language: str = "zh") -> str:
    return _catalog(language).get("risk_levels", {}).get(risk_level, risk_level)


def format_ban_reason(
    time_window: int,
    trigger_count: int,
    risk_level: str,
    language: str = "zh",
) -> str:
    return translate(
        "ban_reason_template",
        language,
        time_window=time_window,
        trigger_count=trigger_count,
        risk_level=get_risk_level_text(risk_level, language),
    )
