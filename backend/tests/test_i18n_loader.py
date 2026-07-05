import json

import utils.i18n_loader as loader


def setup_function():
    loader.clear_translations_cache()


def test_unknown_language_uses_english_catalog(tmp_path):
    tmp_path.joinpath("en.json").write_text(json.dumps({"key": "value"}))
    loader.get_i18n_path = lambda: tmp_path
    assert loader.get_translation("fr", "key") == "value"


def test_missing_localized_key_falls_back_to_english(tmp_path):
    tmp_path.joinpath("en.json").write_text(json.dumps({"nested": {"key": "fallback"}}))
    tmp_path.joinpath("zh.json").write_text(json.dumps({"nested": {}}))
    loader.get_i18n_path = lambda: tmp_path
    assert loader.get_translation("zh", "nested", "key") == "fallback"
