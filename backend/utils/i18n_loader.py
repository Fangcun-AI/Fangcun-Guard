"""JSON-backed translations with English fallback."""

import json
from pathlib import Path
from typing import Any, Dict

_translations_cache: Dict[str, Dict[str, Any]] = {}
_SUPPORTED = {"en", "zh"}


def get_i18n_path() -> Path:
    return Path(__file__).parent.parent / "i18n"


def load_translations(language: str) -> Dict[str, Any]:
    language = language if language in _SUPPORTED else "en"
    if language in _translations_cache:
        return _translations_cache[language]
    path = get_i18n_path() / f"{language}.json"
    try:
        translations = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if language != "en":
            return load_translations("en")
        raise Exception(f"Translation file not found: {path}")
    except json.JSONDecodeError as exc:
        raise Exception(f"Invalid JSON in translation file {path}: {exc}")
    _translations_cache[language] = translations
    return translations


def clear_translations_cache() -> None:
    _translations_cache.clear()


def get_translation(language: str, *keys: str) -> str:
    value: Any = load_translations(language)
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            if language != "en":
                return get_translation("en", *keys)
            raise KeyError(f"Translation key not found: {'.'.join(keys)}")
        value = value[key]
    return value
