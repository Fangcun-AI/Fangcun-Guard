from types import SimpleNamespace

import utils.validators as validators


def setup_function():
    validators.settings = SimpleNamespace(verifymail_api_key=None)
    validators._DISPOSABLE_CACHE.clear()


def test_domain_catalog_is_preserved_and_normalized():
    assert len(validators.PERSONAL_EMAIL_DOMAINS) == 389
    assert validators.is_personal_email("person@Liaphoto.com")


def test_enterprise_email_accepts_non_personal_domain_without_api():
    assert validators.validate_enterprise_email("person@example.org") == {
        "is_valid": True,
        "error": None,
    }


def test_recursive_cleaning_removes_database_control_characters():
    assert validators.clean_detection_data({"items": ["a\x00b", "\x01ok\n"]}) == {
        "items": ["ab", "ok\n"]
    }


def test_password_strength_retains_scoring_contract():
    assert validators.validate_password_strength("LongPassword1!") == {
        "is_valid": True,
        "errors": [],
        "strength_score": 100,
    }


def test_api_key_requires_public_prefix_and_reasonable_length():
    assert validators.validate_api_key("sk-xxai-" + "a" * 52)
    assert not validators.validate_api_key("bad-" + "a" * 52)
